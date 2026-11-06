import { useEffect, useRef, useState } from "react";
import MapView from "./MapView.jsx";
import { getConfig, getPlaces, getRoutes, getScenarios, getSegments, getWaterPoints } from "./api.js";
import "./map.css";

const COLORS = { fastest: "#d62728", coolest: "#1f9d55" };
// The slider shows 0-100%; 100% means lambda = LAMBDA_MAX. Retune this once the real heat score is in.
const LAMBDA_MAX = 12;

export default function App() {
  const [center, setCenter] = useState(null);
  const [segments, setSegments] = useState(null);
  const [waterPoints, setWaterPoints] = useState([]);
  const [places, setPlaces] = useState([]);
  const [showPlaces, setShowPlaces] = useState(true);
  const [scenarios, setScenarios] = useState([{ id: "none", label: "Normal day" }]);

  const [start, setStart] = useState(null);
  const [end, setEnd] = useState(null);
  const [hour, setHour] = useState(14);
  const [coolness, setCoolness] = useState(50); // 0 = fastest route, 100 = coolest route
  const lambda = (coolness / 100) * LAMBDA_MAX;   // what the backend receives
  const [scenario, setScenario] = useState("none");
  const [showShade, setShowShade] = useState(true);
  const [showWater, setShowWater] = useState(true);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backendDown, setBackendDown] = useState(false);

  // initial load of map config + layers
  useEffect(() => {
    Promise.all([getConfig(), getSegments(), getWaterPoints(), getScenarios(), getPlaces()])
      .then(([cfg, seg, wp, sc, pl]) => {
        setCenter(cfg.center); setSegments(seg); setWaterPoints(wp); setScenarios(sc); setPlaces(pl);
      })
      .catch(() => setBackendDown(true));
  }, []);

  // re-request routes whenever an input changes (debounced so sliders don't spam the API)
  const timer = useRef();
  useEffect(() => {
    if (!start || !end) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setLoading(true); setError(null);
      try {
        setResult(await getRoutes({ start, end, hour, lambda, scenario }));
      } catch (e) {
        setError(e.message); setResult(null);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer.current);
  }, [start, end, hour, lambda, scenario]);

  function handlePick(p) {
    if (!start || (start && end)) { setStart(p); setEnd(null); setResult(null); setError(null); }
    else setEnd(p);
  }

  // dropdown helpers for the named places
  const placeId = (pt) => places.find((p) => pt && p.lat === pt.lat && p.lng === pt.lng)?.id ?? "";
  const pickPlace = (id, which) => {
    const p = places.find((x) => String(x.id) === id);
    if (!p) return;
    const pt = { lat: p.lat, lng: p.lng, name: p.name };
    if (which === "from") { setStart(pt); setEnd(null); setResult(null); setError(null); }
    else setEnd(pt);
  };

  if (backendDown)
    return <p style={{ padding: 24, fontFamily: "sans-serif" }}>Cannot reach the backend. Is Flask running on port 5001?</p>;
  if (!center) return <p style={{ padding: 24, fontFamily: "sans-serif" }}>Loading map...</p>;

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <aside style={{ width: 340, padding: 16, overflowY: "auto", borderRight: "1px solid #ddd", boxSizing: "border-box" }}>
        <h2 style={{ margin: "0 0 4px", fontFamily: "Zalando Sans Expanded, sans-serif", color: "#000000" }}>
          <a href="/" style={{ color: "inherit", textDecoration: "none" }}>
            CoolStride
          </a>
        </h2>
        <p style={{ margin: "0 0 12px", color: "#555", fontFamily: "Lexend, sans-serif" }}>
          {!start ? "Click the map to set the start." : !end ? "Click again to set the destination." : "Click the map to start over."}
        </p>

        <label style={{ display: "block", marginBottom: 12, fontFamily: "Lexend, sans-serif", color: "#000000"  }}>
          Time of day: <b>{hour}:00</b>
          <input type="range" min="6" max="18" value={hour} style={{ width: "100%" }}
            onChange={(e) => setHour(+e.target.value)} />
        </label>
        <label style={{ display: "block", marginBottom: 12, fontFamily: "Lexend, sans-serif", color: "#000000"  }}>
          Speed vs coolness: <b>{coolness}%</b>
          <input type="range" min="0" max="100" step="5" value={coolness} style={{ width: "100%" }}
            onChange={(e) => setCoolness(+e.target.value)} />
          <small style={{ color: "#777", display: "flex", justifyContent: "space-between", fontFamily: "Lexend, sans-serif"  }}>
            <span>Fastest</span><span>Coolest</span>
          </small>
        </label>
        <label style={{ display: "block", marginBottom: 12, fontFamily: "Lexend, sans-serif", color: "#000000"  }}>
          Scenario:{" "}
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            {scenarios.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
        <label style={{ marginRight: 12, fontFamily: "Lexend, sans-serif", color: "#000000"  }}>
          <input type="checkbox" checked={showShade} onChange={(e) => setShowShade(e.target.checked)} /> Shade
        </label>
        <label style={{ marginRight: 12, fontFamily: "Lexend, sans-serif", color: "#000000"  }}>
          <input type="checkbox" checked={showWater} onChange={(e) => setShowWater(e.target.checked)} /> Water points
        </label>
        {places.length > 0 && (
          <>
            <label style={{ fontFamily: "Lexend, sans-serif", color: "#000000" }}>
              <input type="checkbox" checked={showPlaces} onChange={(e) => setShowPlaces(e.target.checked)} /> Places
            </label>
            <div style={{ margin: "12px 0", fontFamily: "Lexend, sans-serif"  }}>
              <label style={{ display: "block", marginBottom: 6, fontFamily: "Lexend, sans-serif", color: "#000000"  }}>
                From:{" "}
                <select value={placeId(start)} onChange={(e) => pickPlace(e.target.value, "from")}>
                  <option value="" disabled>pick a place or click the map</option>
                  {places.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <label style={{ color: "#000000" }}>
                To:{" "}
                <select value={placeId(end)} onChange={(e) => pickPlace(e.target.value, "to")}>
                  <option value="" disabled>pick a place or click the map</option>
                  {places.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
            </div>
          </>
        )}

        {loading && <p>Finding routes...</p>}
        {error && <p style={{ color: "#b00020" }}>{error}</p>}

        {result && (
          <>
            {result.changed_because && (
              <p style={{ background: "#fff4d6", padding: 10, borderRadius: 8, color: "#000000" }}>
                <b>Route changed.</b> {result.changed_because} (grey dashed = previous coolest route)
              </p>
            )}
            <p>{result.explanation}</p>
            {result.routes.map((r) => (
              <div key={r.id} style={{ borderLeft: `6px solid ${COLORS[r.id]}`, padding: "6px 10px", margin: "10px 0", background: "#fafafa", color: "#000000" }}>
                <b>{r.label}</b><br />
                {r.travel_time_min} min · {r.distance_m} m<br />
                Heat score {r.heat_score} · Shade {r.shade_pct}%
              </div>
            ))}
          </>
        )}

        <hr />
        <small style={{ color: "#000", fontFamily: "Lexend, sans-serif"  }}>
          Coolest route is coloured green (cool) to red (hot) per segment. Fastest is the red dashed line.
        </small>
      </aside>

      <main style={{ flex: 1 }}>
        <MapView center={center} start={start} end={end} result={result} segments={segments}
          waterPoints={waterPoints} places={places} showShade={showShade} showWater={showWater}
          showPlaces={showPlaces} onPick={handlePick} />
      </main>
    </div>
  );
}
