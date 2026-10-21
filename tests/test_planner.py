"""Bounded planner and end-to-end artifact checks."""
import csv
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
from airspace.planner import plan_fleet
from airspace.vertical import VerticalTrajectory
from tools.plan_nominal import write_outputs


def flight(fid, x, vx, z=6000):
    return dict(flight_id=fid, x_m=x,y_m=0,alt_m=z,vx_mps=vx,vy_mps=0,vz_mps=0)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.scenario, unused = load_inputs(ROOT/'scenario.json')
        self.rules = load_rules(ROOT/'rules.json')
        self.scenario['target'].update(x_m=1e7,y_m=1e7)
        self.scenario['hostile_object'].update(x_m=-1e7,y_m=-1e7)

    def test_find_known_feasible_return_schedule_deterministically(self):
        self.rules['duration_s']=300
        flights=[flight('A',0,220),flight('B',44000,-220)]
        result=plan_fleet(self.scenario,flights,self.rules,max_candidates=100)
        self.assertEqual(result['initial_verification']['violation_count'],1)
        self.assertTrue(result['verification']['verified_safe'])
        self.assertEqual(result['verification']['unresolved_count'],0)
        self.assertEqual(result,plan_fleet(self.scenario,flights,self.rules,max_candidates=100))
        changed=result['search']['accepted_repairs']
        self.assertEqual(len(changed),1)
        self.assertIsNotNone(changed[0]['return_start_s'])
        self.assertEqual([d['flight_id'] for d in result['trajectories']],['A','B'])

    def test_terminal_deviation_resolves_persistent_horizon_conflict(self):
        flights=[flight('A',0,220),flight('B',-20000,230)]
        result=plan_fleet(self.scenario,flights,self.rules,max_candidates=100)
        self.assertTrue(result['verification']['verified_safe'])
        self.assertIsNone(result['search']['accepted_repairs'][0]['return_start_s'])
        with tempfile.TemporaryDirectory() as temporary:
            verification=write_outputs(result,self.scenario,flights,self.rules,temporary,1200)
            remaining=[d['remaining_destination_distance_m'] for d in verification['destinations']]
            self.assertEqual(sorted(remaining),[0,300])
            self.assertTrue(all(d['horizontal_destination_distance_m']==0 for d in verification['destinations']))
            text=(Path(temporary)/'summary.md').read_text()
            self.assertIn('not an arrival-delay estimate',text)

    def test_initial_conflict_remains_honest_bounded_failure(self):
        flights=[flight('A',0,220),flight('B',0,220)]
        result=plan_fleet(self.scenario,flights,self.rules,max_candidates=3)
        self.assertFalse(result['verification']['verified_safe'])
        self.assertGreater(result['verification']['violation_count'],0)
        self.assertLessEqual(result['search']['candidate_attempts'],3)
        self.assertEqual(result['search']['status'],'bounded_search_incomplete')
        self.assertEqual(result['search']['stop_reason'],'candidate_budget')

    def test_zero_budget_and_invalid_search_parameters(self):
        flights=[flight('A',0,220),flight('B',0,220)]
        result=plan_fleet(self.scenario,flights,self.rules,max_candidates=0)
        self.assertFalse(result['verification']['verified_safe'])
        self.assertEqual(result['search']['candidate_attempts'],0)
        for kwargs in (dict(max_candidates=True),dict(max_candidates=-1),dict(max_repairs=-1),dict(max_repairs=1.5)):
            with self.assertRaises(ValueError):plan_fleet(self.scenario,flights,self.rules,**kwargs)

    def test_outputs_deterministic_and_samples_not_used_as_proof(self):
        self.rules['duration_s']=300
        flights=[flight('A',0,220),flight('B',44000,-220)]
        result=plan_fleet(self.scenario,flights,self.rules,max_candidates=100)
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            write_outputs(result,self.scenario,flights,self.rules,a,60)
            write_outputs(result,self.scenario,flights,self.rules,b,60)
            for p in Path(a).iterdir():self.assertEqual(p.read_bytes(),(Path(b)/p.name).read_bytes())
            v=json.loads((Path(a)/'verification.json').read_text())
            self.assertFalse(v['sampled_csv']['establishes_safety'])
            data=json.loads((Path(a)/'segments.json').read_text())
            self.assertEqual(v['segments_file_sha256'],hashlib.sha256((Path(a)/'segments.json').read_bytes()).hexdigest())
            self.assertTrue(ContinuousChecker(self.scenario,flights,self.rules).verify_document(data)['verified_safe'])
            with (Path(a)/'trajectories.csv').open() as stream:rows=list(csv.DictReader(stream))
            self.assertEqual({r['flight_id'] for r in rows},{'A','B'})
            self.assertEqual({float(r['time_s']) for r in rows},{0,60,120,180,240,300})

    def test_cli_other_cwd_exports_failure_without_success_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'planned'
            process=subprocess.run([sys.executable,str(ROOT/'tools/plan_nominal.py'),'--max-candidates','0',
                                    '--sample-step-s','1200','--output-dir',str(output)],cwd=temporary,
                                    capture_output=True,text=True)
            self.assertEqual(process.returncode,1,process.stderr)
            result=json.loads((output/'verification.json').read_text())
            self.assertEqual(result['aircraft_count'],40)
            self.assertEqual((result['violation_count'],result['unresolved_count']),(12,0))
            self.assertIn('bounded_search_incomplete',process.stdout)


