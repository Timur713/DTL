"""Independent geometric answers, strict boundaries and delivery integrity."""
from copy import deepcopy
import csv
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from airspace.analysis import load_inputs, load_rules
from airspace.checker import ContinuousChecker
from airspace.evidence import sqrt_enclosure, sphere_excursion_bounds, endpoint_error_witnesses, vertical_reference_sensitivity
from tools.build_submission import validate_config


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.flights = load_inputs(ROOT/'scenario.json')
        cls.rules = load_rules(ROOT/'rules.json')
        cls.document = json.loads((ROOT/'reports/improved_second/alternatives/pass2-b8f763f4b8b0/segments.json').read_text())

    def test_square_root_enclosures_are_certified_including_irrational(self):
        for value in (Q(0), Q(9), Q(2), Q(1, 7), Q(10**20, 3)):
            lo, hi = sqrt_enclosure(value)
            self.assertLessEqual(lo*lo, value)
            self.assertGreaterEqual(hi*hi, value)
            self.assertLessEqual(hi-lo, Q(1, 10**9))
        self.assertEqual(sqrt_enclosure(9), (3, 3))
        with self.assertRaises(ValueError):
            sqrt_enclosure(-1)
        with self.assertRaises(ValueError):
            sqrt_enclosure(True)

    def sample(self, horizontal, source_alt=3000, center_alt=4000, radius=5000):
        scenario, rules = deepcopy(self.scenario), deepcopy(self.rules)
        scenario['hostile_object'].update(x_m=0, y_m=0, alt_m=center_alt, vx_mps=0, vy_mps=0, vz_mps=0)
        scenario['target'].update(x_m=1e6, y_m=1e6)
        rules['zones']['threat']['radius_m'] = radius
        rules['sensitivity']['threat_radius_m'] = sorted({3000, 10000, radius})
        flight = dict(flight_id='A', x_m=horizontal, y_m=0, alt_m=source_alt, vx_mps=0, vy_mps=0, vz_mps=0)
        return scenario, [flight], rules

    def test_known_three_four_five_geometry_forces_five_km_climb(self):
        report = sphere_excursion_bounds(*self.sample(3000))
        w = report['strongest']
        self.assertEqual(w['required_altitude_lower_m'], 8000)
        self.assertEqual(w['excursion_lower_exact'], '5000')
        self.assertEqual(report['max_excursion_lower_bound_m'], 5000)

    def test_lower_branch_at_floor_is_allowed_not_forced_upward(self):
        # Radius 2000 directly overhead: lower boundary 5000-2000 = floor 3000.
        report = sphere_excursion_bounds(*self.sample(0, center_alt=5000, radius=2000))
        self.assertIsNone(report['strongest'])
        self.assertEqual(report['witnesses'], [])

    def test_tangent_horizontal_pass_needs_no_vertical_excursion(self):
        self.assertEqual(sphere_excursion_bounds(*self.sample(5000))['witnesses'], [])

    def test_closest_approach_is_clipped_at_horizon_and_no_time_sampling(self):
        s, flights, r = self.sample(6000)
        flights[0]['vx_mps'] = -1
        w = sphere_excursion_bounds(s, flights, r)['strongest']
        self.assertEqual(w['time_exact'], '1200')
        self.assertEqual(w['horizontal_distance_squared_exact'], str(4800**2))
        self.assertEqual(w['excursion_lower_m'], 2400)  # sqrt(5000²-4800²)=1400.
        flights[0]['vz_mps'] = 1
        with self.assertRaises(ValueError):
            sphere_excursion_bounds(s, flights, r)

    def test_real_excursion_witness_independently_recomputed(self):
        report = sphere_excursion_bounds(self.scenario, self.flights, self.rules)
        w = report['strongest']
        self.assertEqual(w['flight_id'], 'F031')
        self.assertTrue(5679.45 < w['excursion_lower_m'] < 5679.46)
        t = Q(w['time_exact'])
        flight = next(f for f in self.flights if f['flight_id'] == 'F031')
        threat = self.scenario['hostile_object']
        x = Q(str(flight['x_m']))-Q(str(threat['x_m']))+t*(Q(str(flight['vx_mps']))-Q(str(threat['vx_mps'])))
        y = Q(str(flight['y_m']))-Q(str(threat['y_m']))+t*(Q(str(flight['vy_mps']))-Q(str(threat['vy_mps'])))
        lo, hi = Q(w['excursion_lower_exact'])-1000, Q(w['excursion_upper_exact'])-1000
        self.assertLessEqual(lo**2+x*x+y*y, 5000**2)
        self.assertGreaterEqual(hi**2+x*x+y*y, 5000**2)

    def test_endpoint_counterexamples_are_exact_and_not_a_full_stress_claim(self):
        report = endpoint_error_witnesses(self.document, self.scenario, self.flights, self.rules)
        self.assertEqual([w['aircraft'] for w in report['witnesses']], [['F018', 'F034'], ['F030', 'F039']])
        for w in report['witnesses']:
            self.assertEqual(w['possible_separation_exact'], '298')
            self.assertEqual(w['nominal_separation_exact'], '300')
        self.assertFalse(report['establishes_full_horizon_robustness'])
        with self.assertRaises(ValueError):
            endpoint_error_witnesses(self.document, self.scenario, self.flights, self.rules, True)

    def test_alternative_threshold_rechecks_controls_without_mutation(self):
        rules, document = deepcopy(self.rules), deepcopy(self.document)
        result = vertical_reference_sensitivity(document, self.scenario, self.flights, rules)
        self.assertEqual(result['verification']['thresholds']['vertical_m'], 304.8)
        self.assertEqual(result['verification']['counts_by_type']['aircraft_aircraft'], 16)
        self.assertEqual(result['verification']['unresolved_count'], 0)
        metric = next(p for p in result['rules']['profiles'] if p['id'] == 'metric')
        self.assertIn('304.8', metric['label'])
        self.assertEqual(rules, self.rules)
        self.assertEqual(document, self.document)

    def test_submission_config_rejects_unsupported_and_boolean_parameters(self):
        config = json.loads((ROOT/'experiments/submission.json').read_text())
        for key, value in [('sample_step_s', True), ('sample_step_s', 0), ('endpoint_altitude_error_probe_m', False),
                           ('include_all_segment_joins', 1), ('vertical_reference_sensitivity', False)]:
            invalid = dict(config, **{key: value})
            with self.assertRaises(ValueError):
                validate_config(invalid)

    def test_delivery_manifest_csv_all_aircraft_and_every_join(self):
        directory = ROOT/'submission'
        manifest = json.loads((directory/'manifest.json').read_text())
        for name, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(), expected)
        with (directory/'trajectories.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        checker = ContinuousChecker(self.scenario, self.flights, self.rules)
        fleet = {d['flight_id']:checker.compile(d) for d in self.document['trajectories']}
        by_time = {}
        for row in rows:
            time = Q(row['time_exact_s'])
            by_time.setdefault(time, set()).add(row['flight_id'])
        self.assertTrue(all(ids == set(fleet) for ids in by_time.values()))
        self.assertEqual(len(rows), len(by_time)*40)
        self.assertIn(Q(0), by_time)
        self.assertIn(Q(1200), by_time)
        for trajectory in fleet.values():
            for piece in trajectory.pieces:
                self.assertIn(piece.start, by_time)
                self.assertIn(piece.end, by_time)
        # Check all six state columns at every piece join with the independent
        # trajectory implementation, rather than the CSV exporter's polynomial path.
        from airspace.vertical import VerticalTrajectory
        sources = {f['flight_id']:f for f in self.flights}
        models = {d['flight_id']:VerticalTrajectory.from_dict(d, flight=sources[d['flight_id']], scenario=self.scenario, rules=self.rules) for d in self.document['trajectories']}
        indexed = {(r['flight_id'], Q(r['time_exact_s'])):r for r in rows}
        for fid, trajectory in fleet.items():
            for time in {p.start for p in trajectory.pieces} | {Q(1200)}:
                state = models[fid].state_at(float(time))
                for key in ('x_m', 'y_m', 'alt_m', 'vx_mps', 'vy_mps', 'vz_mps'):
                    self.assertAlmostEqual(float(indexed[fid, time][key]), getattr(state, key), places=8)

    def test_export_reproduces_saved_files_from_another_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'delivery'
            result = subprocess.run([sys.executable, str(ROOT/'tools/build_submission.py'), '--output-dir', str(output)],
                                    cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for file in output.iterdir():
                self.assertEqual(file.read_bytes(), (ROOT/'submission'/file.name).read_bytes(), file.name)


if __name__ == '__main__':
    unittest.main()
