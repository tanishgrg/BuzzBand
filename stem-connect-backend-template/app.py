import time
import requests
import serial
import serial.tools.list_ports
from datetime import datetime, timezone

# --- Config ---
API_KEY = "c03504c502784cf2800d09ffa832c0e9"
HEADERS = {"x-api-key": API_KEY}

ORIGIN_STOP = "place-babck"    # Babcock Street (Green Line B)
DEST_STOP   = "70147"          # BU East

NEARBY_THRESHOLD_SEC     = 180   # <= 3 min at origin -> NEARBY
APPROACH_THRESHOLD_SEC   = 300   # <= 5 min at destination -> APPROACH
STOP_THRESHOLD_SEC       = 60    # <= 1 min at destination -> STOP

POLL_INTERVAL = 30  # seconds

# Arduino communication
arduino_connection: serial.Serial | None = None
BAUD = 115200  # must match sketch

# --- Arduino Helpers ---

def find_arduino_port():
    """Find likely Arduino Nano ESP32 port on Win/Mac/Linux."""
    candidates = []
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(k in desc for k in [
            "arduino", "nano", "esp32", "cp210", "silicon labs", "wch", "ch340", "usb-serial"
        ]) or "esp32" in hwid:
            candidates.append(p.device)
    # fallback: return first enumerated port if nothing matched
    if candidates:
        return candidates[0]
    ports = list(serial.tools.list_ports.comports())
    return ports[0].device if ports else None

def connect_to_arduino(wait_ready=True):
    """Connect to Arduino via serial."""
    global arduino_connection

    port = find_arduino_port()
    if port is None:
        print("Arduino not found. Please check connection.")
        return False

    try:
        arduino_connection = serial.Serial(port, BAUD, timeout=1)
        # Allow board to reboot after serial open
        time.sleep(1.5)

        if wait_ready:
            # Read lines briefly to catch "READY"
            t0 = time.time()
            while time.time() - t0 < 3.0:
                line = arduino_connection.readline().decode(errors="ignore").strip()
                if line:
                    # print(f"[Serial] {line}")
                    if "READY" in line:
                        break

        print(f"Connected to Arduino on {port} @ {BAUD}")
        return True
    except Exception as e:
        print(f"Failed to connect to Arduino: {e}")
        arduino_connection = None
        return False

def send_command(line: str):
    """Send a line to Arduino with newline."""
    global arduino_connection
    if arduino_connection and arduino_connection.is_open:
        try:
            arduino_connection.write((line.strip() + "\n").encode())
        except Exception as e:
            print(f"Failed to send command '{line}': {e}")
    else:
        print("Arduino not connected")

def send_buzz_command(freq_hz: int, duration_ms: int):
    send_command(f"BUZZ {freq_hz} {duration_ms}")

# --- MBTA Helpers ---

def get_predictions_for_stop(stop_id):
    url = "https://api-v3.mbta.com/predictions"
    params = {
        "filter[stop]": stop_id,
        "sort": "arrival_time",
        "page[limit]": 5
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=8)
    resp.raise_for_status()
    return resp.json()

def parse_time(timestr):
    if not timestr:
        return None
    try:
        dt = datetime.fromisoformat(timestr)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def time_until(arrival_dt):
    now = datetime.now(timezone.utc)
    return (arrival_dt - now).total_seconds()

# --- Test routine ---

def test_arduino_connection():
    """Exercise alert commands + BUZZ."""
    if not connect_to_arduino(wait_ready=True):
        return False

    print("Testing alerts...")
    patterns = [
        ("ORIGIN_NEARBY",   "Origin nearby (green)"),
        ("ORIGIN_APPROACH", "Origin approach (green)"),
        ("ORIGIN_STOP",     "Origin stop (red)"),
        ("DEST_NEARBY",     "Dest nearby (green)"),
        ("DEST_APPROACH",   "Dest approach (green)"),
        ("DEST_STOP",       "Dest stop (red)"),
    ]
    for cmd, label in patterns:
        print(f"  -> {label}")
        send_command(cmd)
        time.sleep(1.2)

    print("Testing BUZZ tones (doorbell-ish)...")
    send_buzz_command(880, 150)
    time.sleep(0.08)
    send_buzz_command(988, 150)
    time.sleep(0.08)
    send_buzz_command(1175, 250)

    print("Test complete.")
    return True

# --- Main loop ---

def main():
    print("Starting transit alert prototype")
    state = "IDLE"  # IDLE, NEARBY_SENT, APPROACH_SENT, STOP_SENT

    if connect_to_arduino():
        print("Arduino haptics ready")
    else:
        print("Running without Arduino connection (alerts still printed)")

    while True:
        # ORIGIN
        try:
            preds_origin = get_predictions_for_stop(ORIGIN_STOP)
        except Exception as e:
            print("Error fetching origin predictions:", e)
            time.sleep(POLL_INTERVAL)
            continue

        origin_arrival = None
        for item in preds_origin.get("data", []):
            at = parse_time(item.get("attributes", {}).get("arrival_time"))
            if at:
                secs = time_until(at)
                if secs > 0:
                    origin_arrival = secs
                    break

        if origin_arrival is None:
            print("No upcoming train at origin.")
            if state != "IDLE":
                send_command("IDLE")
            state = "IDLE"
        else:
            print(f"ETA at Babcock St: {origin_arrival:.0f}s")
            if state == "IDLE" and origin_arrival <= NEARBY_THRESHOLD_SEC:
                print("→ ALERT: ORIGIN_NEARBY")
                # three quick tones
                send_buzz_command(880, 150)
                time.sleep(0.05)
                send_buzz_command(988, 150)
                time.sleep(0.05)
                send_buzz_command(1175, 250)
                send_command("ORIGIN_NEARBY")
                state = "NEARBY_SENT"

        # DESTINATION
        try:
            preds_dest = get_predictions_for_stop(DEST_STOP)
        except Exception as e:
            print("Error fetching destination predictions:", e)
            time.sleep(POLL_INTERVAL)
            continue

        dest_arrival = None
        for item in preds_dest.get("data", []):
            at = parse_time(item.get("attributes", {}).get("arrival_time"))
            if at:
                secs = time_until(at)
                if secs > 0:
                    dest_arrival = secs
                    break

        if dest_arrival is None:
            print("No upcoming train projected to destination.")
        else:
            print(f"ETA at BU East: {dest_arrival:.0f}s")
            if state == "NEARBY_SENT" and dest_arrival <= APPROACH_THRESHOLD_SEC:
                print("→ ALERT: DEST_APPROACH")
                send_buzz_command(988, 500)
                send_command("DEST_APPROACH")
                state = "APPROACH_SENT"

            if state in ("NEARBY_SENT", "APPROACH_SENT") and dest_arrival <= STOP_THRESHOLD_SEC:
                print("→ ALERT: DEST_STOP")
                send_buzz_command(1175, 1000)
                send_command("DEST_STOP")
                state = "STOP_SENT"

        print("---")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].lower() == "test":
        test_arduino_connection()
    else:
        main()
