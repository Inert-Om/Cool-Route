"""Checks the data files and lists problems for the data team to fix.   python check_data.py"""
import collections
import csv

import app
from graph_loader import PLACES_CSV, SEGMENTS_CSV, osmnx_edge_id

G = app.G
graph_roads = {e["edge_id"] for *_, e in G.edges(data=True)}
print("GRAPH   :", app.GRAPH_SOURCE)
print("WATER   :", len(app.WATER_POINTS), "points,", app.WATER_SOURCE)
print("PLACES  :", len(app.PLACES), "named places,", app.PLACES_SKIPPED, "rows skipped (bad coordinates / unknown osmid)\n")

shade, water, seen = collections.defaultdict(list), collections.defaultdict(set), set()
with open(SEGMENTS_CSV, newline="", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        r = {k.strip().lower().replace(" ", "").replace("_", ""): (v or "").strip() for k, v in r.items() if k}
        eid = r.get("edgeid") or osmnx_edge_id(int(r["u"]), int(r["v"]), int(r.get("key") or 0))
        seen.add(eid)
        for col in ("shade", "shadecover"):
            if r.get(col):
                shade[eid].append(float(r[col]))
        if r.get("waterpoints"):
            water[eid].add(int(float(r["waterpoints"])))

problems = 0
for title, items in [
    ("Roads in segments.csv that are NOT in the map (typo in u / v / key?)", sorted(seen - graph_roads)),
    ("Roads on the map with NO row in segments.csv", sorted(graph_roads - seen)),
    ("Roads with no shade value (placeholder shade used)", sorted(r for r in graph_roads if not shade[r])),
    ("Shade outside 0 to 1", sorted(e for e, v in shade.items() if any(x < 0 or x > 1 for x in v))),
    ("Two directions of one road disagree on shade by more than 0.05 (average used)",
     [f"{e}: {v}" for e, v in sorted(shade.items()) if len(v) > 1 and max(v) - min(v) > 0.05]),
    ("Two directions of one road disagree on water point count (largest used)",
     [f"{e}: {sorted(v)}" for e, v in sorted(water.items()) if len(v) > 1]),
]:
    if items:
        problems += len(items)
        print(f"! {title}:")
        for i in items:
            print("    ", i)
if not problems:
    print("No problems found.")
print(f"\nTotals: {len(graph_roads)} roads, {sum(max(v) for v in water.values())} water points counted, "
      f"{len(shade)} roads with shade.")
