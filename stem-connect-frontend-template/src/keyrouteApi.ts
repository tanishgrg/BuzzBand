const API = (import.meta as any).env.VITE_API_BASE;

export const createSession = (origin_stop_id: string, dest_stop_id: string, route_id?: string) =>
  fetch(`${API}/session`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin_stop_id, dest_stop_id, route_id }) }).then(r => r.json());

export const getArrivals = (origin_stop_id: string, route_id?: string) =>
  fetch(`${API}/arrivals?origin_stop_id=${origin_stop_id}${route_id ? `&route_id=${route_id}` : ""}`).then(r => r.json());

export const boardTrip = (session_id: string, trip_id: string) =>
  fetch(`${API}/board`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id, trip_id }) }).then(r => r.json());

export const getProgress = (session_id: string) =>
  fetch(`${API}/progress?session_id=${session_id}`).then(r => r.json());

export const stopsNear = (lat: number, lon: number, radius_m = 2000) =>
  fetch(`${API}/stops/near?lat=${lat}&lon=${lon}&radius_m=${radius_m}`).then(r => r.json());

export const stopsSearch = (q: string) =>
  fetch(`${API}/stops/search?q=${encodeURIComponent(q)}`).then(r => r.json());
