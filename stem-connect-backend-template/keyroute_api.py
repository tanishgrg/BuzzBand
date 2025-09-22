# keyroute_api.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from time import time
import uuid
import os, requests, json, glob

# ---- MBTA API config ----
MBTA_API_KEY = os.getenv("MBTA_API_KEY", "")
MBTA_BASE = "https://api-v3.mbta.com"

# ---- Flask app ----
app = Flask(__name__)
CORS(app)  # allow http://localhost:5173 (Vite dev) to call the API

# ---- Hardware (Arduino) ----
SERIAL_BAUD = int(os.getenv("KEYROUTE_SERIAL_BAUD", "115200"))

def find_serial_port():
    # Common Arduino device patterns on macOS
    candidates = glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/tty.usbserial*")
    return os.getenv("KEYROUTE_SERIAL_PORT") or (candidates[0] if candidates else None)

try:
    import serial
    port = find_serial_port()
    if port:
        ser = serial.Serial(port, SERIAL_BAUD, timeout=0.5)
        print(f"[HW] Connected to {port}@{SERIAL_BAUD}")
    else:
        ser = None
        print("[HW] No serial port found; running in log-only mode")
except Exception as e:
    ser = None
    print(f"[HW] Not connected: {e}")

def send_hw(msg: dict):
    """Send one JSON line to Arduino; falls back to console if no serial."""
    try:
        line = (json.dumps(msg) + "\n").encode("utf-8")
        if ser and ser.writable():
            ser.write(line)
        else:
            print("HW>", msg)
    except Exception as e:
        print("HW error:", e)

