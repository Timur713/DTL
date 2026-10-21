"""Prepare offline comparison data from saved accepted repairs, never replan."""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

from .analysis import _read_json
from .checker import ContinuousChecker, at, fingerprint, number
from .planner import _schedule, baseline_fleet
from .polynomial import add, derivative, scale
from .vertical import VerticalTrajectory


def profile_data(definition, flight, scenario, rules, repair=None):
    """Exact extrema and phases; samples are diagnostic plotting data only."""
    model = VerticalTrajectory.from_dict(definition, flight=flight, scenario=scenario, rules=rules)
    compiled = ContinuousChecker(scenario, [flight], rules).compile(definition)
    maximum, phases = Q(0), []
    times = {Q(t) for t in range(0, int(model.duration_s)+1, 5)} | {number(model.duration_s, 'duration')}
    for piece, local in zip(compiled.pieces, model.segment_definitions()):
        delta = add(piece.z, scale((number(flight['alt_m'], 'z'), number(flight['vz_mps'], 'vz')), -1))
        d = derivative(delta)
        candidates = [piece.start, piece.end]
        if len(d) == 2 and d[1]:
            root = -d[0]/d[1]
            if piece.start < root < piece.end:
                candidates.append(root)
        maximum = max(maximum, *(abs(at(delta, t)) for t in candidates))
        times.update(candidates)
        mid = (piece.start+piece.end)/2
        vz = at(derivative(piece.z), mid)
        returning = repair is not None and repair['return_start_s'] is not None and piece.start >= number(repair['return_start_s'], 'return')
        if vz:
            kind = 'climb' if vz > 0 else 'descent'
            action = 'constant rate' if not piece.az else 'accelerate' if vz*piece.az > 0 else 'brake'
            label = ('Return · ' if returning else '')+kind.title()+' · '+action
        else:
            kind = 'hold' if at(delta, mid) else 'level'
            label = 'Altitude hold' if kind == 'hold' else 'Level flight'
        phases.append(dict(local, kind=kind, label=label))
    ordered = sorted(times)
    states = [model.state_at(float(t)) for t in ordered]
    dz = at(compiled.pieces[-1].z, compiled.pieces[-1].end) - number(flight['alt_m'], 'z') - number(flight['vz_mps'], 'vz')*compiled.pieces[-1].end
    return dict(flight_id=flight['flight_id'], segments=phases,
                max_altitude_deviation_m=float(maximum), terminal_altitude_offset_m=float(dz),
                remaining_destination_distance_m=float(abs(dz)),
                profile=dict(time_s=[float(t) for t in ordered], alt_m=[s.alt_m for s in states], vz_mps=[s.vz_mps for s in states]))


def ui_run(verification, step):
    events = []
    for i, original in enumerate(verification['events']):
        # Preserve certified brackets. Float roots are displayed approximations;
        # the exact rational violating witness supplies event navigation.
        e = dict(original)
        e.update(id=f'replay-{step}-{i}', flight_ids=[p for p in e['participants'] if p not in ('THREAT','TARGET')],
                 severity='nominal_violation', representative_s=e['witness_s'], metrics={},
                 initial_violation=e['start_s']==0 and e['start_inclusive'],
                 continues_at_horizon=e['end_s']==verification['duration_s'] and e['end_inclusive'])
        events.append(e)
    affected = sorted({fid for e in events for fid in e['flight_ids']})
    return dict(id=f'replay-{step}', profile_id='metric', mode_id='nominal', variant_id='base',
        thresholds=verification['thresholds'], events=events,
        unresolved_count=verification['unresolved_count'],
        summary=dict(event_count=len(events), aircraft_pair_count=len({tuple(e['participants']) for e in events if e['type']=='aircraft_aircraft'}),
                     affected_flight_count=len(affected), initial_event_count=sum(e['initial_violation'] for e in events)))


