"""Scenario-derived necessary endpoint bounds, independent of maneuver search."""
from fractions import Fraction as Q
from itertools import combinations
from .checker import number, fingerprint


def endpoint_bounds(scenario,flights,rules):
    """Triangle-inequality bounds from a deterministic disjoint conflict matching.

    These are necessary bounds only: neither dynamics nor earlier conflicts are
    relaxed into a claim of attainability. Non-disjoint deficits are not summed.
    """
    profile=next(p for p in rules['profiles'] if p['id']=='metric')
    H=number(profile['horizontal_m'],'H');V=number(profile['vertical_m'],'V')
    T=number(rules['duration_s'],'T')
    if H<=0 or V<=0 or T<=0:raise ValueError('Positive thresholds and horizon required')
    if not isinstance(flights,list) or not flights:raise ValueError('Nonempty flight list required')
    points={}
    for f in flights:
        fid=f['flight_id']
        if not isinstance(fid,str) or not fid:raise ValueError('Invalid flight ID')
        if fid in points:raise ValueError('Duplicate flight ID')
        points[fid]=tuple(number(f[p],p)+number(f[v],v)*T for p,v in [('x_m','vx_mps'),('y_m','vy_mps'),('alt_m','vz_mps')])
    pairs=[];selected=[];used=set()
    for a,b in combinations(sorted(points),2):
        u,v=points[a],points[b];h2=(u[0]-v[0])**2+(u[1]-v[1])**2;dz=abs(u[2]-v[2])
        if h2>=H*H or dz>=V:continue
        deficit=V-dz
        row=dict(aircraft=[a,b],horizontal_distance_squared_exact=str(h2),baseline_vertical_distance_m=float(dz),
                 necessary_sum_deviation_m=float(deficit),necessary_max_deviation_m=float(deficit/2),
                 necessary_sum_deviation_exact=str(deficit),necessary_max_deviation_exact=str(deficit/2))
        pairs.append(row)
        if a not in used and b not in used:selected.append(row);used.update((a,b))
    total=sum((Q(p['necessary_sum_deviation_exact']) for p in selected),Q(0))
    maximum=max((Q(p['necessary_max_deviation_exact']) for p in pairs),default=Q(0))
    return dict(schema_version='1.0',source_sha256=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)),
                duration_s=float(T),horizontal_threshold_m=float(H),vertical_threshold_m=float(V),
                terminal_conflict_pairs=pairs,disjoint_pairs=selected,
                max_endpoint_deviation_lower_bound_m=float(maximum),total_endpoint_deviation_lower_bound_m=float(total),
                max_endpoint_deviation_lower_bound_exact=str(maximum),total_endpoint_deviation_lower_bound_exact=str(total),
                derivation='Fixed XY at T forces |delta_i-delta_j+baseline_dz| >= V. Triangle inequality gives |delta_i|+|delta_j| >= V-|baseline_dz| and max >= (V-|baseline_dz|)/2. Sum only disjoint pairs.',
                attainability='Necessary scenario-specific bounds; attainability requires full continuous verification.')


def endpoint_gaps(quality,bounds):
    return {key:quality[key]-bounds[key.replace('_m','_lower_bound_m')] for key in ('max_endpoint_deviation_m','total_endpoint_deviation_m')}
