import { MapContainer, TileLayer, LayersControl, Polyline, CircleMarker, GeoJSON, Tooltip, useMapEvents } from "react-leaflet";

// heat_per_m roughly 0.2 (cool) .. 1.7 (hot) -> green..red
const heatColor = (h) => {
  const t = Math.min(1, Math.max(0, (h - 0.2) / 1.5));
  return `hsl(${120 - 120 * t}, 80%, 42%)`;
};
// shade 0 (sun) .. 1 (full shade) -> light grey .. dark green
const shadeColor = (s) => `hsl(140, ${20 + 50 * s}%, ${80 - 45 * s}%)`;

function ClickPicker({ onPick }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

export default function MapView({ center, start, end, result, segments, waterPoints, places, showShade, showWater, showPlaces, onPick }) {
  const fastest = result?.routes.find((r) => r.id === "fastest");
  const coolest = result?.routes.find((r) => r.id === "coolest");

  return (
    <MapContainer center={center} zoom={16} style={{ height: "100%", width: "100%" }}>
      <LayersControl position="topright">
        <LayersControl.BaseLayer checked name="Satellite">
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
            maxNativeZoom={18}
            maxZoom={20}
          />
        </LayersControl.BaseLayer>
        <LayersControl.BaseLayer name="Road map">
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution="&copy; OpenStreetMap contributors"
            maxZoom={20}
          />
        </LayersControl.BaseLayer>
      </LayersControl>
      <ClickPicker onPick={onPick} />

      {showShade && segments && (
        <GeoJSON
          key={segments.features.length}
          data={segments}
          style={(f) => ({ color: shadeColor(f.properties.shade), weight: 5, opacity: 0.55 })}
        />
      )}

      {showWater &&
        waterPoints.map((w) => (
          <CircleMarker key={w.id} center={[w.lat, w.lng]} radius={8}
            pathOptions={{ color: "#0b5cad", fillColor: "#4aa3ff", fillOpacity: 0.9 }}>
            <Tooltip>{w.type}{w.approximate ? " (approximate location)" : ""}</Tooltip>
          </CircleMarker>
        ))}

      {/* previous coolest route (shown dashed after a scenario reroute) */}
      {result?.previous &&
        result.previous.segments.map((s, i) => (
          <Polyline key={`prev-${i}`} positions={s.coords}
            pathOptions={{ color: "#555", weight: 5, dashArray: "4 10" }} />
        ))}

      {/* white outlines under the routes so they stay readable on satellite imagery */}
      {fastest && (
        <Polyline positions={fastest.segments.flatMap((s) => s.coords)}
          pathOptions={{ color: "#ffffff", weight: 8, opacity: 0.85 }} />
      )}
      {coolest &&
        coolest.segments.map((s, i) => (
          <Polyline key={`case-${i}`} positions={s.coords} pathOptions={{ color: "#ffffff", weight: 12, opacity: 0.85 }} />
        ))}

      {/* fastest: one dashed line */}
      {fastest && (
        <Polyline positions={fastest.segments.flatMap((s) => s.coords)}
          pathOptions={{ color: "#d62728", weight: 4, dashArray: "10 8" }} />
      )}

      {/* coolest: each segment coloured by heat */}
      {coolest &&
        coolest.segments.map((s, i) => (
          <Polyline key={`cool-${i}`} positions={s.coords}
            pathOptions={{ color: heatColor(s.heat_per_m), weight: 8 }} />
        ))}

      {start && <CircleMarker center={[start.lat, start.lng]} radius={9} pathOptions={{ color: "green", fillOpacity: 1 }} />}
      {end && <CircleMarker center={[end.lat, end.lng]} radius={9} pathOptions={{ color: "black", fillOpacity: 1 }} />}

      {/* named campus places: always-visible labels, click one to use it as start / end */}
      {showPlaces &&
        places.map((p) => (
          <CircleMarker key={p.id} center={[p.lat, p.lng]} radius={6} bubblingMouseEvents={false}
            pathOptions={{ color: "#4a148c", fillColor: "#ab47bc", fillOpacity: 1, weight: 2 }}
            eventHandlers={{ click: () => onPick({ lat: p.lat, lng: p.lng, name: p.name }) }}>
            <Tooltip permanent direction="top" offset={[0, -6]} className="place-label">{p.name}</Tooltip>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}