class PlannedArtifactTests(unittest.TestCase):
    def test_actual_all_forty_are_independently_verified(self):
        scenario,flights=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json')
        output=ROOT/'reports/planned'
        data=json.loads((output/'segments.json').read_text())
        actual=ContinuousChecker(scenario,flights,rules).verify_document(data)
        stored=json.loads((output/'verification.json').read_text())
        self.assertEqual(actual['aircraft_count'],40)
        self.assertEqual(actual['pair_checks'],780)
        self.assertTrue(actual['verified_safe'])
        self.assertEqual((actual['violation_count'],actual['unresolved_count']),(0,0))
        for key,value in actual.items():self.assertEqual(value,stored[key],key)
        self.assertEqual(stored['segments_file_sha256'],hashlib.sha256((output/'segments.json').read_bytes()).hexdigest())
        self.assertEqual(stored['sampled_csv']['rows'],40*1201)
        with (output/'trajectories.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),40*1201)
        self.assertEqual({r['flight_id'] for r in rows},{f['flight_id'] for f in flights})
        self.assertEqual(json.loads((output/'baseline_verification.json').read_text())['violation_count'],12)
        self.assertTrue(any(d['remaining_destination_distance_m']>0 for d in stored['destinations']))
        sources={f['flight_id']:f for f in flights}
        models={d['flight_id']:VerticalTrajectory.from_dict(d,flight=sources[d['flight_id']],
                scenario=scenario,rules=rules) for d in data['trajectories']}
        for row in rows:
            if float(row['time_s']) in (0,100,400,833,1200):
                expected=models[row['flight_id']].state_at(float(row['time_s'])).to_dict()
                for key,value in expected.items():self.assertEqual(float(row[key]),value)
        search=json.loads((output/'search.json').read_text())
        objective=(9,3)
        for repair in search['accepted_repairs']:
            next_objective=(objective[0]-repair['removed_unary_events'],
                            objective[1]-repair['removed_pair_events']+repair['introduced_pair_events'])
            self.assertLessEqual(next_objective,objective)
            self.assertEqual(repair['plateau_move'],next_objective==objective)
            objective=next_objective
        self.assertEqual(objective,(0,0))
        self.assertTrue(any(r['plateau_move'] for r in search['accepted_repairs']))


if __name__=='__main__':unittest.main()
