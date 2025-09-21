# app.py
# Your original backend, enhanced to:
# - speak the Arduino sketch protocol: ORIGIN_NEARBY/APPROACH/STOP, DEST_*, IDLE, URGENT, LED_STATUS_*
# - use 115200 baud to match the .ino
# - maintain your existing Flask endpoints and frontend contract

import os
import sys
import time
import threading
import requests
import serial
import serial.tools.list_ports
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS

# ==============================
# Config (original + additions)
# ==============================
API_KEY = os.getenv("MBTA_API_KEY", "c03504c502784cf2800d09ffa832c0e9")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

# Frontend continues to use these generic thresholds to derive /status.status
NEARBY_THRESHOLD_SEC   = int(os.getenv("NEARBY_THRESHOLD_SEC", "180"))  # 3 min
APPROACH_THRESHOLD_SEC = int(os.getenv("APPROACH_THRESHOLD_SEC", "300"))# 5 min
STOP_THRESHOLD_SEC     = int(os.getenv("STOP_THRESHOLD_SEC", "60"))     # 1 min

# New: separate origin/dest thresholds used to drive Arduino alerts (from teammate)
ORIGIN_NEARBY_THRESHOLD    = int(os.getenv("ORIGIN_NEARBY_THRESHOLD", "300"))  # 5m
ORIGIN_APPROACH_THRESHOLD  = int(os.getenv("ORIGIN_APPROACH_THRESHOLD", "120"))# 2m
ORIGIN_STOP_THRESHOLD      = int(os.getenv("ORIGIN_STOP_THRESHOLD", "60"))     # 1m

DEST_NEARBY_THRESHOLD      = int(os.getenv("DEST_NEARBY_THRESHOLD", "600"))    #10m
DEST_APPROACH_THRESHOLD    = int(os.getenv("DEST_APPROACH_THRESHOLD", "300"))  # 5m
DEST_STOP_THRESHOLD        = int(os.getenv("DEST_STOP_THRESHOLD", "120"))      # 2m

ORIGIN_STOP  = os.getenv("ORIGIN_STOP", "place-babck")   # Babcock St
DEST_STOP    = os.getenv("DEST_STOP",   "70147")         # BU East
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))    # seconds

# Arduino
BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))  # match transit_keychain.ino (Serial.begin 115200)
arduino_connection = None

# =======================
# Shared state for UI
# =======================
current_status    = "IDLE"  # IDLE | NEARBY | APPROACH | STOP (generic for UI badge)
last_origin_secs  = None
last_dest_secs    = None
last_updated_iso  = None
event_log         = []      # recent events for /events
last_origin_alert = "IDLE"  # ORIGIN_NEARBY/APPROACH/STOP/URGENT/IDLE (for Arduino dedupe)
last_dest_alert   = "IDLE"  # DEST_*/URGENT/IDLE

def _log_event(kind, payload):
    global event_log
    event_log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "payload": payload,
    })
    if len(event_log) > 100:
        event_log = event_log[-100:]

# =======================
# Arduino helpers
# =======================
def find_arduino_port():
    for p in serial.tools.list_ports.comports():
        if 'Arduino' in p.description or 'USB' in p.description:
            return p.device
    return None

def connect_to_arduino():
    """Connect (or reconnect) to Arduino."""
    global arduino_connection
    port = find_arduino_port()
    if port is None:
        print("Arduino not found.")
        return False
    try:
        arduino_connection = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)  # board reset window
        print(f"Connected to Arduino on {port} @ {BAUD_RATE} baud")
        return True
    except Exception as e:
        print(f"Failed to connect to Arduino: {e}")
        arduino_connection = None
        return False

def _arduino_write(line: str) -> bool:
    """Low-level write with auto-reconnect; logs to /events."""
    global arduino_connection
    msg = (line.strip() + "\n").encode()
    try:
        if not (arduino_connection and arduino_connection.is_open):
            if not connect_to_arduino():
                return False
        arduino_connection.write(msg)
        _log_event("arduino_cmd", {"send": line.strip()})
        return True
    except Exception as e:
        print(f"Arduino write failed: {e}")
        arduino_connection = None
        return False

def send_alert(command: str):
    """High-level alert to match .ino commands."""
    ok = _arduino_write(command)
    if ok:
        print(f"🔔 ALERT → {command}")
    else:
        print(f"❌ ALERT send failed → {command}")

def send_urgent_alert():
    send_alert("URGENT")

def send_status_update():
    send_alert("STATUS_UPDATE")

