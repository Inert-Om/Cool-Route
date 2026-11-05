"""THE ONE PLACE the ML person's heat score plugs in.

Backend only ever calls `edge_heat(...)`. When ML delivers heat.py, change the body of
this function (or import theirs) and nothing else needs to change.

Return value: heat load for traversing the whole edge (higher = hotter).
"""
import math

SCENARIOS = {
    "none": {"label": "Normal day", "sun_boost": 0.0, "temp_boost": 0.0},
    "heatwave": {"label": "Heatwave (+5 C)", "sun_boost": 0.3, "temp_boost": 5.0},
}


def sun_intensity(hour):
    """0 at night, 1.0 at solar noon (placeholder; ML replaces with NASA data)."""
    return max(0.0, math.sin(math.pi * (hour - 6) / 12))


def edge_heat(edge, hour, scenario="none"):
    sc = SCENARIOS.get(scenario, SCENARIOS["none"])
    sun = min(1.5, sun_intensity(hour) + sc["sun_boost"])
    base = 0.2 + sc["temp_boost"] * 0.04
    heat = edge["length"] * (base + 1.5 * sun * (1.0 - edge["shade"]))
    # water access cools the road. Dividing by something >= 1 keeps heat >= 0 (Dijkstra needs that).
    return heat / (1.0 + 0.15 * edge.get("water_points", 0))
