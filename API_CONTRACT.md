# API contract (frozen: tell the other person before changing)

Base: `/api` (Vite proxies to Flask on :5001). Coordinates are always `[lat, lng]` except GeoJSON (`[lng, lat]`).

| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{status, graph, nodes, edges}` |
| `GET /api/config` | `{center: [lat, lng]}` |
| `GET /api/scenarios` | `[{id, label}]` |
| `GET /api/water-points` | `[{id, type, lat, lng}]` |
| `GET /api/segments` | GeoJSON FeatureCollection, `properties.shade` 0-1 |
| `POST /api/route` | see below |

## POST /api/route

Request
```json
{"start": {"lat": 20.35, "lng": 85.81}, "end": {"lat": 20.36, "lng": 85.82},
 "hour": 14, "lambda": 2, "scenario": "none"}
```

Response
```json
{
  "routes": [
    {"id": "fastest", "label": "Fastest", "distance_m": 780, "travel_time_min": 9.2,
     "heat_score": 74, "shade_pct": 28,
     "segments": [{"coords": [[lat, lng], [lat, lng]], "heat_per_m": 1.2}]},
    {"id": "coolest", "...": "same shape"}
  ],
  "explanation": "Coolest route takes +3.0 min vs fastest and has 41% lower heat score ...",
  "changed_because": null,
  "previous": null
}
```
`changed_because` / `previous` are set only when a scenario changed the coolest route
(`previous` = the coolest route under normal conditions, same shape as a route).

Errors: HTTP 400/404 with `{"error": "message"}`.
