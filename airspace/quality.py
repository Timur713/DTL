"""Continuous nominal vertical quality metrics and certified Pareto comparisons.

Integrals use exact rational antiderivatives. Irrational altitude roots have
certified rational enclosures; rounded display values never drive dominance.
"""
from fractions import Fraction as Q
from math import isqrt

from .checker import ContinuousChecker, number
from .polynomial import Boundary, add, at, bernstein_bounds, derivative, isolate_roots, scale, trim

LEGACY_OBJECTIVES = ('max_endpoint_deviation_m','total_endpoint_deviation_m',
              'accumulated_altitude_deviation_m_s','vertical_travel_m',
              'changed_aircraft_count','reversal_count')

OBJECTIVES = LEGACY_OBJECTIVES[:2]+('max_altitude_excursion_m',)+LEGACY_OBJECTIVES[2:]
SCORE_OBJECTIVES = LEGACY_OBJECTIVES[:4]

def roots(p, a, b):
    p=trim(p)
    exact=[]
    if len(p)==2:
        exact=[-p[0]/p[1]]
    elif len(p)==3:
        d=p[1]**2-4*p[2]*p[0]
        if d<0:return []
        n,k=isqrt(d.numerator),isqrt(d.denominator)
        if n*n==d.numerator and k*k==d.denominator:
            root=Q(n,k)
            exact=[(-p[1]-root)/(2*p[2]),(-p[1]+root)/(2*p[2])]
        else:
            return isolate_roots(p,a,b,bits=64,max_depth=200)
    elif len(p)>3:
        raise ValueError('Quality supports polynomials of degree at most two')
    return [Boundary.exact(t) for t in sorted(set(exact)) if a<t<b]


def integral(p,a,b):
    antiderivative=(Q(0),)+tuple(c/Q(i+1) for i,c in enumerate(p))
    return at(antiderivative,b)-at(antiderivative,a)


def absolute_integral(p,a,b):
    """Return certified (lower,upper) bounds of integral |p|, without sampling."""
    p=trim(p);a,b=Q(a),Q(b)
    if a>b:raise ValueError('Reversed integration interval')
    if a==b or p==(0,):return Q(0),Q(0)
    boundaries=[Boundary.exact(a),*roots(p,a,b),Boundary.exact(b)]
    lower=upper=Q(0)
    for left,right in zip(boundaries,boundaries[1:]):
        value=abs(integral(p,left.high,right.low))
        lower+=value;upper+=value
    for root in boundaries[1:-1]:
        if root.low!=root.high:
            lo,hi=bernstein_bounds(p,root.low,root.high)
            upper+=(root.high-root.low)*max(abs(lo),abs(hi))
    return lower,upper


def bound(lo,hi=None):
    hi=lo if hi is None else hi
    return dict(lower_exact=str(lo),upper_exact=str(hi))


def interval(metric,key):
    b=metric['bounds'][key]
    return Q(b['lower_exact']),Q(b['upper_exact'])


def dominates(first,second,objectives=OBJECTIVES):
    """Certified configured-objective weak-all / strict-one dominance, no epsilon."""
    strict=False
    for key in objectives:
        a,b=interval(first,key),interval(second,key)
        if a==b:
            if a[0]!=a[1]:return False  # overlapping enclosures do not prove equality
            continue
        if a[1]>b[0]:return False
        strict |= a[1]<b[0]
    return strict


def lex_key(quality,order):
    # Ranking only; uncertain equal values use lower/upper pairs deterministically.
    return tuple(interval(quality,key) for key in order)


