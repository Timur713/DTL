"""Analytic continuous-checker fixtures, independent of planner construction."""
import copy
from fractions import Fraction as Q
import json
import random
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from airspace.analysis import load_inputs, load_rules, STATE_KEYS
from airspace.checker import ContinuousChecker, fingerprint
from airspace.planner import baseline_fleet
from airspace.polynomial import (IsolationUnresolved, at, isolate_roots, mul,
                                negative_cells, trim)


def source(fid="A", **updates):
    f = dict(flight_id=fid, x_m=0, y_m=0, alt_m=6000, vx_mps=220, vy_mps=0, vz_mps=0)
    f.update(updates)
    return f


def definition(flight, controls, scenario, rules):
    # Raw authoritative definitions let the independent checker see violations
    # that VerticalTrajectory would reject, rather than trusting its validator.
    return dict(schema_version="1.0", model="piecewise_constant_vertical_acceleration",
        units="SI: m, s, m/s, m/s^2", mode_id="nominal", flight_id=flight["flight_id"],
        duration_s=rules["duration_s"], initial_state={k:flight[k] for k in STATE_KEYS},
        segments=[dict(duration_s=dt, az_mps2=az) for dt,az in controls],
        source_sha256=fingerprint(dict(flight=flight, scenario=scenario, rules=rules)))


