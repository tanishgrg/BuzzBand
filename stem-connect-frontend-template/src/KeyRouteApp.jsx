import { useEffect, useRef, useState } from 'react'
import './App.css'
import { fetchPredictions, firstUpcomingArrivalSeconds, prettySeconds, buzz } from './api' // no ping, no KeyRouteApp import

const NEARBY_THRESHOLD_SEC   = 720
const APPROACH_THRESHOLD_SEC = 480
const STOP_THRESHOLD_SEC     = 240
const DEFAULT_ORIGIN = 'place-babck'
const DEFAULT_DEST   = '70147'
const POLL_INTERVAL_MS = 30_000

const NEARBY_DEMO_STOPS = [
  { id: 'place-babck', name: 'Babcock St',  lat: 42.35178, lon: -71.12168 },
  { id: '70147',       name: 'BU East',      lat: 42.35029, lon: -71.10696 },
  { id: 'place-bland', name: 'Blandford St', lat: 42.34959, lon: -71.09953 },
]

function toRad(d) { return (d * Math.PI) / 180 }
function haversineMeters(lat1, lon1, lat2, lon2) {
  const R = 6371e3
  const φ1 = toRad(lat1), φ2 = toRad(lat2)
  const Δφ = toRad(lat2 - lat1), Δλ = toRad(lon2 - lon1)
  const a = Math.sin(Δφ/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin(Δλ/2)**2
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}
function metersToMiles(m){ return m/1609.344 }
function buildNearbyList(lat, lon) {
  return NEARBY_DEMO_STOPS
    .map(s => ({ ...s, dMiles: metersToMiles(haversineMeters(lat, lon, s.lat, s.lon)) }))
    .sort((a,b)=> a.dMiles - b.dMiles)
    .slice(0, 8)
}

export default function App() {
  const [guidanceOn, setGuidanceOn] = useState(false)

  const [originStop, setOriginStop] = useState(DEFAULT_ORIGIN)
  const [destStop, setDestStop]     = useState(DEFAULT_DEST)

  const [originEta, setOriginEta]   = useState(null)
  const [destEta, setDestEta]       = useState(null)
  const [status, setStatus]         = useState('IDLE')
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const [toast, setToast] = useState(null)
  const [flash, setFlash] = useState(false)

  const [nearbyOrigin, setNearbyOrigin] = useState([])
  const [nearbyDest, setNearbyDest]     = useState([])
  const [locBusy, setLocBusy] = useState(false)

  const timerRef = useRef(null)
  const lastAnnouncedRef = useRef(null)

  async function refresh() {
    setLoading(true); setError(null)
    try {
      const [pO, pD] = await Promise.all([
        fetchPredictions(originStop),
        fetchPredictions(destStop),
      ])
      const oSecs = firstUpcomingArrivalSeconds(pO)
      const dSecs = firstUpcomingArrivalSeconds(pD)
      setOriginEta(oSecs)
      setDestEta(dSecs)
      setLastUpdated(new Date())

      let next = 'IDLE'
      if (oSecs != null && oSecs <= NEARBY_THRESHOLD_SEC) next = 'NEARBY'
      if (dSecs != null && dSecs <= APPROACH_THRESHOLD_SEC) next = 'APPROACH'
      if (dSecs != null && dSecs <= STOP_THRESHOLD_SEC) next = 'STOP'
      setStatus(next)
    } catch (e) {
      setError(e.message || 'Failed to fetch')
    } finally {
      setLoading(false)
    }
  }

  function startPolling() { stopPolling(); timerRef.current = setInterval(refresh, POLL_INTERVAL_MS) }
  function stopPolling()  { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null } }

  function vibrate(pattern) { try { navigator.vibrate?.(pattern) } catch {} }
  function showToast(msg, ms=1500) {
    setToast(msg)
    setFlash(true)
    setTimeout(() => setFlash(false), Math.min(ms, 800))
    setTimeout(() => setToast(null), ms)
  }

  async function notify(statusNow) {
    if (lastAnnouncedRef.current === statusNow) return
    lastAnnouncedRef.current = statusNow
    try { await buzz(statusNow) } catch {}
    const phrase =
      statusNow === 'NEARBY'   ? 'Vehicle near your origin stop'
    : statusNow === 'APPROACH' ? 'Approaching destination'
    : statusNow === 'STOP'     ? 'Arrived: stop now'
    : 'Idle'
    showToast(phrase, 1800)
    if (statusNow === 'NEARBY')   vibrate([200, 80, 200])
    if (statusNow === 'APPROACH') vibrate([300, 80, 300])
    if (statusNow === 'STOP')     vibrate([500, 120, 500])
  }

  useEffect(() => { if (guidanceOn) notify(status) }, [status, guidanceOn])
  useEffect(() => { refresh(); startPolling(); return stopPolling }, [originStop, destStop])

  function toggleGuidance() {
    const next = !guidanceOn
    setGuidanceOn(next)
    if (!next) lastAnnouncedRef.current = null
  }

  function findNearbyFor(which) {
    if (!navigator.geolocation) { setToast('Geolocation not available'); return }
    setLocBusy(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords
        const list = buildNearbyList(latitude, longitude)
        if (which === 'origin') setNearbyOrigin(list)
        else setNearbyDest(list)
        setToast('Nearby stops updated')
        setLocBusy(false)
      },
      () => { setToast('Location denied'); setLocBusy(false) },
      { enableHighAccuracy: true, timeout: 7000 }
    )
  }

  return (
    <div className="app">
      <header className="header">
        <h1>KeyRoute</h1>
        {/* Mode buttons, status pill, and idle badge removed */}
      </header>

      {/* Optional visual flash when notifying */}
      {flash && <div className={`flash flash-${status.toLowerCase()}`} aria-hidden="true" />}

      <section className="grid">
        <div className="card">
          <h2>Stops</h2>

          <div className="row">
            <label>Origin Stop</label>
            <input value={originStop} onChange={e=>setOriginStop(e.target.value)} aria-label="Origin Stop ID" />
          </div>
          <div className="row">
            <button onClick={()=>findNearbyFor('origin')} disabled={locBusy}>
              {locBusy ? 'Locating…' : 'Find nearby (Origin)'}
            </button>
            {nearbyOrigin.length > 0 && (
              <select
                onChange={(e)=> setOriginStop(e.target.value)}
                value={originStop}
                aria-label="Nearby origin stops"
              >
                {nearbyOrigin.map(s=>(
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.dMiles.toFixed(2)} mi
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="row" style={{marginTop:12}}>
            <label>Destination Stop</label>
            <input value={destStop} onChange={e=>setDestStop(e.target.value)} aria-label="Destination Stop ID" />
          </div>
          <div className="row">
            <button onClick={()=>findNearbyFor('dest')} disabled={locBusy}>
              {locBusy ? 'Locating…' : 'Find nearby (Destination)'}
            </button>
            {nearbyDest.length > 0 && (
              <select
                onChange={(e)=> setDestStop(e.target.value)}
                value={destStop}
                aria-label="Nearby destination stops"
              >
                {nearbyDest.map(s=>(
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.dMiles.toFixed(2)} mi
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div className="card">
          <h2>ETAs</h2>
          <p><b>Origin ETA:</b> {prettySeconds(originEta)}</p>
          <p><b>Destination ETA:</b> {prettySeconds(destEta)}</p>
          <p className="muted">{lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : '—'}</p>
        </div>
      </section>

      <section className="actions">
        <button onClick={refresh} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh now'}</button>
        <button onClick={()=>{startPolling(); setToast('Auto-refresh on')}}>Start auto-refresh</button>
        <button onClick={()=>{stopPolling(); setToast('Auto-refresh off')}}>Stop auto-refresh</button>

        <button className={guidanceOn ? 'primary' : ''} onClick={toggleGuidance}>
          {guidanceOn ? 'Stop Guidance' : 'Start Guidance'}
        </button>

        {/* Removed: Ping backend + Backend status + Developer buzz tests */}
      </section>

      {toast && <div role="status" aria-live="assertive" className="toast">{toast}</div>}
      <div aria-live="assertive" className="sr-only">{guidanceOn ? `Status: ${status}` : 'Guidance off'}</div>
      {error && <p className="error">Error: {error}</p>}
      {/* Removed: bottom KeyRoute demo flow panel */}
    </div>
  )
}

console.log("API base:", import.meta.env.VITE_API_BASE);
