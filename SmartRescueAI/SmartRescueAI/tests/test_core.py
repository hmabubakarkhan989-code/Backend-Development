"""Run with:  python -m unittest discover tests -v"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.city_data import AMBULANCES, HOSPITALS, build_graph  # noqa: E402
from core.dispatch import rank_hospitals, select_ambulance  # noqa: E402
from core.search_engine import ALGORITHMS, astar, bfs, run_all, ucs  # noqa: E402


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.g = build_graph()

    def test_every_algorithm_finds_valid_path(self):
        for name, algo in ALGORITHMS.items():
            r = algo(self.g, "F6", "SHIFA")
            self.assertTrue(r["found"], name)
            self.assertEqual(r["path"][0], "F6")
            self.assertEqual(r["path"][-1], "SHIFA")
            for a, b in zip(r["path"], r["path"][1:]):
                self.assertTrue(self.g.has_edge(a, b), f"{name}: {a}-{b} is not a road")

    def test_ucs_and_astar_are_optimal_and_equal(self):
        for start, goal in [("DK", "FZ"), ("G10", "POLY"), ("F6", "I8")]:
            u, a = ucs(self.g, start, goal), astar(self.g, start, goal)
            self.assertAlmostEqual(u["cost"], a["cost"], places=2)
            for r in run_all(self.g, start, goal):
                self.assertGreaterEqual(r["cost"], u["cost"] - 1e-6)

    def test_bfs_has_fewest_hops(self):
        b = bfs(self.g, "DK", "FZ")
        for r in run_all(self.g, "DK", "FZ"):
            self.assertLessEqual(b["hops"], r["hops"])

    def test_astar_visits_no_more_than_ucs(self):
        self.assertLessEqual(astar(self.g, "DK", "FZ")["visited"], ucs(self.g, "DK", "FZ")["visited"])

    def test_no_route_is_handled(self):
        for nbr in list(self.g.adj["DK"]):
            self.g.toggle_block("DK", nbr)
        for name, algo in ALGORITHMS.items():
            r = algo(self.g, "F6", "DK")
            self.assertFalse(r["found"], name)
            self.assertEqual(r["path"], [])

    def test_blocked_road_is_avoided(self):
        before = ucs(self.g, "FM", "F7")["path"]
        self.assertEqual(before, ["FM", "F7"])
        self.g.toggle_block("FM", "F7")
        after = ucs(self.g, "FM", "F7")
        self.assertTrue(after["found"])
        self.assertNotIn(["FM", "F7"], [after["path"][i:i + 2] for i in range(len(after["path"]) - 1)])


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.g = build_graph()
        self.amb = copy.deepcopy(AMBULANCES)
        self.hosp = copy.deepcopy(HOSPITALS)

    def test_unavailable_ambulance_never_selected(self):
        amb, _ = select_ambulance(self.g, self.amb, "G10")  # A4 is parked at G10 but busy
        self.assertNotEqual(amb["id"], "A4")

    def test_nearest_available_ambulance_chosen(self):
        amb, _ = select_ambulance(self.g, self.amb, "F6")
        self.assertEqual(amb["id"], "A1")

    def test_no_ambulance_when_all_busy(self):
        for a in self.amb.values():
            a["available"] = False
        self.assertIsNone(select_ambulance(self.g, self.amb, "F6"))

    def test_full_hospital_is_skipped(self):
        self.hosp["H1"]["beds"] = 0
        names = [r["hospital"]["name"] for r in rank_hospitals(self.g, self.hosp, "PIMS", "general")]
        self.assertNotIn("PIMS", names)

    def test_specialty_and_low_beds_affect_score(self):
        ranked = {r["hospital"]["id"]: r["score"] for r in rank_hospitals(self.g, self.hosp, "G6", "maternity")}
        route_cost = astar(self.g, "G6", "POLY")["cost"]
        self.assertAlmostEqual(ranked["H2"], route_cost + 5.0 - 3.0, places=1)  # low beds + specialty


if __name__ == "__main__":
    unittest.main()
