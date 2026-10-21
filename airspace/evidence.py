"""Independent geometric witnesses and scope checks for the final delivery.

These necessary bounds do not assume a maneuver schedule and do not replace
continuous verification. All authoritative inequalities use decimal rationals.
"""
from copy import deepcopy
from fractions import Fraction as Q
from math import isqrt

from .analysis import _validate_rules, _validate_scenario
from .checker import ContinuousChecker, fingerprint, number
from .polynomial import at


def sqrt_enclosure(value, digits=9):
    """Certified rational bounds, not floating-point rounding of a square root."""
    if isinstance(value, bool):
        raise ValueError('Square-root input cannot be bool')
    value = Q(value)
    if value < 0 or type(digits) is not int or not 0 <= digits <= 30:
        raise ValueError('Invalid square-root enclosure')
    scale = 10**digits
    k = isqrt(value.numerator * scale * scale // value.denominator)
    lower = Q(k, scale)
    return lower, lower if lower*lower == value else Q(k+1, scale)


def sphere_excursion_bounds(scenario, flights, rules):
    """Necessary upward excursion when the lower side of a sphere is below floor.

    For fixed XY and level source/threat motion, horizontal CPA maximizes the
    spherical upper boundary. A witness with center_z - sqrt(R²-dh²) < floor
    forces an aircraft above center_z + sqrt(R²-dh²). Equality remains safe.
    """
    _validate_rules(rules)
    _validate_scenario(scenario, flights)
    if any(number(f['vz_mps'], 'vz') for f in flights) or number(scenario['hostile_object']['vz_mps'], 'threat vz'):
        raise ValueError('Excursion bound supports initially level aircraft and a level threat only')
    floor = number(scenario['airspace']['alt_min_m'], 'floor')
    horizon = number(rules['duration_s'], 'horizon')
    target = dict(scenario['target'], alt_m=rules['zones']['target']['center_alt_m'],
                  vx_mps=0, vy_mps=0)
    witnesses = []
    for flight in sorted(flights, key=lambda f: f['flight_id']):
        for label, obj, radius in (
                ('THREAT', scenario['hostile_object'], rules['zones']['threat']['radius_m']),
                ('TARGET', target, rules['zones']['target']['radius_m'])):
            x, y, vx, vy = (number(flight[k], k)-number(obj[k], k)
                            for k in ('x_m', 'y_m', 'vx_mps', 'vy_mps'))
            speed2 = vx*vx+vy*vy
            time = min(horizon, max(Q(0), -(x*vx+y*vy)/speed2)) if speed2 else Q(0)
            distance2 = (x+vx*time)**2+(y+vy*time)**2
            radicand = number(radius, 'radius')**2-distance2
            if radicand <= 0:
                continue
            center = number(obj['alt_m'], 'center')
            # Strictness matters: a lower boundary equal to the floor is allowed.
            below_floor = center < floor or radicand > (center-floor)**2
            if not below_floor:
                continue
            lo, hi = sqrt_enclosure(radicand)
            base = number(flight['alt_m'], 'altitude')
            lower, upper = max(Q(0), center+lo-base), max(Q(0), center+hi-base)
            if not upper:
                continue
            witnesses.append(dict(flight_id=flight['flight_id'], obstacle=label,
                time_s=float(time), time_exact=str(time), horizontal_distance_squared_exact=str(distance2),
                radius_m=radius, center_alt_m=float(center), floor_alt_m=float(floor),
                source_alt_m=float(base), radicand_exact=str(radicand),
                required_altitude_lower_m=float(center+lo), required_altitude_upper_m=float(center+hi),
                excursion_lower_m=float(lower), excursion_upper_m=float(upper),
                excursion_lower_exact=str(lower), excursion_upper_exact=str(upper)))
    strongest = max(witnesses, key=lambda w: (Q(w['excursion_lower_exact']), w['flight_id'])) if witnesses else None
    return dict(schema_version='1.0', scope='necessary_bound_for_fixed_XY_level_sources',
        source_sha256=fingerprint(dict(scenario=scenario, flights=flights, rules=rules)),
        witnesses=witnesses, strongest=strongest,
        max_excursion_lower_bound_m=strongest['excursion_lower_m'] if strongest else 0,
        interpretation='A necessary lower bound, not a proof that dynamics or other aircraft allow equality.')


def endpoint_error_witnesses(document, scenario, flights, rules, error_m=1):
    """Exact snapshot counterexamples; not a bounded-stress trajectory model."""
    error = number(error_m, 'endpoint error')
    if error <= 0:
        raise ValueError('Endpoint error must be positive')
    checker = ContinuousChecker(scenario, flights, rules)
    fleet = sorted((checker.compile(d) for d in document['trajectories']), key=lambda f: f.flight_id)
    time = checker.horizon
    witnesses = []
    for i, first in enumerate(fleet):
        for second in fleet[i+1:]:
            dh2 = (at(first.x, time)-at(second.x, time))**2+(at(first.y, time)-at(second.y, time))**2
            dz = abs(at(first.pieces[-1].z, time)-at(second.pieces[-1].z, time))
            if dh2 < checker.H**2 and checker.V <= dz < checker.V+2*error:
                perturbed = max(Q(0), dz-2*error)
                witnesses.append(dict(aircraft=[first.flight_id, second.flight_id], time_s=float(time),
                    nominal_separation_m=float(dz), possible_separation_m=float(perturbed),
                    per_aircraft_error_bound_m=float(error), vertical_threshold_m=float(checker.V),
                    nominal_separation_exact=str(dz), possible_separation_exact=str(perturbed),
                    horizontal_distance_squared_exact=str(dh2)))
    return dict(scope='endpoint_snapshot_only', witnesses=witnesses,
        establishes_full_horizon_robustness=False,
        interpretation='Opposing bounded altitude errors at T can invalidate nominal separation. No probability or error dynamics is assumed.')


def vertical_reference_sensitivity(document, scenario, flights, rules):
    """Recheck unchanged controls against the configured alternative V reference.

    The in-memory experiment gets new provenance; source rules and saved plans
    remain unchanged. This checks a different threshold, not uncertain motion.
    """
    variant = deepcopy(rules)
    reference = next(p for p in rules['profiles'] if p['id'] == 'feet_reference')
    target = reference['vertical_m']
    profile = next(p for p in variant['profiles'] if p['id'] == 'metric')
    profile['vertical_m'] = target
    profile['label'] = 'Saved-control sensitivity: '+reference.get('label', str(target)+' m')
    variant['sensitivity']['vertical_m'] = sorted({p['vertical_m'] for p in variant['profiles']})
    candidate = deepcopy(document)
    sources = {f['flight_id']: f for f in flights}
    for trajectory in candidate['trajectories']:
        trajectory['source_sha256'] = fingerprint(dict(flight=sources[trajectory['flight_id']], scenario=scenario, rules=variant))
    candidate['source_sha256'] = fingerprint(dict(scenario=scenario, flights=flights, rules=variant))
    result = ContinuousChecker(scenario, flights, variant).verify_document(candidate)
    return dict(experiment='configured_alternative_vertical_threshold', rules=variant,
                controls_unchanged=True, verification=result,
                original_rules_sha256=fingerprint(rules), experimental_rules_sha256=fingerprint(variant))
