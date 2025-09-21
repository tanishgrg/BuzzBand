# app.py — BuzzBand backend (merged + improved)
# - Flask API for frontend
# - MBTA predictions + trip_id matching (consistent ETAs)
# - Arduino serial with robust port detection
# - SIM mode (forced via env) + auto-fallback to SIM if no hardware
# - Dev endpoints: /events, /selftest, /sim

import os
import time
import threading
import requests
import serial
import serial.tools.list_ports
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS

# ==============================
# Config
# ==============================
API_KEY = os.getenv("MBTA_API_KEY", "c03504c502784cf2800d09ffa832c0e9")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

# SIM control:
# - If SIM_MODE=true -> always simulate
# - If SIM_MODE not set/false -> try real Arduino; auto-fallback to SIM if not found / errors
SIM_MODE = os.getenv("SIM_MODE", "").lower() == "true"
sim_last_cmd = None

# UI thresholds (simple badge)
NEARBY_THRESHOLD_SEC   = int(os.getenv("NEARBY_THRESHOLD_SEC", "180"))  # 3 min
APPROACH_THRESHOLD_SEC = int(os.getenv("APPROACH_THRESHOLD_SEC", "300"))# 5 min
STOP_THRESHOLD_SEC     = int(os.getenv("STOP_THRESHOLD_SEC", "60"))     # 1 min

# Device thresholds (alert mapping)
ORIGIN_NEARBY_THRESHOLD    = int(os.getenv("ORIGIN_NEARBY_THRESHOLD", "300"))  # 5m
ORIGIN_APPROACH_THRESHOLD  = int(os.getenv("ORIGIN_APPROACH_THRESHOLD", "120"))# 2m
ORIGIN_STOP_THRESHOLD      = int(os.getenv("ORIGIN_STOP_THRESHOLD", "60"))     # 1m

DEST_NEARBY_THRESHOLD      = int(os.getenv("DEST_NEARBY_THRESHOLD", "600"))    #10m
DEST_APPROACH_THRESHOLD    = int(os.getenv("DEST_APPROACH_THRESHOLD", "300"))  # 5m
DEST_STOP_THRESHOLD        = int(os.getenv("DEST_STOP_THRESHOLD", "120"))      # 2m

# Default stops (env-overridable)
ORIGIN_STOP  = os.getenv("ORIGIN_STOP", "place-babck")   # Babcock St (Green-B)
DEST_STOP    = os.getenv("DEST_STOP",   "70147")         # BU East (bus example)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))    # seconds

# Arduino
BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))
arduino_connection: serial.Serial | None = None

# =======================
# Shared state for UI
# =======================
current_status    = "IDLE"  # IDLE | NEARBY | APPROACH | STOP
last_origin_secs  = None
last_dest_secs    = None
last_trip_id      = None
last_updated_iso  = None
event_log         = []      # recent events for /events
last_origin_alert = "IDLE"  # ORIGIN_NEARBY/APPROACH/STOP/URGENT/IDLE
last_dest_alert   = "IDLE"  # DEST_NEARBY/APPROACH/STOP/URGENT/IDLE

def _log_event(kind, payload):
    global event_log
    event_log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "payload": payload,
    })
    if len(event_log) > 200:
        event_log = event_log[-200:]

# =======================
# Arduino helpers
# =======================
def find_arduino_port():
    """Find likely Arduino/Nano/ESP32 serial port across OSes (robust)."""
    candidates = []
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        dev  = (p.device or "")

        # Common matches by description or hwid
        if any(k in desc for k in [
            "arduino", "nano", "esp32", "cp210", "silicon labs", "wch", "ch340", "usb-serial"
        ]) or "esp32" in hwid:
            candidates.append(dev)

        # macOS device name hints
        if any(k in dev.lower() for k in ["usbmodem", "usbserial"]):
            candidates.append(dev)

    # De-dup & prefer /dev/cu.* on macOS
    seen = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            seen.add(c); ordered.append(c)
    ordered = sorted(ordered, key=lambda d: ("/cu." not in d, d))
    if ordered:
        return ordered[0]

    # Fallback: first enumerated port if nothing matched
    ports = list(serial.tools.list_ports.comports())
    return ports[0].device if ports else None

