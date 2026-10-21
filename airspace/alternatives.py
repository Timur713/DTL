"""Validate saved quality alternatives and prepare offline plotting data."""
import hashlib
from pathlib import Path

from .analysis import _read_json
from .checker import ContinuousChecker,fingerprint
from .quality import QualityEvaluator,dominates,experimental_score,interval,OBJECTIVES,verify_reference_scales
from .replay import profile_data,ui_run


def prepare_alternatives(scenario,flights,rules,reference_dir,improved_dir,experiment):
    directory=Path(improved_dir);catalog=_read_json(directory/'catalog.json')
    if catalog.get('schema_version')!='1.0' or catalog.get('experiment')!=experiment:
        raise ValueError('Unsupported or stale quality catalog experiment')
    if catalog.get('source_sha256')!=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)):
        raise ValueError('Quality catalog source/configuration mismatch')
    ref_path=Path(reference_dir)/'segments.json'
    if hashlib.sha256(ref_path.read_bytes()).hexdigest()!=catalog.get('reference_segments_sha256'):
        raise ValueError('Quality catalog reference changed')
    evaluator=QualityEvaluator(scenario,flights,rules);sources={f['flight_id']:f for f in flights}
    ids=sorted(sources);versions=[];version_cache={};entries=[]
    reference_quality=None
    for entry in catalog['entries']:
        if entry['id']=='reference':
            path=ref_path
        else:
            path=(directory/entry['segments_file']).resolve()
            if directory.resolve() not in path.parents:raise ValueError('Invalid alternative path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['segments_sha256']:
            raise ValueError('Alternative file checksum mismatch')
        document=_read_json(path)
        verification=ContinuousChecker(scenario,flights,rules).verify_document(document)
        if verification!=entry['verification'] or not verification['verified_safe']:
            raise ValueError('Alternative independent verification mismatch')
        quality=evaluator.evaluate(document['trajectories'])
        if quality!=entry['quality'] or not quality['terminal_vertical_speed_zero']:
            raise ValueError('Alternative quality/terminal speed mismatch')
        if entry['id']=='reference':
            reference_quality=quality;verify_reference_scales(quality,experiment)
        if reference_quality is None:raise ValueError('Catalog reference must be first')
        difference={key:float(sum(interval(quality,key))/2-sum(interval(reference_quality,key))/2) for key in (*OBJECTIVES,'max_altitude_excursion_m')}
        if difference!=entry['differences_from_reference'] or experimental_score(quality,experiment)!=entry['experimental_J']:
            raise ValueError('Alternative score/difference mismatch')
        fleet=[]
        for definition in sorted(document['trajectories'],key=lambda d:d['flight_id']):
            signature=fingerprint(definition)
            if signature not in version_cache:
                version_cache[signature]=len(versions)
                versions.append(profile_data(definition,sources[definition['flight_id']],scenario,rules))
            fleet.append(version_cache[signature])
        entries.append(dict(entry,fleet_versions=fleet,run=ui_run(verification,entry['id'])))
    if len({e['id'] for e in entries})!=len(entries):raise ValueError('Duplicate quality alternative ID')
    archive=[e for e in entries if e['pareto_member']]
    for a in archive:
        if any(dominates(b['quality'],a['quality']) for b in archive if b is not a):
            raise ValueError('Stored archive contains a dominated member')
    return dict(schema_version='2.0',entries=entries,versions=versions,flight_ids=ids,
                experiment=experiment,search=catalog['search'],objectives=list(OBJECTIVES),
                scope='Metric / nominal / base, T=1200 s. Original endpoint deviation is not airport arrival.',
                reference_segments_sha256=catalog['reference_segments_sha256'],
                catalog_sha256=hashlib.sha256((directory/'catalog.json').read_bytes()).hexdigest())


def merge_second_pass(payload,scenario,flights,rules,reference_dir,first_dir,second_dir,experiment):
    """Freshly verify pass two; keep immutable first-pass membership separately."""
    from .endpoint_bounds import endpoint_bounds,endpoint_gaps
    directory=Path(second_dir);catalog=_read_json(directory/'catalog.json')
    bounds=endpoint_bounds(scenario,flights,rules)
    if catalog.get('schema_version')!='2.0' or catalog.get('objectives')!=list(OBJECTIVES) or catalog.get('experiment')!=experiment:
        raise ValueError('Unsupported second-pass catalog')
    if catalog['endpoint_bounds']!=bounds or catalog['source_sha256']!=bounds['source_sha256']:
        raise ValueError('Stale second-pass scenario or bounds')
    if catalog['reference_segments_sha256']!=payload['reference_segments_sha256'] or catalog['first_catalog_sha256']!=payload['catalog_sha256']:
        raise ValueError('Earlier solution provenance changed')
    evaluator=QualityEvaluator(scenario,flights,rules);sources={f['flight_id']:f for f in flights}
    ref=payload['entries'][0]['quality'];versions=payload['versions']
    version_cache={fingerprint(v):i for i,v in enumerate(versions)}
    for e in payload['entries']:
        e['group']='reference' if e['is_reference'] else 'first_pass'
        e['original_pareto_member']=e['pareto_member'];e['endpoint_gaps_m']=endpoint_gaps(e['quality'],bounds)
    for e in catalog['entries']:
        path=(directory/e['segments_file']).resolve()
        if directory.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest()!=e['segments_sha256']:raise ValueError('Invalid second-pass path/hash')
        document=_read_json(path);v=ContinuousChecker(scenario,flights,rules).verify_document(document)
        q=evaluator.evaluate(document['trajectories'])
        if v!=e['verification'] or not v['verified_safe'] or q!=e['quality'] or not q['terminal_vertical_speed_zero']:raise ValueError('Second-pass quality/verification mismatch')
        delta={k:float(sum(interval(q,k))/2-sum(interval(ref,k))/2) for k in OBJECTIVES}
        if delta!=e['differences_from_reference'] or endpoint_gaps(q,bounds)!=e['endpoint_gaps_m'] or experimental_score(q,experiment)!=e['experimental_J']:raise ValueError('Second-pass score/gap/difference mismatch')
        fleet=[]
        for d in sorted(document['trajectories'],key=lambda d:d['flight_id']):
            version=profile_data(d,sources[d['flight_id']],scenario,rules);signature=fingerprint(version)
            if signature not in version_cache:
                version_cache[signature]=len(versions);versions.append(version)
            fleet.append(version_cache[signature])
        payload['entries'].append(dict(e,fleet_versions=fleet,run=ui_run(v,e['id'])))
    entries=payload['entries']
    first_endpoint=min((e for e in entries if e['group']=='first_pass'),key=lambda e:(e['quality']['max_endpoint_deviation_m'],e['quality']['total_endpoint_deviation_m'],e['id']))
    prior_changed={r['flight_id'] for r in first_endpoint['quality']['per_aircraft'] if r['changed']}
    for e in entries:
        changed={r['flight_id'] for r in e['quality']['per_aircraft'] if r['changed']}
        e['first_endpoint_comparison']=dict(id=first_endpoint['id'],changed_aircraft_delta=e['quality']['changed_aircraft_count']-first_endpoint['quality']['changed_aircraft_count'],
                                            additional_aircraft=sorted(changed-prior_changed),restored_aircraft=sorted(prior_changed-changed))
    if len(set(e['id'] for e in entries))!=len(entries):raise ValueError('Duplicate combined solution ID')
    for e in entries:
        e['dominated_by']=[o['id'] for o in entries if o is not e and dominates(o['quality'],e['quality'])]
        e['pareto_member']=not e['dominated_by']
    second=[e for e in entries if e['group']=='second_pass']
    if any(any(dominates(b['quality'],a['quality']) for b in second if a is not b) for a in second):raise ValueError('Dominated second-pass archive member')
    payload.update(schema_version='2.0',objectives=list(OBJECTIVES),endpoint_bounds=bounds,
                   first_search=payload['search'],search=catalog['search'],second_catalog_sha256=hashlib.sha256((directory/'catalog.json').read_bytes()).hexdigest())
    return payload
