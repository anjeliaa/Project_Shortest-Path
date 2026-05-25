from flask import Flask, request, jsonify
from flask_cors import CORS
import osmnx as ox
import networkx as nx
import math

app = Flask(__name__)
CORS(app)

ox.settings.use_cache = False

# =====================================================================
# POOL TITIK KOORDINAT (KUNCI PRESISI INTERNAL KAMPUS UNIB)
# =====================================================================
locations = {
    "Gerbang Utama": (-3.760568, 102.272638),
    "Gedung Layanan Terpadu": (-3.758209, 102.272176), 
    "Gerbang Kedua (Akses Gang Juwita)": (-3.759452, 102.275033),
    "Laboratorium Fisika": (-3.755810, 102.273885),
    "Gedung Bersama V": (-3.755753, 102.276481),
    "Gedung Bersama III": (-3.756111, 102.276192),
    "Gedung Serba Guna": (-3.757851, 102.276916),
    "Dekanat Teknik": (-3.758555, 102.27667),
    "Laboratorium Teknik": (-3.758911, 102.276650),
    "Gerbang Keluar": (-3.759387, 102.276240)
}

print("Mengunduh data graf murni Universitas Bengkulu...")
center_point = (-3.7575, 102.2755)
base_drive_graph = ox.graph_from_point(center_point, dist=1500, network_type="all")
base_walk_graph = ox.graph_from_point(center_point, dist=1500, network_type="walk")


# =========================================
# HELPER FUNCTIONS FOR AI ROUTING
# =========================================
def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    y = math.sin(dLon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
    bearing = math.atan2(y, x)
    return (math.degrees(bearing) + 360) % 360


def generate_smart_instructions(route, G, start, destination, vehicle):
    instructions = []

    if vehicle == "drive":
        instructions.append(f"Mulai berkendara dari <b>{start}</b>. Patuhi batas kecepatan lingkungan kampus.")
    else:
        instructions.append(f"Mulai berjalan kaki dari <b>{start}</b>. Gunakan fasilitas trotoar jalan.")

    for i in range(len(route) - 2):
        n1, n2, n3 = route[i], route[i+1], route[i+2]
        lat1, lon1 = G.nodes[n1]['y'], G.nodes[n1]['x']
        lat2, lon2 = G.nodes[n2]['y'], G.nodes[n2]['x']
        lat3, lon3 = G.nodes[n3]['y'], G.nodes[n3]['x']
        
        b1 = calculate_bearing(lat1, lon1, lat2, lon2)
        b2 = calculate_bearing(lat2, lon2, lat3, lon3)
        angle_diff = (b2 - b1 + 180) % 360 - 180
        
        if angle_diff < -45 and angle_diff >= -120:
            instructions.append("Belok <b>kiri</b> di persimpangan jalan.")
        elif angle_diff > 45 and angle_diff <= 120:
            instructions.append("Belok <b>kanan</b> di persimpangan jalan.")
        elif angle_diff <= -120 or angle_diff >= 120:
            instructions.append("Lakukan gerakan <b>putar balik arah</b>.")

    instructions.append(f"🏁 Tiba di lokasi tujuan akhir: <b>{destination}</b>.")
    
    cleaned_instructions = []
    for ins in instructions:
        if not cleaned_instructions or ins != cleaned_instructions[-1]:
            cleaned_instructions.append(ins)
    return cleaned_instructions


# =====================================================================
# GRAPH MANIPULATION (CONSTRAINTS ENGINE)
# =====================================================================
def apply_constraints(G, is_drive=False):
    graph_copy = G.copy()
    if is_drive:
        # Penalty area parkir perpustakaan
        for u, v, key, data in graph_copy.edges(keys=True, data=True):
            u_lat = graph_copy.nodes[u]['y']
            u_lng = graph_copy.nodes[u]['x']
            
            di_dalam_area_perpus = (-3.757300 <= u_lat <= -3.756200) and (102.274000 <= u_lng <= 102.275500)
            if di_dalam_area_perpus:
                data['length'] = 9999999

        # Regulasi One-Way Gang Juwita ke GSG
        node_keluar_juwita = ox.distance.nearest_nodes(graph_copy, 102.275033, -3.759452)
        node_arah_gsg = ox.distance.nearest_nodes(graph_copy, 102.275464, -3.758832)
        if graph_copy.has_edge(node_keluar_juwita, node_arah_gsg):
            graph_copy.edges[node_keluar_juwita, node_arah_gsg, 0]['length'] = 9999999

    return graph_copy


graphs = {
    "walk": base_walk_graph, 
    "drive": apply_constraints(base_drive_graph, is_drive=True)
}
print("Komponen Graf AI Sukses Disinkronkan Sempurna!")


# =========================================
# ROUTE API ENDPOINT
# =========================================
@app.route('/route', methods=['POST'])
def route():
    data = request.json
    start, destination, vehicle = data['start'], data['destination'], data['vehicle']
    
    if start not in locations or destination not in locations:
        return jsonify({"status": "error", "message": "Titik lokasi tidak terdaftar dalam sistem."}), 400
        
    G = graphs[vehicle]

    # Validasi Logis Regulasi Akses Berkendara Kampus
    if vehicle == "drive":
        if destination == "Gerbang Utama":
            return jsonify({
                "status": "error",
                "message": "Akses ditolak! Kendaraan dilarang keluar melewati Gerbang Utama (Khusus akses masuk)."
            }), 400
            
        if destination == "Gerbang Kedua (Akses Gang Juwita)":
            return jsonify({
                "status": "error",
                "message": "Akses ditolak! Gerbang Kedua (Gang Juwita) hanya berlaku untuk akses masuk kendaraan."
            }), 400

        if start == "Gerbang Keluar":
            return jsonify({
                "status": "error",
                "message": "Akses ditolak! Kendaraan dilarang masuk dari arah Gerbang Keluar."
            }), 400

    # Pencarian node terdekat OSMnx (Urutan koordinat: X=Lng, Y=Lat)
    orig_node = ox.distance.nearest_nodes(G, locations[start][1], locations[start][0])
    dest_node = ox.distance.nearest_nodes(G, locations[destination][1], locations[destination][0])

    try:
        route = nx.astar_path(G, orig_node, dest_node, weight='length')
        path = [{"lat": G.nodes[node]['y'], "lng": G.nodes[node]['x']} for node in route]
        
        distance = nx.path_weight(G, route, weight='length')
        
        if distance >= 9999999:
            raise nx.NetworkXNoPath
            
        speed = 1.4 if vehicle == "walk" else 8.0
        duration = max(1, round((distance / speed) / 60))
        instructions = generate_smart_instructions(route, G, start, destination, vehicle)

        return jsonify({
            "status": "success",
            "path": path,
            "distance": round(distance),
            "duration": duration,
            "instructions": instructions
        })
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return jsonify({
            "status": "error",
            "message": "Rute terblokir buntu! Lintasan berkendara melanggar batas regulasi atau jalan satu arah."
        }), 400

if __name__ == '__main__':
    app.run(debug=True)