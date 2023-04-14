import sqlite3
import requests

def get_osrm_distance(lat1, lon1, lat2, lon2):
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