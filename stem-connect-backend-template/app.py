import time
import requests
import serial
import serial.tools.list_ports
from datetime import datetime, timezone

# --- Config ---
API_KEY = "c03504c502784cf2800d09ffa832c0e9"
HEADERS = {"x-api-key": API_KEY}

ORIGIN_STOP = "place-babck"    # Babcock Street
DEST_STOP   = "70147"          # BU East
NEARBY_THRESHOLD_SEC     = 180   # 3 minu
APPROACH_THRESHOLD_SEC   = 300   # e.g. when arrival time to DEST stop <= 5 min, mark as approaching
STOP_THRESHOLD_SEC       = 60    # <1 minute → STOP

POLL_INTERVAL = 30  # seconds

# Arduino communication
arduino_connection = None

# --- Arduino Helpers ---

def find_arduino_port():
    """Find the Arduino port automatically"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'Arduino' in port.description or 'USB' in port.description:
            return port.device
    return None

def connect_to_arduino():
    """Connect to Arduino via serial"""
    global arduino_connection
    
    port = find_arduino_port()
    if port is None:
        print("Arduino not found. Please check connection.")
        return False
    
    try:
        arduino_connection = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        print(f"Connected to Arduino on {port}")
        return True
    except Exception as e:
        print(f"Failed to connect to Arduino: {e}")
        return False

def send_vibration_command(command):
    """Send vibration command to Arduino"""
    global arduino_connection
    
    if arduino_connection and arduino_connection.is_open:
        try:
            arduino_connection.write(f"{command}\n".encode())
            print(f"Sent vibration command: {command}")
        except Exception as e:
            print(f"Failed to send command to Arduino: {e}")
    else:
        print("Arduino not connected")

def send_buzz_command(freq_hz, duration_ms):
    """Send BUZZ command like testArduino"""
    global arduino_connection
    
    if arduino_connection and arduino_connection.is_open:
        try:
            cmd = f"BUZZ {freq_hz} {duration_ms}\n"
            arduino_connection.write(cmd.encode())
            print(f"Sent BUZZ command: {freq_hz}Hz for {duration_ms}ms")
        except Exception as e:
            print(f"Failed to send BUZZ command: {e}")
    else:
        print("Arduino not connected")

# --- Helpers ---

def get_predictions_for_stop(stop_id):
    url = "https://api-v3.mbta.com/predictions"
    params = {
        "filter[stop]": stop_id,
        "sort": "arrival_time",
        "page[limit]": 5
    }
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()

def parse_time(timestr):
    # timestr is ISO 8601 or may be null
    if not timestr:
        return None
    try:
        # example: "2025-09-20T12:34:00-04:00"
        dt = datetime.fromisoformat(timestr)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        return None

def time_until(arrival_dt):
    now = datetime.now(timezone.utc)
    return (arrival_dt - now).total_seconds()

# --- Main loop ---

def test_arduino_connection():
    """Test Arduino connection using the working approach"""
    global arduino_connection
    
    port = find_arduino_port()
    if port is None:
        print("❌ Arduino not found. Please check connection.")
        return False
    
    print(f"✅ Found Arduino on {port}")
    
    try:
        # Connect to Arduino
        arduino_connection = serial.Serial(port, 9600, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        
        print("✅ Connected to Arduino")
        print("Testing beep patterns...")
        
        # Test each beep pattern
        patterns = [
            ("NEARBY", "Short beep pattern"),
            ("APPROACH", "Medium beep pattern"), 
            ("STOP", "Long beep pattern"),
            ("IDLE", "Stop all beeps")
        ]
        
        for command, description in patterns:
            print(f"\n🧪 Testing {command}: {description}")
            arduino_connection.write(f"{command}\n".encode())
            
            # Wait for pattern to complete
            if command == "NEARBY":
                arduino.write(b"BUZZ 1000 1000\n")
                time.sleep(1)
            elif command == "APPROACH":
                arduino.write(b"BUZZ 2000 500\n")
                time.sleep(2)
            elif command == "STOP":
                arduino.write(b"BUZZ 500 500\n")
                time.sleep(4)
            else:
                arduino.write(b"BUZZ 0 0\n")
                time.sleep(0.5)
            
            print(f"✅ {command} test completed")
        
        print("\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Arduino: {e}")
        return False

def main():
    print("Starting transit alert prototype")
    state = "IDLE"  # IDLE, NEARBY_SENT, APPROACH_SENT, STOP_SENT
    
    # Try to connect to Arduino
    if connect_to_arduino():
        print("Arduino vibration system ready")
    else:
        print("Running without Arduino vibration")
    
    while True:
        # Get predictions for origin
        try:
            preds_origin = get_predictions_for_stop(ORIGIN_STOP)
        except Exception as e:
            print("Error fetching origin predictions:", e)
            time.sleep(POLL_INTERVAL)
            continue
        
        # find first upcoming arrival with valid time
        origin_arrival = None
        for item in preds_origin.get("data", []):
            attr = item.get("attributes", {})
            at = parse_time(attr.get("arrival_time"))
            if at:
                secs = time_until(at)
                if secs > 0:
                    origin_arrival = secs
                    break
        
        if origin_arrival is None:
            print("No upcoming train at origin.")
            if state != "IDLE":
                send_vibration_command("IDLE")
            state = "IDLE"
        else:
            print(f"ETA at Babcock St: {origin_arrival:.0f} seconds.")
            if state == "IDLE" and origin_arrival <= NEARBY_THRESHOLD_SEC:
                print("→ ALERT: NEARBY")
                # Use same doorbell sequence as testArduino
                send_buzz_command(880, 150)   # First note
                time.sleep(0.05)
                send_buzz_command(988, 150)   # Second note  
                time.sleep(0.05)
                send_buzz_command(1175, 250)  # Third note
                state = "NEARBY_SENT"
        
        # Also check predictions for destination
        try:
            preds_dest = get_predictions_for_stop(DEST_STOP)
        except Exception as e:
            print("Error fetching destination predictions:", e)
            time.sleep(POLL_INTERVAL)
            continue
        
        dest_arrival = None
        for item in preds_dest.get("data", []):
            attr = item.get("attributes", {})
            at = parse_time(attr.get("arrival_time"))
            if at:
                secs = time_until(at)
                if secs > 0:
                    dest_arrival = secs
                    break
        
        if dest_arrival is None:
            print("No upcoming train projected to destination.")
        else:
            print(f"ETA at BU East: {dest_arrival:.0f} seconds.")
            if state == "NEARBY_SENT" and dest_arrival <= APPROACH_THRESHOLD_SEC:
                print("→ ALERT: APPROACHING DESTINATION")
                # Use second note of doorbell sequence
                send_buzz_command(988, 500)
                state = "APPROACH_SENT"
            if state in ("NEARBY_SENT","APPROACH_SENT") and dest_arrival <= STOP_THRESHOLD_SEC:
                print("→ ALERT: STOP NOW")
                # Use third note of doorbell sequence
                send_buzz_command(1175, 1000)
                state = "STOP_SENT"
        
        print("---")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    import sys
    
    # Check if user wants to test Arduino first
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🧪 Testing Arduino connection...")
        test_arduino_connection()
    else:
        main()

arduino_connection = serial.Serial(port, 115200, timeout=1)
