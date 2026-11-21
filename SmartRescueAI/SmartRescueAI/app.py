"""SmartRescue AI - Flask application (routes only; logic lives in core/)."""
import csv
import io

from flask import Flask, Response, jsonify, render_template, request

from core import database
from core.city_data import EMERGENCY_TYPES, build_graph
from core.dispatch import rank_hospitals, select_ambulance
from core.search_engine import ALGORITHMS, run_all

app = Flask(__name__)
graph = build_graph()
database.init_db()
for _a, _b in database.get_blocked():          # restore saved road closures
    graph.blocked.add(frozenset((_a, _b)))


def error(message, status=400):
    return jsonify({"error": message}), status


@app.route("/")
def index():
    return render_template("index.html")


# ---------- data for the dashboard ----------
@app.route("/api/network")
def network():
    return jsonify({
        "nodes": {n: {"name": graph.names[n], "lat": c[0], "lng": c[1]}
                  for n, c in graph.coords.items()},
        "edges": [{"a": a, "b": b, "cost": round(cost, 2), "blocked": graph.is_blocked(a, b)}
                  for a in graph.adj for b, cost in graph.adj[a].items() if a < b],
        "ambulances": list(database.get_ambulances().values()),
        "hospitals": list(database.get_hospitals().values()),
        "emergency_types": list(EMERGENCY_TYPES),
        "algorithms": list(ALGORITHMS),
    })


@app.route("/api/summary")
def summary():
    ambs, hosps = database.get_ambulances(), database.get_hospitals()
    return jsonify({
        "stats": database.stats(),
        "ambulances_available": sum(a["available"] for a in ambs.values()),
        "ambulances_total": len(ambs),
        "beds_free": sum(h["beds"] for h in hosps.values()),
        "beds_total": sum(h["capacity"] for h in hosps.values()),
        "blocked_roads": len(graph.blocked),
    })


@app.route("/api/incidents")
def incidents():
    limit = min(request.args.get("limit", 200, type=int), 1000)
    items = database.list_incidents(request.args.get("status"), request.args.get("q", "").strip(), limit)
    return jsonify({"items": items})


@app.route("/api/export.csv")
def export_csv():
    out = io.StringIO()
    cols = ["id", "created_at", "resolved_at", "status", "emergency_type", "location",
            "algorithm", "ambulance", "hospital", "total_cost"]
    writer = csv.writer(out)
    writer.writerow(cols)
    for item in database.list_incidents(limit=100000):
        writer.writerow([item[c] for c in cols])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=smartrescue_incidents.csv"})


# ---------- actions ----------
@app.route("/api/dispatch", methods=["POST"])
def dispatch():
    data = request.get_json(silent=True) or {}
    node, etype, algo = data.get("location"), data.get("emergency_type"), data.get("algorithm")
    if node not in graph.coords:
        return error("Please choose a valid incident location.")
    if etype not in EMERGENCY_TYPES:
        return error("Please choose a valid emergency type.")
    if algo not in ALGORITHMS:
        return error("Please choose a valid algorithm.")

    picked = select_ambulance(graph, database.get_ambulances(), node)
    if picked is None:
        return error("No available ambulance can reach this location (check blocked roads).", 409)
    amb, _ = picked
    to_incident = ALGORITHMS[algo](graph, amb["node"], node)

    ranked = rank_hospitals(graph, database.get_hospitals(), node, EMERGENCY_TYPES[etype])
    if not ranked:
        return error("No hospital with free beds is reachable from this location.", 409)
    hosp = ranked[0]["hospital"]
    to_hospital = ALGORITHMS[algo](graph, node, hosp["node"])

    total = round((to_incident["cost"] or 0) + (to_hospital["cost"] or 0), 2)
    payload = {
        "incident": {"node": node, "name": graph.names[node], "type": etype},
        "ambulance": amb, "hospital": hosp, "algorithm": algo,
        "route_to_incident": to_incident, "route_to_hospital": to_hospital,
        "total_cost": total,
        "hospital_ranking": [{"name": r["hospital"]["name"], "score": r["score"]} for r in ranked],
        "comparison": run_all(graph, amb["node"], node),
    }
    database.add_incident(etype, graph.names[node], algo, amb, hosp, total, payload)
    database.set_ambulance(amb["id"], False)
    database.change_beds(hosp["id"], -1)
    return jsonify(payload)


@app.route("/api/incidents/<int:inc_id>/resolve", methods=["POST"])
def resolve(inc_id):
    inc = database.resolve_incident(inc_id)
    if inc is None:
        return error("Incident not found or already resolved.", 404)
    hosp = database.get_hospitals().get(inc["hospital_id"])
    database.set_ambulance(inc["ambulance_id"], True, hosp["node"] if hosp else None)
    return jsonify({"ok": True})


@app.route("/api/roads/toggle", methods=["POST"])
def toggle_road():
    data = request.get_json(silent=True) or {}
    a, b = data.get("a"), data.get("b")
    if not graph.has_edge(a, b):
        return error("That road does not exist.")
    blocked = graph.toggle_block(a, b)
    database.set_block(a, b, blocked)
    return jsonify({"blocked": blocked})


@app.route("/api/ambulances/<amb_id>/toggle", methods=["POST"])
def toggle_ambulance(amb_id):
    amb = database.get_ambulances().get(amb_id)
    if amb is None:
        return error("Ambulance not found.", 404)
    database.set_ambulance(amb_id, not amb["available"])
    return jsonify({"available": not amb["available"]})


@app.route("/api/hospitals/<hosp_id>/discharge", methods=["POST"])
def discharge(hosp_id):
    if hosp_id not in database.get_hospitals():
        return error("Hospital not found.", 404)
    database.change_beds(hosp_id, +1)
    return jsonify({"ok": True})


@app.route("/api/lab", methods=["POST"])
def lab():
    data = request.get_json(silent=True) or {}
    start, end = data.get("start"), data.get("end")
    if start not in graph.coords or end not in graph.coords:
        return error("Please choose two valid locations.")
    return jsonify({"results": run_all(graph, start, end)})


@app.route("/api/reset", methods=["POST"])
def reset():
    graph.clear_blocks()
    database.reset(bool((request.get_json(silent=True) or {}).get("clear_history")))
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
    
        
    
   
    
