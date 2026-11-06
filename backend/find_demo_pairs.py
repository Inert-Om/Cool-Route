"""Finds start/end points where a heatwave changes the coolest route (your rerouting demo).

    python find_demo_pairs.py [lambda] [hour]      # defaults: 6 14

Re-run it whenever shade (segments.csv) or the heat score (heat_adapter.py) changes,
because the best demo pair changes with the data. Click near the printed coordinates.
"""
import itertools
import sys

import app

lam = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
hour = float(sys.argv[2]) if len(sys.argv) > 2 else 14.0
G = app.G

junctions = [n for n in G.nodes if isinstance(n, int)]  # real OSM junctions / road ends
rows = []
for o, d in itertools.combinations(junctions, 2):
    _, normal = app.find_routes(o, d, hour, lam, "none")
    fast, heat = app.find_routes(o, d, hour, lam, "heatwave")[0], app.find_routes(o, d, hour, lam, "heatwave")[1]
    if normal["_nodes"] != heat["_nodes"]:
        rows.append((abs(normal["shade_pct"] - heat["shade_pct"]), o, d, normal, heat, fast))

rows.sort(key=lambda r: -r[0])
print(f"lambda={lam} hour={hour}: {len(rows)} of {len(junctions) * (len(junctions) - 1) // 2} pairs reroute in a heatwave\n")
for _, o, d, normal, heat, fast in rows[:8]:
    a, b = G.nodes[o], G.nodes[d]
    print(f"start ({a['y']:.5f}, {a['x']:.5f})  ->  end ({b['y']:.5f}, {b['x']:.5f})")
    print(f"   normal day coolest: {normal['travel_time_min']} min, shade {normal['shade_pct']}%, heat {normal['heat_score']}")
    print(f"   heatwave   coolest: {heat['travel_time_min']} min, shade {heat['shade_pct']}%, heat {heat['heat_score']}\n")
if not rows:
    print("No pair reroutes. Try a higher lambda (e.g. 6) or another hour, or wait for real shade data.")
