"""Loads the walking graph.

Priority:
  1. data/campus.graphml  (real OSM footpaths, built by build_graph.py)
  2. a synthetic grid graph (so the app runs before the real data exists)

Both return a simple networkx DiGraph whose nodes have x (lng) / y (lat) and whose
edges have `length` (m), `shade` (0-1) and optionally `geometry` (shapely LineString).
"""
import math
import os
import random

import networkx as nx

# >>> CHANGE THIS to your campus / zone centre <<<
CENTER = (20.3555, 85.8190)  # (lat, lng)

GRAPHML = os.path.join(os.path.dirname(__file__), "data", "campus.graphml")
GEOJSON = os.path.join(os.path.dirname(__file__), "data", "campus.geojson")
WATER_GEOJSON = os.path.join(os.path.dirname(__file__), "data", "water_points.geojson")
EDGES_GEOJSON = os.path.join(os.path.dirname(__file__), "data", "campus_edges.geojson")  # OSMnx export
SEGMENTS_CSV = os.path.join(os.path.dirname(__file__), "data", "segments.csv")


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _synthetic_graph(n=8, spacing_m=110, seed=7):
    """n x n street grid around CENTER. Column 2 is a tree-lined 'cool corridor'."""
    rng = random.Random(seed)
    lat0, lng0 = CENTER
    dlat = spacing_m / 111_320
    dlng = spacing_m / (111_320 * math.cos(math.radians(lat0)))
    G = nx.DiGraph()
    for i in range(n):
        for j in range(n):
            G.add_node((i, j),
                       y=lat0 + (i - n / 2) * dlat + rng.uniform(-0.1, 0.1) * dlat,
                       x=lng0 + (j - n / 2) * dlng + rng.uniform(-0.1, 0.1) * dlng)
    for i in range(n):
        for j in range(n):
            for di, dj in ((0, 1), (1, 0)):
                a, b = (i, j), (i + di, j + dj)
                if b not in G:
                    continue
                length = haversine_m(G.nodes[a]["y"], G.nodes[a]["x"], G.nodes[b]["y"], G.nodes[b]["x"])
                shade = rng.choice([0.1, 0.2, 0.3, 0.6])
                if dj == 0 and j == 2:          # vertical tree-lined corridor
                    shade = 0.9
                if di == 0 and i == n - 2:      # covered walkway along one row
                    shade = 0.8
                G.add_edge(a, b, length=length, shade=shade)
                G.add_edge(b, a, length=length, shade=shade)
    return G, "synthetic grid (no campus.graphml found)"


def _osm_graph():
    import osmnx as ox
    GM = ox.load_graphml(GRAPHML)
    G = ox.convert.to_digraph(GM, weight="length")
    rng = random.Random(42)
    for _, _, e in G.edges(data=True):
        e["length"] = float(e["length"])
        # TODO(data/ML): replace random shade with real segments.csv values
        e["shade"] = rng.choice([0.1, 0.3, 0.5, 0.8, 0.9])
    return G, "OSM graph from campus.graphml"


