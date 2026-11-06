"""Reusable AHP-based route costs and CSV loading for CoolStride."""

from datetime import datetime
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"
WEATHER_FILE = DATA_DIR / "POWER_Point_Hourly_20260501_20260531_020d28N_085d78E_LST.csv"
NODES_FILE = DATA_DIR / "nodes.csv"
EDGES_FILE = DATA_DIR / "edges.csv"

SCENARIOS = {
    "none": {"temp_boost": 0.0, "sun_boost": 0.0},
    "heatwave": {"temp_boost": 5.0, "sun_boost": 0.3},
}


def load_data():
    """Load the pathfinder node, edge, and NASA weather CSV files."""
    for path in (NODES_FILE, EDGES_FILE, WEATHER_FILE):
        if not path.is_file():
            raise FileNotFoundError(f"Required pathfinder data file not found: {path}")

    nodes = pd.read_csv(NODES_FILE)
    edges = pd.read_csv(EDGES_FILE)
    weather = pd.read_csv(WEATHER_FILE, skiprows=12)
    weather = weather.rename(columns={"MO": "month", "DY": "date", "HR": "hour"})
    weather = appTemp(weather)
    return nodes, _normalize_edges(edges), weather


def appTemp(df):
    """Add water-vapour pressure and apparent temperature to NASA weather data."""
    result = df.copy()
    result["WVP"] = (result["RH2M"] / 100) * 6.105 * np.exp(
        17.27 * result["T2M"] / (237.7 + result["T2M"])
    )
    result["AT2M"] = (
        result["T2M"] + 0.33 * result["WVP"] - 0.70 * result["WS10M"] - 4
    )
    return result


def getAHPWeights():
    """Return normalized AHP weights for route criteria."""
    matrix = np.array([
        [1.0, 2.0, 2.0, 1.5, 3.0],
        [0.5, 1.0, 1.5, 0.5, 2.0],
        [0.5, 0.67, 1.0, 0.33, 2.0],
        [0.67, 2.0, 3.0, 1.0, 3.0],
        [0.33, 0.5, 0.5, 0.33, 1.0],
    ])
    normalized = matrix / matrix.sum(axis=0)
    names = ("Distance", "Apparent Temperature", "Solar Radiation", "Shade", "Water Points")
    return dict(zip(names, normalized.mean(axis=1)))


def _normalize_edges(edgesdf):
    df = edgesdf.copy()
    columns = {
        str(column).strip().lower().replace("_", " "): column
        for column in df.columns
    }
    aliases = {
        "shade cover": ("shade cover", "shade"),
        "water points": ("water points", "water"),
    }
    for target, names in aliases.items():
        if target not in df.columns:
            source = next((columns[name] for name in names if name in columns), None)
            if source is not None:
                df[target] = df[source]

    required = ("u", "v", "length")
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Edges CSV is missing required columns: {', '.join(missing)}")
    if "shade cover" not in df.columns:
        df["shade cover"] = 0.0
    if "water points" not in df.columns:
        df["water points"] = 0.0

    for column in ("length", "shade cover", "water points"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["u", "v", "length"])
    df = df[df["length"] > 0].copy()
    if df.empty:
        raise ValueError("Edges CSV contains no usable positive-length edges")
    return df


def _weather_values(metrodf, timedate):
    if timedate is None:
        raise ValueError("A route hour or datetime is required")
    weather = metrodf.copy()
    hour = timedate.hour if isinstance(timedate, datetime) else float(timedate)
    weather_hour = pd.to_numeric(weather["hour"], errors="coerce")
    nearest_hour = int(np.clip(round(hour), 0, 23))
    rows = weather.loc[weather_hour == nearest_hour]

    if isinstance(timedate, datetime):
        rows = rows.loc[
            (pd.to_numeric(rows["month"], errors="coerce") == timedate.month)
            & (pd.to_numeric(rows["date"], errors="coerce") == timedate.day)
        ]
    if rows.empty:
        if isinstance(timedate, datetime):
            raise ValueError(
                f"No weather data found for {timedate:%Y-%m-%d %H}:00"
            )
        raise ValueError(f"No weather data found for hour {nearest_hour}:00")
    return float(rows["AT2M"].mean()), float(rows["ALLSKY_SFC_SW_DWN"].mean())


