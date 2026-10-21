"""Independent kinematic answers and continuous-limit checks for vertical motion."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airspace.analysis import load_inputs, load_rules
from airspace.vertical import LimitViolation, VerticalSegment, VerticalTrajectory
from tools.example_vertical import build_example


class VerticalTests(unittest.TestCase):
    def setUp(self):
        self.scenario, self.flights = load_inputs(ROOT / "scenario.json")
        self.rules = load_rules(ROOT / "rules.json")
        self.flight = dict(flight_id="TEST", x_m=10, y_m=-20, alt_m=6000,
                           vx_mps=220, vy_mps=0, vz_mps=0)

    def make(self, controls, duration=None, **options):
        if duration is not None:
            self.rules["duration_s"] = duration
        return VerticalTrajectory(self.flight, [VerticalSegment(*s) for s in controls],
                                  self.scenario, self.rules, **options)

    def test_known_climb_constant_rate_level_descent_and_return(self):
        trajectory = self.make([(20, .5), (10, 0), (20, -.5), (30, 0),
                                (20, -.5), (10, 0), (20, .5)], duration=130)
        # Independent integrated areas under vz: 100 + 100 + 100 m up,
        # then a level hold followed by the mirrored 300 m descent.
        expected = [(0, 6000, 0), (10, 6025, 5), (20, 6100, 10),
                    (30, 6200, 10), (40, 6275, 5), (50, 6300, 0),
                    (80, 6300, 0), (100, 6200, -10), (110, 6100, -10),
                    (120, 6025, -5), (130, 6000, 0)]
        for time, altitude, vz in expected:
            with self.subTest(time=time):
                self.assertEqual(trajectory.position_at(time), (10 + 220 * time, -20, altitude))
                self.assertEqual(trajectory.velocity_at(time), (220, 0, vz))
                self.assertEqual(trajectory.state_at(time).alt_m, altitude)

    def test_nonzero_initial_vertical_velocity(self):
        self.flight["vz_mps"] = -2
        trajectory = self.make([(4, .5)], duration=4)
        self.assertEqual(trajectory.position_at(2), (450, -20, 5997))
        self.assertEqual(trajectory.velocity_at(2), (220, 0, -1))
        self.assertEqual(trajectory.state_at(4).alt_m, 5996)
        self.assertEqual(trajectory.state_at(4).vz_mps, 0)

    def test_continuity_and_coefficients_at_all_joins(self):
        trajectory = self.make([(20, .5), (20, -.5), (10, 0), (20, -.5), (20, .5)], duration=90)
        for left, right in zip(trajectory.segment_definitions(), trajectory.segment_definitions()[1:]):
            dt = left["end_s"] - left["start_s"]
            self.assertEqual(left["end_s"], right["start_s"])
            self.assertEqual(left["alt_start_m"] + left["vz_start_mps"] * dt + .5 * left["az_mps2"] * dt**2, right["alt_start_m"])
            self.assertEqual(left["vz_start_mps"] + left["az_mps2"] * dt, right["vz_start_mps"])
            join = right["start_s"]
            self.assertEqual(trajectory.state_at(join).alt_m, right["alt_start_m"])
            self.assertEqual(trajectory.state_at(join).vz_mps, right["vz_start_mps"])
            for offset in (-1e-6, 1e-6):
                self.assertAlmostEqual(trajectory.state_at(join + offset).alt_m, right["alt_start_m"], delta=2e-5)
                self.assertAlmostEqual(trajectory.state_at(join + offset).vz_mps, right["vz_start_mps"], delta=1e-6)

    def test_decimal_durations_have_exact_coverage_and_no_join_drift(self):
        trajectory = self.make([(.1, .3), (.1, -.3), (.1, 0)], duration=.3)
        self.assertEqual(trajectory.state_at(.2).alt_m, 6000.003)
        self.assertEqual(trajectory.state_at(.2).vz_mps, 0)
        self.assertEqual(trajectory.state_at(.3).alt_m, 6000.003)

    def test_all_real_level_flights_match_baseline_and_keep_xy_outside_frame(self):
        for flight in self.flights:
            trajectory = VerticalTrajectory(flight, [VerticalSegment(self.rules["duration_s"], 0)], self.scenario, self.rules)
            for t in (0, .125, 280.313481630, 1200):
                for key, initial, velocity in (("x_m", "x_m", "vx_mps"), ("y_m", "y_m", "vy_mps"), ("alt_m", "alt_m", "vz_mps")):
                    self.assertAlmostEqual(getattr(trajectory.state_at(t), key), flight[initial] + flight[velocity]*t, places=7)
        f040 = next(f for f in self.flights if f["flight_id"] == "F040")
        trajectory = VerticalTrajectory(f040, [VerticalSegment(1200, 0)], self.scenario, self.rules)
        self.assertLess(trajectory.position_at(1200)[0], self.scenario["airspace"]["x_min_m"])

    def test_vertical_acceleration_and_speed_limits_inclusive(self):
        trajectory = self.make([(30, .5), (30, -.5)], duration=60)
        self.assertEqual(trajectory.velocity_at(30)[2], 15)
        self.assertEqual(trajectory.state_at(60).vz_mps, 0)
        self.flight["alt_m"] = 7000
        trajectory = self.make([(30, -.5), (30, .5)], duration=60)
        self.assertEqual(trajectory.velocity_at(30)[2], -15)

    def test_acceleration_and_speed_excess_at_segment_end_rejected(self):
        for acceleration in (.5000000001, -.5000000001):
            with self.subTest(acceleration=acceleration), self.assertRaises(LimitViolation) as caught:
                self.make([(1, acceleration)], duration=1)
            self.assertEqual(caught.exception.constraint, "vertical_acceleration_mps2")
        for acceleration in (.5, -.5):
            with self.subTest(acceleration=acceleration), self.assertRaises(LimitViolation) as caught:
                self.make([(30.00000001, acceleration)], duration=30.00000001)
            self.assertEqual(caught.exception.constraint, "vertical_speed_mps")

    def test_altitude_interior_extremum_tangency_is_allowed(self):
        # z(t)=11999.9875 + .1t - .2t² reaches exactly 12000 at .25 s.
        self.flight.update(alt_m=11999.9875, vz_mps=.1)
        trajectory = self.make([(1, -.4)], duration=1)
        self.assertEqual(trajectory.state_at(.25).alt_m, 12000)
        self.flight.update(alt_m=3000.0125, vz_mps=-.1)
        trajectory = self.make([(1, .4)], duration=1)
        self.assertEqual(trajectory.state_at(.25).alt_m, 3000)

    def test_short_altitude_excursion_between_integer_samples_rejected(self):
        # Both endpoints are allowed, but the vertex at .25 s exceeds the bound.
        for altitude, velocity, acceleration, expected in ((11999.99, .1, -.4, 12000.0025), (3000.01, -.1, .4, 2999.9975)):
            self.flight.update(alt_m=altitude, vz_mps=velocity)
            with self.subTest(altitude=altitude), self.assertRaises(LimitViolation) as caught:
                self.make([(1, acceleration)], duration=1)
            self.assertEqual(caught.exception.constraint, "altitude_m")
            self.assertEqual(caught.exception.time_s, .25)
            self.assertEqual(caught.exception.value, expected)

    def test_altitude_at_horizon_and_initial_state(self):
        self.flight.update(alt_m=11999, vz_mps=1)
        self.assertEqual(self.make([(1, 0)], duration=1).state_at(1).alt_m, 12000)
        with self.assertRaises(LimitViolation):
            self.make([(1.000001, 0)], duration=1.000001)
        self.flight.update(alt_m=2999.99999999, vz_mps=0)
        with self.assertRaises(LimitViolation) as caught:
            self.make([(1, 0)], duration=1)
        self.assertEqual(caught.exception.time_s, 0)
        self.flight.update(alt_m=6000, vz_mps=15.00000001)
        with self.assertRaises(LimitViolation):
            self.make([(1, -.5)], duration=1)

    def test_limit_violations_at_later_join(self):
        with self.assertRaises(LimitViolation) as caught:
            self.make([(30, .5), (1, .5)], duration=31)
        self.assertEqual(caught.exception.time_s, 31)
        with self.assertRaises(LimitViolation) as caught:
            self.make([(1, 0), (1, .6)], duration=2)
        self.assertEqual(caught.exception.time_s, 1)

    def test_limits_read_from_configuration_and_scenario(self):
        self.rules["motion_limits"]["aircraft"]["vertical_acceleration_abs_max_mps2"] = .1
        with self.assertRaises(LimitViolation):
            self.make([(1, .2)], duration=1)
        self.rules["motion_limits"]["aircraft"]["vertical_speed_abs_max_mps"] = .05
        with self.assertRaises(LimitViolation):
            self.make([(1, .1)], duration=1)
        self.scenario["airspace"]["alt_max_m"] = 5999
        with self.assertRaises(LimitViolation):
            self.make([(1, 0)], duration=1)

    def test_horizontal_speed_boundaries_and_unrounded_comparison(self):
        for speed in (200, 260):
            self.flight["vx_mps"] = speed
            self.make([(1, 0)], duration=1)
        for speed in (199.99999999, 260.00000001):
            self.flight["vx_mps"] = speed
            with self.assertRaises(LimitViolation):
                self.make([(1, 0)], duration=1)
        self.flight.update(vx_mps=260, vy_mps=1e-8)
        with self.assertRaises(LimitViolation):
            self.make([(1, 0)], duration=1)

    def test_invalid_segments_and_coverage(self):
        for duration in (True, "1", None, 0, -1, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                VerticalSegment(duration, 0)
        for acceleration in (False, "0", None, float("nan"), float("-inf")):
            with self.subTest(acceleration=acceleration), self.assertRaises(ValueError):
                VerticalSegment(1, acceleration)
        for segments in ([], [{"duration_s": 1200, "az_mps2": 0}], None, "segments"):
            with self.subTest(segments=segments), self.assertRaises(ValueError):
                VerticalTrajectory(self.flight, segments, self.scenario, self.rules)
        for duration in (1199.9999999999, 1200.0000000001):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.make([(duration, 0)])

    def test_invalid_times_and_seek_is_stateless(self):
        trajectory = self.make([(20, .5), (20, -.5)], duration=40)
        expected = trajectory.state_at(5)
        trajectory.state_at(40)
        self.assertEqual(trajectory.state_at(5), expected)
        for time in (-.000001, 40.000001, True, "1", None, float("nan"), float("inf")):
            with self.subTest(time=time), self.assertRaises(ValueError):
                trajectory.state_at(time)

    def test_invalid_input_semantics(self):
        for key, value in (("flight_id", "THREAT"), ("flight_id", "bad id"), ("x_m", True), ("vz_mps", float("inf"))):
            bad = dict(self.flight, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                VerticalTrajectory(bad, [VerticalSegment(1200, 0)], self.scenario, self.rules)
        for mode in ("bounded_stress", "unknown", True):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.make([(1200, 0)], mode_id=mode)
        for section, key, value in ((self.rules, "schema_version", "2.0"),
                                    (self.rules, "units", "feet"), (self.scenario, "units", "feet"),
                                    (self.rules["motion_limits"]["aircraft"], "wind_mps", [1, 0, 0]),
                                    (self.rules["delays"], "execution_s", 1),
                                    (self.rules["motion_limits"]["aircraft"], "vertical_speed_abs_max_mps", True)):
            original = section[key]
            section[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.make([(1200, 0)])
            section[key] = original

    def test_serialization_roundtrip_and_source_snapshot(self):
        trajectory = self.make([(20, .5), (20, -.5)], duration=40)
        definition = json.loads(json.dumps(trajectory.to_dict(), allow_nan=False))
        restored = VerticalTrajectory.from_dict(definition, flight=self.flight, scenario=self.scenario, rules=self.rules)
        self.assertEqual(restored.to_dict(), definition)
        for t in (0, 10, 20, 39.125, 40):
            self.assertEqual(restored.state_at(t), trajectory.state_at(t))
        self.flight["alt_m"] = 9000
        self.rules["duration_s"] = 100
        definition["segments"][0]["az_mps2"] = 0
        self.assertEqual(trajectory.state_at(40).alt_m, 6200)
        self.assertEqual(trajectory.duration_s, 40)
        self.assertEqual(trajectory.to_dict()["initial_state"]["alt_m"], 6000)
        self.assertEqual(trajectory.segments[0].az_mps2, .5)

    def test_serialization_rejects_unsupported_and_tampered_definitions(self):
        trajectory = self.make([(1200, 0)])
        for key, value in (("schema_version", 1), ("model", "turn"), ("units", "feet"),
                           ("mode_id", "bounded_stress"), ("flight_id", "OTHER"),
                           ("duration_s", True), ("duration_s", 1199), ("source_sha256", "wrong"),
                           ("segments", None), ("initial_state", {})):
            bad = dict(trajectory.to_dict(), **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                VerticalTrajectory.from_dict(bad, flight=self.flight, scenario=self.scenario, rules=self.rules)
        for mutate in (lambda d: d.update(extra=True),
                       lambda d: d["initial_state"].update(vx_mps=221),
                       lambda d: d["initial_state"].update(vz_mps=False),
                       lambda d: d["segments"][0].update(alt_start_m=7000),
                       lambda d: d["segments"][0].update(az_mps2=.5)):
            bad = trajectory.to_dict()
            mutate(bad)
            with self.assertRaises(ValueError):
                VerticalTrajectory.from_dict(bad, flight=self.flight, scenario=self.scenario, rules=self.rules)
        changed_rules = copy.deepcopy(self.rules)
        changed_rules["motion_limits"]["aircraft"]["vertical_speed_abs_max_mps"] = 16
        with self.assertRaises(ValueError):
            VerticalTrajectory.from_dict(trajectory.to_dict(), flight=self.flight, scenario=self.scenario, rules=changed_rules)

    def test_f020_example_known_states_and_original_endpoint(self):
        trajectory = build_example(self.scenario, self.flights, self.rules)
        for t, z, vz in ((0, 8100, 0), (100, 8100, 0), (120, 8200, 10),
                          (140, 8300, 0), (240, 8300, 0), (260, 8200, -10),
                          (280, 8100, 0), (1200, 8100, 0)):
            self.assertEqual((trajectory.state_at(t).alt_m, trajectory.state_at(t).vz_mps), (z, vz))
        self.assertEqual(trajectory.position_at(1200), (-249689.9, 38926.3, 8100))
        self.assertEqual(trajectory.velocity_at(1200), (-229.98, 38.67, 0))

    def test_example_artifact_and_cli_from_another_cwd(self):
        expected = (ROOT / "examples/F020_vertical.json").read_bytes()
        trajectory = build_example(self.scenario, self.flights, self.rules)
        self.assertEqual(json.loads(expected), trajectory.to_dict())
        with tempfile.TemporaryDirectory(prefix="dtl-vertical-") as temporary:
            output = Path(temporary) / "nested/example.json"
            subprocess.run([sys.executable, str(ROOT / "tools/example_vertical.py"), "--output", str(output)],
                           cwd=temporary, check=True, capture_output=True)
            self.assertEqual(output.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
