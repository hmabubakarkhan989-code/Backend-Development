"""Tests for the website API and saved data. Uses a temporary database."""
import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SMARTRESCUE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as app_module  # noqa: E402
from core import database  # noqa: E402


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.client.post("/api/reset", json={"clear_history": True})

    def dispatch(self, location="FZ", etype="Cardiac Arrest", algo="A*"):
        return self.client.post("/api/dispatch", json={
            "location": location, "emergency_type": etype, "algorithm": algo})

    def test_dispatch_is_saved_and_updates_state(self):
        r = self.dispatch().get_json()
        items = self.client.get("/api/incidents").get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "Active")
        self.assertEqual(items[0]["payload"]["incident_id"], r["incident_id"])
        ambs = database.get_ambulances()
        self.assertFalse(ambs[r["ambulance"]["id"]]["available"])      # now busy
        hosp = database.get_hospitals()[r["hospital"]["id"]]
        self.assertEqual(hosp["beds"], r["hospital"]["beds"] - 1)      # bed used

    def test_data_survives_restart(self):
        self.client.post("/api/roads/toggle", json={"a": "FM", "b": "F7"})
        self.dispatch()
        importlib.reload(database)                      # simulates closing and reopening the app
        database.init_db()
        self.assertIn(("F7", "FM"), database.get_blocked())
        self.assertEqual(len(database.list_incidents()), 1)

    def test_resolve_frees_ambulance_at_hospital(self):
        r = self.dispatch().get_json()
        res = self.client.post(f"/api/incidents/{r['incident_id']}/resolve")
        self.assertEqual(res.status_code, 200)
        amb = database.get_ambulances()[r["ambulance"]["id"]]
        self.assertTrue(amb["available"])
        self.assertEqual(amb["node"], r["hospital"]["node"])
        self.assertEqual(self.client.post(f"/api/incidents/{r['incident_id']}/resolve").status_code, 404)

    def test_offline_ambulance_never_dispatched(self):
        for amb_id in ("A1", "A2", "A3", "A5"):
            self.client.post(f"/api/ambulances/{amb_id}/toggle")
        self.assertEqual(self.dispatch().status_code, 409)

    def test_blocked_road_persists_and_is_used(self):
        self.client.post("/api/roads/toggle", json={"a": "I8", "b": "FZ"})
        self.assertEqual(self.client.get("/api/summary").get_json()["blocked_roads"], 1)
        route = self.dispatch("FZ").get_json()["route_to_incident"]["path"]
        self.assertNotIn(["I8", "FZ"], [route[i:i + 2] for i in range(len(route) - 1)])

    def test_discharge_never_exceeds_capacity(self):
        for _ in range(60):
            self.client.post("/api/hospitals/H1/discharge")
        h = database.get_hospitals()["H1"]
        self.assertEqual(h["beds"], h["capacity"])

    def test_lab_and_csv_and_stats(self):
        lab = self.client.post("/api/lab", json={"start": "DK", "end": "FZ"}).get_json()["results"]
        self.assertEqual([x["algorithm"] for x in lab], ["BFS", "DFS", "UCS", "A*"])
        self.dispatch()
        csv_text = self.client.get("/api/export.csv").get_data(as_text=True)
        self.assertIn("emergency_type", csv_text.splitlines()[0])
        self.assertEqual(len(csv_text.splitlines()), 2)
        self.assertEqual(self.client.get("/api/summary").get_json()["stats"]["total"], 1)

    def test_invalid_input_rejected(self):
        self.assertEqual(self.dispatch(location="XX").status_code, 400)
        self.assertEqual(self.client.post("/api/lab", json={"start": "XX", "end": "FZ"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
