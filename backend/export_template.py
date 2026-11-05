"""Makes data/segments_template.csv from data/campus_edges.geojson.

Give this file to the data collector. They fill in `surface` and `shade` for every row and save it
as data/segments.csv. Rows with an empty shade fall back to the placeholder shade.

    python export_template.py
"""
import csv
import json

from graph_loader import EDGES_GEOJSON, haversine_m, osmnx_edge_id

with open(EDGES_GEOJSON, encoding="utf-8") as f:
    feats = json.load(f)["features"]

seen, rows = set(), []
for ft in feats:
    pr, coords = ft["properties"], ft["geometry"]["coordinates"]
    eid = osmnx_edge_id(int(pr["u"]), int(pr["v"]), int(pr.get("key", 0)))
    if eid in seen:
        continue
    seen.add(eid)
    mx, my = coords[len(coords) // 2][:2]  # a point on the road, to find it on a map
    rows.append({"edge_id": eid, "highway": pr.get("highway", ""), "length_m": round(pr["length"]),
                 "mid_lat": round(my, 6), "mid_lng": round(mx, 6), "surface": "", "shade": ""})

with open("data/segments_template.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"Wrote data/segments_template.csv with {len(rows)} roads")
