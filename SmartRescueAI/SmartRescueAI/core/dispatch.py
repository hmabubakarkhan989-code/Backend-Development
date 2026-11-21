"""Dispatch rules: choose an ambulance and recommend a hospital."""
from .search_engine import astar

LOW_BED_LIMIT = 2        # hospitals with <= this many free beds are penalised
LOW_BED_PENALTY = 5.0    # added to the travel cost
SPECIALTY_BONUS = 3.0    # subtracted when the hospital matches the emergency


def select_ambulance(graph, ambulances, incident_node):
    """Nearest AVAILABLE ambulance by A* route cost. Returns (ambulance, route) or None."""
    best = None
    for amb in ambulances.values():
        if not amb["available"]:
            continue
        route = astar(graph, amb["node"], incident_node)
        if route["found"] and (best is None or route["cost"] < best[1]["cost"]):
            best = (amb, route)
    return best


def rank_hospitals(graph, hospitals, incident_node, specialty):
    """Hospitals with free beds, best first. Lower score = better.

    score = route cost (+ penalty if beds are low) (- bonus if specialty matches)
    """
    ranked = []
    for hosp in hospitals.values():
        if hosp["beds"] <= 0:
            continue
        route = astar(graph, incident_node, hosp["node"])
        if not route["found"]:
            continue
        score = route["cost"]
        if hosp["beds"] <= LOW_BED_LIMIT:
            score += LOW_BED_PENALTY
        if specialty in hosp["specialties"]:
            score -= SPECIALTY_BONUS
        ranked.append({"hospital": hosp, "route": route, "score": round(score, 2)})
    ranked.sort(key=lambda item: item["score"])
    return ranked
