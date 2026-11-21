"""SQLite storage. Incidents, fleet, hospitals and road closures all persist between runs."""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .city_data import AMBULANCES, HOSPITALS

DB_PATH = Path(os.environ.get(
    "SMARTRESCUE_DB", Path(__file__).resolve().parent.parent / "smartrescue_v2.db"))


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _seed(c):
    c.execute("DELETE FROM ambulances")
    c.execute("DELETE FROM hospitals")
    c.executemany("INSERT INTO ambulances VALUES (?,?,?,?)", [
        (a["id"], a["name"], a["node"], int(a["available"])) for a in AMBULANCES.values()])
    c.executemany("INSERT INTO hospitals VALUES (?,?,?,?,?,?)", [
        (h["id"], h["name"], h["node"], h["beds"], h["capacity"], ",".join(h["specialties"]))
        for h in HOSPITALS.values()])


def init_db():
    with _connect() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL, resolved_at TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                emergency_type TEXT NOT NULL, location TEXT NOT NULL, algorithm TEXT NOT NULL,
                ambulance_id TEXT NOT NULL, ambulance TEXT NOT NULL,
                hospital_id TEXT NOT NULL, hospital TEXT NOT NULL,
                total_cost REAL NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS ambulances (
                id TEXT PRIMARY KEY, name TEXT, node TEXT, available INTEGER);
            CREATE TABLE IF NOT EXISTS hospitals (
                id TEXT PRIMARY KEY, name TEXT, node TEXT, beds INTEGER, capacity INTEGER,
                specialties TEXT);
            CREATE TABLE IF NOT EXISTS blocked_roads (
                a TEXT, b TEXT, PRIMARY KEY (a, b));""")
        if c.execute("SELECT COUNT(*) FROM ambulances").fetchone()[0] == 0:
            _seed(c)


# ---------- fleet and hospitals ----------
def get_ambulances():
    with _connect() as c:
        return {r["id"]: {**dict(r), "available": bool(r["available"])}
                for r in c.execute("SELECT * FROM ambulances ORDER BY id")}


def get_hospitals():
    with _connect() as c:
        return {r["id"]: {**dict(r), "specialties": r["specialties"].split(",")}
                for r in c.execute("SELECT * FROM hospitals ORDER BY id")}


def set_ambulance(amb_id, available, node=None):
    with _connect() as c:
        if node:
            c.execute("UPDATE ambulances SET available=?, node=? WHERE id=?",
                      (int(available), node, amb_id))
        else:
            c.execute("UPDATE ambulances SET available=? WHERE id=?", (int(available), amb_id))


def change_beds(hosp_id, delta):
    with _connect() as c:
        c.execute("UPDATE hospitals SET beds = MAX(0, MIN(capacity, beds + ?)) WHERE id=?",
                  (delta, hosp_id))


# ---------- road closures ----------
def get_blocked():
    with _connect() as c:
        return [(r["a"], r["b"]) for r in c.execute("SELECT a, b FROM blocked_roads")]


def set_block(a, b, blocked):
    a, b = sorted((a, b))
    with _connect() as c:
        if blocked:
            c.execute("INSERT OR IGNORE INTO blocked_roads VALUES (?,?)", (a, b))
        else:
            c.execute("DELETE FROM blocked_roads WHERE a=? AND b=?", (a, b))


# ---------- incidents ----------
def add_incident(emergency_type, location, algorithm, amb, hosp, total_cost, payload):
    with _connect() as c:
        cur = c.execute(
            "INSERT INTO incidents (created_at, emergency_type, location, algorithm, ambulance_id,"
            " ambulance, hospital_id, hospital, total_cost) VALUES (?,?,?,?,?,?,?,?,?)",
            (_now(), emergency_type, location, algorithm, amb["id"], amb["name"],
             hosp["id"], hosp["name"], total_cost))
        payload["incident_id"] = cur.lastrowid
        c.execute("UPDATE incidents SET payload_json=? WHERE id=?",
                  (json.dumps(payload), cur.lastrowid))
        return cur.lastrowid


def list_incidents(status=None, q=None, limit=200):
    sql, args = "SELECT * FROM incidents WHERE 1=1", []
    if status in ("Active", "Resolved"):
        sql += " AND status=?"
        args.append(status)
    if q:
        sql += (" AND (emergency_type LIKE ? OR location LIKE ? OR ambulance LIKE ?"
                " OR hospital LIKE ?)")
        args += [f"%{q}%"] * 4
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _connect() as c:
        items = []
        for r in c.execute(sql, args):
            row = dict(r)
            row["payload"] = json.loads(row.pop("payload_json"))
            items.append(row)
        return items


def resolve_incident(inc_id):
    """Mark an ACTIVE incident resolved. Returns the incident row, or None."""
    with _connect() as c:
        row = c.execute("SELECT * FROM incidents WHERE id=? AND status='Active'",
                        (inc_id,)).fetchone()
        if row:
            c.execute("UPDATE incidents SET status='Resolved', resolved_at=? WHERE id=?",
                      (_now(), inc_id))
        return dict(row) if row else None


def stats():
    with _connect() as c:
        row = c.execute("SELECT COUNT(*) AS n, SUM(status='Active') AS active,"
                        " AVG(total_cost) AS avg FROM incidents").fetchone()
        by_type = {r["emergency_type"]: r["n"] for r in c.execute(
            "SELECT emergency_type, COUNT(*) AS n FROM incidents GROUP BY emergency_type")}
        by_algo = {r["algorithm"]: r["n"] for r in c.execute(
            "SELECT algorithm, COUNT(*) AS n FROM incidents GROUP BY algorithm")}
    return {"total": row["n"], "active": row["active"] or 0,
            "avg_cost": round(row["avg"], 2) if row["avg"] else 0,
            "by_type": by_type, "by_algorithm": by_algo}


def reset(clear_history=False):
    with _connect() as c:
        c.execute("DELETE FROM blocked_roads")
        _seed(c)
        if clear_history:
            c.execute("DELETE FROM incidents")
        else:
            c.execute("UPDATE incidents SET status='Resolved', resolved_at=? WHERE status='Active'",
                      (_now(),))
