import { useEffect, useRef, useState } from "react";
import {
  createSession,
  getArrivals,
  boardTrip,
  getProgress,
  stopsNear,
  stopsSearch,
} from "./keyrouteApi";

const fmt = (s) =>
  s == null
    ? "—"
    : s < 60
    ? `in ${Math.max(5, Math.round(s / 5) * 5)}s`
    : `in ${Math.round(s / 60)} min`;

const asClock = (epoch) =>
  new Date(epoch * 1000).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

export default function KeyRouteApp() {
  const [origin, setOrigin] = useState(null);
  const [dest, setDest] = useState(null);
  const [sessionId, setSessionId] = useState();
  const [state, setState] = useState("IDLE");
  const [arrivals, setArrivals] = useState([]);
  const [etaO, setEtaO] = useState(null);
  const [etaD, setEtaD] = useState(null);
  const [nearOrigin, setNearOrigin] = useState(false);

  const poll = useRef();

  // Ensure mobile viewport meta exists
  useEffect(() => {
    if (!document.querySelector('meta[name="viewport"]')) {
      const m = document.createElement("meta");
      m.name = "viewport";
      m.content = "width=device-width, initial-scale=1";
      document.head.appendChild(m);
    }
  }, []);

  // Track geolocation to decide when user is near origin
  useEffect(() => {
    if (!navigator.geolocation || !origin) return;

    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        // TODO: compare (latitude, longitude) with origin.lat/lon
        setNearOrigin(true); // for now always true
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 5000 }
    );

    return () => navigator.geolocation.clearWatch(id);
  }, [origin]);

  const pickNearby = async () => {
    const r = await stopsNear(42.349, -71.097, 2000);
    setOrigin(r.stops?.[0] || null);
  };

  const searchDest = async (q) => {
    const r = await stopsSearch(q);
    setDest(r.stops?.[0] || null);
  };

  const start = async () => {
    if (!origin || !dest) return;
    const s = await createSession(origin.stop_id, dest.stop_id, "B");
    setSessionId(s.session_id);
    setState(s.state); // AWAITING_BOARD
    const a = await getArrivals(origin.stop_id, "B");
    setArrivals(a.arrivals || []);
  };

  const confirm = async (trip_id) => {
    if (!sessionId) return;
    const r = await boardTrip(sessionId, trip_id);
    setState(r.state); // ONBOARD

    if (poll.current) clearInterval(poll.current);
    poll.current = setInterval(async () => {
      const p = await getProgress(sessionId);
      setState(p.state);
      setEtaO(p.eta_to_origin_sec);
      setEtaD(p.eta_to_destination_sec);
      if (p.state === "ARRIVED") {
        clearInterval(poll.current);
      }
    }, 3000);
  };

  return (
    <div className="max-w-md mx-auto p-4 space-y-4">
      <h2 className="text-xl font-bold">KeyRoute (demo flow)</h2>

      {/* Origin */}
      <div className="space-y-1 p-3 border rounded-2xl">
        <div className="text-sm opacity-70">Origin</div>
        <button className="px-3 py-2 border rounded-xl" onClick={pickNearby}>
          Use Nearby
        </button>
        <div className="text-sm">{origin ? origin.name : "Not selected"}</div>
      </div>

      {/* Destination */}
      <div className="space-y-1 p-3 border rounded-2xl">
        <div className="text-sm opacity-70">Destination</div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const q = e.target.q.value;
            searchDest(q);
          }}
        >
          <input
            name="q"
            className="px-3 py-2 border rounded-xl w-full"
            placeholder="Search stop (e.g., Park Street)"
          />
        </form>
        <div className="text-sm">{dest ? dest.name : "Not selected"}</div>
      </div>

      {/* Start */}
      <button
        className="w-full py-3 rounded-2xl bg-black text-white disabled:opacity-40"
        disabled={!origin || !dest}
        onClick={start}
      >
        Start
      </button>

      {/* Arrivals + Confirm boarding */}
      {state === "AWAITING_BOARD" && (
        <div className="space-y-2 p-3 border rounded-2xl">
          <div className="font-semibold">Upcoming trains</div>

          {nearOrigin ? (
            arrivals.map((a) => (
              <div
                key={a.trip_id}
                className="flex items-center justify-between p-2 border rounded-xl"
              >
                <div>
                  <div className="font-medium">{a.headsign}</div>
                  <div className="text-sm opacity-70">
                    To origin: {fmt(a.eta_sec)}
                  </div>
                  <div className="text-xs opacity-60">
                    Departs {asClock(a.dep_epoch)}
                  </div>
                </div>
                <button
                  className="px-3 py-2 rounded-xl bg-black text-white"
                  onClick={() => confirm(a.trip_id)}
                >
                  Confirm Boarding
                </button>
              </div>
            ))
          ) : (
            <div className="text-sm opacity-70">
              Get closer to your origin stop to confirm boarding.
            </div>
          )}
        </div>
      )}

      {/* Live ETAs panel */}
      {sessionId && (
        <div className="space-y-2 p-3 border rounded-2xl sticky bottom-4 bg-white/90 backdrop-blur">
          <div className="text-sm opacity-70">Status</div>
          <div className="text-lg font-semibold">
            {state.replaceAll("_", " ")}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 border rounded-xl">
              <div className="text-xs opacity-70">To Origin</div>
              <div>{fmt(etaO)}</div>
            </div>
            <div className="p-2 border rounded-xl">
              <div className="text-xs opacity-70">To Destination</div>
              <div>{fmt(etaD)}</div>
            </div>
          </div>
        </div>
      )}

      <div className="h-16" />
    </div>
  );
}
