#!/usr/bin/env python3
"""Search, independently certify and export separate second-pass alternatives."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import _read_json,load_inputs,load_rules
from airspace.checker import ContinuousChecker,fingerprint
from airspace.quality import OBJECTIVES,QualityEvaluator,dominates,experimental_score,verify_reference_scales,interval
from airspace.endpoint_bounds import endpoint_bounds,endpoint_gaps
from airspace.second_pass import search
from tools.improve_nominal import write_json


def load_starts(reference_dir,first_dir):
    catalog=_read_json(first_dir/'catalog.json');starts={'reference':_read_json(reference_dir/'segments.json')}
    if catalog.get('schema_version')!='1.0' or hashlib.sha256((reference_dir/'segments.json').read_bytes()).hexdigest()!=catalog.get('reference_segments_sha256'):raise ValueError('Invalid first-pass/reference provenance')
    for e in catalog['entries']:
        if not e['is_reference']:
            path=(first_dir/e['segments_file']).resolve()
            if first_dir.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest()!=e['segments_sha256']:raise ValueError('Invalid first-pass path/checksum')
            starts[e['id']]=_read_json(path)
    return starts,catalog


def export(result,scenario,flights,rules,starts,first_catalog,experiment,output,reference_dir,first_dir):
    output=Path(output);evaluator=QualityEvaluator(scenario,flights,rules);refq=evaluator.evaluate(starts['reference']['trajectories'])
    verify_reference_scales(refq,experiment);bounds=endpoint_bounds(scenario,flights,rules);result['endpoint_bounds']=bounds;entries=[]
    for r in result['archive']:
        if not r['id'].startswith('pass2-'):continue
        document=dict(schema_version='1.0',model='nominal_vertical_fleet',profile_id='metric',mode_id='nominal',variant_id='base',duration_s=rules['duration_s'],source_sha256=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)),trajectories=r['trajectories'])
        path=output/'alternatives'/r['id'];write_json(path/'segments.json',document)
        saved=_read_json(path/'segments.json');v=ContinuousChecker(scenario,flights,rules).verify_document(saved)
        result['search']['independent_verifications']+=1
        q=evaluator.evaluate(saved['trajectories'])
        if not v['verified_safe'] or not q['terminal_vertical_speed_zero'] or q!=r['quality']:raise ValueError('Saved alternative failed verification')
        write_json(path/'verification.json',v);write_json(path/'quality.json',q)
        delta={k:float(sum(interval(q,k))/2-sum(interval(refq,k))/2) for k in OBJECTIVES}
        parent=next((a['quality'] for a in result['verified_comparisons'] if a['id']==r['origin']['parent_id']),refq)
        entries.append(dict(id=r['id'],label=r['id'],is_reference=False,group='second_pass',pareto_member=True,
                            segments_file=str(Path('alternatives')/r['id']/'segments.json'),segments_sha256=hashlib.sha256((path/'segments.json').read_bytes()).hexdigest(),
                            quality=q,verification=v,origin=r['origin'],differences_from_reference=delta,endpoint_gaps_m=endpoint_gaps(q,bounds),experimental_J=experimental_score(q,experiment),
                            changed_aircraft_delta_from_parent=q['changed_aircraft_count']-parent['changed_aircraft_count']))
    earlier=[]
    for e in first_catalog['entries']:
        dominators=[a['id'] for a in entries if dominates(a['quality'],e['quality'])]
        earlier.append(dict(id=e['id'],dominated_by_second_pass=dominators,quality=e['quality'],endpoint_gaps_m=endpoint_gaps(e['quality'],bounds)))
    catalog=dict(schema_version='2.0',objectives=list(OBJECTIVES),experiment=experiment,source_sha256=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)),
                 reference_segments_sha256=hashlib.sha256((reference_dir/'segments.json').read_bytes()).hexdigest(),first_catalog_sha256=hashlib.sha256((first_dir/'catalog.json').read_bytes()).hexdigest(),
                 entries=entries,endpoint_bounds=bounds,earlier_comparisons=earlier,search=result['search'])
    write_json(output/'catalog.json',catalog);write_json(output/'search.json',result['search']);write_json(output/'endpoint_bounds.json',bounds)
    write_json(output/'verified_comparisons.json',result['verified_comparisons'])
    write_summary(catalog,first_catalog,output)
    return catalog


def write_summary(catalog,first_catalog,output):
    bounds=catalog['endpoint_bounds'];entries=catalog['entries'];earlier=catalog['earlier_comparisons']
    lines=['# Second-pass nominal quality alternatives','', 'Earlier reference and first-pass artifacts are unchanged. Endpoint bounds derive from the current scenario; they are not universal constants. Every saved second-pass alternative passed fresh full continuous verification with zero violations/unresolved checks and zero terminal vertical speed.','',
           '| Plan | Dmax m | Dtotal m | Excursion m | A m·s | Travel m | Changed | Reversals | Dmax gap m | Dtotal gap m |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for e in first_catalog['entries']+entries:
        q=e['quality'];g=endpoint_gaps(q,bounds)
        lines.append('| '+e['id']+' | '+' | '.join((str(q[k]) if k.endswith('_count') else f'{q[k]:.6f}') for k in OBJECTIVES)+f" | {g['max_endpoint_deviation_m']:g} | {g['total_endpoint_deviation_m']:g} |")
    s=catalog['search'];attained=any(e['quality']['max_endpoint_deviation_m']==bounds['max_endpoint_deviation_lower_bound_m'] and e['quality']['total_endpoint_deviation_m']==bounds['total_endpoint_deviation_lower_bound_m'] for e in entries)
    lines+=['',f"Both endpoint lower bounds attained by a fully verified plan: {attained}. Only metrics with a valid attained lower bound are proven optimal; no other global optimality is claimed.",'',f"Evaluations {s['candidate_evaluations']}/{s['limits']['max_candidate_evaluations']}; full verifications {s['independent_verifications']}/{s['limits']['max_independent_verifications']}; archive {s['archive_size']}/{s['limits']['max_archive_size']}; runtime guard {s['limits']['max_seconds']} s; stop {s['stop_reason']}; pruning operations {len(s['archive_pruning'])}.",'', '## Earlier plans dominated by saved second-pass alternatives','']
    lines += [f"- {e['id']}: {', '.join(e['dominated_by_second_pass']) or 'none'}" for e in earlier]
    lines += ['', 'Seven raw objectives determine dominance. The unchanged frozen experimental J is never a ranking/filter criterion. Search is limited to configured level-to-level constant-acceleration schedules, terminal balancing, discrete peak/time grids and bounded coordinated neighbor repairs. Round-robin seeds/priorities preserve trade-off diversity. A failed candidate or exhausted budget does not prove infeasibility. The cooperative guard is checked between operations; seed checks and final export verification add a bounded tail. Pruned IDs and per-job stopping reasons are in search.json.']
    first_endpoint=min((e for e in first_catalog['entries'] if not e['is_reference']),key=lambda e:(e['quality']['max_endpoint_deviation_m'],e['quality']['total_endpoint_deviation_m'],e['quality']['accumulated_altitude_deviation_m_s']))
    witnesses=[e for e in entries if e['endpoint_gaps_m']['max_endpoint_deviation_m']==0 and e['endpoint_gaps_m']['total_endpoint_deviation_m']==0]
    lines+=['','## Achieved improvements and trade-offs','']
    if witnesses:
        witness=min(witnesses,key=lambda e:(e['quality']['accumulated_altitude_deviation_m_s'],e['id']))
        q=witness['quality'];old=first_endpoint['quality']
        added={r['flight_id'] for r in q['per_aircraft'] if r['changed']}-{r['flight_id'] for r in old['per_aircraft'] if r['changed']}
        restored={r['flight_id'] for r in old['per_aircraft'] if r['changed']}-{r['flight_id'] for r in q['per_aircraft'] if r['changed']}
        lines.append(f"Endpoint-optimal witness {witness['id']}: Dmax={q['max_endpoint_deviation_m']:g} m, Dtotal={q['total_endpoint_deviation_m']:g} m. Compared with first-pass endpoint plan {first_endpoint['id']}, excursion {old['max_altitude_excursion_m']:g} -> {q['max_altitude_excursion_m']:g} m, A {old['accumulated_altitude_deviation_m_s']:g} -> {q['accumulated_altitude_deviation_m_s']:g} m*s, travel {old['vertical_travel_m']:g} -> {q['vertical_travel_m']:g} m, changed {old['changed_aircraft_count']} -> {q['changed_aircraft_count']}, reversals {old['reversal_count']} -> {q['reversal_count']}. Added aircraft: {', '.join(sorted(added)) or 'none'}; restored aircraft: {', '.join(sorted(restored)) or 'none'}. A minimum changed-aircraft count is not proved.")
    lines.append('')
    for key,label in [('max_altitude_excursion_m','Maximum excursion'),('accumulated_altitude_deviation_m_s','Accumulated deviation'),('vertical_travel_m','Vertical travel')]:
        before=min(e['quality'][key] for e in first_catalog['entries'])
        after=min((e['quality'][key] for e in entries),default=before)
        lines.append(f"- Lowest saved {label.lower()} across each set, possibly different plans: first pass {before:.6f}; second pass {after:.6f}; difference {after-before:.6f}. These are observed set minima, not global optimality claims.")
    (Path(output)/'summary.md').write_text('\n'.join(lines)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-dir',type=Path,default=ROOT/'reports/planned');p.add_argument('--first-dir',type=Path,default=ROOT/'reports/improved')
    p.add_argument('--output-dir',type=Path,default=ROOT/'reports/improved_second');p.add_argument('--search-config',type=Path,default=ROOT/'experiments/quality_second.json')
    args=p.parse_args()
    try:
        for protected in (args.reference_dir,args.first_dir):
            a,b=args.output_dir.resolve(),protected.resolve()
            if a==b or a in b.parents or b in a.parents:raise ValueError('Output must be separate from earlier artifacts')
        scenario,flights=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json');experiment=_read_json(ROOT/'experiments/quality_score.json')
        starts,first=load_starts(args.reference_dir,args.first_dir)
        result=search(scenario,flights,rules,starts,_read_json(args.reference_dir/'search.json'),_read_json(args.search_config),
                      progress=lambda s,r:print(f"evaluation {s['candidate_evaluations']}, checks {s['independent_verifications']}, {r['id']}: "+', '.join(f'{k}={r["quality"][k]:g}' for k in OBJECTIVES),flush=True))
        c=export(result,scenario,flights,rules,starts,first,experiment,args.output_dir,args.reference_dir,args.first_dir)
    except (ValueError,OSError) as e:p.exit(2,str(e)+'\n')
    print(f"Saved {len(c['entries'])} second-pass alternatives; {c['search']['stop_reason']}")
if __name__=='__main__':main()