def _generic_lines_graph(data):
    """Build the walking graph from generic LineString / MultiLineString features (campus.geojson).

    - Lines are 'noded' with shapely, so roads that cross or touch become connected
      even if the GeoJSON has no shared vertex at the junction.
    - Every vertex becomes a graph node, so clicks snap close to where you clicked.
    - Optional feature properties are kept: `shade` (0-1), `surface`, `name`.
    - Pieces not connected to the main network are dropped (and counted).
    """
    from shapely.geometry import shape
    from shapely.ops import unary_union

    feats = data["features"]

    lines = []  # (LineString, properties)
    for ft in feats:
        if not ft.get("geometry"):
            continue
        geom = shape(ft["geometry"])
        props = ft.get("properties") or {}
        if geom.geom_type == "LineString":
            lines.append((geom, props))
        elif geom.geom_type == "MultiLineString":
            lines.extend((g, props) for g in geom.geoms)
        # points / polygons are ignored here
    if not lines:
        raise ValueError("campus.geojson has no LineString features")

    noded = unary_union([ln for ln, _ in lines])
    pieces = [g for g in getattr(noded, "geoms", [noded]) if g.geom_type == "LineString"]

    def props_for(piece):
        pt, best, best_d = piece.representative_point(), {}, 1e-6  # ~0.1 m in degrees
        for ln, pr in lines:
            d = ln.distance(pt)
            if d < best_d:
                best, best_d = pr, d
        return best

    rng = random.Random(42)
    G = nx.DiGraph()
    key = lambda x, y: (round(x, 5), round(y, 5))  # ~1 m merge tolerance
    for piece in pieces:
        pr = props_for(piece)
        shade = pr.get("shade")
        shade = min(1.0, max(0.0, float(shade))) if shade is not None else rng.choice([0.1, 0.3, 0.5, 0.8, 0.9])
        coords = list(piece.coords)
        for (x1, y1), (x2, y2) in zip(coords[:-1], coords[1:]):
            a, b = key(x1, y1), key(x2, y2)
            if a == b:
                continue
            for n, (x, y) in ((a, (x1, y1)), (b, (x2, y2))):
                if n not in G:
                    G.add_node(n, x=x, y=y)
            length = haversine_m(y1, x1, y2, x2)
            attrs = dict(length=length, shade=shade, surface=pr.get("surface", "unknown"), name=pr.get("name", ""))
            G.add_edge(a, b, **attrs)
            G.add_edge(b, a, **attrs)

    total = G.number_of_nodes()
    main = max(nx.weakly_connected_components(G), key=len)
    G = G.subgraph(main).copy()
    dropped = total - G.number_of_nodes()
    return G, f"GeoJSON network ({G.number_of_nodes()} nodes, {dropped} disconnected nodes dropped)"


def osmnx_edge_id(u, v, key=0):
    """The edge_id used in segments.csv: smaller-larger OSM node id, '#key' for a parallel road."""
    return f"{min(u, v)}-{max(u, v)}" + (f"#{key}" if key else "")


def _stable_shade(eid):
    """PLACEHOLDER shade: random-looking but identical on every run, until segments.csv exists."""
    import hashlib

    return [0.1, 0.3, 0.5, 0.8, 0.9][int(hashlib.md5(eid.encode()).hexdigest()[:8], 16) % 5]