def connect_to_arduino(wait_ready=True):
    """Connect (or reconnect) to Arduino, optionally waiting for sketch banner."""
    global arduino_connection
    port = find_arduino_port()
    if port is None:
        print("Arduino not found.")
        return False
    try:
        arduino_connection = serial.Serial(port, BAUD_RATE, timeout=1)
        # allow board reboot after opening serial
        time.sleep(1.5)
        if wait_ready:
            t0 = time.time()
            while time.time() - t0 < 3.0:
                try:
                    line = arduino_connection.readline().decode(errors="ignore").strip()
                except Exception:
                    line = ""
                if line:
                    # Uncomment to debug: print(f"[Serial] {line}")
                    if ("Transit Keychain Ready" in line) or ("Starting Transit Keychain" in line) or ("READY" in line):
                        break
        print(f"Connected to Arduino on {port} @ {BAUD_RATE} baud")
        return True
    except Exception as e:
        print(f"Failed to connect to Arduino: {e}")
        arduino_connection = None
        return False

def _arduino_write(line: str) -> bool:
    """Low-level write with SIM and auto-fallback; logs to /events."""
    global arduino_connection, sim_last_cmd, SIM_MODE
    msg_txt = line.strip()
    msg = (msg_txt + "\n").encode()

    try:
        # Forced SIM mode
        if SIM_MODE:
            sim_last_cmd = {"ts": datetime.now(timezone.utc).isoformat(), "cmd": msg_txt}
            _log_event("sim_cmd", {"send": msg_txt})
            print(f"[SIM] {msg_txt}")
            return True

        # Try real hardware
        if not (arduino_connection and arduino_connection.is_open):
            if not connect_to_arduino(wait_ready=True):
                # Auto-fallback to SIM if not found
                sim_last_cmd = {"ts": datetime.now(timezone.utc).isoformat(), "cmd": msg_txt}
                _log_event("sim_cmd", {"send": msg_txt, "note": "auto-fallback-no-device"})
                print(f"[SIM-fallback] {msg_txt}")
                return True

        arduino_connection.write(msg)
        _log_event("arduino_cmd", {"send": msg_txt})
        return True

    except Exception as e:
        print(f"Arduino write failed: {e}")
        arduino_connection = None
        # Auto-fallback to SIM on error
        sim_last_cmd = {"ts": datetime.now(timezone.utc).isoformat(), "cmd": msg_txt}
        _log_event("sim_cmd", {"send": msg_txt, "note": "auto-fallback-error"})
        print(f"[SIM-fallback after error] {msg_txt}")
        return True

def send_alert(command: str):
    ok = _arduino_write(command)
    if ok:
        print(f"🔔 ALERT → {command}")
    else:
        print(f"❌ ALERT send failed → {command}")

def send_urgent_alert():
    send_alert("URGENT")

def send_status_update():
    send_alert("STATUS_UPDATE")

def send_led_status_update(origin_secs, dest_secs):
    """Send LED_STATUS_* based on which side is sooner/available."""
    try:
        if origin_secs is not None and dest_secs is not None:
            if origin_secs < dest_secs:
                send_alert("LED_STATUS_ORIGIN")
            else:
                send_alert("LED_STATUS_DEST")
        elif origin_secs is not None:
            send_alert("LED_STATUS_ORIGIN")
        elif dest_secs is not None:
            send_alert("LED_STATUS_DEST")
        else:
            send_alert("LED_STATUS_NONE")
    except Exception as e:
        print(f"LED status update error: {e}")

def _doorbell():
    """Optional tiny tone flourish on transitions (safe if simulated)."""
    try:
        _arduino_write("BUZZ 880 120"); time.sleep(0.05)
        _arduino_write("BUZZ 988 120"); time.sleep(0.05)
        _arduino_write("BUZZ 1175 180")
    except Exception:
        pass

# =======================
# MBTA helpers
# =======================
def get_predictions_for_stop(stop_id, limit=8):
    url = "https://api-v3.mbta.com/predictions"
    params = {"filter[stop]": stop_id, "sort": "arrival_time", "page[limit]": limit}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
    resp.raise_for_status()
    return resp.json()

