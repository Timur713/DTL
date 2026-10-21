"""Independent continuous integrals, reversal invariance and Pareto semantics."""
from decimal import Decimal,localcontext
from fractions import Fraction as Q
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import load_inputs,load_rules
from airspace.quality import (OBJECTIVES,LEGACY_OBJECTIVES,QualityEvaluator,absolute_integral,bound,dominates,
                              experimental_score,verify_reference_scales)
from airspace.vertical import VerticalSegment,VerticalTrajectory


def metric(values):
    result=dict(bounds={key:bound(Q(value)) for key,value in zip(LEGACY_OBJECTIVES,values)})
    result['bounds']['max_altitude_excursion_m']=bound(Q(0))
    return result


class IntegralTests(unittest.TestCase):
    def test_known_constant_linear_and_altitude_crossing_integrals(self):
        for p,a,b,expected in [((-3,),0,4,12),((-1,1),0,2,1),((-1,0,1),0,2,2),
                                ((-1,2,-1),0,2,Q(2,3)),((-Q(1,3),1),0,Q(2,3),Q(1,9)),((0,),0,20,0)]:
            self.assertEqual(absolute_integral(p,a,b),(Q(expected),Q(expected)))

    def test_irrational_crossing_has_certified_integral_bounds(self):
        lo,hi=absolute_integral((-2,0,1),0,2)
        with localcontext() as c:
            c.prec=80
            expected=(8*Decimal(2).sqrt()-4)/3
            lower=Decimal(lo.numerator)/Decimal(lo.denominator)
            upper=Decimal(hi.numerator)/Decimal(hi.denominator)
            self.assertLessEqual(lower,expected);self.assertGreaterEqual(upper,expected)
        self.assertLess(hi-lo,Q(1,10**30))

    def test_integral_is_invariant_under_segment_splitting(self):
        p=(-2,0,1)
        whole=absolute_integral(p,0,2)
        left,right=absolute_integral(p,0,1),absolute_integral(p,1,2)
        self.assertLess(abs(sum(whole)/2-(sum(left)+sum(right))/2),Q(1,10**30))
        self.assertEqual(absolute_integral((1,-2,1),1,1),(0,0))
        with self.assertRaises(ValueError):absolute_integral((1,),2,1)


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.scenario,self.flights=load_inputs(ROOT/'scenario.json');self.rules=load_rules(ROOT/'rules.json')
        self.flight=dict(flight_id='A',x_m=0,y_m=0,alt_m=6000,vx_mps=220,vy_mps=0,vz_mps=0)

    def evaluate(self,controls,vz=0):
        self.flight['vz_mps']=vz;self.rules['duration_s']=sum(dt for dt,az in controls)
        d=VerticalTrajectory(self.flight,[VerticalSegment(*c) for c in controls],self.scenario,self.rules).to_dict()
        return QualityEvaluator(self.scenario,[self.flight],self.rules).evaluate([d])

    def test_known_triangular_climb_hold_return_metrics(self):
        q=self.evaluate([(2,.5),(2,-.5),(3,0),(2,-.5),(2,.5)])
        # 2 m excursion; 4 m total travel. Up/down each has 4 m*s area,
        # plateau contributes 6: integral altitude deviation=14 m*s.
        self.assertEqual(q['max_endpoint_deviation_m'],0)
        self.assertEqual(q['total_endpoint_deviation_m'],0)
        self.assertEqual(q['accumulated_altitude_deviation_m_s'],14)
        self.assertEqual(q['vertical_travel_m'],4)
        self.assertEqual(q['max_altitude_excursion_m'],2)
        self.assertEqual((q['changed_aircraft_count'],q['reversal_count']),(1,1))
        self.assertTrue(q['terminal_vertical_speed_zero'])

    def test_reversal_count_ignores_holds_and_identical_splits(self):
        a=self.evaluate([(2,-.5),(2,0),(2,-.5),(2,.5)],vz=1)
        b=self.evaluate([(1,-.5),(1,-.5),(1,0),(1,0),(1,-.5),(1,-.5),(2,.5)],vz=1)
        self.assertEqual(a,b)
        self.assertEqual(a['reversal_count'],1)
        self.assertEqual(self.evaluate([(2,-.5),(2,.5)],vz=1)['reversal_count'],0)

    def test_constant_baseline_with_redundant_segments_is_unchanged(self):
        q=self.evaluate([(1,0),(2,0),(1,0)])
        self.assertEqual(q['changed_aircraft_count'],0)
        self.assertEqual(q['vertical_travel_m'],0)
        self.assertEqual(q['reversal_count'],0)
        q=self.evaluate([(4,0)],vz=1)
        self.assertEqual(q['accumulated_altitude_deviation_m_s'],0)
        self.assertEqual(q['vertical_travel_m'],4)
        self.assertFalse(q['terminal_vertical_speed_zero'])

    def test_saved_reference_reproduces_frozen_experiment(self):
        d=json.loads((ROOT/'reports/planned/segments.json').read_text())
        q=QualityEvaluator(self.scenario,self.flights,self.rules).evaluate(d['trajectories'])
        c=json.loads((ROOT/'experiments/quality_score.json').read_text())
        self.assertTrue(verify_reference_scales(q,c))
        self.assertEqual(experimental_score(q,c)['value'],1)
        self.assertEqual([q[k] for k in OBJECTIVES],[6300,14100,6300,19809900,47700,15,10])
        bad=copy.deepcopy(c);bad['reference_scales']['max_endpoint_deviation_m']=6301
        with self.assertRaises(ValueError):verify_reference_scales(q,bad)
        bad=copy.deepcopy(c);bad['weights']['max_endpoint_deviation_m']=True
        with self.assertRaises(ValueError):experimental_score(q,bad)

    def test_duplicate_or_missing_aircraft_are_rejected(self):
        d=json.loads((ROOT/'reports/planned/segments.json').read_text())['trajectories']
        evaluator=QualityEvaluator(self.scenario,self.flights,self.rules)
        with self.assertRaises(ValueError):evaluator.evaluate(d[:-1])
        with self.assertRaises(ValueError):evaluator.evaluate(d+[d[0]])


class DominanceTests(unittest.TestCase):
    def test_strict_one_and_weak_all_objectives(self):
        self.assertTrue(dominates(metric([1,2,3,4,5,6]),metric([1,2,4,4,5,6])))
        self.assertFalse(dominates(metric([1,2,3,4,5,6]),metric([1,2,3,4,5,6])))
        self.assertFalse(dominates(metric([1,2,3,4,6,6]),metric([2,2,3,4,5,6])))

    def test_excursion_is_a_seventh_minimized_objective(self):
        a,b=metric([1,2,3,4,5,6]),metric([1,2,3,4,5,6])
        a['bounds']['max_altitude_excursion_m']=bound(Q(1));b['bounds']['max_altitude_excursion_m']=bound(Q(100))
        self.assertTrue(dominates(a,b))
        self.assertFalse(dominates(b,a))

    def test_uncertain_overlapping_integral_does_not_prove_dominance(self):
        a,b=metric([1,2,3,4,5,6]),metric([2,2,3,4,5,6])
        a['bounds']['accumulated_altitude_deviation_m_s']=bound(Q(299,100),Q(301,100))
        self.assertFalse(dominates(a,b))


if __name__=='__main__':unittest.main()