def prepare_replay(scenario, flights, rules, planned_dir):
    directory = Path(planned_dir)
    document = _read_json(directory/'segments.json')
    saved_verification = _read_json(directory/'verification.json')
    history = _read_json(directory/'search.json')
    checker = ContinuousChecker(scenario, flights, rules)
    final_verification = checker.verify_document(document)
    for key, value in final_verification.items():
        if saved_verification.get(key) != value:
            raise ValueError(f'Saved verification mismatch: {key}')
    if saved_verification.get('segments_file_sha256') != hashlib.sha256((directory/'segments.json').read_bytes()).hexdigest():
        raise ValueError('Saved segment file checksum mismatch')
    if not final_verification['verified_safe'] or history.get('status') != 'verified_safe':
        raise ValueError('Comparison requires an independently verified saved final plan')
    repairs = history.get('accepted_repairs')
    if not isinstance(repairs, list) or not repairs:
        raise ValueError('Saved accepted repair history is required')
    sources = {f['flight_id']:f for f in flights}
    ids = sorted(sources)
    current = {d['flight_id']:d for d in baseline_fleet(scenario, flights, rules)}
    versions, fleet_versions, steps = [], {}, []
    for fid in ids:
        fleet_versions[fid] = len(versions)
        versions.append(profile_data(current[fid], sources[fid], scenario, rules))
    if type(history.get('candidate_attempts')) is not int or history['candidate_attempts'] < len(repairs):
        raise ValueError('Invalid saved candidate-attempt count')
    previous = None
    for index, repair in enumerate([None, *repairs]):
        timing = None
        if repair is not None:
            required = {'flight_id','offset_m','start_s','return_start_s','removed_unary_events',
                        'removed_pair_events','introduced_pair_events','plateau_move'}
            if not isinstance(repair,dict) or repair.keys() != required:
                raise ValueError('Unsupported accepted-repair fields')
            fid = repair['flight_id']
            if fid not in sources:
                raise ValueError('Unknown repair aircraft')
            for key in ('offset_m','start_s'):
                number(repair[key],key)
            if repair['return_start_s'] is not None:
                number(repair['return_start_s'],'return_start_s')
            if not repair['offset_m'] or repair['start_s'] < 0 or (repair['return_start_s'] is not None and repair['return_start_s'] < repair['start_s']):
                raise ValueError('Invalid saved maneuver timing/offset')
            for key in ('removed_unary_events','removed_pair_events','introduced_pair_events'):
                if type(repair[key]) is not int or repair[key] < 0:
                    raise ValueError('Invalid repair event count')
            if type(repair['plateau_move']) is not bool:
                raise ValueError('Invalid plateau flag')
            controls, duration = _schedule(sources[fid], number(repair['offset_m'],'offset'),
                        number(repair['start_s'],'start'), None if repair['return_start_s'] is None else number(repair['return_start_s'],'return'), rules)
            timing = dict(transition_end_s=float(number(repair['start_s'],'start')+duration),
                          return_end_s=None if repair['return_start_s'] is None else float(number(repair['return_start_s'],'return')+duration))
            current[fid] = VerticalTrajectory(sources[fid],controls,scenario,rules).to_dict()
            fleet_versions[fid] = len(versions)
            versions.append(profile_data(current[fid], sources[fid], scenario, rules, repair))
        verification = checker.verify([current[fid] for fid in ids])
        if verification['unresolved_count']:
            raise ValueError('Cannot export unresolved search replay')
        if repair is not None:
            old = [e for e in previous['events'] if repair['flight_id'] in e['participants']]
            new = [e for e in verification['events'] if repair['flight_id'] in e['participants']]
            measured = dict(removed_unary_events=sum(e['type']!='aircraft_aircraft' for e in old),
                            removed_pair_events=sum(e['type']=='aircraft_aircraft' for e in old),
                            introduced_pair_events=sum(e['type']=='aircraft_aircraft' for e in new))
            if any(e['type']!='aircraft_aircraft' for e in new) or any(repair[k]!=v for k,v in measured.items()):
                raise ValueError(f'Step {index} conflict counts do not match saved history')
            old_score = (previous['violation_count']-previous['counts_by_type']['aircraft_aircraft'], previous['counts_by_type']['aircraft_aircraft'])
            score = (verification['violation_count']-verification['counts_by_type']['aircraft_aircraft'], verification['counts_by_type']['aircraft_aircraft'])
            if repair['plateau_move'] != (old_score == score) or score > old_score:
                raise ValueError('Replay objective disagrees with search history')
        counts = verification['counts_by_type']
        steps.append(dict(index=index, repair=repair, timing=timing, fleet_versions=[fleet_versions[fid] for fid in ids],
                    zone_count=counts['aircraft_threat']+counts['aircraft_target'],
                    pair_count=counts['aircraft_aircraft'], violation_count=verification['violation_count'],
                    unresolved_count=verification['unresolved_count'], run=ui_run(verification,index)))
        previous = verification
    if [current[fid] for fid in ids] != sorted(document['trajectories'],key=lambda d:d['flight_id']):
        raise ValueError('Final reconstructed controls differ from saved segments.json')
    if previous != final_verification:
        raise ValueError('Final replay verification differs from independent saved-plan verification')
    changed = []
    for fid in sorted({r['flight_id'] for r in repairs}):
        final = versions[fleet_versions[fid]]
        changed.append(dict(flight_id=fid, max_altitude_deviation_m=final['max_altitude_deviation_m'],
                            largest_accepted_deviation_m=max(v['max_altitude_deviation_m'] for v in versions if v['flight_id']==fid),
                            terminal_altitude_offset_m=final['terminal_altitude_offset_m'],
                            remaining_destination_distance_m=final['remaining_destination_distance_m'],
                            repair_steps=[i+1 for i,r in enumerate(repairs) if r['flight_id']==fid]))
    return dict(schema_version='1.0', configuration=dict(profile_id='metric',mode_id='nominal',variant_id='base'),
        source_sha256=fingerprint(dict(scenario=scenario,flights=flights,rules=rules)),
        saved_sha256={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ('segments.json','verification.json','search.json')},
        flight_ids=ids, versions=versions, steps=steps, changed_aircraft=changed,
        final_matches_saved=True, final_verification=final_verification,
        history_scope=f"Accepted repairs only ({len(repairs)} recorded steps from {history['candidate_attempts']:,} candidate attempts). Rejected candidates and their unrecorded details are not replayed.",
        event_time_semantics='Display roots are certified bracket midpoints; exact brackets retained. Near roots display status is approximate; the Python checker establishes safety.')