def parse_time(timestr):
    if not timestr:
        return None
    try:
        # Handle trailing Z and timezone normalize
        return datetime.fromisoformat(timestr.replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def time_until(dt):
    if not dt:
        return None
    return (dt - datetime.now(timezone.utc)).total_seconds()

def _normalize_predictions(stop_id, limit=8):
    """
    Return sorted list of upcoming predictions at a stop with keys:
    { 'ts': datetime (arrival or departure), 'secs': float, 'trip_id': str|None, 'direction_id': int|None }
    """
    raw = get_predictions_for_stop(stop_id, limit=limit)
    now = datetime.now(timezone.utc)
    rows = []
    for item in raw.get("data", []):
        attrs = item.get("attributes", {}) or {}
        rels  = item.get("relationships", {}) or {}
        trip  = (rels.get("trip", {}) or {}).get("data", {}) or {}
        trip_id = trip.get("id")
        direction_id = attrs.get("direction_id")

        at = parse_time(attrs.get("arrival_time"))
        dt = parse_time(attrs.get("departure_time"))
        ts = at or dt
        if not ts:
            continue
        secs = (ts - now).total_seconds()
        if secs <= 0:
            continue

        rows.append({
            "ts": ts,
            "secs": secs,
            "trip_id": trip_id,
            "direction_id": direction_id
        })
    rows.sort(key=lambda r: r["secs"])
    return rows

def match_origin_dest_by_trip(origin_stop, dest_stop):
    """
    Pick the next upcoming origin prediction, then find the matching destination prediction by trip_id
    so ETAs are consistent for the same vehicle.
    Returns (origin_secs, dest_secs, trip_id) — any may be None if not found.
    """
    origin_rows = _normalize_predictions(origin_stop, limit=8)
    dest_rows   = _normalize_predictions(dest_stop,   limit=12)

    if not origin_rows:
        return (None, None, None)

    # Try each candidate at origin until we find a matching trip at dest
    for o in origin_rows:
        trip_id = o["trip_id"]
        if not trip_id:
            continue
        # same trip_id (and typically same direction_id)
        match = next((d for d in dest_rows if d["trip_id"] == trip_id), None)
        if match:
            return (int(o["secs"]), int(match["secs"]), trip_id)

    # If no direct match, return the next origin and leave dest as None
    return (int(origin_rows[0]["secs"]), None, origin_rows[0]["trip_id"])

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
    global current_status, last_origin_secs, last_dest_secs, last_trip_id, last_updated_iso
    global last_origin_alert, last_dest_alert

    print("Starting transit alert poller")
    if not SIM_MODE and not (arduino_connection and arduino_connection.is_open):
        connect_to_arduino(wait_ready=True)  # best-effort

    while True:
        try:
            # Trip-matched ETAs
            try:
                o_secs, d_secs, trip_id = match_origin_dest_by_trip(ORIGIN_STOP, DEST_STOP)
            except Exception as e:
                print(f"Prediction fetch/match error: {e}")
                o_secs, d_secs, trip_id = (None, None, None)

            last_origin_secs = o_secs
            last_dest_secs   = d_secs
            last_trip_id     = trip_id
            last_updated_iso = datetime.now(timezone.utc).isoformat()

            # UI badge status (simple)
            next_status = "IDLE"
            if o_secs is not None and o_secs <= NEARBY_THRESHOLD_SEC:
                next_status = "NEARBY"
            if d_secs is not None and d_secs <= APPROACH_THRESHOLD_SEC:
                next_status = "APPROACH"
            if d_secs is not None and d_secs <= STOP_THRESHOLD_SEC:
                next_status = "STOP"
            current_status = next_status

            # Compute Arduino alerts (change-driven)
            origin_alert = check_origin_alerts(o_secs)
            dest_alert   = check_dest_alerts(d_secs)

            if origin_alert != last_origin_alert:
                _doorbell()
                if origin_alert == "URGENT": send_urgent_alert()
                elif origin_alert != "IDLE": send_alert(origin_alert)
                else: send_alert("IDLE")
                last_origin_alert = origin_alert
                if o_secs is not None:
                    print(f"🚉 Origin {int(o_secs)}s → {origin_alert}")

            if dest_alert != last_dest_alert:
                _doorbell()
                if dest_alert == "URGENT": send_urgent_alert()
                elif dest_alert != "IDLE": send_alert(dest_alert)
                else: send_alert("IDLE")
                last_dest_alert = dest_alert
                if d_secs is not None:
                    print(f"🎯 Dest {int(d_secs)}s → {dest_alert}")

            # Update LED orientation every loop
            send_led_status_update(o_secs, d_secs)

            print("---")
        except Exception as e:
            print(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)

# =======================
# Flask API
# =======================
app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    connected = bool(arduino_connection and arduino_connection.is_open)
    mode = "arduino" if connected and not SIM_MODE else "sim"
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
        "trip_id": last_trip_id,
        "last_updated": last_updated_iso,
        "thresholds": {
            "nearby": NEARBY_THRESHOLD_SEC,
            "approach": APPROACH_THRESHOLD_SEC,
            "stop": STOP_THRESHOLD_SEC
        }
    })

