import time
import requests
from datetime import datetime, timezone

# --- Config ---
API_KEY = "c03504c502784cf2800d09ffa832c0e9"
HEADERS = {"x-api-key": API_KEY}

ORIGIN_STOP = "place-babck"    # Babcock Street
DEST_STOP   = "70147"          # BU East
NEARBY_THRESHOLD_SEC     = 180   # 3 minutes
APPROACH_THRESHOLD_SEC   = 300   # e.g. when arrival time to DEST stop <= 5 min, mark as approaching
STOP_THRESHOLD_SEC       = 60    # <1 minute → STOP

POLL_INTERVAL = 30  # seconds

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

def main():
    print("Starting transit alert prototype")
    state = "IDLE"  # IDLE, NEARBY_SENT, APPROACH_SENT, STOP_SENT
    
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
            state = "IDLE"
        else:
            print(f"ETA at Babcock St: {origin_arrival:.0f} seconds.")
            if state == "IDLE" and origin_arrival <= NEARBY_THRESHOLD_SEC:
                print("→ ALERT: NEARBY")
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
                state = "APPROACH_SENT"
            if state in ("NEARBY_SENT","APPROACH_SENT") and dest_arrival <= STOP_THRESHOLD_SEC:
                print("→ ALERT: STOP NOW")
                state = "STOP_SENT"
        
        print("---")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