def read_segments_csv():
    """data/segments.csv -> {edge_id: {"shade": float|None, "surface": str, "water_points": int}}.

    Two layouts are accepted (header names are case-insensitive; spaces and underscores ignored):
      A) edge_id, surface, shade, water_points
      B) OSMnx-style rows: u, v, key, "shade cover", "water points"   (what the data team sent)
    OSMnx lists both directions of a road, so rows are merged per road: shade is the average of the
    rows that have a value, water_points is the largest value, empty cells are ignored.
    """
    import csv

    if not os.path.exists(SEGMENTS_CSV):
        return {}
    norm = lambda s: (s or "").strip().lower().replace(" ", "").replace("_", "")
    acc = {}
    with open(SEGMENTS_CSV, newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            row = {norm(k): (v or "").strip() for k, v in raw.items() if k}
            try:
                eid = row.get("edgeid") or osmnx_edge_id(int(row["u"]), int(row["v"]), int(row.get("key") or 0))
            except (KeyError, ValueError):
                continue
            a = acc.setdefault(eid, {"shade": [], "surface": "", "water": []})
            for col, bucket in (("shade", "shade"), ("shadecover", "shade"), ("waterpoints", "water")):
                if row.get(col):
                    try:
                        a[bucket].append(float(row[col]))
                    except ValueError:
                        pass
            a["surface"] = a["surface"] or row.get("surface", "")
    return {eid: {"shade": sum(a["shade"]) / len(a["shade"]) if a["shade"] else None,
                  "surface": a["surface"],
                  "water_points": int(max(a["water"])) if a["water"] else 0}
            for eid, a in acc.items()}


def _osmnx_edges_graph(data):
    """Graph from an OSMnx edges export (campus_edges.geojson: properties u, v, key, oneway ...).

    - Uses the real OSM node ids (u, v), so edge_id = "u-v" matches the other files.
    - OSMnx lists each two-way road twice (u->v and v->u): we keep one and add both directions.
    - oneway roads (roundabouts) are added in one direction only.
    - Every geometry vertex becomes a node, so clicks snap close to where you clicked
      (the long roads here are up to ~450 m between junctions).
    - Shade / surface come from data/segments.csv when present, else a stable placeholder.
    """
    seg = read_segments_csv()
    G = nx.DiGraph()
    seen = set()
    for ft in data["features"]:
        geom, pr = ft.get("geometry"), ft.get("properties") or {}
        if not geom or geom.get("type") != "LineString" or "u" not in pr or "v" not in pr:
            continue
        u, v, key = int(pr["u"]), int(pr["v"]), int(pr.get("key", 0))
        eid = osmnx_edge_id(u, v, key)
        if eid in seen:
            continue
        seen.add(eid)

        raw = [tuple(c[:2]) for c in geom["coordinates"]]
        coords = [raw[0]] + [c for p, c in zip(raw[:-1], raw[1:]) if c != p]  # drop repeated points
        if len(coords) < 2:
            continue
        if len(coords) == 2 and (G.has_edge(u, v) or G.has_edge(v, u)):  # parallel straight road
            (x1, y1), (x2, y2) = coords
            coords = [coords[0], ((x1 + x2) / 2, (y1 + y2) / 2), coords[1]]
        nodes = [u] + [f"{eid}:{i}" for i in range(1, len(coords) - 1)] + [v]

        row = seg.get(eid, {})
        shade = row.get("shade")
        shade = min(1.0, max(0.0, shade)) if shade is not None else _stable_shade(eid)
        water = row.get("water_points", 0)
        oneway = pr.get("oneway") in (True, "True", "true", 1)

        for n, (x, y) in zip(nodes, coords):
            if n not in G:
                G.add_node(n, x=x, y=y)
        for i in range(len(nodes) - 1):
            (x1, y1), (x2, y2) = coords[i], coords[i + 1]
            attrs = dict(length=haversine_m(y1, x1, y2, x2), shade=shade, edge_id=eid, water_points=water,
                         surface=row.get("surface") or "unknown", highway=pr.get("highway"))
            G.add_edge(nodes[i], nodes[i + 1], **attrs)
            if not oneway:
                G.add_edge(nodes[i + 1], nodes[i], **attrs)

    if not seen:
        raise ValueError("campus_edges.geojson has no usable LineString features with u/v properties")
    total = G.number_of_nodes()
    main = max(nx.weakly_connected_components(G), key=len)
    G = G.subgraph(main).copy()
    n_real = sum(1 for eid in seen if seg.get(eid, {}).get("shade") is not None)
    shade_src = (f"shade from segments.csv for {n_real} of {len(seen)} roads (rest PLACEHOLDER)"
                 if seg else "shade is PLACEHOLDER (random)")
    return G, (f"OSMnx GeoJSON export: {len(seen)} roads, {G.number_of_nodes()} nodes, "
               f"{total - G.number_of_nodes()} dropped as disconnected; {shade_src}")


def _geojson_graph(path):
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    feats = data["features"] if data.get("type") == "FeatureCollection" else [data]
    data = {"type": "FeatureCollection", "features": feats}
    first = next((ft.get("properties") or {} for ft in feats if ft.get("geometry")), {})
    if "u" in first and "v" in first:
        return _osmnx_edges_graph(data)
    return _generic_lines_graph(data)


def load_graph():
    for path in (EDGES_GEOJSON, GEOJSON):
        if os.path.exists(path):
            return _geojson_graph(path)
    if os.path.exists(GRAPHML):
        return _osm_graph()
    return _synthetic_graph()


def graph_center(G):
    """Centre of the graph's bounding box as (lat, lng): no need to hand-set CENTER."""
    ys = [d["y"] for _, d in G.nodes(data=True)]
    xs = [d["x"] for _, d in G.nodes(data=True)]
    return ((min(ys) + max(ys)) / 2, (min(xs) + max(xs)) / 2)


PLACES_CSV = os.path.join(os.path.dirname(__file__), "data", "places.csv")


def load_places(G):
    """Named campus places from data/places.csv -> ([{id, name, type, lat, lng}], n_skipped).

    Accepted columns (case-insensitive):
      name            required (also: place, label)
      lat + lng       coordinates (also: latitude/longitude, lon, y/x), OR
      osmid           id of a graph junction (also: node, node_id): its coordinates come from the graph
      type            optional (hostel, library, gate ...)
    Rows with no name, or an osmid that is not in the graph, are skipped and counted.
    """
    import csv

    if not os.path.exists(PLACES_CSV):
        return [], 0

    def pick(row, *names):
        for k, v in row.items():
            if k and k.strip().lower() in names and v is not None and str(v).strip():
                return str(v).strip()
        return None

    out, skipped = [], 0
    with open(PLACES_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = pick(row, "name", "place", "label")
            if not name:  # an unnamed node (most junctions): nothing to show, not an error
                continue
            lat, lng = pick(row, "lat", "latitude", "y"), pick(row, "lng", "lon", "long", "longitude", "x")
            osm = pick(row, "osmid", "node", "node_id")
            try:
                if lat and lng:
                    lat, lng = float(lat), float(lng)
                elif osm and int(float(osm)) in G:
                    n = int(float(osm))
                    lat, lng = G.nodes[n]["y"], G.nodes[n]["x"]
                else:
                    raise ValueError
            except ValueError:
                skipped += 1
                continue
            out.append({"id": len(out), "name": name, "type": pick(row, "type", "category") or "",
                        "lat": lat, "lng": lng})
    return out, skipped


def water_points_from_counts(G, seed_prefix="water"):
    """Water points are known per road (a count) but not WHERE. Place that many markers at random,
    but repeatable, spots along each road. Every marker is flagged approximate=True."""
    roads = {}
    for u, v, e in G.edges(data=True):
        if e.get("water_points", 0) > 0 and (not G.has_edge(v, u) or str(u) <= str(v)):  # each road once
            roads.setdefault(e["edge_id"], []).append((u, v, e))
    out = []
    for eid, segs in sorted(roads.items()):
        rng = random.Random(f"{seed_prefix}:{eid}")
        for _ in range(int(segs[0][2]["water_points"])):
            u, v, e = rng.choices(segs, weights=[s[2]["length"] for s in segs])[0]
            t = rng.uniform(0.1, 0.9)
            a, b = G.nodes[u], G.nodes[v]
            out.append({"id": len(out), "type": "water point", "status": "open", "approximate": True,
                        "edge_id": eid, "lat": a["y"] + t * (b["y"] - a["y"]), "lng": a["x"] + t * (b["x"] - a["x"])})
    return out


def load_water_points():
    """Point features from data/water_points.geojson -> [{id, type, status, lat, lng}], or None."""
    import json

    if not os.path.exists(WATER_GEOJSON):
        return None
    with open(WATER_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for ft in data.get("features", []):
        g = ft.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        pr = ft.get("properties") or {}
        lng, lat = g["coordinates"][:2]
        out.append({"id": len(out), "type": pr.get("type", "water point"),
                    "status": pr.get("status", "open"), "lat": lat, "lng": lng})
    return out


def nearest_node(G, lat, lng):
    return min(G.nodes, key=lambda n: (G.nodes[n]["y"] - lat) ** 2 + (G.nodes[n]["x"] - lng) ** 2)


def edge_coords(G, u, v, e):
    """[lat, lng] points for one edge, ordered u -> v (this is what makes lines follow roads)."""
    if "geometry" in e and e["geometry"] is not None:
        pts = [(lat, lng) for lng, lat in e["geometry"].coords]
        # make sure the first point is near u
        du = (pts[0][0] - G.nodes[u]["y"]) ** 2 + (pts[0][1] - G.nodes[u]["x"]) ** 2
        dv = (pts[-1][0] - G.nodes[u]["y"]) ** 2 + (pts[-1][1] - G.nodes[u]["x"]) ** 2
        return pts if du <= dv else pts[::-1]
    return [(G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"])]
