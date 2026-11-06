import os

import osmnx as ox

from graph_loader import CENTER

RADIUS_M = 800
os.makedirs("data", exist_ok=True)
G = ox.graph_from_point(CENTER, dist=RADIUS_M, network_type="walk")
ox.save_graphml(G, "data/campus.graphml")
print(f"Saved {len(G.nodes)} nodes, {len(G.edges)} edges to data/campus.graphml")