def send_led_status_update(origin_arrival, dest_arrival):
    """Send LED_STATUS_* based on which side is closer / available."""
    try:
        if origin_arrival and dest_arrival:
            # Prioritize whichever is closer
            if origin_arrival < dest_arrival:
                send_alert("LED_STATUS_ORIGIN")
            else:
                send_alert("LED_STATUS_DEST")
        elif origin_arrival:
            send_alert("LED_STATUS_ORIGIN")
        elif dest_arrival:
            send_alert("LED_STATUS_DEST")
        else:
            send_alert("LED_STATUS_NONE")
    except Exception as e:
        print(f"LED status update error: {e}")

# Back-compat helpers you already had (kept; used by /buzz dev tool)
def send_buzz_command(freq_hz, duration_ms):
    _arduino_write(f"BUZZ {int(freq_hz)} {int(duration_ms)}")

def send_vibration_command(command):
    """Accepts legacy generic commands from the dev buttons:
       NEARBY / APPROACH / STOP / IDLE.
       Default scope='origin'. Use extended commands for precise control."""
    command = (command or "").upper()
    if command == "IDLE":
        send_alert("IDLE")
    elif command in ("NEARBY","APPROACH","STOP"):
        # Default to ORIGIN_* so your current dev buttons still work.
        send_alert(f"ORIGIN_{command}")
    else:
        # If caller already passed extended commands, just forward.
        send_alert(command)

# =======================
# MBTA helpers
# =======================
def get_predictions_for_stop(stop_id):
    url = "https://api-v3.mbta.com/predictions"
    params = {"filter[stop]": stop_id, "sort": "arrival_time", "page[limit]": 5}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
    resp.raise_for_status()
    return resp.json()

