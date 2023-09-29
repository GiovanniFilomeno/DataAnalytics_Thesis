import sqlite3
import requests
import math
import networkx as nx
import numpy as np

import urllib3

# Disabilita i warning per le richieste senza verifica SSL
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # raggio della Terra in km

    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.sin(dLon / 2) * math.sin(dLon / 2) * math.cos(lat1) * math.cos(lat2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_osrm_distance(lat1, lon1, lat2, lon2):

    # Calcolo approssimativo della distanza

    approx_distance = 1000 * haversine_distance(lat1, lon1, lat2, lon2)

    # print(f"Approximate distance: {approx_distance}")


    if approx_distance <= 100:
        # print("Using OSRM for distance calculation")


        # Verifica se la distanza è già stata calcolata e salvata nel database
        conn = sqlite3.connect('distances.db', isolation_level=None, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS distances
                        (lat1 REAL, lon1 REAL, lat2 REAL, lon2 REAL, distance REAL)''')
        conn.commit()
        
        cursor.execute("SELECT distance FROM distances WHERE lat1=? AND lon1=? AND lat2=? AND lon2=?",
                    (lat1, lon1, lat2, lon2))
        result = cursor.fetchone()
        
        if result is not None:
            distance = result[0]
        else:
            url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if 'routes' in data and len(data['routes']) > 0:
                    distance = data['routes'][0]['distance']
                    # Chiudi la connessione al database prima di eseguire l'INSERT
                    conn.close()
                    # Riapri la connessione al database
                    conn = sqlite3.connect('distances.db', isolation_level=None, check_same_thread=False)
                    cursor = conn.cursor()
                    # Salva la distanza nel database
                    cursor.execute("INSERT INTO distances (lat1, lon1, lat2, lon2, distance) VALUES (?, ?, ?, ?, ?)",
                                (lat1, lon1, lat2, lon2, distance))
                    conn.commit()
            else:
                distance = None

        conn.close()
        return distance
    
    else:
        # print("Using approximate distance")
        return approx_distance
    
def draw_graph(graph_to_draw, title=''):
    import matplotlib.pyplot as plt
    import geopandas as gpd
    import networkx as nx
    from pyproj import Transformer
    import numpy as np

    options = {
        'node_color': 'lavender',
        'node_size': 10,
        'width': 1,
        'arrowsize': 1,
    }

    # Leggi il file GeoJSON dei confini della Germania
    germany_boundary = gpd.read_file('boundaries/4_niedrig.geo.json')

    # Converti le coordinate geografiche in coordinate UTM
    germany_boundary = germany_boundary.to_crs('epsg:32632')

    # Crea un nuovo plot
    fig, ax = plt.subplots(figsize=(12, 8))

    # Assumi che 'nodes_id' sia una lista di numeri interi rappresentanti gli identificatori dei nodi nel tuo grafo
    nodes_id = list(graph_to_draw.nodes)

    # Crea un dizionario delle posizioni dei nodi nel grafo, utilizzando le coordinate di latitudine e longitudine
    transformer = Transformer.from_crs('epsg:4326', 'epsg:32632', always_xy=True)
    positions = [(graph_to_draw.nodes[node_id]['latitude'], graph_to_draw.nodes[node_id]['longitude']) for node_id in nodes_id]
    positions_utm = np.array([transformer.transform(x[1], x[0]) for x in positions])
    pos = {nodes_id[i]: positions_utm[i] for i in range(len(nodes_id))}

    # Disegna il network ottimizzato
    nx.draw_networkx(graph_to_draw, pos=pos, ax=ax, **options)

    # Disegna i confini della Germania
    germany_boundary.boundary.plot(ax=ax, linewidth=2, color='red', zorder=3)

    # Imposta i titoli e visualizza il grafico
    plt.title(title, fontsize=15)
    plt.show()


def calculate_metrics(graph):
    metrics = {}

    # Calcolo delle metriche di base
    metrics["density"] = nx.density(graph)
    metrics["average_distance"] = np.mean([edge[2]['weight'] for edge in graph.edges(data=True)]) / 1000  # Converti in km
    # metrics["diameter"] = nx.diameter(graph, e=None, usebounds=False)
    metrics["diameter"] = nx.approximation.diameter(graph)
    # metrics["average_clustering"] = nx.average_clustering(graph)
    metrics["average_clustering"] = nx.approximation.average_clustering(graph)

    # Calcolo delle metriche di centralità
    # degree_centrality = nx.degree_centrality(graph)
    # closeness_centrality = nx.closeness_centrality(graph)
    # betweenness_centrality = nx.betweenness_centrality(graph)

    # metrics["average_degree_centrality"] = np.mean(list(degree_centrality.values()))
    # metrics["average_closeness_centrality"] = np.mean(list(closeness_centrality.values()))
    # metrics["average_betweenness_centrality"] = np.mean(list(betweenness_centrality.values()))

    return metrics

def weighted_mean(values, weights):
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)

def calculate_weighted_metrics(graph, year):
    components = [graph.subgraph(cc) for cc in nx.connected_components(graph) if len(cc) >= 2]

    # metric_sums = {"density": 0.0, "average_distance": 0.0, "diameter": 0, "average_clustering": 0.0,
    #                "average_degree_centrality": 0.0, "average_closeness_centrality": 0.0, "average_betweenness_centrality": 0.0}
    
    metric_sums = {"density": 0.0, "average_distance": 0.0, "diameter": 0, "average_clustering": 0.0}
    
    total_weight = 0
    subnetwork_sizes = []
    for component in components:
        metrics = calculate_metrics(component)
        weight = component.number_of_nodes()
        total_weight += weight
        for metric, value in metrics.items():
            metric_sums[metric] += value * weight
        subnetwork_sizes.append(weight)

    weighted_metrics = {metric: value / total_weight for metric, value in metric_sums.items()}
    weighted_metrics["year"] = year
    weighted_metrics["total_nodes"] = graph.number_of_nodes()
    weighted_metrics["subnetwork_sizes"] = subnetwork_sizes

    return weighted_metrics

# import requests
# import math
# import sqlite3
# from concurrent.futures import ThreadPoolExecutor, as_completed

# # Aggiungi questo parametro per controllare il numero di thread
# NUM_WORKERS = 10

# def haversine_distance(lat1, lon1, lat2, lon2):
#     R = 6371  # raggio della Terra in km

#     dLat = math.radians(lat2 - lat1)
#     dLon = math.radians(lon2 - lon1)
#     lat1 = math.radians(lat1)
#     lat2 = math.radians(lat2)

#     a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.sin(dLon / 2) * math.sin(dLon / 2) * math.cos(lat1) * math.cos(lat2)
#     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c

# def get_osrm_distance(lat1, lon1, lat2, lon2):
#     # ... (mantieni il codice esistente fino alla richiesta API)

#     approx_distance = 1000 * haversine_distance(lat1, lon1, lat2, lon2)

#     if approx_distance <= 100:
#         url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
#         return url, (lat1, lon1, lat2, lon2)
#     else:
#         return approx_distance

# def process_api_responses(urls_and_coordinates):
#     with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
#         # Prepara un dizionario per memorizzare i risultati delle richieste
#         distance_results = {}

#         # Effettua le richieste in parallelo
#         futures = {executor.submit(requests.get, url): coordinates for url, coordinates in urls_and_coordinates}

#         for future in as_completed(futures):
#             coordinates = futures[future]
#             try:
#                 response = future.result()
#                 if response.status_code == 200:
#                     data = response.json()
#                     if 'routes' in data and len(data['routes']) > 0:
#                         distance = data['routes'][0]['distance']
#                         distance_results[coordinates] = distance
#             except Exception as e:
#                 print(f"Error processing coordinates {coordinates}: {e}")

#         return distance_results

# # Esempio di utilizzo:
# # urls_and_coordinates = [(url1, coords1), (url2, coords2), ...]
# # distances = process_api_responses(urls_and_coordinates)
