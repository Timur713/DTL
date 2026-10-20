"""Artifact/contract checks independent of the geometric detector implementation."""

import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airspace.analysis import analyze_all, load_inputs, load_rules, write_reports


def contains(outer, inner):
    """Exact interval inclusion, including open/closed endpoint semantics."""
    left = (outer['start_s'] < inner['start_s'] or
            (outer['start_s'] == inner['start_s'] and
             (outer['start_inclusive'] or not inner['start_inclusive'])))
    right = (outer['end_s'] > inner['end_s'] or
             (outer['end_s'] == inner['end_s'] and
              (outer['end_inclusive'] or not inner['end_inclusive'])))
    return left and right


def event_key(event):
    return event['type'], event['rule_id'], tuple(sorted(event['participants']))


class IntegratedArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario, cls.flights = load_inputs(ROOT / 'scenario.json')
        cls.rules = load_rules(ROOT / 'rules.json')
        cls.analysis = analyze_all(cls.scenario, cls.flights, cls.rules)
        cls.runs = {run['id']: run for run in cls.analysis['runs']}

    def assert_event_set_contains(self, outer, inner):
        groups = {}
        for event in outer['events']:
            groups.setdefault(event_key(event), []).append(event)
        for event in inner['events']:
            self.assertTrue(any(contains(candidate, event)
                                for candidate in groups.get(event_key(event), [])),
                            '{} not contained in {}'.format(event['id'], outer['id']))

    def test_four_base_runs_and_reference_pair_counts(self):
        self.assertEqual(len(self.runs), 20)
        self.assertEqual(self.runs['metric__nominal__base']['summary']['aircraft_pair_count'], 3)
        self.assertEqual(self.runs['feet_reference__nominal__base']['summary']['aircraft_pair_count'], 24)
        for run in self.runs.values():
            self.assertTrue(run['motion_checks']['all_pass'])
            self.assertEqual(run['summary']['event_count'], len(run['events']))
            self.assertEqual(run['summary']['initial_event_count'],
                             sum(event['initial_violation'] for event in run['events']))
            self.assertEqual(run['initial_state']['has_violations'],
                             bool(run['summary']['initial_event_count']))

    def test_stress_contains_every_nominal_interval(self):
        for profile in self.rules['profiles']:
            for variant in self.rules['sensitivity']['variants']:
                prefix, suffix = profile['id'], variant['id']
                self.assert_event_set_contains(
                    self.runs[f'{prefix}__bounded_stress__{suffix}'],
                    self.runs[f'{prefix}__nominal__{suffix}'])

    def test_larger_radii_contain_smaller_radius_intervals(self):
        for profile in self.rules['profiles']:
            for mode in self.rules['modes']:
                prefix = f"{profile['id']}__{mode['id']}__"
                for zone in ('threat', 'target'):
                    self.assert_event_set_contains(self.runs[prefix + 'base'],
                                                   self.runs[prefix + zone + '_3000'])
                    self.assert_event_set_contains(self.runs[prefix + zone + '_10000'],
                                                   self.runs[prefix + 'base'])

    def test_report_reproducibility_and_csv_event_count(self):
        with tempfile.TemporaryDirectory(prefix='dtl-report-check-') as temporary:
            directory = Path(temporary)
            write_reports(self.analysis, directory)
            for filename in ('analysis.json', 'events.csv', 'summary.csv',
                             'sensitivity.csv', 'summary.md'):
                self.assertEqual((directory / filename).read_bytes(),
                                 (ROOT / 'reports' / filename).read_bytes(), filename)
            with (directory / 'events.csv').open(newline='', encoding='utf-8') as source:
                rows = list(csv.DictReader(source))
            self.assertEqual(len(rows), sum(len(run['events']) for run in self.runs.values()))

    def test_html_embeds_current_inputs_rules_and_actual_reports(self):
        html = (ROOT / 'baseline.html').read_text(encoding='utf-8')
        match = re.search(r'<script id="baseline-data" type="application/json">(.*?)</script>',
                          html, flags=re.DOTALL)
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        self.assertEqual(payload['scenario'], self.scenario)
        self.assertEqual(payload['flights'], self.flights)
        self.assertEqual(payload['rules'], self.rules)
        self.assertEqual(payload['analysis'], self.analysis)
        self.assertFalse(payload['analysis'].get('fixture', False))
        for key, filename in [('scenario', 'scenario.json'), ('flights', 'flights.csv'),
                              ('rules', 'rules.json')]:
            self.assertEqual(payload['source_sha256'][key],
                             hashlib.sha256((ROOT / filename).read_bytes()).hexdigest())

    def test_generator_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix='dtl-generator-check-') as temporary:
            directory = Path(temporary)
            output = directory / 'nested' / 'viewer.html'
            reports = directory / 'reports'
            subprocess.run([sys.executable, str(ROOT / 'tools' / 'generate_baseline.py'),
                            '--output', str(output), '--reports-dir', str(reports)],
                           cwd=directory, check=True, capture_output=True, text=True)
            self.assertEqual(output.read_bytes(), (ROOT / 'baseline.html').read_bytes())
            self.assertEqual((reports / 'analysis.json').read_bytes(),
                             (ROOT / 'reports' / 'analysis.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
