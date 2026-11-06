import pandas as pd
import geopandas as gpd
import numpy as np
from datetime import datetime
import networkx as nx

metrodf = pd.read_csv("POWER_Point_Hourly_20260501_20260531_020d28N_085d78E_LST.csv", skiprows=12, header=0)
nodesdf = pd.read_csv("nodes.csv")
edgesdf = pd.read_csv("edges.csv")

# calculate apparent temperature
def appTemp(df):
    metrodf = df.copy()
    metrodf['WVP'] = (metrodf['RH2M']/100) * 6.105 * np.exp(17.27*metrodf['T2M']/(237.7+metrodf['T2M']))
    metrodf['AT2M'] = metrodf['T2M'] + 0.33 * metrodf['WVP'] - 0.70 * metrodf['WS10M'] - 4
    return metrodf


# Calculate weights for each parameter
def getAHPWeights():
    matrix = np.array([
        [1.0,   2.0,   2.0,   1.5,   3.0],  # 1. Distance (Primary baseline anchor)
        [0.5,   1.0,   1.5,   0.5,   2.0],  # 2. Apparent Temp (Macro thermal stress)
        [0.5,   0.67,  1.0,   0.33,  2.0],  # 3. Solar Radiation (Overhead sun load)
        [0.67,  2.0,   3.0,   1.0,   3.0],  # 4. Shade % (Critical local mitigation)
        [0.33,  0.5,   0.5,   0.33,  1.0]   # Water Points (Secondary relief bonus)
    ])

    col_sums = matrix.sum(axis=0)
    norm_matrix = matrix/col_sums
    weights = norm_matrix.mean(axis=1)
    criteria = ['Distance', 'Apparent Temperature', 'Solar Radiation', 'Shade', 'Water Points']
    weight_dict = {}
    for crit, w in zip(criteria, weights):
        print(f"{crit}: {w:.4f}")
        weight_dict[crit] = w
        
    return weight_dict


# with weights, calculate costs from the weights and parameters
def calculateCosts(edgesdf, metrodf, weights, timedate):
    df = edgesdf.copy()

    target_month = timedate.month
    target_date = timedate.day
    target_hour = timedate.hour
    
    weather_row = metrodf[
        (metrodf['month'] == target_month) & 
        (metrodf['date'] == target_date) & 
        (metrodf['hour'] == target_hour)
    ]
    
    if weather_row.empty:
        raise ValueError(f"No weather data found for Month: {target_month}, Date: {target_date}, Hour: {target_hour}")
    
    apparent_temp = weather_row['AT2M'].values[0]
    solar_radiation = weather_row['ALLSKY_SFC_SW_DWN'].values[0]

    norm_distance = df['length'] / df['length'].mean()

    temp_stress = max(0.0, (apparent_temp - 25.0) / 25.0)

    norm_solar = np.clip(solar_radiation / df['ALLSKY_SFC_SW_DWN'].max(), 0.0, 1.0)

    shade_ratio = np.clip(df.get('shade cover', 0.0) / 100.0, 0.0, 1.0)

    water_count = df.get('water points', 0.0)

    w_dist = weights.get('Distance', 0.3)
    w_temp = weights.get('Apparent Temperature', 0.2)
    w_solar = weights.get('Solar Radiation', 0.15)
    w_shade = weights.get('Shade %', 0.25)
    w_water = weights.get('Water Points', 0.1)

    environmental_load = 1.0 + (w_temp * temp_stress) + (w_solar * norm_solar)
    shade_mitigation = 1.0 - (w_shade * shade_ratio)
    shade_mitigation = np.maximum(shade_mitigation, 0.2)
    water_relief = w_water * water_count * 10.0

    base_scale = df['length']
    df['cost'] = (base_scale * norm_distance * environmental_load * shade_mitigation) - water_relief

    df['cost'] = np.maximum(df['cost'], 1.0)

    return df


# Using costs, find and return optimal and shortest path
def dijkstra_route(edgesdf, snode, tnode):
    G = nx.from_pandas_edgelist(
        edgesdf,
        source='u',
        target='v',
        edge_attr=True
    )

    try:
        opt_path_nodes = nx.shortest_path(G, source=snode, target=tnode, weight='cost')
        opt_total_length = nx.path_weight(G, opt_path_nodes, weight='length')

        short_path_nodes = nx.shortest_path(G, source=snode, target=tnode, weight='length')
        short_total_length = nx.path_weight(G, short_path_nodes, weight='length')
        return (opt_path_nodes, opt_total_length), (short_path_nodes, short_total_length)

    except nx.NetworkXNoPath:
        print(f"Error: No valid path found between node {snode} and node {tnode}.")
        return [], float('inf')

    except nx.NodeNotFound as e:
        print(f"Error: Start or target node not found in graph: {e}")
        return [], float('inf')


# from node name, find osmid of node
def findNode(nodesdf, ustr):
    matches = nodesdf.loc[nodesdf['name'] == ustr, 'osmid']
    
    if not matches.empty:
        osmid = matches.values[0]
        return osmid if osmid else 0
        
    return 0


ustr = "Textiile dept."
vstr = "Gate 1"

u = findNode(nodesdf, ustr)
v = findNode(nodesdf, vstr)

weight_dict = getAHPWeights()
metrodf = appTemp(metrodf)
edgesdf = calculateCosts(edgesdf, metrodf, weight_dict, "2026-05-15 10:10:00")

print(u, v)
opt, short = dijkstra_route(edgesdf, u, v)
print(opt, short)