"""Saved-search reconstruction and visualization contract checks."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import load_inputs,load_rules
from airspace.replay import prepare_replay


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario,cls.flights=load_inputs(ROOT/'scenario.json')
        cls.rules=load_rules(ROOT/'rules.json')
        cls.replay=prepare_replay(cls.scenario,cls.flights,cls.rules,ROOT/'reports/planned')

    def version(self,fid,step=-1):
        return self.replay['versions'][self.replay['steps'][step]['fleet_versions'][self.replay['flight_ids'].index(fid)]]

    def test_recorded_zone_and_pair_counts_through_all_steps(self):
        expected=[(9,3),(9,2),(8,2),(7,3),(6,4),(6,3),(5,4),(5,3),(4,4),(4,3),(4,2),
                  (3,5),(3,4),(3,3),(2,2),(1,2),(0,4),(0,3),(0,2),(0,1),(0,1),(0,0)]
        self.assertEqual([(s['zone_count'],s['pair_count']) for s in self.replay['steps']],expected)
        for step in self.replay['steps']:
            self.assertEqual(len(step['fleet_versions']),40)
            self.assertEqual(step['unresolved_count'],0)
            self.assertEqual(step['violation_count'],step['zone_count']+step['pair_count'])
            self.assertEqual(len(step['run']['events']),step['violation_count'])
            for fid,index in zip(self.replay['flight_ids'],step['fleet_versions']):
                self.assertEqual(self.replay['versions'][index]['flight_id'],fid)

    def test_final_controls_and_verification_match_saved_solution(self):
        self.assertTrue(self.replay['final_matches_saved'])
        saved=json.loads((ROOT/'reports/planned/verification.json').read_text())
        for key,value in self.replay['final_verification'].items():self.assertEqual(value,saved[key],key)
        self.assertTrue(self.replay['final_verification']['verified_safe'])
        self.assertEqual(self.replay['final_verification']['pair_checks'],780)
        for name,checksum in self.replay['saved_sha256'].items():
            self.assertEqual(checksum,hashlib.sha256((ROOT/'reports/planned'/name).read_bytes()).hexdigest())

    def test_only_changed_version_is_replaced_at_each_step(self):
        self.assertEqual(len(self.replay['versions']),61)
        for previous,current in zip(self.replay['steps'],self.replay['steps'][1:]):
            changed=[fid for fid,a,b in zip(self.replay['flight_ids'],previous['fleet_versions'],current['fleet_versions']) if a!=b]
            self.assertEqual(changed,[current['repair']['flight_id']])

    def test_plateau_uses_actual_pair_change_and_then_resolves(self):
        steps=self.replay['steps']
        self.assertEqual([s['index'] for s in steps if s['repair'] and s['repair']['plateau_move']],[20])
        self.assertEqual(steps[19]['run']['events'][0]['participants'],['F004','F031'])
        self.assertEqual(steps[20]['run']['events'][0]['participants'],['F004','F034'])
        self.assertEqual(steps[21]['run']['events'],[])
        self.assertEqual((steps[20]['repair']['removed_pair_events'],steps[20]['repair']['introduced_pair_events']),(1,1))
        self.assertEqual(steps[21]['repair']['flight_id'],'F034')

    def test_profiles_phases_and_temporary_maximum_are_not_terminal_distance(self):
        version=self.version('F020')
        self.assertEqual((version['max_altitude_deviation_m'],version['terminal_altitude_offset_m'],version['remaining_destination_distance_m']),(300,0,0))
        expected={200:(8100,0),220:(8200,10),230:(8300,10),250:(8400,0),342:(8400,0),392:(8100,0),1200:(8100,0)}
        for time,(altitude,speed) in expected.items():
            index=version['profile']['time_s'].index(time)
            self.assertEqual(version['profile']['alt_m'][index],altitude)
            self.assertEqual(version['profile']['vz_mps'][index],speed)
        self.assertIn('Return · Descent · accelerate',[p['label'] for p in version['segments']])
        self.assertIn('Altitude hold',[p['label'] for p in version['segments']])
        self.assertEqual(self.version('F034')['max_altitude_deviation_m'],6300)
        self.assertEqual(self.version('F034')['remaining_destination_distance_m'],6300)
        self.assertEqual(self.version('F004')['remaining_destination_distance_m'],0)

    def test_changed_aircraft_and_exactly_five_terminal_offsets(self):
        rows=self.replay['changed_aircraft']
        self.assertEqual(len(rows),15)
        self.assertEqual({r['flight_id']:r['terminal_altitude_offset_m'] for r in rows if r['terminal_altitude_offset_m']},
                         dict(F013=900,F018=5700,F023=900,F030=300,F034=6300))
        for row in rows:
            self.assertGreaterEqual(row['largest_accepted_deviation_m'],row['max_altitude_deviation_m'])
            self.assertEqual(row['remaining_destination_distance_m'],abs(row['terminal_altitude_offset_m']))

    def test_new_artifact_and_html_embed_reproducible_actual_data(self):
        self.assertEqual(json.loads((ROOT/'reports/replay.json').read_text()),self.replay)
        html=(ROOT/'baseline.html').read_text()
        payload=json.loads(re.search(r'<script id="baseline-data" type="application/json">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(payload['planning'],self.replay)
        self.assertIn('Accepted repairs only',self.replay['history_scope'])
        self.assertIn('exact brackets',self.replay['event_time_semantics'])

    def test_stale_or_tampered_saved_history_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            for name in ('segments.json','verification.json','search.json'):
                (directory/name).write_bytes((ROOT/'reports/planned'/name).read_bytes())
            history=json.loads((directory/'search.json').read_text())
            history['accepted_repairs'][0]['introduced_pair_events']=1
            (directory/'search.json').write_text(json.dumps(history))
            with self.assertRaisesRegex(ValueError,'conflict counts'):
                prepare_replay(self.scenario,self.flights,self.rules,directory)
            (directory/'search.json').write_bytes((ROOT/'reports/planned/search.json').read_bytes())
            doc=json.loads((directory/'verification.json').read_text());doc['fleet_sha256']='stale'
            (directory/'verification.json').write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'verification mismatch'):
                prepare_replay(self.scenario,self.flights,self.rules,directory)


if __name__=='__main__':unittest.main()