def calculateCosts(edgesdf, metrodf, weights, timedate, scenario="none", lam=1.0):
    """Return edge costs for the selected hour, AHP preferences, and heat scenario.

    ``lam`` blends shortest-distance routing (0) with the AHP environmental
    preference as it increases. A nonnegative cost is maintained for Dijkstra.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    lam = float(lam)
    if not np.isfinite(lam) or lam < 0:
        raise ValueError("lambda must be a finite nonnegative number")

    df = _normalize_edges(edgesdf)
    apparent_temp, solar_radiation = _weather_values(metrodf, timedate)
    scenario_adjustments = SCENARIOS[scenario]
    apparent_temp += scenario_adjustments["temp_boost"]

    lengths = df["length"].astype(float)
    shade = df["shade cover"].fillna(0.0).astype(float)
    if shade.max() > 1.0:
        shade = shade / 100.0
    shade = shade.clip(0.0, 1.0)
    water_count = df["water points"].fillna(0.0).astype(float).clip(lower=0.0)

    temp_weight = float(weights.get("Apparent Temperature", 0.2))
    solar_weight = float(weights.get("Solar Radiation", 0.15))
    distance_weight = float(weights.get("Distance", 0.3))
    shade_weight = float(weights.get("Shade", weights.get("Shade %", 0.25)))
    water_weight = float(weights.get("Water Points", 0.1))

    temp_stress = max(0.0, (apparent_temp - 25.0) / 25.0)
    weather_solar = pd.to_numeric(metrodf["ALLSKY_SFC_SW_DWN"], errors="coerce")
    solar_reference = max(float(weather_solar.max()), 1.0)
    norm_solar = float(np.clip(
        solar_radiation / solar_reference + scenario_adjustments["sun_boost"], 0.0, 1.5
    ))

    environmental_load = 1.0 + temp_weight * temp_stress + solar_weight * norm_solar
    shade_mitigation = (1.0 - shade_weight * shade).clip(lower=0.2)
    water_relief = (water_weight * water_count * 0.1).clip(upper=0.8)
    mean_length = float(lengths.mean())
    ahp_multiplier = (
        distance_weight * (lengths / mean_length)
        + (1.0 - distance_weight) * (environmental_load * shade_mitigation - water_relief)
    ).clip(lower=0.05)

    blend = lam / (1.0 + lam)
    df["cost"] = lengths * ((1.0 - blend) + blend * ahp_multiplier)
    return df


def edge_costs_by_id(edgesdf):
    """Map each source road ID to its AHP cost per meter."""
    road_costs = {}
    for row in _normalize_edges(edgesdf).itertuples(index=False):
        values = row._asdict()
        try:
            u, v = int(values["u"]), int(values["v"])
            key = int(values.get("key", 0) or 0)
            edge_id = f"{min(u, v)}-{max(u, v)}" + (f"#{key}" if key else "")
            total_cost = float(values.get("cost", values["length"]))
            road_costs.setdefault(edge_id, []).append(total_cost / float(values["length"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    return {edge_id: float(np.mean(costs)) for edge_id, costs in road_costs.items()}


def dijkstra_route(edgesdf, snode, tnode):
    """Return (AHP-optimal route, shortest route), each as (nodes, distance)."""
    df = _normalize_edges(edgesdf)
    if "cost" not in df.columns:
        raise ValueError("Calculate edge costs before calling dijkstra_route")

    graph = nx.DiGraph()
    for row in df.to_dict("records"):
        u, v = row["u"], row["v"]
        graph.add_edge(u, v, **row)
        oneway = str(row.get("oneway", "")).strip().lower() in ("true", "1", "yes")
        if not oneway and not graph.has_edge(v, u):
            reverse = dict(row)
            reverse["u"], reverse["v"] = v, u
            graph.add_edge(v, u, **reverse)

    try:
        optimal = nx.shortest_path(graph, source=snode, target=tnode, weight="cost")
        shortest = nx.shortest_path(graph, source=snode, target=tnode, weight="length")
        return (
            (optimal, nx.path_weight(graph, optimal, weight="length")),
            (shortest, nx.path_weight(graph, shortest, weight="length")),
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return (([], float("inf")), ([], float("inf")))


def findNode(nodesdf, ustr):
    """Find a node ID by its name, returning 0 when there is no match."""
    matches = nodesdf.loc[nodesdf["name"] == ustr, "osmid"]
    if matches.empty:
        return 0
    return int(matches.iloc[0])


def main():
    nodes, edges, weather = load_data()
    target = datetime(2026, 5, 15, 10)
    costs = calculateCosts(edges, weather, getAHPWeights(), target)
    start = findNode(nodes, "Textiile dept.")
    end = findNode(nodes, "Gate 1")
    print(start, end)
    print(dijkstra_route(costs, start, end))


if __name__ == "__main__":
    main()
