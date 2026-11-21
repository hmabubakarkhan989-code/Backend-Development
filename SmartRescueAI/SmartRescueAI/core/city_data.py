"""Simulated Islamabad-inspired city data (coordinates are approximate).

Road cost = straight-line km x ROAD_FACTOR x traffic multiplier (>= 1.0).
Because cost >= straight-line distance, the A* heuristic stays admissible.
"""
from .search_engine import Graph, haversine_km

ROAD_FACTOR = 1.3

# id: (name, latitude, longitude)
NODES = {
    "DK": ("Daman-e-Koh", 33.7438, 73.0553),
    "FM": ("Faisal Mosque", 33.7295, 73.0372),
    "F6": ("F-6 Markaz", 33.7290, 73.0763),
    "F7": ("F-7 Markaz", 33.7215, 73.0560),
    "G6": ("G-6 Markaz", 33.7140, 73.0780),
    "BA": ("Blue Area", 33.7100, 73.0600),
    "AB": ("Aabpara", 33.7090, 73.0680),
    "G9": ("G-9 Markaz", 33.6990, 73.0370),
    "G10": ("G-10 Markaz", 33.6820, 73.0130),
    "ZP": ("Zero Point", 33.6938, 73.0651),
    "I8": ("I-8 Markaz", 33.6660, 73.0750),
    "FZ": ("Faizabad", 33.6590, 73.0830),
    "PIMS": ("PIMS Hospital Area", 33.7040, 73.0500),
    "POLY": ("Polyclinic Area", 33.7075, 73.0720),
    "SHIFA": ("Shifa Hospital Area", 33.6800, 73.0480),
}

# (node A, node B, traffic multiplier)
EDGES = [
    ("DK", "FM", 1.0), ("DK", "F6", 1.1), ("FM", "F6", 1.2), ("FM", "F7", 1.1),
    ("F6", "F7", 1.3), ("F6", "G6", 1.2), ("F7", "BA", 1.4), ("F7", "G9", 1.2),
    ("G6", "POLY", 1.1), ("G6", "AB", 1.2), ("BA", "AB", 1.5), ("AB", "POLY", 1.2),
    ("BA", "PIMS", 1.3), ("BA", "ZP", 1.4), ("AB", "ZP", 1.3), ("PIMS", "ZP", 1.2),
    ("PIMS", "G9", 1.1), ("G9", "G10", 1.0), ("G9", "SHIFA", 1.1),
    ("PIMS", "SHIFA", 1.2), ("G10", "SHIFA", 1.1), ("ZP", "I8", 1.2),
    ("SHIFA", "I8", 1.1), ("I8", "FZ", 1.0), ("ZP", "FZ", 1.3),
]

AMBULANCES = {
    "A1": {"id": "A1", "name": "Ambulance 01", "node": "F6", "available": True},
    "A2": {"id": "A2", "name": "Ambulance 02", "node": "G6", "available": True},
    "A3": {"id": "A3", "name": "Ambulance 03", "node": "ZP", "available": True},
    "A4": {"id": "A4", "name": "Ambulance 04", "node": "G10", "available": False},
    "A5": {"id": "A5", "name": "Ambulance 05", "node": "I8", "available": True},
}

HOSPITALS = {
    "H1": {"id": "H1", "name": "PIMS", "node": "PIMS", "beds": 12, "capacity": 40,
           "specialties": ["trauma", "cardiac", "general"]},
    "H2": {"id": "H2", "name": "Polyclinic", "node": "POLY", "beds": 2, "capacity": 25,
           "specialties": ["general", "maternity"]},
    "H3": {"id": "H3", "name": "Shifa International", "node": "SHIFA", "beds": 8, "capacity": 30,
           "specialties": ["cardiac", "burns", "maternity"]},
    "H4": {"id": "H4", "name": "Kulsum International", "node": "BA", "beds": 5, "capacity": 20,
           "specialties": ["general", "trauma"]},
}

EMERGENCY_TYPES = {
    "Cardiac Arrest": "cardiac",
    "Road Accident": "trauma",
    "Burn / Fire Injury": "burns",
    "Maternity Emergency": "maternity",
    "General Medical": "general",
}


def build_graph():
    graph = Graph()
    for nid, (name, lat, lon) in NODES.items():
        graph.add_node(nid, name, lat, lon)
    for a, b, traffic in EDGES:
        km = haversine_km(*graph.coords[a], *graph.coords[b])
        graph.add_edge(a, b, round(km * ROAD_FACTOR * traffic, 3))
    return graph
