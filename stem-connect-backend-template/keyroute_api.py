# keyroute_api.py
from flask import Flask, request, jsonify
from time import time
import uuid



app = Flask(__name__)

from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allow your React dev server (http://localhost:5173) to call the API

# --- In-memory store (fine for hackathon) ---
class Session:
    def __init__(self, origin_stop_id, dest_stop_id, route_id=None):
        self.id = str(uuid.uuid4())
        self.origin_stop_id = origin_stop_id
        self.dest_stop_id = dest_stop_id
        self.route_id = route_id
        self.state = "AWAITING_BOARD"   # AWAITING_BOARD | ONBOARD | APPROACHING_DEST | ARRIVED
        self.trip_id = None
        self.created_ts = time()
        # simple stub timers (seconds)
        self.stub_origin_eta = 240      # 4 min until train reaches origin
        self.stub_dest_eta = 1800       # 30 min total to destination
        self.boarded_ts = None

sessions = {}  # session_id -> Session

# --- Helpers (stubs for now) ---
def fmt_arrivals(origin_stop_id, route_id, now=None):
    # Return 3 fake arrivals spaced 2–4 min apart with unique trip_ids
    base = int(time())
    items = []
    for i, gap in enumerate([180, 360, 540], start=1):  # 3, 6, 9 min
        items.append({
            "trip_id": f"TRIP_{base}_{i}",
            "headsign": "Inbound",
            "dep_epoch": base + gap,
            "eta_sec": gap
        })
    return items

def clamp_nonneg(x): return max(0, int(x))

# --- API: create session ---
@app.post("/session")
def create_session():
    data = request.get_json(force=True)
    s = Session(
        origin_stop_id=data["origin_stop_id"],
        dest_stop_id=data["dest_stop_id"],
        route_id=data.get("route_id")
    )
    sessions[s.id] = s
    return jsonify({"session_id": s.id, "state": s.state})

# --- API: list arrivals at origin ---
@app.get("/arrivals")
def list_arrivals():
    origin_stop_id = request.args.get("origin_stop_id")
    route_id = request.args.get("route_id")
    return jsonify({"arrivals": fmt_arrivals(origin_stop_id, route_id)})

# --- API: confirm boarding (lock to a trip) ---
@app.post("/board")
def board_trip():
    data = request.get_json(force=True)
    s = sessions[data["session_id"]]
    s.trip_id = data["trip_id"]
    s.state = "ONBOARD"
    s.boarded_ts = time()
    # Optional: turn off green LED when boarding confirmed
    # send_hw({"led":"off","buzz":"none"})
    return jsonify({"ok": True, "state": s.state, "trip_id": s.trip_id})

# --- API: progress (two ETAs + state machine nubs) ---
@app.get("/progress")
def progress():
    session_id = request.args.get("session_id")
    s = sessions[session_id]

    now = time()
    if s.state == "AWAITING_BOARD":
        # origin ETA counts down from stub_origin_eta
        eta_origin = clamp_nonneg(s.stub_origin_eta - (now - s.created_ts))
        # dest ETA is origin + travel; while not boarded, still show total
        eta_dest = clamp_nonneg(s.stub_dest_eta - (now - s.created_ts))
        # Green “origin” tiny buzz cadence handled elsewhere; no transitions here
    else:
        # ONBOARD or later: origin ETA disabled; destination counts down from board time
        eta_origin = None
        elapsed_onboard = now - (s.boarded_ts or now)
        # After boarding, assume ~25 min left (stub). Adjust as needed.
        eta_dest = clamp_nonneg(1500 - elapsed_onboard)

        # Simple demo transitions:
        if s.state == "ONBOARD" and eta_dest <= 240:
            s.state = "APPROACHING_DEST"
            # send_hw({"led":"yellow","buzz":"short"})
        if eta_dest == 0 and s.state in ("ONBOARD", "APPROACHING_DEST"):
            s.state = "ARRIVED"
            # send_hw({"led":"red","buzz":"long"})

    return jsonify({
        "state": s.state,
        "eta_to_origin_sec": eta_origin,        # show as “in X min/s”, or "—" if None
        "eta_to_destination_sec": eta_dest,     # same formatting on frontend
        "trip_id": s.trip_id
    })

# --- API: stops (stubbed) ---
@app.get("/stops/near")
def stops_near():
    # Return a few fake nearby stops; replace with real data later
    return jsonify({"stops":[
        {"stop_id":"STOP_A","name":"Commonwealth Ave @ St. Paul St","routes":["B"]},
        {"stop_id":"STOP_B","name":"BU Central","routes":["B"]},
        {"stop_id":"STOP_C","name":"Kenmore","routes":["B","C","D"]}
    ]})

@app.get("/stops/search")
def stops_search():
    q = (request.args.get("q") or "").lower()
    catalog = [
        {"stop_id":"STOP_C","name":"Kenmore","routes":["B","C","D"]},
        {"stop_id":"STOP_D","name":"Park Street","routes":["B","C","D","E"]},
        {"stop_id":"STOP_E","name":"Government Center","routes":["B","C","D","E"]}
    ]
    results = [s for s in catalog if q in s["name"].lower()]
    return jsonify({"stops": results[:10]})

# --- (Optional) hardware hook stub ---
def send_hw(msg: dict):
    # TODO: swap in your serial write; stub logs for now
    print("HW>", msg)

if __name__ == "__main__":
    app.run(port=5002, debug=True)
