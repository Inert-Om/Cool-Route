import networkx as nx
from flask import Flask, jsonify, request
from flask_cors import CORS

from graph_loader import (edge_coords, graph_center, load_graph, load_places, load_water_points,
                          nearest_node, water_points_from_counts)
from heat_adapter import SCENARIOS, edge_heat

app = Flask(__name__)
CORS(app)  # lets the React dev server call us directly if you skip the Vite proxy

G, GRAPH_SOURCE = load_graph()
PLACES, PLACES_SKIPPED = load_places(G)
WALK_SPEED = 1.4  # m/s

# Placeholder water / rest points. TODO(data): load water_points.geojson instead.
WATER_POINTS = []
WATER_SOURCE = "placeholder (random)"

def _init_water_points():
    global WATER_SOURCE
    real = load_water_points()
    if real is not None:
        WATER_POINTS.extend(real)
        WATER_SOURCE = "water_points.geojson"
        return
    from_counts = water_points_from_counts(G)
    if from_counts:
        WATER_POINTS.extend(from_counts)
        WATER_SOURCE = "APPROXIMATE: random spots along roads, from the per-road counts in segments.csv"
        return
    nodes = list(G.nodes)
    for k, idx in enumerate(range(5, len(nodes), max(1, len(nodes) // 8))):
        n = nodes[idx]
        WATER_POINTS.append({
            "id": k,
            "type": ["fountain", "shaded rest area", "bench"][k % 3],
            "lat": G.nodes[n]["y"],
            "lng": G.nodes[n]["x"],
        })


_init_water_points()


def build_route(path, hour, scenario, route_id, label):
    segments, dist, heat, shaded = [], 0.0, 0.0, 0.0
    for u, v in zip(path[:-1], path[1:]):
        e = G[u][v]
        h = edge_heat(e, hour, scenario)
        dist += e["length"]
        heat += h
        shaded += e["length"] * e["shade"]
        segments.append({
            "coords": [[float(a), float(b)] for a, b in edge_coords(G, u, v, e)],
            "heat_per_m": round(h / e["length"], 3) if e["length"] else 0.0,
        })
    return {
        "id": route_id, "label": label, "segments": segments,
        "distance_m": round(dist),
        "travel_time_min": round(dist / WALK_SPEED / 60, 1),
        "heat_score": round(heat),
        "shade_pct": round(100 * shaded / dist) if dist else 0,
        "_nodes": path,
    }


def find_routes(o, d, hour, lam, scenario):
    fastest = nx.shortest_path(G, o, d, weight="length")
    cost = lambda u, v, e: e["length"] / WALK_SPEED + lam * edge_heat(e, hour, scenario) / 10.0
    coolest = nx.shortest_path(G, o, d, weight=cost)
    return (build_route(fastest, hour, scenario, "fastest", "Fastest"),
            build_route(coolest, hour, scenario, "coolest", "Coolest"))


@app.get("/api/health")
def health():
    return jsonify(status="ok", graph=GRAPH_SOURCE, nodes=G.number_of_nodes(), edges=G.number_of_edges(),
                   places=len(PLACES), places_skipped=PLACES_SKIPPED,
                   water_points=len(WATER_POINTS), water_points_source=WATER_SOURCE)


@app.get("/api/config")
def config():
    return jsonify(center=list(graph_center(G)))


@app.get("/api/scenarios")
def scenarios():
    return jsonify([{"id": k, "label": v["label"]} for k, v in SCENARIOS.items()])


@app.get("/api/places")
def places():
    return jsonify(PLACES)


@app.get("/api/water-points")
def water_points():
    return jsonify(WATER_POINTS)


@app.get("/api/segments")
def segments():
    feats = []
    for u, v, e in G.edges(data=True):
        if G.has_edge(v, u) and str(u) > str(v):  # two-way road: draw it once (one-way: always draw)
            continue
        feats.append({
            "type": "Feature",
            "properties": {"shade": e["shade"], "edge_id": e.get("edge_id", ""), "surface": e.get("surface", "")},
            "geometry": {"type": "LineString",
                         "coordinates": [[lng, lat] for lat, lng in edge_coords(G, u, v, e)]},
        })
    return jsonify({"type": "FeatureCollection", "features": feats})


@app.post("/api/route")
def route():
    body = request.get_json(silent=True) or {}
    try:
        s, t = body["start"], body["end"]
        hour = float(body.get("hour", 14))
        lam = float(body.get("lambda", 1.0))
        scenario = body.get("scenario") or "none"
        o = nearest_node(G, float(s["lat"]), float(s["lng"]))
        d = nearest_node(G, float(t["lat"]), float(t["lng"]))
    except (KeyError, TypeError, ValueError):
        return jsonify(error="Body needs start{lat,lng}, end{lat,lng}; optional hour, lambda, scenario"), 400
    if o == d:
        return jsonify(error="Start and end snap to the same point; pick points further apart"), 400
    if scenario not in SCENARIOS:
        return jsonify(error=f"Unknown scenario '{scenario}'"), 400
    try:
        fastest, coolest = find_routes(o, d, hour, lam, scenario)
    except nx.NetworkXNoPath:
        return jsonify(error="No walking path between these points"), 404

    drop = round(100 * (1 - coolest["heat_score"] / fastest["heat_score"])) if fastest["heat_score"] else 0
    extra = round(coolest["travel_time_min"] - fastest["travel_time_min"], 1)
    explanation = (f"Coolest route takes {extra:+.1f} min vs fastest and has "
                   f"{drop}% lower heat score ({coolest['shade_pct']}% shaded vs {fastest['shade_pct']}%).")

    # Rerouting: compare against the same trip under normal conditions
    changed_because, previous = None, None
    if scenario != "none":
        _, base_cool = find_routes(o, d, hour, lam, "none")
        if base_cool["_nodes"] != coolest["_nodes"]:
            changed_because = (f"{SCENARIOS[scenario]['label']}: sun exposure rose, so the coolest "
                               f"route switched to a shadier path.")
            previous = {k: v for k, v in base_cool.items() if k != "_nodes"}
            previous["id"], previous["label"] = "previous", "Previous coolest"
    for r in (fastest, coolest):
        r.pop("_nodes")
    return jsonify(routes=[fastest, coolest], explanation=explanation,
                   changed_because=changed_because, previous=previous)


if __name__ == "__main__":
    app.run(port=5001, debug=True)
