# CoolStride

CoolStride is a heat-aware walking route planner. It displays a campus walking network on an interactive Leaflet map and compares:

- the **Fastest** path: the shortest walking route.
- the **Coolest** path: a route that trades extra walking time for lower estimated heat
  exposure.

The interface supports time-of-day changes, a heatwave scenario, shade and water-point overlays, named places, and route metrics such as distance, travel time, heat score, and shade percentage.

## Architecture

```text
coolroute/
    backend/              Flask API and routing/heat calculations
        app.py
        graph_loader.py
        heat_adapter.py
        data/             Walking network and campus data
    frontend/             React + Vite + React-Leaflet application
```

The frontend runs on port `5173` and proxies `/api` requests to the Flask backend on port `5000`.

## Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer and npm
- Internet access for the basemap tiles (once)

## Running it locally

Open two terminals from the repository root.

### 1. Start the backend

Create and activate a virtual environment, then install the Python dependencies:

```powershell
cd backend
python -m pip install -r requirements.txt
python app.py
```

The API is available at <http://localhost:5000>. Verify it with:

```text
http://localhost:5000/api/health
```

### 2. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, then click two points on the map to select a start and destination. The frontend automatically requests a fastest and a coolest route.

## Data and graph loading

The backend selects the first available graph in this order:

1. `backend/data/campus_edges.geojson` (OSMnx edge export)
2. `backend/data/campus.geojson` (generic LineString/MultiLineString data)
3. `backend/data/campus.graphml` (OSMnx GraphML)
4. A built-in synthetic walking grid

Data files in `backend/data/`:

| File | Purpose |
| --- | --- |
| `segments.csv` | Shade, surface, and water-point counts per road |
| `places.csv` | Named locations for map labels and From/To selectors |
| `water_points.geojson` | Exact water-point locations |
| `campus.geojson` | Alternative generic walking network |
| `nodes.csv`, `edges.csv` | Node names and road attributes used by `pathfinder.py` |
| `POWER_Point_Hourly_*.csv` | NASA POWER hourly weather used for AHP route costs |

* If `water_points.geojson` is absent, water points are placed at repeatable approximate positions using counts from `segments.csv`. Missing shade values use placeholder values; `/api/health` reports the active data sources.
* When the pathfinder CSV files are available, the coolest route uses the AHP costs in `backend/pathfinder.py`. The fastest route remains distance-based. If those files are absent, the backend reports that it is using its built-in heat costs instead.

## API overview

The Vite development server forwards these endpoints to Flask:

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Backend and loaded-data status |
| `GET` | `/api/config` | Map centre |
| `GET` | `/api/scenarios` | Available heat scenarios |
| `GET` | `/api/places` | Named places |
| `GET` | `/api/water-points` | Water/rest points |
| `GET` | `/api/segments` | Walking network as GeoJSON |
| `POST` | `/api/route` | Calculate fastest and coolest routes |

Example route request:

```json
{
  "start": { "lat": 20.35, "lng": 85.81 },
  "end": { "lat": 20.36, "lng": 85.82 },
  "hour": 14,
  "lambda": 2,
  "scenario": "none"
}
```

## Development notes
- `backend/app.py` contains routing and API endpoint behavior.
- `frontend/src/` contains the map and user interface.
- Basemap tiles come from Esri satellite imagery and OpenStreetMap and require network access.