class PolynomialTests(unittest.TestCase):
    def test_quartic_four_roots_and_two_negative_cells(self):
        # (t-1)(t-2)(t-3)(t-4), strictly negative on (1,2) and (3,4).
        p = (Q(1),)
        for root in (1, 2, 3, 4):
            p = mul(p, (-Q(root), Q(1)))
        cells = negative_cells([p], 0, 5)
        self.assertEqual(len(cells), 2)
        for cell, expected in zip(cells, ((1,2),(3,4))):
            self.assertAlmostEqual(float(cell.start.midpoint), expected[0], places=9)
            self.assertAlmostEqual(float(cell.end.midpoint), expected[1], places=9)
            self.assertFalse(cell.start_inclusive or cell.end_inclusive)
            self.assertLess(at(p, cell.witness), 0)

    def test_repeated_tangent_root_and_safe_instant_not_merged(self):
        square = (Q(1), Q(-2), Q(1))
        self.assertEqual(negative_cells([square], 0, 2), [])
        cells = negative_cells([tuple(-c for c in square)], 0, 2)
        self.assertEqual(len(cells), 2)
        self.assertEqual(cells[0].end.low, 1)
        self.assertEqual(cells[1].start.low, 1)
        self.assertFalse(cells[0].end_inclusive)
        self.assertFalse(cells[1].start_inclusive)

    def test_horizon_roots_zero_and_constant_polynomials(self):
        self.assertEqual(negative_cells([(0,)], 0, 1), [])
        self.assertEqual(negative_cells([(1,)], 0, 1), [])
        cell = negative_cells([(-1,)], 0, 1)[0]
        self.assertTrue(cell.start_inclusive and cell.end_inclusive)
        # -t(1-t) < 0 only on (0,1), despite both endpoints being safe.
        cell = negative_cells([(0,-1,1)], 0, 1)[0]
        self.assertFalse(cell.start_inclusive or cell.end_inclusive)

    def test_close_roots_and_between_sample_violation(self):
        a, b = Q(1,2), Q(1,2)+Q(1,10**12)
        cells = negative_cells([mul((-a,1),(-b,1))], 0, 1)
        self.assertEqual(len(cells), 1)
        self.assertLess(a, cells[0].witness)
        self.assertLess(cells[0].witness, b)
        with self.assertRaises(IsolationUnresolved):
            negative_cells([mul((-a,1),(-b,1))], 0, 1, max_depth=2)

    def test_sign_conjunction_nonoverlapping_and_degree_six(self):
        self.assertEqual(negative_cells([(-1,1),(2,-1)], 0, 3), [])
        # Product of three quadratics has six roots; conjunction is (2,3).
        polys = [mul((-a,1),(-b,1)) for a,b in ((0,5),(1,4),(2,3))]
        cells = negative_cells(polys, -1, 6)
        self.assertEqual(len(cells), 1)
        self.assertAlmostEqual(float(cells[0].start.midpoint), 2, places=9)
        self.assertAlmostEqual(float(cells[0].end.midpoint), 3, places=9)

    def test_constructed_factor_oracle_with_endpoint_and_repeated_roots(self):
        rng=random.Random(20261021)
        choices=[Q(-2),Q(-1),Q(0),Q(1,4),Q(1,2),Q(3,4),Q(1),Q(2)]
        for unused in range(40):
            roots=[rng.choice(choices) for unused in range(rng.randint(1,6))]
            sign=rng.choice((-1,1));p=(Q(sign),)
            for root in roots:p=mul(p,(-root,1))
            bounds=[Q(0),*sorted({r for r in roots if 0<r<1}),Q(1)]
            expected=[]
            for a,b in zip(bounds,bounds[1:]):
                point=(a+b)/2
                # Independent factor evaluation, rather than root solver output.
                value=Q(sign)
                for root in roots:value*=point-root
                if value<0:expected.append((a,b))
            actual=negative_cells([p],0,1)
            self.assertEqual(len(actual),len(expected),(roots,sign))
            for cell,(a,b) in zip(actual,expected):
                self.assertLessEqual(cell.start.low,a);self.assertGreaterEqual(cell.start.high,a)
                self.assertLessEqual(cell.end.low,b);self.assertGreaterEqual(cell.end.high,b)
                self.assertEqual(cell.start_inclusive,a==0 and at(p,0)<0)
                self.assertEqual(cell.end_inclusive,b==1 and at(p,1)<0)

    def test_certified_brackets_contain_known_irrational_roots(self):
        roots = isolate_roots((-2,0,1), Q(-2), Q(2))
        self.assertEqual(len(roots), 2)
        for root in roots:
            self.assertLessEqual(root.high-root.low, Q(1,2**36))
            self.assertLessEqual(at((-2,0,1), root.low)*at((-2,0,1), root.high), 0)
        with self.assertRaises(IsolationUnresolved):
            isolate_roots((-2,0,1), -2, 2, max_nodes=1)


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.scenario, unused = load_inputs(ROOT / 'scenario.json')
        self.rules = load_rules(ROOT / 'rules.json')
        self.rules['duration_s'] = 1
        self.scenario['target'].update(x_m=1e7, y_m=1e7)
        self.scenario['hostile_object'].update(x_m=-1e7, y_m=-1e7)

    def verify(self, flights, controls, **options):
        definitions = [definition(f,c,self.scenario,self.rules) for f,c in zip(flights,controls)]
        return ContinuousChecker(self.scenario,flights,self.rules,**options).verify(definitions)

    def test_accelerated_quartic_sphere_entry_between_samples(self):
        self.scenario['target'].update(x_m=0,y_m=0)
        f = source(x_m=-100, vx_mps=200, alt_m=5000.0525, vz_mps=-.25)
        result = self.verify([f],[[(1,.5)]])
        self.assertEqual(result['counts_by_type']['aircraft_target'],1)
        self.assertEqual(result['unresolved_count'],0)
        event = next(e for e in result['events'] if e['type']=='aircraft_target')
        self.assertGreater(event['start_s'],0)
        self.assertLess(event['end_s'],1)
        self.assertAlmostEqual(event['witness_s'],.5,places=8)
        self.assertFalse(result['verified_safe'])

    def test_accelerated_quartic_sphere_tangency_is_safe(self):
        self.scenario['target'].update(x_m=0,y_m=0)
        f=source(x_m=-100,vx_mps=200,alt_m=5000.0625,vz_mps=-.25)
        # z=5000+.25(t-.5)^2, x=200(t-.5): tangent at t=.5.
        result=self.verify([f],[[(1,.5)]])
        self.assertTrue(result['verified_safe'])

    def test_drone_accelerated_relative_distance(self):
        self.scenario['hostile_object'].update(x_m=0,y_m=0,alt_m=4000,vx_mps=200,vy_mps=0,vz_mps=0)
        f=source(x_m=0,vx_mps=200,alt_m=9000.0525,vz_mps=-.25)
        result=self.verify([f],[[(1,.5)]])
        self.assertEqual(result['counts_by_type']['aircraft_threat'],1)

    def test_accelerated_pair_short_violation_and_equality(self):
        # dz=300.0525-.25t+.25t²: dz(.5)=299.99, safe at 0 and 1.
        a,b=source(alt_m=6000.0525,vz_mps=-.25),source('B',alt_m=5700)
        result=self.verify([a,b],[[(1,.5)],[(1,0)]])
        self.assertEqual(result['counts_by_type']['aircraft_aircraft'],1)
        e=result['events'][0]
        self.assertAlmostEqual(e['start_s'],.3,places=9)
        self.assertAlmostEqual(e['end_s'],.7,places=9)
        a['alt_m']=6000.0625
        self.assertTrue(self.verify([a,b],[[(1,.5)],[(1,0)]])['verified_safe'])

    def test_strict_horizontal_and_vertical_boundaries(self):
        for updates in (dict(x_m=9260,alt_m=6000),dict(x_m=0,alt_m=6300)):
            a,b=source(),source('B',**updates)
            self.assertTrue(self.verify([a,b],[[(1,0)],[(1,0)]])['verified_safe'])
        b=source('B',x_m=9259.999,alt_m=6299.999)
        self.assertEqual(self.verify([source(),b],[[(1,0)],[(1,0)]])['violation_count'],1)

    def test_independent_altitude_and_motion_checks(self):
        # Raw controls deliberately bypass VerticalTrajectory construction.
        f=source(alt_m=11999.99,vz_mps=.1)
        result=self.verify([f],[[(1,-.4)]])
        self.assertEqual(result['counts_by_type']['altitude'],1)
        self.assertGreater(result['events'][0]['start_s'],0)
        self.assertLess(result['events'][0]['end_s'],1)
        for f,controls in ((source(vx_mps=199),[(1,0)]),(source(vz_mps=15),[(1,.5)]),
                           (source(),[(.5,0),(.5,.6)])):
            self.assertGreater(self.verify([f],[controls])['counts_by_type']['motion'],0)

    def test_complete_horizon_joins_and_inclusive_altitude(self):
        a,b=source(),source('B',alt_m=6000)
        result=self.verify([a,b],[[ (.25,.5),(.75,-.5)],[(.5,0),(.5,0)]])
        self.assertEqual(result['counts_by_type']['aircraft_aircraft'],1)
        e=next(e for e in result['events'] if e['type']=='aircraft_aircraft')
        self.assertEqual((e['start_s'],e['end_s']),(0,1))
        self.assertTrue(e['start_inclusive'] and e['end_inclusive'])
        self.assertTrue(self.verify([source(alt_m=3000)],[[(1,0)]])['verified_safe'])
        self.assertTrue(self.verify([source(alt_m=12000)],[[(1,0)]])['verified_safe'])

    def test_acceleration_join_uses_following_control(self):
        f=source()
        r=self.verify([f],[[ (.5,.6),(.5,0)]])
        e=next(e for e in r['events'] if e['rule_id']=='vertical_acceleration_max')
        self.assertEqual(e['end_s'],.5)
        self.assertFalse(e['end_inclusive'])

    def test_unresolved_prevents_verified_safe(self):
        a,b=source(alt_m=6000.0525,vz_mps=-.25),source('B',alt_m=5700)
        r=self.verify([a,b],[[(1,.5)],[(1,0)]],max_depth=0)
        self.assertFalse(r['verified_safe'])
        self.assertGreater(r['unresolved_count'],0)

    def test_initial_and_horizon_violation_not_ignored(self):
        a,b=source(),source('B',alt_m=6000)
        result=self.verify([a,b],[[(1,0)],[(1,0)]])
        e=next(e for e in result['events'] if e['type']=='aircraft_aircraft')
        self.assertTrue(e['start_inclusive'] and e['end_inclusive'])

    def test_full_fleet_validation_and_unsupported_semantics(self):
        a,b=source(),source('B',y_m=20000)
        c=ContinuousChecker(self.scenario,[a,b],self.rules)
        da,db=(definition(f,[(1,0)],self.scenario,self.rules) for f in (a,b))
        for fleet in ([da],[da,da],[],[dict(da,flight_id='OTHER'),db]):
            with self.assertRaises(ValueError):c.verify(fleet)
        for mutate in (lambda d:d.update(units='feet'),lambda d:d.update(schema_version=True),
                       lambda d:d.update(source_sha256='bad'),lambda d:d['initial_state'].update(vx_mps=221),
                       lambda d:d['segments'][0].update(duration_s=.9),lambda d:d['segments'][0].update(az_mps2=True),
                       lambda d:d['segments'][0].update(az_mps2=float('nan')),lambda d:d.update(mode_id='bounded_stress')):
            bad=copy.deepcopy(da);mutate(bad)
            with self.assertRaises(ValueError):c.verify([bad,db])
        with self.assertRaises(ValueError):ContinuousChecker(self.scenario,[a],self.rules,mode_id='bounded_stress')
        with self.assertRaises(ValueError):ContinuousChecker(self.scenario,[a],self.rules,max_depth=True)

    def test_caches_are_keyed_by_complete_controls(self):
        f=source(); c=ContinuousChecker(self.scenario,[f],self.rules)
        good=definition(f,[(1,0)],self.scenario,self.rules)
        bad=definition(f,[(1,.6)],self.scenario,self.rules)
        self.assertTrue(c.verify([good])['verified_safe'])
        self.assertTrue(c.verify([good])['verified_safe'])
        self.assertGreater(c.cache_hits,0)
        self.assertFalse(c.verify([bad])['verified_safe'])

    def test_exact_rejection_witness_and_fleet_envelope(self):
        self.scenario['target'].update(x_m=0,y_m=0)
        f=source(x_m=-100,vx_mps=200,alt_m=5000.0525,vz_mps=-.25)
        c=ContinuousChecker(self.scenario,[f],self.rules)
        d=definition(f,[(1,.5)],self.scenario,self.rules)
        witness=c.zone_violation_witness(c.compile(d))
        self.assertEqual(witness,dict(participant='TARGET',time_exact='1/2'))
        document=dict(schema_version='1.0',model='nominal_vertical_fleet',profile_id='metric',
                      mode_id='nominal',variant_id='base',duration_s=1,trajectories=[d],
                      source_sha256=fingerprint(dict(scenario=self.scenario,flights=[f],rules=self.rules)))
        self.assertFalse(c.verify_document(document)['verified_safe'])
        for key,value in (('mode_id','bounded_stress'),('schema_version',1),('duration_s',True),
                          ('source_sha256','wrong'),('profile_id','feet_reference')):
            with self.assertRaises(ValueError):c.verify_document(dict(document,**{key:value}))
        f['alt_m']=5000.0625
        c=ContinuousChecker(self.scenario,[f],self.rules)
        self.assertIsNone(c.zone_violation_witness(c.compile(definition(f,[(1,.5)],self.scenario,self.rules))))

    def test_reproduces_all_twelve_baseline_events(self):
        scenario,flights=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json')
        actual=ContinuousChecker(scenario,flights,rules).verify(baseline_fleet(scenario,flights,rules))
        expected=next(r for r in json.loads((ROOT/'reports/analysis.json').read_text())['runs'] if r['id']=='metric__nominal__base')
        self.assertEqual(actual['violation_count'],12)
        self.assertEqual(actual['unresolved_count'],0)
        self.assertEqual(actual['counts_by_type'],expected['summary']['counts_by_type'])
        for a,b in zip(actual['events'],expected['events']):
            self.assertEqual((a['type'],a['participants']),(b['type'],b['participants']))
            self.assertAlmostEqual(a['start_s'],b['start_s'],places=8)
            self.assertAlmostEqual(a['end_s'],b['end_s'],places=8)
            self.assertEqual((a['start_inclusive'],a['end_inclusive']),(b['start_inclusive'],b['end_inclusive']))


if __name__=='__main__':unittest.main()