@app.route("/sim")
def sim_state():
    return jsonify({"sim_forced": SIM_MODE, "last": sim_last_cmd})

@app.route("/selftest", methods=["POST"])
def selftest():
    """Quick sequence of alerts + tones to validate device link (works in SIM too)."""
    seq = [
        "ORIGIN_NEARBY", "ORIGIN_APPROACH", "ORIGIN_STOP",
        "DEST_NEARBY",   "DEST_APPROACH",   "DEST_STOP"
    ]
    ok_all = True
    for cmd in seq:
        ok = _arduino_write(cmd)
        ok_all = ok_all and ok
        time.sleep(0.3)
    # doorbell-ish tones
    _arduino_write("BUZZ 880 150");   time.sleep(0.08)
    _arduino_write("BUZZ 988 150");   time.sleep(0.08)
    _arduino_write("BUZZ 1175 250")
    return jsonify({"ok": ok_all, "sequence": seq})

@app.route("/buzz", methods=["POST"])
def buzz():
    """
    Dev hook: supports both legacy generic commands and extended .ino commands.
    Body:
      { "command": "NEARBY|APPROACH|STOP|IDLE" }              # legacy (defaults to ORIGIN_* unless scope='dest')
      { "command": "ORIGIN_NEARBY|DEST_STOP|...|IDLE" }       # extended .ino commands
      { "freq_hz": 1200, "duration_ms": 400 }                 # low-level BUZZ
      Optional: {"scope":"origin"|"dest"} used only with legacy generic commands.
    """
    data = request.get_json(silent=True) or {}

    # Low-level BUZZ passthrough
    if "freq_hz" in data and "duration_ms" in data:
        try:
            freq = int(data["freq_hz"]); dur = int(data["duration_ms"])
            sent = _arduino_write(f"BUZZ {freq} {dur}")
            status_code = 200 if sent else 503
            return jsonify({"ok": sent, "pattern": {"freq_hz": freq, "duration_ms": dur}}), status_code
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    cmd = (data.get("command") or "").upper()
    scope = (data.get("scope") or "origin").lower()

    if not cmd:
        return jsonify({"ok": False, "error": "missing command"}), 400

    # Extended commands → send as-is
    if any(cmd.startswith(prefix) for prefix in ("ORIGIN_", "DEST_")) or cmd in {
        "URGENT","IDLE","STATUS_UPDATE","LED_STATUS_ORIGIN","LED_STATUS_DEST","LED_STATUS_NONE"
    }:
        sent = _arduino_write(cmd)
        return jsonify({"ok": sent, "sent": cmd}), (200 if sent else 503)

    # Legacy generic → map to ORIGIN_* or DEST_* (default origin)
    if cmd in {"NEARBY","APPROACH","STOP","IDLE"}:
        mapped = "IDLE" if cmd == "IDLE" else f"{'ORIGIN' if scope!='dest' else 'DEST'}_{cmd}"
        sent = _arduino_write(mapped)
        return jsonify({"ok": sent, "sent": mapped}), (200 if sent else 503)

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
    return jsonify({"events": event_log[-50:]})

# =======================
# Entrypoint
# =======================
def start_background():
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    start_background()
    port = int(os.getenv("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True)