def parse_time(timestr):
    if not timestr:
        return None
    try:
        return datetime.fromisoformat(timestr.replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def time_until(arrival_dt):
    now = datetime.now(timezone.utc)
    return (arrival_dt - now).total_seconds()

# =======================
# Alert decision logic
# =======================
def check_origin_alerts(origin_secs):
    if origin_secs is None: return "IDLE"
    if origin_secs <= 30:                      return "URGENT"
    if origin_secs <= ORIGIN_STOP_THRESHOLD:   return "ORIGIN_STOP"
    if origin_secs <= ORIGIN_APPROACH_THRESHOLD:return "ORIGIN_APPROACH"
    if origin_secs <= ORIGIN_NEARBY_THRESHOLD: return "ORIGIN_NEARBY"
    return "IDLE"

def check_dest_alerts(dest_secs):
    if dest_secs is None: return "IDLE"
    if dest_secs <= 60:                   return "URGENT"
    if dest_secs <= DEST_STOP_THRESHOLD:  return "DEST_STOP"
    if dest_secs <= DEST_APPROACH_THRESHOLD:return "DEST_APPROACH"
    if dest_secs <= DEST_NEARBY_THRESHOLD:return "DEST_NEARBY"
    return "IDLE"

# =======================
# Poller (runs in thread)
# =======================
def poll_loop():
    global current_status, last_origin_secs, last_dest_secs, last_updated_iso
    global last_origin_alert, last_dest_alert

    print("Starting transit alert poller")
    if not (arduino_connection and arduino_connection.is_open):
        connect_to_arduino()  # best-effort

    while True:
        try:
            # Origin predictions
            origin_secs = None
            try:
                preds_origin = get_predictions_for_stop(ORIGIN_STOP)
                for item in preds_origin.get("data", []):
                    at = parse_time(item.get("attributes", {}).get("arrival_time"))
                    if at:
                        secs = time_until(at)
                        if secs > 0:
                            origin_secs = secs; break
            except Exception as e:
                print(f"Origin fetch error: {e}")

            # Destination predictions
            dest_secs = None
            try:
                preds_dest = get_predictions_for_stop(DEST_STOP)
                for item in preds_dest.get("data", []):
                    at = parse_time(item.get("attributes", {}).get("arrival_time"))
                    if at:
                        secs = time_until(at)
                        if secs > 0:
                            dest_secs = secs; break
            except Exception as e:
                print(f"Dest fetch error: {e}")

            # Update UI-facing fields
            last_origin_secs = int(origin_secs) if origin_secs is not None else None
            last_dest_secs   = int(dest_secs)   if dest_secs   is not None else None
            last_updated_iso = datetime.now(timezone.utc).isoformat()

            # Derive generic UI status using your original thresholds
            next_status = "IDLE"
            if origin_secs is not None and origin_secs <= NEARBY_THRESHOLD_SEC: next_status = "NEARBY"
            if dest_secs   is not None and dest_secs   <= APPROACH_THRESHOLD_SEC: next_status = "APPROACH"
            if dest_secs   is not None and dest_secs   <= STOP_THRESHOLD_SEC:     next_status = "STOP"
            current_status = next_status

            # Compute Arduino alerts (separate for origin/dest) using teammate thresholds
            origin_alert = check_origin_alerts(origin_secs)
            dest_alert   = check_dest_alerts(dest_secs)

            # Fire only on change to reduce spam
            if origin_alert != last_origin_alert:
                if origin_alert == "URGENT": send_urgent_alert()
                elif origin_alert != "IDLE": send_alert(origin_alert)
                else: send_alert("IDLE")
                last_origin_alert = origin_alert
                if origin_secs is not None:
                    print(f"🚉 Origin {int(origin_secs)}s → {origin_alert}")

            if dest_alert != last_dest_alert:
                if dest_alert == "URGENT": send_urgent_alert()
                elif dest_alert != "IDLE": send_alert(dest_alert)
                else: send_alert("IDLE")
                last_dest_alert = dest_alert
                if dest_secs is not None:
                    print(f"🎯 Dest {int(dest_secs)}s → {dest_alert}")

            # Always update LED orientation so user sees priority side
            send_led_status_update(origin_secs, dest_secs)

            print("---")
        except Exception as e:
            print(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)

# =======================
# Flask API (unchanged contract)
# =======================
app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    connected = bool(arduino_connection and arduino_connection.is_open)
    mode = "arduino" if connected else "sim"
    return jsonify({
        "status": "ok",
        "mode": mode,
        "arduino": "connected" if connected else "not-connected",
        "origin_stop": ORIGIN_STOP,
        "dest_stop": DEST_STOP
    })

@app.route("/status")
def status():
    return jsonify({
        "status": current_status,
        "origin_secs": last_origin_secs,
        "dest_secs": last_dest_secs,
        "last_updated": last_updated_iso,
        "thresholds": {
            "nearby": NEARBY_THRESHOLD_SEC,
            "approach": APPROACH_THRESHOLD_SEC,
            "stop": STOP_THRESHOLD_SEC
        }
    })

@app.route("/buzz", methods=["POST"])
def buzz():
    """
    Dev hook: supports both your legacy generic commands and extended .ino commands.
    Body:
      { "command": "NEARBY|APPROACH|STOP|IDLE" }              # legacy (defaults to ORIGIN_*)
      { "command": "ORIGIN_NEARBY|DEST_STOP|...|IDLE" }       # extended .ino commands
      { "freq_hz": 1200, "duration_ms": 400 }                 # low-level BUZZ
      Optional: {"scope":"origin"|"dest"} used only with legacy generic commands.
    """
    data = request.get_json(silent=True) or {}

    if "freq_hz" in data and "duration_ms" in data:
        try:
            send_buzz_command(int(data["freq_hz"]), int(data["duration_ms"]))
            return jsonify({"ok": True, "pattern": {"freq_hz": int(data["freq_hz"]), "duration_ms": int(data["duration_ms"])}})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    cmd = (data.get("command") or "").upper()
    scope = (data.get("scope") or "origin").lower()  # optional
    if not cmd:
        return jsonify({"ok": False, "error": "missing command"}), 400

    # Extended commands pass-through
    if any(cmd.startswith(prefix) for prefix in ("ORIGIN_","DEST_")) or cmd in {"URGENT","IDLE","STATUS_UPDATE","LED_STATUS_ORIGIN","LED_STATUS_DEST","LED_STATUS_NONE"}:
        send_alert(cmd)
        return jsonify({"ok": True, "sent": cmd})

    # Legacy generic → map to ORIGIN_* or DEST_* (default origin)
    if cmd in {"NEARBY","APPROACH","STOP","IDLE"}:
        if cmd == "IDLE":
            send_alert("IDLE")
            return jsonify({"ok": True, "sent": "IDLE"})
        mapped = f"{'ORIGIN' if scope!='dest' else 'DEST'}_{cmd}"
        send_alert(mapped)
        return jsonify({"ok": True, "sent": mapped})

    return jsonify({"ok": False, "error": "unknown command"}), 400

@app.route("/config", methods=["POST"])
def config():
    global ORIGIN_STOP, DEST_STOP
    data = request.get_json(silent=True) or {}
    if "origin_stop" in data: ORIGIN_STOP = str(data["origin_stop"])
    if "dest_stop"   in data: DEST_STOP   = str(data["dest_stop"])
    return jsonify({"ok": True, "origin_stop": ORIGIN_STOP, "dest_stop": DEST_STOP})

@app.route("/events")
def events():
    return jsonify({"events": event_log[-20:]})

# =======================
# Entrypoint
# =======================
def start_background():
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    # Optional: CLI test path preserved if you had one (not required here)
    start_background()
    port = int(os.getenv("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
