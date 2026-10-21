"""Verified multiobjective improvement, coordination and deterministic bounds."""
import copy
from fractions import Fraction as Q
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import load_inputs,load_rules
from airspace.checker import ContinuousChecker
from airspace.improve import append_transition,improve,neighborhood,prune_archive,validate_search
from airspace.quality import QualityEvaluator,LEGACY_OBJECTIVES as OBJECTIVES,bound,dominates
from tools.improve_nominal import export_result


class ImproveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario,cls.flights=load_inputs(ROOT/'scenario.json');cls.rules=load_rules(ROOT/'rules.json')
        cls.reference=json.loads((ROOT/'reports/planned/segments.json').read_text())
        cls.history=json.loads((ROOT/'reports/planned/search.json').read_text())
        cls.config=json.loads((ROOT/'experiments/quality_search.json').read_text())
        cls.experiment=json.loads((ROOT/'experiments/quality_score.json').read_text())

    def test_coordinated_return_preserves_separation_and_terminal_speed(self):
        fleet={d['flight_id']:d for d in self.reference['trajectories']};sources={f['flight_id']:f for f in self.flights}
        # Rational offsets are deliberately tested: the search generates these.
        for fid,offset in [('F018',Q(0)),('F034',Q(300))]:
            fleet[fid]=append_transition(fleet[fid],sources[fid],offset,550,self.scenario,self.rules)
        verification=ContinuousChecker(self.scenario,self.flights,self.rules).verify(list(fleet.values()))
        self.assertTrue(verification['verified_safe'])
        q=QualityEvaluator(self.scenario,self.flights,self.rules).evaluate(list(fleet.values()))
        self.assertEqual(q['max_endpoint_deviation_m'],900)
        self.assertEqual(q['total_endpoint_deviation_m'],2400)
        self.assertEqual(q['vertical_travel_m'],59400)
        self.assertTrue(q['terminal_vertical_speed_zero'])

    def test_actual_neighborhood_contains_coordinated_rational_targets(self):
        sources={f['flight_id']:f for f in self.flights};repairs={r['flight_id']:r for r in self.history['accepted_repairs']}
        checker=ContinuousChecker(self.scenario,self.flights,self.rules)
        neighbors=neighborhood(self.reference['trajectories'],sources,self.scenario,self.rules,repairs,self.config,0,checker)
        found=False
        for index,(fleet,origin) in enumerate(neighbors):
            if index>20:break
            if origin['kind']=='coordinated terminal transitions':
                q=QualityEvaluator(self.scenario,self.flights,self.rules).evaluate(fleet)
                if q['max_endpoint_deviation_m']==900 and q['total_endpoint_deviation_m']==2400:found=True;break
        self.assertTrue(found)

    def test_small_bounded_search_is_deterministic(self):
        c=copy.deepcopy(self.config);c.update(max_candidate_evaluations=12,max_independent_verifications=12,max_archive_size=3,max_moves_per_strategy=1,max_seconds=300)
        first=improve(self.scenario,self.flights,self.rules,self.reference,self.history,c)
        second=improve(self.scenario,self.flights,self.rules,self.reference,self.history,c)
        self.assertEqual(first,second)
        self.assertLessEqual(first['search']['candidate_evaluations'],12)
        for record in first['archive']:
            self.assertTrue(record['verification']['verified_safe']);self.assertTrue(record['quality']['terminal_vertical_speed_zero'])
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            export_result(copy.deepcopy(first),self.scenario,self.flights,self.rules,self.experiment,a,ROOT/'reports/planned/segments.json')
            export_result(copy.deepcopy(second),self.scenario,self.flights,self.rules,self.experiment,b,ROOT/'reports/planned/segments.json')
            paths=sorted(p.relative_to(a) for p in Path(a).rglob('*') if p.is_file())
            self.assertEqual(paths,sorted(p.relative_to(b) for p in Path(b).rglob('*') if p.is_file()))
            for p in paths:self.assertEqual((Path(a)/p).read_bytes(),(Path(b)/p).read_bytes())

    def test_archive_capacity_pruning_does_not_use_experimental_score(self):
        rows=[]
        for i in range(5):
            values=[Q(i+1),Q(5-i),Q(10),Q(10),Q(2),Q(1)]
            q={k:float(v) for k,v in zip(OBJECTIVES,values)};q['bounds']={k:bound(v) for k,v in zip(OBJECTIVES,values)}
            rows.append(dict(id=str(i),quality=q,experimental_J=1000-i))
        kept,pruned=prune_archive(rows,2)
        self.assertEqual({r['id'] for r in kept},{'0','4'})
        self.assertEqual(set(pruned),{'1','2','3'})

    def test_invalid_search_parameters_and_nonlevel_transition(self):
        for key,value in [('max_candidate_evaluations',True),('max_archive_size',0),('max_seconds',float('inf'))]:
            c=dict(self.config,**{key:value})
            with self.assertRaises(ValueError):validate_search(c)
        d=next(d for d in self.reference['trajectories'] if d['flight_id']=='F020');f=next(f for f in self.flights if f['flight_id']=='F020')
        with self.assertRaises(ValueError):append_transition(d,f,0,210,self.scenario,self.rules)


class ImprovedArtifacts(unittest.TestCase):
    def test_saved_archive_is_safe_zero_terminal_and_pairwise_nondominated(self):
        scenario,flights=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json')
        directory=ROOT/'reports/improved';catalog=json.loads((directory/'catalog.json').read_text())
        evaluator=QualityEvaluator(scenario,flights,rules)
        archive=[e for e in catalog['entries'] if e['pareto_member']]
        self.assertLessEqual(len(archive),catalog['search']['limits']['max_archive_size'])
        self.assertEqual(catalog['entries'][0]['experimental_J']['value'],1)
        for entry in catalog['entries']:
            path=ROOT/'reports/planned/segments.json' if entry['is_reference'] else directory/entry['segments_file']
            document=json.loads(path.read_text());v=ContinuousChecker(scenario,flights,rules).verify_document(document)
            self.assertTrue(v['verified_safe']);self.assertEqual(v,entry['verification'])
            quality=evaluator.evaluate(document['trajectories']);self.assertEqual(quality,entry['quality'])
            self.assertTrue(quality['terminal_vertical_speed_zero'])
        for a in archive:
            self.assertFalse(any(dominates(b['quality'],a['quality']) for b in archive if b is not a))
        self.assertTrue(any(e['quality']['total_endpoint_deviation_m']<14100 for e in archive))


if __name__=='__main__':unittest.main()
