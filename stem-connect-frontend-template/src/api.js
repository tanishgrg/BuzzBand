const API = 'https://api-v3.mbta.com'
const API_KEY = import.meta.env.VITE_MBTA_API_KEY

export async function fetchPredictions(stopId, limit = 5) {
  const params = new URLSearchParams({
    'filter[stop]': stopId,
    sort: 'arrival_time',
    'page[limit]': String(limit),
  })
  const headers = {}
  if (API_KEY) headers['x-api-key'] = API_KEY

  const res = await fetch(`${API}/predictions?${params.toString()}`, { headers })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function firstUpcomingArrivalSeconds(predJson) {
  const now = new Date()
  for (const d of predJson?.data ?? []) {
    const t = d?.attributes?.arrival_time
    if (!t) continue
    const dt = new Date(t)
    const secs = (dt - now) / 1000
    if (secs > 0) return Math.round(secs)
  }
  return null
}

export function prettySeconds(secs) {
  if (secs == null) return 'N/A'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return m ? `${m}m ${s}s` : `${s}s`
}
// ---- Arduino buzz via local backend ----
export async function buzz(command) {
  const res = await fetch('http://127.0.0.1:5001/buzz', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command })
  })
  if (!res.ok) throw new Error(`Buzz failed (${res.status})`)
  return res.json()
}

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:5001';

export async function ping() {
  const r = await fetch(`${BACKEND}/health`);
  if (!r.ok) throw new Error('backend unreachable');
  return r.json();
}
