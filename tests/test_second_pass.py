"""Scenario endpoint proof, seven-objective search and immutable earlier plans."""
import copy,json,tempfile,unittest,sys
from fractions import Fraction as Q
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import load_inputs,load_rules
from airspace.checker import ContinuousChecker
from airspace.endpoint_bounds import endpoint_bounds,endpoint_gaps
from airspace.quality import OBJECTIVES,QualityEvaluator,dominates,bound,experimental_score
from airspace.second_pass import level_schedule,search,validate_config,prune
from tools.improve_second import load_starts,export

class EndpointTests(unittest.TestCase):
    def test_real_terminal_pairs_independent_scalar_calculation(self):
        scenario,flights=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json')
        b=endpoint_bounds(scenario,flights,rules)
        self.assertEqual([p['aircraft'] for p in b['terminal_conflict_pairs']],[['F018','F034'],['F030','F039']])
        # Independent decimal scalar enumeration of all 780 original endpoints.
        import itertools,decimal
        D=decimal.Decimal;T=D(str(rules['duration_s']));profile=rules['profiles'][0]
        pairs=[]
        for a,c in itertools.combinations(flights,2):
            x=D(str(a['x_m']))-D(str(c['x_m']))+(D(str(a['vx_mps']))-D(str(c['vx_mps'])))*T
            y=D(str(a['y_m']))-D(str(c['y_m']))+(D(str(a['vy_mps']))-D(str(c['vy_mps'])))*T
            z=D(str(a['alt_m']))-D(str(c['alt_m']))+(D(str(a['vz_mps']))-D(str(c['vz_mps'])))*T
            if x*x+y*y<D(profile['horizontal_m'])**2 and abs(z)<D(profile['vertical_m']):pairs.append([a['flight_id'],c['flight_id']])
        self.assertEqual(pairs,[p['aircraft'] for p in b['terminal_conflict_pairs']])
        self.assertEqual(b['max_endpoint_deviation_lower_bound_m'],150)
        self.assertEqual(b['total_endpoint_deviation_lower_bound_m'],600)
        self.assertEqual(endpoint_gaps(dict(max_endpoint_deviation_m=300,total_endpoint_deviation_m=600),b),dict(max_endpoint_deviation_m=150,total_endpoint_deviation_m=0))

    def test_bounds_are_scenario_specific_disjoint_and_strict(self):
        scenario,flights=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json')
        def f(i,z):return dict(flight_id=i,x_m=0,y_m=0,alt_m=z,vx_mps=220,vy_mps=0,vz_mps=0)
        b=endpoint_bounds(scenario,[f('A',6000),f('B',6100),f('C',6200)],rules)
        self.assertEqual(len(b['terminal_conflict_pairs']),3)
        self.assertEqual(b['total_endpoint_deviation_lower_bound_m'],200) # no double-counting shared vertices
        self.assertEqual(b['max_endpoint_deviation_lower_bound_m'],100)
        self.assertEqual(len(endpoint_bounds(scenario,[f('A',6000),f('B',6300)],rules)['terminal_conflict_pairs']),0)
        rules=copy.deepcopy(rules);rules['profiles'][0]['vertical_m']=400
        self.assertEqual(endpoint_bounds(scenario,[f('A',6000),f('B',6000)],rules)['max_endpoint_deviation_lower_bound_m'],200)

class SecondSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario,cls.flights=load_inputs(ROOT/'scenario.json');cls.rules=load_rules(ROOT/'rules.json')
        cls.config=json.loads((ROOT/'experiments/quality_second.json').read_text())
        cls.starts,cls.first=load_starts(ROOT/'reports/planned',ROOT/'reports/improved')
        cls.history=json.loads((ROOT/'reports/planned/search.json').read_text())

    def test_level_transitions_known_motion_and_zero_terminal_speed(self):
        f=next(f for f in self.flights if f['flight_id']=='F018')
        d=level_schedule(f,600,0,100,-150,self.scenario,self.rules)
        t=ContinuousChecker(self.scenario,[f],self.rules).compile(d)
        from airspace.polynomial import at,derivative
        self.assertEqual(at(t.piece_at(100).z,Q(100)),4200)
        self.assertEqual(at(t.pieces[-1].z,Q(1200)),3450)
        self.assertEqual(at(derivative(t.pieces[-1].z),Q(1200)),0)
        with self.assertRaises(ValueError):level_schedule(f,600,0,10,0,self.scenario,self.rules)
        with self.assertRaises(ValueError):level_schedule(f,True,0,100,0,self.scenario,self.rules)

    def test_seven_objective_dominance_with_excursion_tradeoff(self):
        def q(vals):return dict(bounds={k:bound(Q(v)) for k,v in zip(OBJECTIVES,vals)})
        a=q([150,600,5000,1,2,3,4]);b=q([150,600,6300,1,2,3,4])
        self.assertTrue(dominates(a,b));self.assertFalse(dominates(b,a))
        self.assertFalse(dominates(q([150,600,5000,2,2,3,4]),b))

    def test_excursion_enters_archive_but_not_frozen_score(self):
        evaluator=QualityEvaluator(self.scenario,self.flights,self.rules)
        original=evaluator.evaluate(self.starts['reference']['trajectories'])
        reduced=copy.deepcopy(original);reduced['max_altitude_excursion_m']=6000
        reduced['bounds']['max_altitude_excursion_m']=bound(Q(6000))
        self.assertTrue(dominates(reduced,original))
        experiment=json.loads((ROOT/'experiments/quality_score.json').read_text())
        self.assertEqual(experimental_score(original,experiment),experimental_score(reduced,experiment))
        rows=[]
        for name,x,e in [('a',150,6000),('b',300,5000),('c',225,5500)]:
            q=copy.deepcopy(original)
            for key,value in [('max_endpoint_deviation_m',x),('max_altitude_excursion_m',e)]:
                q[key]=value;q['bounds'][key]=bound(Q(value))
            rows.append(dict(id=name,quality=q))
        kept,removed=prune(rows,2)
        self.assertEqual({r['id'] for r in kept},{'a','b'});self.assertEqual(removed,['c'])

    def test_bounded_search_determinism_and_export(self):
        c=copy.deepcopy(self.config);c.update(max_candidate_evaluations=4,max_independent_verifications=20,max_archive_size=4,max_moves_per_job=1)
        a=search(self.scenario,self.flights,self.rules,self.starts,self.history,c)
        b=search(self.scenario,self.flights,self.rules,self.starts,self.history,c)
        self.assertEqual(a,b);self.assertEqual(a['search']['candidate_evaluations'],4)
        self.assertTrue(any(r['quality']['max_endpoint_deviation_m']==150 and r['quality']['total_endpoint_deviation_m']==600 for r in a['archive']))
        experiment=json.loads((ROOT/'experiments/quality_score.json').read_text())
        with tempfile.TemporaryDirectory() as x,tempfile.TemporaryDirectory() as y:
            for result,d in [(a,x),(b,y)]:export(result,self.scenario,self.flights,self.rules,self.starts,self.first,experiment,d,ROOT/'reports/planned',ROOT/'reports/improved')
            files=sorted(p.relative_to(x) for p in Path(x).rglob('*') if p.is_file())
            self.assertEqual(files,sorted(p.relative_to(y) for p in Path(y).rglob('*') if p.is_file()))
            for p in files:self.assertEqual((Path(x)/p).read_bytes(),(Path(y)/p).read_bytes())

    def test_invalid_budgets_types_and_unknown_seed(self):
        for key,v in [('max_seconds',True),('max_archive_size',0),('max_candidate_evaluations',float('inf'))]:
            c=copy.deepcopy(self.config);c[key]=v
            with self.assertRaises(ValueError):validate_config(c)
        c=copy.deepcopy(self.config);c['seed_ids']=['missing']
        with self.assertRaises(ValueError):search(self.scenario,self.flights,self.rules,self.starts,self.history,c)

class SavedSecondPass(unittest.TestCase):
    def test_all_saved_plans_reverify_quality_bounds_and_dominance(self):
        s,f=load_inputs(ROOT/'scenario.json');r=load_rules(ROOT/'rules.json');e=QualityEvaluator(s,f,r)
        directory=ROOT/'reports/improved_second';c=json.loads((directory/'catalog.json').read_text())
        self.assertEqual(c['objectives'],list(OBJECTIVES));self.assertLessEqual(c['search']['independent_verifications'],200)
        self.assertLessEqual(len(c['entries']),32)
        for entry in c['entries']:
            d=json.loads((directory/entry['segments_file']).read_text());v=ContinuousChecker(s,f,r).verify_document(d)
            self.assertEqual(v,entry['verification']);self.assertTrue(v['verified_safe'])
            q=e.evaluate(d['trajectories']);self.assertEqual(q,entry['quality']);self.assertTrue(q['terminal_vertical_speed_zero'])
            self.assertEqual(endpoint_gaps(q,c['endpoint_bounds']),entry['endpoint_gaps_m'])
            # The frozen score remains the original four-term expression after
            # adding excursion to objective order.
            manual=.60*q['max_endpoint_deviation_m']/6300+.25*q['total_endpoint_deviation_m']/14100+.10*q['accumulated_altitude_deviation_m_s']/19809900+.05*q['vertical_travel_m']/47700
            self.assertAlmostEqual(entry['experimental_J']['value'],manual,places=14)
            self.assertFalse(any(dominates(other['quality'],q) for other in c['entries'] if other is not entry))
        for earlier in c['earlier_comparisons']:
            self.assertEqual(earlier['dominated_by_second_pass'],[p['id'] for p in c['entries'] if dominates(p['quality'],earlier['quality'])])
if __name__=='__main__':unittest.main()
