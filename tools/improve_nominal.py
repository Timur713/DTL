#!/usr/bin/env python3
"""Improve the saved nominal reference, certify a bounded Pareto archive, export."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import _read_json,load_inputs,load_rules
from airspace.checker import ContinuousChecker,fingerprint
from airspace.improve import improve
from airspace.quality import LEGACY_OBJECTIVES as OBJECTIVES,experimental_score,interval,verify_reference_scales,QualityEvaluator


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')


def export_result(result,scenario,flights,rules,experiment,output,reference_path):
    output=Path(output);reference=result['reference'];verify_reference_scales(reference['quality'],experiment)
    entries=[]
    records=[reference]+[r for r in result['archive'] if r['id']!='reference']
    for record in records:
        is_reference=record['id']=='reference'
        if not is_reference:
            document=dict(schema_version='1.0',model='nominal_vertical_fleet',profile_id='metric',mode_id='nominal',variant_id='base',
                          duration_s=rules['duration_s'],source_sha256=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)),trajectories=record['trajectories'])
            destination=output/'alternatives'/record['id'];write_json(destination/'segments.json',document)
            saved=_read_json(destination/'segments.json')
            v=ContinuousChecker(scenario,flights,rules).verify_document(saved)
            result['search']['independent_verifications']+=1
            if not v['verified_safe']:raise ValueError('Exported candidate failed independent verification')
            q=QualityEvaluator(scenario,flights,rules).evaluate(saved['trajectories'])
            if q!=record['quality'] or not q['terminal_vertical_speed_zero']:raise ValueError('Exported quality mismatch')
            write_json(destination/'verification.json',v);write_json(destination/'quality.json',q)
            file_name=str(Path('alternatives')/record['id']/'segments.json')
            checksum=hashlib.sha256((destination/'segments.json').read_bytes()).hexdigest()
        else:
            file_name=str(Path(reference_path).resolve()) # reference link replaced with portable marker below
            checksum=hashlib.sha256(Path(reference_path).read_bytes()).hexdigest();v=record['verification'];q=record['quality']
        differences={key:float(sum(interval(q,key))/2-sum(interval(reference['quality'],key))/2)
                     for key in (*OBJECTIVES,'max_altitude_excursion_m')}
        entries.append(dict(id=record['id'],is_reference=is_reference,
            label='Unchanged verified reference' if is_reference else record['id'],
            pareto_member=any(r['id']==record['id'] for r in result['archive']),
            segments_file='REFERENCE' if is_reference else file_name,segments_sha256=checksum,
            quality=q,differences_from_reference=differences,experimental_J=experimental_score(q,experiment),
            verification=v,origin=record['origin']))
    catalog=dict(schema_version='1.0',configuration=dict(profile_id='metric',mode_id='nominal',variant_id='base',duration_s=rules['duration_s']),
                 reference_segments_sha256=entries[0]['segments_sha256'],source_sha256=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)),
                 experiment=experiment,reference_scales_verified=True,objectives=list(OBJECTIVES),entries=entries,
                 search=result['search'],limitations='Bounded local search; retained archive is capacity limited, not a proof of global optimality. Endpoint deviation is not airport arrival.')
    write_json(output/'catalog.json',catalog);write_json(output/'reference_quality.json',reference['quality']);write_json(output/'search.json',result['search'])
    write_json(output/'verified_comparisons.json',result['verified_comparisons'])
    lines=['# Nominal vertical quality alternatives','',
           'The reference under reports/planned/ is unchanged. Every saved alternative independently verifies all 40 aircraft over [0,1200] s with zero violations/unresolved checks and zero terminal vertical speed.',
           '', 'Six minimized Pareto objectives are Dmax, Dtotal, accumulated altitude deviation A, vertical travel L, changed-aircraft count N and reversals R. Maximum excursion is diagnostic. Endpoint deviations refer to the original endpoint, not airport arrival or landing.',
           '', '| Plan | Pareto | Dmax m | Dtotal m | A m·s | L m | N | R | Max excursion m | Experimental J |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for e in entries:
        q=e['quality'];lines.append(f"| {e['id']} | {'yes' if e['pareto_member'] else 'no'} | "+' | '.join(f'{q[k]:.6f}' if not k.endswith('_count') else str(q[k]) for k in (*OBJECTIVES,'max_altitude_excursion_m'))+f" | {e['experimental_J']['value']:.9f} |")
    s=result['search']
    lines+=['','## Search limits and findings','',f"Candidate evaluations: {s['candidate_evaluations']} / {s['limits']['max_candidate_evaluations']}; independent verifications: {s['independent_verifications']} / {s['limits']['max_independent_verifications']}; search runtime guard: {s['limits']['max_seconds']} s; stop: {s['stop_reason']}.",
            f"Verified feasible candidates including reference: {s['verified_feasible_count']}; retained Pareto size: {s['archive_size']} / {s['limits']['max_archive_size']}; capacity-pruning operations: {len(s['archive_pruning'])}.",
            'Six deterministic lexicographic strategies explore different objective priorities. Terminal transitions, altitude/time changes, original-aircraft restoration and coordinated changes are considered. Unchanged checks are reused; each admitted candidate receives a fresh complete independent verification.',
            'Archive dominance uses all six raw objectives. Capacity pruning, if needed, preserves objective extrema then normalized crowding distance; every removed ID is reported in search.json. The experimental J never ranks the search or filters the archive.',
            'Frozen J weights/scales are stored in experiments/quality_score.json. The reference exactly reproduces Dmax=6300, Dtotal=14100, A=19809900, L=47700 and J=1.',
            'The wall-clock guard is checked between bounded candidate/check operations, with a final verification/export tail. Candidate and verification caps are deterministic; a runtime stop can change the explored prefix. No global optimality or infeasibility claim is made.']
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return catalog


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',type=Path,default=ROOT/'scenario.json');parser.add_argument('--rules',type=Path,default=ROOT/'rules.json')
    parser.add_argument('--reference-dir',type=Path,default=ROOT/'reports/planned');parser.add_argument('--output-dir',type=Path,default=ROOT/'reports/improved')
    parser.add_argument('--search-config',type=Path,default=ROOT/'experiments/quality_search.json');parser.add_argument('--score-config',type=Path,default=ROOT/'experiments/quality_score.json')
    args=parser.parse_args()
    try:
        scenario,flights=load_inputs(args.scenario);rules=load_rules(args.rules);document=_read_json(args.reference_dir/'segments.json')
        experiment=_read_json(args.score_config)
        verify_reference_scales(QualityEvaluator(scenario,flights,rules).evaluate(document['trajectories']),experiment)
        result=improve(scenario,flights,rules,document,_read_json(args.reference_dir/'search.json'),_read_json(args.search_config),
            progress=lambda p,m,n,q:print(f"Strategy {p+1}, move {m}, evaluation {n}: Dmax={q['max_endpoint_deviation_m']:g}, total={q['total_endpoint_deviation_m']:g}, A={q['accumulated_altitude_deviation_m_s']:g}, L={q['vertical_travel_m']:g}, N={q['changed_aircraft_count']}, R={q['reversal_count']}",flush=True))
        catalog=export_result(result,scenario,flights,rules,experiment,args.output_dir,args.reference_dir/'segments.json')
    except (ValueError,OSError) as exc:parser.exit(2,f'Improvement failed: {exc}\n')
    print(f"Saved {len(catalog['entries'])-1} alternatives; {catalog['search']['stop_reason']}; {args.output_dir.resolve()}")


if __name__=='__main__':main()