# ---- MBTA helper ----
def mbta_get(path, params):
    headers = {"accept": "application/json"}
    if MBTA_API_KEY:
        headers["x-api-key"] = MBTA_API_KEY
    r = requests.get(f"{MBTA_BASE}{path}", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

def clamp_nonneg(x): 
    return max(0, int(x))

# --- In-memory store (fine for hackathon) ---
class Session:
    def __init__(self, origin_stop_id, dest_stop_id, route_id=None):
        self.id = str(uuid.uuid4())
        self.origin_stop_id = origin_stop_id
        self.dest_stop_id = dest_stop_id
        self.route_id = route_id
        self.state = "AWAITING_BOARD"   # AWAITING_BOARD | ONBOARD | APPROACHING_DEST | ARRIVED
        self.trip_id = None
        self.last_emitted_state = None
        self.created_ts = time()
        # simple stub timers (seconds)
        self.stub_origin_eta = 240      # 4 min until train reaches origin
        self.stub_dest_eta = 1800       # 30 min total to destination
        self.boarded_ts = None

sessions = {}  # session_id -> Session

def emit_state_change(session, new_state):
    """Fire LEDs/buzz exactly once per meaningful transition."""
    if session.last_emitted_state == new_state:
        return
    session.last_emitted_state = new_state

    if new_state == "AWAITING_BOARD":
        send_hw({"led":"green","buzz":"tiny"})
    elif new_state == "ONBOARD":
        send_hw({"led":"off","buzz":"none"})
    elif new_state == "APPROACHING_DEST":
        send_hw({"led":"yellow","buzz":"short"})
    elif new_state == "ARRIVED":
        send_hw({"led":"red","buzz":"long"})

# --- API: create session ---
@app.post("/session")
def create_session():
    data = request.get_json(force=True)
    s = Session(
        origin_stop_id=data["origin_stop_id"],
        dest_stop_id=data["dest_stop_id"],
        route_id=data.get("route_id"),
    )
    sessions[s.id] = s
    emit_state_change(s, s.state)  
    return jsonify({"session_id": s.id, "state": s.state})

# --- API: arrivals at origin stop ---
def fmt_arrivals_real(origin_stop_id, route_id=None, limit=3):
    params = {
        "filter[stop]": origin_stop_id,
        "sort": "departure_time",
        "page[limit]": limit,
        "include": "trip,route"
    }
    if route_id:
        params["filter[route]"] = route_id

    data = mbta_get("/predictions", params)
    included = {item["id"]: item for item in data.get("included", [])}

    items = []
    now = time()
    for p in data.get("data", []):
        attrs = p["attributes"]
        dep_iso = attrs.get("departure_time") or attrs.get("arrival_time")
        if not dep_iso:
            continue
        dep_epoch = __import__("datetime").datetime.fromisoformat(dep_iso.replace("Z","+00:00")).timestamp()
        eta_sec = max(0, int(dep_epoch - now))
        trip_id = p["relationships"]["trip"]["data"]["id"] if p["relationships"]["trip"]["data"] else None

        headsign = None
        if trip_id and trip_id in included and included[trip_id]["type"] == "trip":
            headsign = included[trip_id]["attributes"].get("headsign")

        items.append({
            "trip_id": trip_id or f"UNKNOWN_{int(dep_epoch)}",
            "headsign": headsign or "Towards destination",
            "dep_epoch": int(dep_epoch),
            "eta_sec": eta_sec
        })

    return items[:limit]

@app.get("/arrivals")
def arrivals():
    origin_stop_id = request.args.get("origin_stop_id")
    if not origin_stop_id:
        return jsonify({"arrivals":[]})
    out = fmt_arrivals_real(origin_stop_id)
    return jsonify({"arrivals": out})

# --- API: confirm boarding ---
@app.post("/board")
def board_trip():
    data = request.get_json(force=True)
    s = sessions[data["session_id"]]
    s.trip_id = data["trip_id"]
    s.state = "ONBOARD"
    s.boarded_ts = time()
    emit_state_change(s, s.state)
    return jsonify({"ok": True, "state": s.state, "trip_id": s.trip_id})

# --- API: progress ---
def eta_for_trip_to_stop(trip_id, dest_stop_id):
    params = {
        "filter[trip]": trip_id,
        "filter[stop]": dest_stop_id,
        "sort": "arrival_time",
        "page[limit]": 1
    }
    data = mbta_get("/predictions", params)
    now = time()
    for p in data.get("data", []):
        attrs = p["attributes"]
        arr_iso = attrs.get("arrival_time") or attrs.get("departure_time")
        if not arr_iso:
            continue
        arr_epoch = __import__("datetime").datetime.fromisoformat(arr_iso.replace("Z","+00:00")).timestamp()
        return max(0, int(arr_epoch - now))
    return None

@app.get("/progress")
def progress():
    session_id = request.args.get("session_id")
    s = sessions[session_id]

    now = time()
    if s.state == "AWAITING_BOARD":
        eta_origin = clamp_nonneg(s.stub_origin_eta - (now - s.created_ts))
        eta_dest   = clamp_nonneg(s.stub_dest_eta   - (now - s.created_ts))
    else:
        eta_origin = None
        eta_dest = eta_for_trip_to_stop(s.trip_id, s.dest_stop_id)
        if eta_dest is None:
            elapsed_onboard = now - (s.boarded_ts or now)
            eta_dest = clamp_nonneg(1500 - elapsed_onboard)

        if s.state == "ONBOARD" and eta_dest is not None and eta_dest <= 240:
            s.state = "APPROACHING_DEST"
            emit_state_change(s, s.state)
        if eta_dest is not None and eta_dest == 0 and s.state in ("ONBOARD", "APPROACHING_DEST"):
            s.state = "ARRIVED"
            emit_state_change(s, s.state)

    return jsonify({
        "state": s.state,
        "eta_to_origin_sec": eta_origin,
        "eta_to_destination_sec": eta_dest,
        "trip_id": s.trip_id
    })

# --- Real stops: search by name ---
@app.get("/stops/search")
def stops_search2():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"stops": []})
    data = mbta_get("/stops", {
        "filter[search]": q,
        "page[limit]": 12,
        "sort": "name"
    })
    out = []
    for s in data.get("data", []):
        attrs = s["attributes"]
        out.append({
            "stop_id": s["id"],
            "name": attrs.get("name"),
            "lat": attrs.get("latitude"),
            "lon": attrs.get("longitude"),
        })
    return jsonify({"stops": out})

# --- Real stops: near a lat/lon ---
@app.get("/stops/near")
def stops_near():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    radius_m = request.args.get("radius_m", default=1200, type=int)
    if lat is None or lon is None:
        return jsonify({"stops": []})

    data = mbta_get("/stops", {
        "filter[latitude]": lat,
        "filter[longitude]": lon,
        "filter[radius]": radius_m,
        "page[limit]": 12,
        "sort": "distance"
    })
    out = []
    for s in data.get("data", []):
        attrs = s["attributes"]
        out.append({
            "stop_id": s["id"],
            "name": attrs.get("name"),
            "lat": attrs.get("latitude"),
            "lon": attrs.get("longitude"),
            "distance_m": attrs.get("distance"),
        })
    return jsonify({"stops": out})

if __name__ == "__main__":
    app.run(port=5002, debug=True)
