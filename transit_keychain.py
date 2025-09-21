#!/usr/bin/env python3
"""
Transit Keychain - Python Controller
Controls the Arduino keychain based on train ETAs
"""

import time
import requests
import serial
import serial.tools.list_ports
from datetime import datetime, timezone

# --- Config ---
API_KEY = "c03504c502784cf2800d09ffa832c0e9"
HEADERS = {"x-api-key": API_KEY}

ORIGIN_STOP = "place-babck"    # Babcock Street
DEST_STOP = "70147"            # BU East

# Alert thresholds (in seconds) - More aggressive for pronounced alerts
ORIGIN_NEARBY_THRESHOLD = 1300   # 5 minutes (more time to notice)
ORIGIN_APPROACH_THRESHOLD = 120  # 2 minutes
ORIGIN_STOP_THRESHOLD = 60     # 1 minute

DEST_NEARBY_THRESHOLD = 1400     # 10 minutes (more time to notice)
DEST_APPROACH_THRESHOLD = 300   # 5 minutes
DEST_STOP_THRESHOLD = 120      # 2 minutes

POLL_INTERVAL = 30  # seconds

# Arduino communication
arduino_connection = None

def find_arduino_port():
    """Find Arduino port"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'Arduino' in port.description or 'USB' in port.description:
            return port.device
    return None

def connect_to_arduino():
    """Connect to Arduino"""
    global arduino_connection
    
    port = find_arduino_port()
    if port is None:
        print("❌ Arduino not found")
        return False
    
    try:
        arduino_connection = serial.Serial(port, 115200, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        print(f"✅ Connected to Arduino on {port}")
        return True
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False

def send_alert(command):
    """Send alert command to Arduino"""
    global arduino_connection
    
    if arduino_connection and arduino_connection.is_open:
        try:
            arduino_connection.write(f"{command}\n".encode())
            print(f"🔔 ALERT: {command}")
        except Exception as e:
            print(f"❌ Failed to send alert: {e}")
    else:
        print("❌ Arduino not connected")

def send_urgent_alert():
    """Send urgent alert - impossible to miss"""
    global arduino_connection
    
    if arduino_connection and arduino_connection.is_open:
        try:
            arduino_connection.write(b"URGENT\n")
            print("🚨 URGENT ALERT: Impossible to miss!")
        except Exception as e:
            print(f"❌ Failed to send urgent alert: {e}")
    else:
        print("❌ Arduino not connected")

def send_status_update():
    """Send quick status update beep"""
    global arduino_connection
    
    if arduino_connection and arduino_connection.is_open:
        try:
            arduino_connection.write(b"STATUS_UPDATE\n")
            print("📊 Status update beep")
        except Exception as e:
            print(f"❌ Failed to send status update: {e}")
    else:
        print("❌ Arduino not connected")

def get_predictions_for_stop(stop_id):
    """Get train predictions for a stop"""
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
    """Parse ISO time string"""
    if not timestr:
        return None
    try:
        dt = datetime.fromisoformat(timestr)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def time_until(arrival_dt):
    """Calculate seconds until arrival"""
    now = datetime.now(timezone.utc)
    return (arrival_dt - now).total_seconds()

def check_origin_alerts(origin_arrival):
    """Check if origin alerts should be triggered"""
    if origin_arrival is None:
        return "IDLE"
    
    if origin_arrival <= 30:  # Very urgent - 30 seconds
        return "URGENT"
    elif origin_arrival <= ORIGIN_STOP_THRESHOLD:
        return "ORIGIN_STOP"
    elif origin_arrival <= ORIGIN_APPROACH_THRESHOLD:
        return "ORIGIN_APPROACH"
    elif origin_arrival <= ORIGIN_NEARBY_THRESHOLD:
        return "ORIGIN_NEARBY"
    else:
        return "IDLE"

def check_destination_alerts(dest_arrival):
    """Check if destination alerts should be triggered"""
    if dest_arrival is None:
        return "IDLE"
    
    if dest_arrival <= 60:  # Very urgent - 1 minute
        return "URGENT"
    elif dest_arrival <= DEST_STOP_THRESHOLD:
        return "DEST_STOP"
    elif dest_arrival <= DEST_APPROACH_THRESHOLD:
        return "DEST_APPROACH"
    elif dest_arrival <= DEST_NEARBY_THRESHOLD:
        return "DEST_NEARBY"
    else:
        return "IDLE"

def main():
    """Main transit keychain loop"""
    print("🚊 Transit Keychain Starting")
    print("=" * 40)
    
    # Connect to Arduino
    if not connect_to_arduino():
        print("❌ Cannot connect to Arduino. Exiting.")
        return
    
    print("🔍 Monitoring transit alerts...")
    print(f"Origin: {ORIGIN_STOP} (Babcock Street)")
    print(f"Destination: {DEST_STOP} (BU East)")
    print("=" * 40)
    
    last_origin_alert = "IDLE"
    last_dest_alert = "IDLE"
    
    while True:
        try:
            # Get origin predictions
            origin_preds = get_predictions_for_stop(ORIGIN_STOP)
            origin_arrival = None
            
            for item in origin_preds.get("data", []):
                attr = item.get("attributes", {})
                at = parse_time(attr.get("arrival_time"))
                if at:
                    secs = time_until(at)
                    if secs > 0:
                        origin_arrival = secs
                        break
            
            # Get destination predictions
            dest_preds = get_predictions_for_stop(DEST_STOP)
            dest_arrival = None
            
            for item in dest_preds.get("data", []):
                attr = item.get("attributes", {})
                at = parse_time(attr.get("arrival_time"))
                if at:
                    secs = time_until(at)
                    if secs > 0:
                        dest_arrival = secs
                        break
            
            # Check for origin alerts
            origin_alert = check_origin_alerts(origin_arrival)
            if origin_alert != last_origin_alert:
                if origin_alert == "URGENT":
                    send_urgent_alert()
                else:
                    send_alert(origin_alert)
                last_origin_alert = origin_alert
                
                if origin_arrival:
                    print(f"🚉 Origin: {origin_arrival:.0f}s - {origin_alert}")
            
            # Check for destination alerts
            dest_alert = check_destination_alerts(dest_arrival)
            if dest_alert != last_dest_alert:
                if dest_alert == "URGENT":
                    send_urgent_alert()
                else:
                    send_alert(dest_alert)
                last_dest_alert = dest_alert
                
                if dest_arrival:
                    print(f"🎯 Destination: {dest_arrival:.0f}s - {dest_alert}")
            
            # Send alert every time status is updated (continuous feedback)
            if origin_arrival or dest_arrival:
                print(f"⏰ Status: Origin={origin_arrival:.0f}s, Dest={dest_arrival:.0f}s")
                
                # Determine which alert to send based on current status
                if origin_arrival and dest_arrival:
                    # Both origin and destination have trains
                    if origin_arrival < dest_arrival:
                        # Origin is closer, prioritize origin alert
                        current_alert = origin_alert
                    else:
                        # Destination is closer, prioritize destination alert
                        current_alert = dest_alert
                elif origin_arrival:
                    # Only origin has train
                    current_alert = origin_alert
                elif dest_arrival:
                    # Only destination has train
                    current_alert = dest_alert
                else:
                    current_alert = "IDLE"
                
                # Send continuous status alert
                if current_alert != "IDLE":
                    if current_alert == "URGENT":
                        send_urgent_alert()
                    else:
                        send_alert(current_alert)
                else:
                    send_alert("IDLE")
                
                # Also send a quick status update beep
                send_status_update()
            
            print("---")
            time.sleep(POLL_INTERVAL)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
