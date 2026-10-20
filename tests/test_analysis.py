"""Analytic expectations are independent of the production detection output."""

import copy
import csv
import json
import math
import random
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from airspace.analysis import (
    ERROR_KEYS, Interval, _distance_metrics, _norm_intervals, analyze_all,
    intersect_intervals, load_inputs, load_rules, separation_intervals,
    strict_quadratic_intervals, write_reports,
)


ROOT = Path(__file__).resolve().parents[1]


def flight(flight_id="A", x=0, y=0, z=6000, vx=220, vy=0, vz=0):
    return dict(flight_id=flight_id, x_m=x, y_m=y, alt_m=z, vx_mps=vx, vy_mps=vy, vz_mps=vz)


class GeometryTests(unittest.TestCase):
    def assert_intervals(self, intervals, expected):
        self.assertEqual(len(intervals), len(expected))
        for actual, wanted in zip(intervals, expected):
            if isinstance(wanted, dict):
                wanted = tuple(wanted[key] for key in ("start_s", "end_s", "start_inclusive", "end_inclusive"))
            self.assertAlmostEqual(actual.start_s, wanted[0], places=11)
            self.assertAlmostEqual(actual.end_s, wanted[1], places=11)
            self.assertEqual((actual.start_inclusive, actual.end_inclusive), wanted[2:])

    def test_independent_analytic_fixture(self):
        fixture = json.loads((ROOT / "tests/fixtures/detection_examples.json").read_text())
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                self.assert_intervals(separation_intervals(case["a"], case["b"], case["horizontal_m"],
                    case["vertical_m"], case["duration_s"]), case["expected_intervals"])

    def test_conflict_between_integer_steps(self):
        a, b = flight(x=-100), flight("B", vx=-220)
        self.assert_intervals(separation_intervals(a, b, 10, 3, 2), [(90 / 440, 110 / 440, False, False)])
        intervals = separation_intervals(a, b, 10, 3, 2)
        self.assertFalse(any(intervals[0].contains(t) for t in (0, 1, 2)))

    def test_parallel_zero_relative_and_absolute_speed(self):
        for speed in (0, 220):
            a, b = flight(vx=speed), flight("B", x=5, vx=speed)
            self.assert_intervals(separation_intervals(a, b, 10, 3, 20), [(0, 20, True, True)])
            b["x_m"] = 10
            self.assertEqual(separation_intervals(a, b, 10, 3, 20), [])

    def test_t0_root_open_and_continuing_at_horizon(self):
        a, b = flight(x=10, vx=-1), flight("B", vx=0)
        self.assert_intervals(separation_intervals(a, b, 10, 3, 15), [(0, 15, False, True)])
        self.assertFalse(separation_intervals(a, b, 10, 3, 15)[0].contains(0))

    def test_enters_only_after_horizon(self):
        a, b = flight(x=20, vx=-1), flight("B", vx=0)
        self.assertEqual(separation_intervals(a, b, 10, 3, 10), [])
        self.assert_intervals(separation_intervals(a, b, 10, 3, 15), [(10, 15, False, True)])

    def test_tangency_and_near_tangency_no_physical_epsilon(self):
        for y, expected in ((10, 0), (10 + 1e-10, 0), (10 - 1e-10, 1)):
            intervals = _norm_intervals((-10, y), (1, 0), (10, 0), 20)
            self.assertEqual(len(intervals), expected)

    def test_vertical_equality_safe(self):
        a, b = flight(), flight("B", z=6300)
        self.assertEqual(separation_intervals(a, b, 10, 300, 20), [])
        self.assert_intervals(separation_intervals(a, b, 10, 304.8, 20), [(0, 20, True, True)])

    def test_horizontal_and_vertical_minima_do_not_prove_simultaneity(self):
        a, b = flight(vx=1, z=6010, vz=-1), flight("B", vx=0)
        self.assertEqual(separation_intervals(a, b, 2, 2, 20), [])
        # On one actual event the component minima can also have different times.
        intervals = separation_intervals(a, b, 8, 8, 20)
        self.assert_intervals(intervals, [(2, 8, False, False)])
        metrics = _distance_metrics((0, 0, 10), (1, 0, -1), intervals[0])
        self.assertEqual(metrics["horizontal_min"], {"value_m": 2, "time_s": 2, "attained": False})
        self.assertEqual(metrics["vertical_min"], {"value_m": 2, "time_s": 8, "attained": False})
        self.assertAlmostEqual(metrics["distance_3d_min"]["time_s"], 5)
        self.assertTrue(metrics["distance_3d_min"]["attained"])

    def test_constant_metrics_use_interior_representative(self):
        metrics = _distance_metrics((5, 0, 2), (0, 0, 0), Interval(1, 3, False, False))
        for metric in metrics.values():
            self.assertEqual(metric["time_s"], 2)
            self.assertTrue(metric["attained"])

    def test_linear_zero_quadratic_and_constant_polynomials(self):
        self.assert_intervals(strict_quadratic_intervals(0, -2, 4, 5), [(2, 5, False, True)])
        self.assert_intervals(strict_quadratic_intervals(0, 2, -4, 5), [(0, 2, True, False)])
        self.assert_intervals(strict_quadratic_intervals(0, 0, -1, 5), [(0, 5, True, True)])
        self.assertEqual(strict_quadratic_intervals(0, 0, 0, 5), [])
        self.assertEqual(strict_quadratic_intervals(0, 0, 1, 5), [])
        # ||10+t|| < 1+t makes the quadratic coefficient exactly zero.
        self.assertEqual(_norm_intervals((10,), (1,), (1, 1), 20), [])
        self.assert_intervals(_norm_intervals((10,), (-1,), (1, 1), 20), [(4.5, 20, False, True)])

    def test_affine_growing_radius_negative_quadratic(self):
        # 10 < 1+3t is first true after t=3, although relative velocity is zero.
        self.assert_intervals(_norm_intervals((10, 0), (0, 0), (1, 3), 5), [(3, 5, False, True)])

    def test_two_roots_and_isolated_safe_point_not_merged(self):
        self.assert_intervals(strict_quadratic_intervals(-1, 4, -3, 4), [(0, 1, True, False), (3, 4, False, True)])
        self.assert_intervals(strict_quadratic_intervals(-1, 4, -4, 4), [(0, 2, True, False), (2, 4, False, True)])
        self.assertEqual(strict_quadratic_intervals(1, -4, 4, 4), [])
        intervals = intersect_intervals(strict_quadratic_intervals(-1, 4, -4, 4), [Interval(0, 4, True, True)])
        self.assertEqual(len(intervals), 2)
        self.assertFalse(any(interval.contains(2) for interval in intervals))

    def test_stable_small_root(self):
        result = strict_quadratic_intervals(1, -10**16, 1, 1)
        self.assertAlmostEqual(result[0].start_s / 1e-16, 1, places=14)
        self.assertEqual(result[0].end_s, 1)

    def test_initial_equality_with_growing_error_opens_at_zero(self):
        a, b = flight(), flight("B", x=10)
        errors = dict(zip(ERROR_KEYS, (0, 0, 1, 0)))
        self.assert_intervals(separation_intervals(a, b, 10, 3, 20, errors), [(0, 20, False, True)])

    def test_increasing_errors_include_prior_violation_sets(self):
        a, b = flight(x=-100, z=6030, vz=-1), flight("B", vx=210)
        previous = []
        for factor in (0, 0.5, 1, 2, 5):
            errors = dict(zip(ERROR_KEYS, (10 * factor, 2 * factor, factor, factor / 10)))
            current = separation_intervals(a, b, 20, 10, 20, errors)
            for interval in previous:
                self.assertTrue(any(larger.start_s <= interval.start_s and larger.end_s >= interval.end_s for larger in current))
            previous = current

    def test_fixed_seed_polynomial_oracle(self):
        rng = random.Random(1701)
        for unused in range(80):
            a, b, c = (rng.randint(-20, 20) for index in range(3))
            intervals = strict_quadratic_intervals(a, b, c, 10)
            for index in range(8):
                exact_t = Fraction(rng.randint(0, 10000), 1000)
                exact_sign = a * exact_t**2 + b * exact_t + c < 0
                self.assertEqual(any(interval.contains(float(exact_t)) for interval in intervals), exact_sign)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.flights = load_inputs(ROOT / "scenario.json")
        cls.rules = load_rules(ROOT / "rules.json")
        cls.analysis = analyze_all(cls.scenario, cls.flights, cls.rules)

    def synthetic(self, flights=None, duration=20):
        scenario, rules = copy.deepcopy(self.scenario), copy.deepcopy(self.rules)
        scenario["target"] = {"x_m": 1e7, "y_m": 1e7}
        scenario["hostile_object"].update(x_m=-1e7, y_m=-1e7)
        rules["duration_s"] = duration
        return scenario, flights or [flight()], rules

    def test_real_base_independent_pair_counts_and_initial_state(self):
        expected = {("metric", "nominal"): (12, 3, 5, 4, 0), ("feet_reference", "nominal"): (33, 24, 5, 4, 0),
                    ("metric", "bounded_stress"): (38, 24, 7, 5, 2), ("feet_reference", "bounded_stress"): (38, 24, 7, 5, 2)}
        for run in self.analysis["runs"]:
            if run["variant_id"] != "base":
                continue
            summary, counts = run["summary"], run["summary"]["counts_by_type"]
            self.assertEqual((summary["event_count"], summary["aircraft_pair_count"], counts["aircraft_threat"],
                counts["aircraft_target"], summary["initial_event_count"]), expected[(run["profile_id"], run["mode_id"])])
            self.assertEqual(counts["motion"], 0)
            self.assertTrue(run["motion_checks"]["all_pass"])
            if run["mode_id"] == "bounded_stress":
                initial = [event for event in run["events"] if event["initial_violation"]]
                self.assertEqual({event["participants"][0] for event in initial}, {"F031", "F040"})
                self.assertTrue(all(event["type"] == "altitude" for event in initial))

    def test_synthetic_ui_fixture_geometry(self):
        fixture = json.loads((ROOT / "tests/fixtures/analysis_example.json").read_text())
        actual = analyze_all(fixture["scenario"], fixture["flights"], fixture["rules"])
        for actual_run, wanted in zip(actual["runs"], fixture["analysis"]["runs"]):
            self.assertEqual(actual_run["id"], wanted["id"])
            self.assertEqual(len(actual_run["events"]), 1)
            event, expected = actual_run["events"][0], wanted["events"][0]
            for key in ("start_s", "end_s"):
                self.assertAlmostEqual(event[key], expected[key], places=11)
            self.assertEqual(event["thresholds"], expected["thresholds"])
            self.assertEqual(event["severity"], expected["severity"])

    def test_zero_error_stress_equals_nominal_geometry(self):
        scenario, flights, rules = self.synthetic([flight(x=-10000), flight("B", x=10000, vx=-220)])
        rules["modes"][1]["error_bounds"] = dict.fromkeys(ERROR_KEYS, 0)
        analysis = analyze_all(scenario, flights, rules)
        by_id = {run["id"]: run for run in analysis["runs"]}
        for profile in ("metric", "feet_reference"):
            for variant in rules["sensitivity"]["variants"]:
                nominal = by_id[profile + "__nominal__" + variant["id"]]
                stress = by_id[profile + "__bounded_stress__" + variant["id"]]
                self.assertEqual(nominal["summary"], stress["summary"])
                for a, b in zip(nominal["events"], stress["events"]):
                    for key in ("start_s", "end_s", "start_inclusive", "end_inclusive", "metrics", "thresholds"):
                        self.assertEqual(a[key], b[key])
                    self.assertEqual(b["severity"], "possible_violation")

    def test_all_events_schema_and_true_interior_representative(self):
        self.assertEqual(len(self.analysis["runs"]), 20)
        ids = set()
        for run in self.analysis["runs"]:
            self.assertEqual(len(run["motion_checks"]["checks"]), 40 * 6)
            self.assertEqual(set(run["summary"]["counts_by_type"]), set(("aircraft_aircraft", "aircraft_threat", "aircraft_target", "altitude", "motion")))
            for event in run["events"]:
                self.assertNotIn(event["id"], ids)
                ids.add(event["id"])
                self.assertLess(event["start_s"], event["representative_s"])
                self.assertLess(event["representative_s"], event["end_s"])
                self.assertEqual(event["initial_violation"], event["start_s"] == 0 and event["start_inclusive"])
                self.assertEqual(event["continues_at_horizon"], event["end_s"] == 1200 and event["end_inclusive"])
                self.assertEqual(event["severity"], "nominal_violation" if run["mode_id"] == "nominal" else "possible_violation")
                for key in ("horizontal", "vertical", "radius", "error_vertical"):
                    if key in event["thresholds"]:
                        self.assertEqual(set(event["thresholds"][key]), {"intercept_m", "slope_mps"})
                if event["type"] == "aircraft_target":
                    self.assertEqual(event["rule_id"], "target_sphere")
                    self.assertEqual(set(event["metrics"]), {"horizontal_min", "vertical_min", "distance_3d_min"})

    def test_affine_thresholds_and_error_reference_time(self):
        run = next(run for run in self.analysis["runs"] if run["id"] == "metric__bounded_stress__base")
        pair = next(event for event in run["events"] if event["type"] == "aircraft_aircraft")
        threat = next(event for event in run["events"] if event["type"] == "aircraft_threat")
        target = next(event for event in run["events"] if event["type"] == "aircraft_target")
        self.assertEqual(pair["thresholds"], {"horizontal": {"intercept_m": 9460, "slope_mps": 2}, "vertical": {"intercept_m": 340, "slope_mps": .2}})
        self.assertEqual(threat["thresholds"]["radius"], {"intercept_m": 5240, "slope_mps": 2.2})
        self.assertEqual(target["thresholds"]["radius"], {"intercept_m": 5120, "slope_mps": 1.1})

    def test_target_sphere_crossing_and_nominal_metrics(self):
        scenario, flights, rules = self.synthetic([flight(x=-6000, z=3000, vx=200)], duration=60)
        scenario["target"] = {"x_m": 0, "y_m": 0}
        run = analyze_all(scenario, flights, rules)["runs"][0]
        events = [e for e in run["events"] if e["type"] == "aircraft_target"]
        self.assertEqual(len(events), 1)
        event = events[0]
        # At z=3000 the 5000 m sphere has a 4000 m horizontal section.
        self.assertEqual((event["start_s"], event["end_s"]), (10, 50))
        self.assertFalse(event["start_inclusive"])
        self.assertFalse(event["end_inclusive"])
        self.assertEqual(event["metrics"]["distance_3d_min"], {"value_m": 3000, "time_s": 30, "attained": True})
        self.assertEqual(event["metrics"]["horizontal_min"]["value_m"], 0)
        self.assertEqual(event["metrics"]["vertical_min"]["value_m"], 3000)

    def test_target_sphere_equality_tangency_and_high_overflight(self):
        cases = (
            (flight(x=-6000, z=5000, vx=200), False),  # Tangency at t=30.
            (flight(x=-6000, z=8100, vx=200), False),  # Above the sphere.
            (flight(z=5000, vx=0), False),            # Stationary equality.
            (flight(x=4000, z=3000, vx=0), False),    # 3-4-5 boundary.
            (flight(z=4999, vx=0), True),             # Initially inside.
        )
        for aircraft, inside in cases:
            with self.subTest(aircraft=aircraft):
                scenario, flights, rules = self.synthetic([aircraft], duration=60)
                scenario["target"] = {"x_m": 0, "y_m": 0}
                events = [e for e in analyze_all(scenario, flights, rules)["runs"][0]["events"] if e["type"] == "aircraft_target"]
                self.assertEqual(len(events), int(inside))
                if inside:
                    self.assertEqual((events[0]["start_s"], events[0]["end_s"]), (0, 60))
                    self.assertTrue(events[0]["initial_violation"])
                    self.assertTrue(events[0]["continues_at_horizon"])

    def test_target_sphere_vertical_entry_from_boundary(self):
        scenario, flights, rules = self.synthetic([flight(z=5000, vx=0, vz=-10)])
        scenario["target"] = {"x_m": 0, "y_m": 0}
        events = [e for e in analyze_all(scenario, flights, rules)["runs"][0]["events"] if e["type"] == "aircraft_target"]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual((event["start_s"], event["end_s"]), (0, 20))
        self.assertFalse(event["initial_violation"])
        self.assertFalse(event["start_inclusive"])
        self.assertTrue(event["end_inclusive"])
        self.assertEqual(event["metrics"]["distance_3d_min"]["value_m"], 4800)

    def test_target_sphere_uses_configured_center_altitude(self):
        scenario, flights, rules = self.synthetic([flight(x=-6000, z=4500, vx=200)], duration=60)
        scenario["target"] = {"x_m": 0, "y_m": 0}
        rules["zones"]["target"]["center_alt_m"] = 1500
        run = analyze_all(scenario, flights, rules)["runs"][0]
        event = next(e for e in run["events"] if e["type"] == "aircraft_target")
        self.assertEqual(run["thresholds"]["target_alt_m"], 1500)
        self.assertEqual((event["start_s"], event["end_s"]), (10, 50))
        self.assertEqual(event["metrics"]["distance_3d_min"]["value_m"], 3000)

    def test_target_sphere_vertical_error_growth(self):
        scenario, flights, rules = self.synthetic([flight(z=5100, vx=0)], duration=1200)
        scenario["target"] = {"x_m": 0, "y_m": 0}
        rules["modes"][1]["error_bounds"].update(position_horizontal_m=0, velocity_horizontal_mps=0)
        analysis = analyze_all(scenario, flights, rules)
        self.assertFalse(any(e["type"] == "aircraft_target" for e in analysis["runs"][0]["events"]))
        events = [e for e in analysis["runs"][5]["events"] if e["type"] == "aircraft_target"]
        self.assertEqual(len(events), 1)
        # Target exact: 5100 < 5000 + 20 + 0.1*t, hence t > 800.
        self.assertEqual((events[0]["start_s"], events[0]["end_s"]), (800, 1200))
        self.assertFalse(events[0]["start_inclusive"])
        self.assertTrue(events[0]["end_inclusive"])
        self.assertEqual(events[0]["severity"], "possible_violation")

    def test_real_target_intervals_match_independent_line_sphere_intersections(self):
        # Projection/chord construction, independent of the production polynomial solver.
        target = self.scenario["target"]
        for run in self.analysis["runs"]:
            if run["mode_id"] != "nominal":
                continue
            radius = run["thresholds"]["target_radius_m"]
            expected = {}
            for f in self.flights:
                p = (f["x_m"] - target["x_m"], f["y_m"] - target["y_m"], f["alt_m"] - run["thresholds"]["target_alt_m"])
                v = (f["vx_mps"], f["vy_mps"], f["vz_mps"])
                speed2 = sum(x*x for x in v)
                closest_t = -sum(x*y for x, y in zip(p, v)) / speed2
                closest2 = sum((x+y*closest_t)**2 for x, y in zip(p, v))
                if closest2 >= radius**2:
                    continue
                half_chord_s = math.sqrt((radius**2 - closest2) / speed2)
                left, right = max(0, closest_t-half_chord_s), min(run["duration_s"], closest_t+half_chord_s)
                if left < right:
                    expected[f["flight_id"]] = (left, right)
            actual = {e["flight_ids"][0]: e for e in run["events"] if e["type"] == "aircraft_target"}
            self.assertEqual(set(actual), set(expected))
            for flight_id, (left, right) in expected.items():
                self.assertAlmostEqual(actual[flight_id]["start_s"], left, places=8)
                self.assertAlmostEqual(actual[flight_id]["end_s"], right, places=8)
            if run["variant_id"] == "base":
                self.assertEqual(set(actual), {"F012", "F013", "F023", "F026"})

    def test_motion_speed_bounds_full_horizon_events_and_coordinated_turn(self):
        scenario, flights, rules = self.synthetic([flight(vx=200, vz=15)])
        analysis = analyze_all(scenario, flights, rules)
        nominal, stress = analysis["runs"][0], analysis["runs"][5]
        self.assertTrue(nominal["motion_checks"]["all_pass"])
        self.assertFalse(stress["motion_checks"]["all_pass"])
        motion = [event for event in stress["events"] if event["type"] == "motion"]
        self.assertEqual({event["rule_id"] for event in motion}, {"horizontal_speed", "vertical_speed"})
        for event in motion:
            self.assertEqual((event["start_s"], event["end_s"], event["initial_violation"], event["continues_at_horizon"]), (0, 20, True, True))
            self.assertEqual(event["severity"], "possible_violation")
        check = next(check for check in stress["motion_checks"]["checks"] if check["rule_id"] == "turn_rate")
        self.assertEqual(check["observed_max"], 0)
        self.assertAlmostEqual(check["allowed_max"], 9.80665 * math.tan(math.radians(25)) / 201)
        self.assertEqual(check["bound_speed_mps"], 201)

    def test_stationary_motion_no_nonfinite_turn_bound(self):
        scenario, flights, rules = self.synthetic([flight(vx=0)])
        analysis = analyze_all(scenario, flights, rules)
        checks = analysis["runs"][0]["motion_checks"]["checks"]
        self.assertFalse(next(check for check in checks if check["rule_id"] == "horizontal_speed")["passes"])
        turn = next(check for check in checks if check["rule_id"] == "turn_rate")
        self.assertTrue(turn["passes"])
        self.assertIsNone(turn["allowed_max"])
        json.dumps(analysis, allow_nan=False)

    def test_altitude_bounds_are_read_from_scenario(self):
        scenario, flights, rules = self.synthetic([flight(z=4000, vz=1)], duration=20)
        scenario["airspace"].update(alt_min_m=4000, alt_max_m=4010)
        analysis = analyze_all(scenario, flights, rules)
        nominal = [event for event in analysis["runs"][0]["events"] if event["type"] == "altitude"]
        self.assertEqual(len(nominal), 1)
        self.assertEqual(nominal[0]["rule_id"], "altitude_max")
        self.assertEqual((nominal[0]["start_s"], nominal[0]["end_s"], nominal[0]["start_inclusive"], nominal[0]["end_inclusive"]), (10, 20, False, True))
        stress = [event for event in analysis["runs"][5]["events"] if event["type"] == "altitude"]
        self.assertEqual({event["rule_id"] for event in stress if event["initial_violation"]}, {"altitude_min", "altitude_max"})

    def test_no_xy_clipping_and_no_threat_stop_at_target(self):
        scenario, flights, rules = self.synthetic([flight(x=500000, z=4000, vx=220)], duration=20)
        scenario["target"] = {"x_m": 500000, "y_m": 0}
        scenario["hostile_object"].update(x_m=490000, y_m=0, alt_m=4000, vx_mps=1000, vy_mps=0)
        run = analyze_all(scenario, flights, rules)["runs"][0]
        self.assertTrue(any(event["type"] == "aircraft_target" and event["initial_violation"] for event in run["events"]))
        threat = next(event for event in run["events"] if event["type"] == "aircraft_threat")
        self.assertAlmostEqual(threat["end_s"], 15000 / 780)
        self.assertGreater(threat["end_s"], 10)  # Threat passes static target at t=10, then continues.

    def test_reject_malformed_nonfinite_and_unsupported_semantics(self):
        modifications = (
            lambda s, f, r: f[0].update(x_m=float("nan")),
            lambda s, f, r: s["target"].update(y_m=float("inf")),
            lambda s, f, r: f.append(copy.deepcopy(f[0])),
            lambda s, f, r: f[0].update(flight_id="THREAT"),
            lambda s, f, r: f[0].update(vx_mps=True),
            lambda s, f, r: r["delays"].update(execution_s=1),
            lambda s, f, r: r["zones"]["threat"].update(shape="cylinder"),
            lambda s, f, r: r["zones"]["target"].update(shape="infinite_vertical_cylinder"),
            lambda s, f, r: r["zones"]["target"].update(center_alt_m=True),
            lambda s, f, r: r["zones"]["target"].update(center_alt_m=float("nan")),
            lambda s, f, r: r["zones"]["target"].update(stress_expansion="e_h_aircraft"),
            lambda s, f, r: r["uncertainty"].update(reset_on_frame=True),
            lambda s, f, r: r["uncertainty"].update(sphere_error_bound="euclidean"),
            lambda s, f, r: r["motion_limits"]["aircraft"].update(wind_mps=[1, 0, 0]),
            lambda s, f, r: r["motion_limits"].update(baseline_turn_rate_radps=0.1),
            lambda s, f, r: r["comparison"].update(equality_is_safe=False),
            lambda s, f, r: r["modes"][0]["error_bounds"].update(position_horizontal_m=1),
            lambda s, f, r: r["modes"][1]["error_bounds"].update(position_horizontal_m=-1),
            lambda s, f, r: r["sensitivity"]["variants"][1]["overrides"].update(target_radius_m=3000),
            lambda s, f, r: s["target"].update(vx_mps=1),
        )
        for index, modify in enumerate(modifications):
            with self.subTest(index=index):
                scenario, flights, rules = self.synthetic()
                modify(scenario, flights, rules)
                with self.assertRaises(ValueError):
                    analyze_all(scenario, flights, rules)

    def test_csv_and_json_input_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            scenario = copy.deepcopy(self.scenario)
            scenario["flights_file"] = "flights.csv"
            (temporary / "scenario.json").write_text(json.dumps(scenario))
            (temporary / "flights.csv").write_text("flight_id,x_m,y_m,alt_m,vx_mps,vy_mps,vz_mps\nA,NaN,0,6000,220,0,0\n")
            with self.assertRaises(ValueError):
                load_inputs(temporary / "scenario.json")
            (temporary / "rules.json").write_text('{"duration_s":1,"duration_s":2}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                load_rules(temporary / "rules.json")
            (temporary / "rules.json").write_text('{"duration_s":NaN}')
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                load_rules(temporary / "rules.json")

    def test_advertised_sensitivity_values_match_actual_runs(self):
        for key in ("vertical_m", "threat_radius_m", "target_radius_m"):
            for replacement in ([42], self.rules["sensitivity"][key] + [self.rules["sensitivity"][key][0]]):
                with self.subTest(key=key, replacement=replacement):
                    scenario, flights, rules = self.synthetic()
                    rules["sensitivity"][key] = replacement
                    with self.assertRaisesRegex(ValueError, "actually analyzed value"):
                        analyze_all(scenario, flights, rules)
        scenario, flights, rules = self.synthetic()
        rules["profiles"][0]["vertical_m"] = 301
        with self.assertRaisesRegex(ValueError, "vertical_m"):
            analyze_all(scenario, flights, rules)
        scenario, flights, rules = self.synthetic()
        rules["zones"]["threat"]["radius_m"] = 6000
        with self.assertRaisesRegex(ValueError, "threat_radius_m"):
            analyze_all(scenario, flights, rules)

    def test_booleans_cannot_impersonate_semantic_numbers(self):
        modifications = (
            lambda s, r: s.update(snapshot_time_s=False),
            lambda s, r: r["uncertainty"].update(reference_time_s=False),
            lambda s, r: r["delays"].update(observation_s=False),
            lambda s, r: r["delays"].update(communication_s=False),
            lambda s, r: r["delays"].update(execution_s=False),
            lambda s, r: r["motion_limits"]["aircraft"].update(wind_mps=[False, 0, 0]),
            lambda s, r: r["motion_limits"].update(baseline_acceleration_mps2=[0, False, 0]),
            lambda s, r: r["motion_limits"].update(baseline_turn_rate_radps=False),
            lambda s, r: r["uncertainty"].update(target_exact=1),
        )
        for index, modify in enumerate(modifications):
            with self.subTest(index=index):
                scenario, flights, rules = self.synthetic()
                modify(scenario, rules)
                with self.assertRaises(ValueError):
                    analyze_all(scenario, flights, rules)

    def test_determinism_complete_reports_and_typed_csv(self):
        scenario, flights, rules = self.synthetic([flight(x=-10000), flight("B", x=10000, vx=-220)])
        first = analyze_all(scenario, flights, rules)
        second = analyze_all(scenario, list(reversed(flights)), rules)
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as temporary:
            first_dir, second_dir = Path(temporary) / "a", Path(temporary) / "b"
            write_reports(first, first_dir)
            write_reports(second, second_dir)
            self.assertEqual({path.name for path in first_dir.iterdir()}, {"analysis.json", "events.csv", "summary.csv", "sensitivity.csv", "summary.md"})
            for path in first_dir.iterdir():
                self.assertEqual(path.read_bytes(), (second_dir / path.name).read_bytes())
            with (first_dir / "events.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), sum(len(run["events"]) for run in first["runs"]))
            for row in rows:
                self.assertEqual(row["run_id"], "__".join((row["profile_id"], row["mode_id"], row["variant_id"])))
                self.assertIn(json.loads(row["start_inclusive"]), (False, True))
                self.assertIsInstance(json.loads(row["thresholds"]), dict)
                self.assertGreater(float(row["end_s"]), float(row["start_s"]))
            with (first_dir / "sensitivity.csv").open() as stream:
                sensitivity = list(csv.DictReader(stream))
            self.assertEqual(len(sensitivity), 20)

    def test_cli_works_from_unrelated_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            process = subprocess.run([sys.executable, str(ROOT / "tools/analyze_baseline.py"), "--output-dir", temporary],
                cwd=temporary, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads((Path(temporary) / "analysis.json").read_text())["runs"][0]["summary"]["aircraft_pair_count"], 3)


if __name__ == "__main__":
    unittest.main()