class QualityEvaluator:
    def __init__(self,scenario,flights,rules):
        self.checker=ContinuousChecker(scenario,flights,rules)
        self.cache={}

    def trajectory(self,definition):
        from .checker import fingerprint
        signature=fingerprint(definition)
        if signature in self.cache:return self.cache[signature]
        t=self.checker.compile(definition)
        f=self.checker.flights[t.flight_id]
        area_lo=area_hi=travel_lo=travel_hi=excursion=Q(0)
        signs=[];changed=False
        for piece in t.pieces:
            delta=add(piece.z,scale((number(f['alt_m'],'z'),number(f['vz_mps'],'vz')),-1))
            changed |= delta!=(0,)
            lo,hi=absolute_integral(delta,piece.start,piece.end);area_lo+=lo;area_hi+=hi
            velocity=derivative(piece.z)
            lo,hi=absolute_integral(velocity,piece.start,piece.end);travel_lo+=lo;travel_hi+=hi
            candidates=[piece.start,piece.end]
            d=derivative(delta)
            if len(d)==2 and d[1]:
                point=-d[0]/d[1]
                if piece.start<point<piece.end:candidates.append(point)
            excursion=max(excursion,*(abs(at(delta,point)) for point in candidates))
            cuts=[piece.start,*[r.low for r in roots(velocity,piece.start,piece.end)],piece.end]
            for a,b in zip(cuts,cuts[1:]):
                value=at(velocity,(a+b)/2)
                sign=1 if value>0 else -1 if value<0 else 0
                if sign and (not signs or signs[-1]!=sign):signs.append(sign)
        horizon=self.checker.horizon
        dz=at(t.pieces[-1].z,horizon)-number(f['alt_m'],'z')-number(f['vz_mps'],'vz')*horizon
        terminal_vz=at(derivative(t.pieces[-1].z),horizon)
        result=dict(flight_id=t.flight_id,endpoint=abs(dz),terminal_offset=dz,area=(area_lo,area_hi),
                    travel=(travel_lo,travel_hi),excursion=excursion,changed=int(changed),
                    reversals=max(0,len(signs)-1),terminal_vz=terminal_vz)
        self.cache[signature]=result
        return result

    def evaluate(self,definitions):
        if not isinstance(definitions,list):raise ValueError('Fleet must be a list')
        rows=[self.trajectory(d) for d in definitions]
        ids=[r['flight_id'] for r in rows]
        if len(ids)!=len(set(ids)) or set(ids)!=set(self.checker.flights):
            raise ValueError('Quality requires all source aircraft exactly once')
        values={
            'max_endpoint_deviation_m':(max(r['endpoint'] for r in rows),)*2,
            'total_endpoint_deviation_m':(sum((r['endpoint'] for r in rows),Q(0)),)*2,
            'accumulated_altitude_deviation_m_s':tuple(sum((r['area'][i] for r in rows),Q(0)) for i in (0,1)),
            'vertical_travel_m':tuple(sum((r['travel'][i] for r in rows),Q(0)) for i in (0,1)),
            'max_altitude_excursion_m':(max(r['excursion'] for r in rows),)*2,
            'changed_aircraft_count':(Q(sum(r['changed'] for r in rows)),)*2,
            'reversal_count':(Q(sum(r['reversals'] for r in rows)),)*2}
        result={key:float((lo+hi)/2) if not key.endswith('_count') else int(lo) for key,(lo,hi) in values.items()}
        result.update(schema_version='1.0',bounds={key:bound(*value) for key,value in values.items()},
                      terminal_vertical_speed_zero=all(r['terminal_vz']==0 for r in rows),
                      per_aircraft=[dict(flight_id=r['flight_id'],endpoint_deviation_m=float(r['endpoint']),
                        terminal_altitude_offset_m=float(r['terminal_offset']),accumulated_altitude_deviation_m_s=float(sum(r['area'])/2),
                        vertical_travel_m=float(sum(r['travel'])/2),max_altitude_excursion_m=float(r['excursion']),
                        changed=bool(r['changed']),reversal_count=r['reversals'],terminal_vz_mps=float(r['terminal_vz'])) for r in sorted(rows,key=lambda r:r['flight_id'])],
                      definition='Original endpoint at T; no airport, landing or arrival-delay semantics. Reversals ignore zero-speed holds and segmentation.')
        return result


def validate_experiment(config):
    from .analysis import _keys
    _keys(config,('schema_version','score','weights','reference_scales'),path='quality experiment')
    if config['schema_version']!='1.0' or config['score']!='experimental_frozen_reference_J':
        raise ValueError('Unsupported quality experiment')
    keys=SCORE_OBJECTIVES
    for section in ('weights','reference_scales'):
        _keys(config[section],keys,path=section)
        for key in keys:
            value=number(config[section][key],key)
            if value<0 or (section=='reference_scales' and value==0):raise ValueError('Invalid experiment value')
    if sum(number(v,'weight') for v in config['weights'].values())!=1:raise ValueError('Weights must sum to one')


def experimental_score(quality,config):
    validate_experiment(config)
    lo=hi=Q(0)
    for key in SCORE_OBJECTIVES:
        weight=number(config['weights'][key],'weight')/number(config['reference_scales'][key],'scale')
        a,b=interval(quality,key);lo+=a*weight;hi+=b*weight
    return dict(value=float((lo+hi)/2),bounds=bound(lo,hi))


def verify_reference_scales(quality,config):
    validate_experiment(config)
    for key,value in config['reference_scales'].items():
        if interval(quality,key)!=(number(value,key),)*2:raise ValueError('Reference scale mismatch: '+key)
    return True
