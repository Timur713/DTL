"""Bounded multiobjective improvement of the saved, immutable nominal reference."""
from fractions import Fraction as Q
from itertools import combinations, product
import time

from .analysis import _keys
from .checker import ContinuousChecker, at, fingerprint, number
from .planner import _schedule, baseline_fleet
from .polynomial import derivative
from .quality import LEGACY_OBJECTIVES as OBJECTIVES, QualityEvaluator, dominates as _dominates, interval, lex_key
from .vertical import VerticalSegment, VerticalTrajectory


def dominates(a,b):
    return _dominates(a,b,OBJECTIVES)

def validate_search(config):
    _keys(config,('schema_version','max_candidate_evaluations','max_independent_verifications','max_archive_size',
                 'max_seconds','max_moves_per_strategy','return_times_s','offset_multiples','start_shifts_s','return_shifts_s'),path='improvement search')
    if config['schema_version']!='1.0':raise ValueError('Unsupported search schema')
    for key in ('max_candidate_evaluations','max_independent_verifications','max_archive_size','max_moves_per_strategy'):
        if type(config[key]) is not int or config[key]<1:raise ValueError('Invalid '+key)
    if config['max_independent_verifications']<=config['max_archive_size']:raise ValueError('Verification budget must reserve final archive checks')
    if number(config['max_seconds'],'max_seconds')<=0:raise ValueError('Invalid runtime bound')
    for key in ('return_times_s','offset_multiples','start_shifts_s','return_shifts_s'):
        if not isinstance(config[key],list) or not config[key]:raise ValueError('Invalid '+key)
        for value in config[key]:number(value,key)
    if any(v<0 for v in config['return_times_s']):raise ValueError('Negative return time')


def append_transition(definition,source,target_offset,start,scenario,rules):
    """Retain the prefix, then move from a level state to a requested endpoint."""
    checker=ContinuousChecker(scenario,[source],rules)
    compiled=checker.compile(definition);start=number(start,'start')
    if not 0<=start<checker.horizon:raise ValueError('Invalid transition start')
    piece=compiled.piece_at(start)
    if at(derivative(piece.z),start):raise ValueError('Additional transition must start level')
    target=number(source['alt_m'],'z')+number(source['vz_mps'],'vz')*checker.horizon+(target_offset if isinstance(target_offset,Q) else number(target_offset,'target'))
    delta=target-at(piece.z,start)
    if not delta:raise ValueError('No change')
    local=dict(rules,duration_s=float(checker.horizon-start))
    extra,unused=_schedule(source,delta,0,None,local)
    controls=[];t=Q(0)
    for segment in definition['segments']:
        dt=number(segment['duration_s'],'duration');end=t+dt
        if t>=start:break
        controls.append(VerticalSegment(float(min(end,start)-t),segment['az_mps2']))
        t=end
    controls.extend(extra)
    return VerticalTrajectory(source,controls,scenario,rules).to_dict()


def graph_close(first,second,rules):
    # Original horizontal endpoint overlap identifies jointly necessary returns.
    T=number(rules['duration_s'],'T')
    dx=number(first['x_m'],'x')-number(second['x_m'],'x')+(number(first['vx_mps'],'vx')-number(second['vx_mps'],'vx'))*T
    dy=number(first['y_m'],'y')-number(second['y_m'],'y')+(number(first['vy_mps'],'vy')-number(second['vy_mps'],'vy'))*T
    H=number(next(p for p in rules['profiles'] if p['id']=='metric')['horizontal_m'],'H')
    V=number(next(p for p in rules['profiles'] if p['id']=='metric')['vertical_m'],'V')
    dz=number(first['alt_m'],'z')-number(second['alt_m'],'z')+(number(first['vz_mps'],'vz')-number(second['vz_mps'],'vz'))*T
    return dx*dx+dy*dy<H*H and abs(dz)<V


def neighborhood(seed,sources,scenario,rules,repairs,config,policy,checker):
    current={d['flight_id']:d for d in seed}
    baseline={d['flight_id']:d for d in baseline_fleet(scenario,list(sources.values()),rules)}
    step=number(next(p for p in rules['profiles'] if p['id']=='metric')['vertical_m'],'V')
    changed=[fid for fid in sorted(current) if current[fid]['segments']!=baseline[fid]['segments']]
    terminal=[]
    for fid in changed:
        t=checker.compile(current[fid]);z=at(t.pieces[-1].z,checker.horizon)-number(sources[fid]['alt_m'],'z')
        if z:terminal.append(fid)
    def emit(updates,label):
        return [updates.get(fid,current[fid]) for fid in sorted(current)],dict(kind=label,aircraft=sorted(updates))
    def returns():
        yield from coordinated_returns()
        for fid in terminal:
            for target,start in product((0,step,-step),config['return_times_s']):
                try:d=append_transition(current[fid],sources[fid],target,start,scenario,rules)
                except ValueError:continue
                yield emit({fid:d},'terminal transition')
    def coordinated_returns():
        for first,second in combinations(changed,2):
            if first not in terminal and second not in terminal:continue
            if not graph_close(sources[first],sources[second],rules):continue
            for goals,start in product(product((0,step,-step),repeat=2),config['return_times_s']):
                try:
                    updates={fid:append_transition(current[fid],sources[fid],target,start,scenario,rules)
                             for fid,target in zip((first,second),goals)}
                except ValueError:continue
                yield emit(updates,'coordinated terminal transitions')
    def knobs():
        for fid in changed:
            if fid not in repairs:continue
            r=repairs[fid];offset=number(r['offset_m'],'offset')
            choices=[(offset+step*k,r['start_s'],r['return_start_s'],'altitude offset') for k in config['offset_multiples']]
            choices += [(offset,r['start_s']+dt,r['return_start_s'],'start time') for dt in config['start_shifts_s']]
            if r['return_start_s'] is not None:
                choices += [(offset,r['start_s'],r['return_start_s']+dt,'return time') for dt in config['return_shifts_s']]
                choices.append((offset,r['start_s'],None,'omit return'))
            for dz,start,ret,label in choices:
                if not dz or start<0:continue
                try:d=VerticalTrajectory(sources[fid],_schedule(sources[fid],dz,start,ret,rules)[0],scenario,rules).to_dict()
                except ValueError:continue
                yield emit({fid:d},label)
    def choices():
        for fid in changed:
            yield emit({fid:baseline[fid]},'restore original aircraft')
            # If restoring this aircraft is blocked by one pair, revisit the
            # other aircraft jointly rather than assuming one-at-a-time changes.
            original=checker.compile(baseline[fid])
            blockers=[]
            if not checker.check_single(original).ok:continue
            for other in changed:
                if other!=fid and not checker.check_pair(original,checker.compile(current[other])).ok:blockers.append(other)
            if len(blockers)!=1 or blockers[0] not in repairs:continue
            other=blockers[0];r=repairs[other]
            for k in config['offset_multiples']:
                try:d=VerticalTrajectory(sources[other],_schedule(sources[other],number(r['offset_m'],'offset')+step*k,
                                           r['start_s'],r['return_start_s'],rules)[0],scenario,rules).to_dict()
                except (ValueError,ZeroDivisionError):continue
                yield emit({fid:baseline[fid],other:d},'coordinated aircraft reassignment')
    families=(returns,knobs,choices) if policy in (0,5) else (knobs,returns,choices) if policy==1 else (choices,knobs,returns)
    for family in families:yield from family()


def pair_violation_witness(first,second,H,V,horizon):
    """Exact rejection only, never acceptance by a finite set of times."""
    x=(first.x+(Q(0),))[:2];xx=(second.x+(Q(0),))[:2]
    y=(first.y+(Q(0),))[:2];yy=(second.y+(Q(0),))[:2]
    rx,ry=x[0]-xx[0],y[0]-yy[0];vx,vy=x[1]-xx[1],y[1]-yy[1]
    speed=vx*vx+vy*vy
    cpa=min(horizon,max(Q(0),-(rx*vx+ry*vy)/speed)) if speed else Q(0)
    if (rx+vx*cpa)**2+(ry+vy*cpa)**2>=H*H:return False
    times={Q(0),horizon,cpa}
    cuts=sorted({p.start for t in (first,second) for p in t.pieces}|{horizon})
    times.update(cuts);times.update((a+b)/2 for a,b in zip(cuts,cuts[1:]))
    for t in times:
        if (rx+vx*t)**2+(ry+vy*t)**2<H*H and abs(at(first.piece_at(t).z,t)-at(second.piece_at(t).z,t))<V:return True
    return False


def objective_vector(record):
    return tuple(interval(record['quality'],key) for key in OBJECTIVES)


def prune_archive(archive,limit):
    """Keep objective extrema, then normalized crowding distance; never J."""
    if len(archive)<=limit:return archive,[]
    crowd={r['id']:0.0 for r in archive};extremes=set()
    for key in OBJECTIVES:
        ordered=sorted(archive,key=lambda r:(interval(r['quality'],key),r['id']))
        lo,hi=ordered[0]['quality'][key],ordered[-1]['quality'][key]
        if hi==lo:continue
        extremes.add(ordered[0]['id'])
        crowd[ordered[0]['id']]=crowd[ordered[-1]['id']]=float('inf')
        for i in range(1,len(ordered)-1):crowd[ordered[i]['id']]+=(ordered[i+1]['quality'][key]-ordered[i-1]['quality'][key])/(hi-lo)
    selected=sorted(archive,key=lambda r:(r['id'] not in extremes,-crowd[r['id']],r['id']))[:limit]
    keep={r['id'] for r in selected}
    return selected,[r['id'] for r in archive if r['id'] not in keep]


def improve(scenario,flights,rules,reference,history,config,progress=None):
    validate_search(config)
    if number(rules['duration_s'],'T')!=1200:raise ValueError('This experiment requires the unchanged 1200 s horizon')
    if any(number(f['vz_mps'],'vz')!=0 for f in flights):raise ValueError('Improvement search requires initially level source aircraft')
    checker=ContinuousChecker(scenario,flights,rules)
    verified=checker.verify_document(reference)
    if not verified['verified_safe']:raise ValueError('Reference must be independently verified safe')
    evaluator=QualityEvaluator(scenario,flights,rules)
    quality=evaluator.evaluate(reference['trajectories'])
    if not quality['terminal_vertical_speed_zero']:raise ValueError('Reference terminal vertical speed is nonzero')
    ref=dict(id='reference',trajectories=reference['trajectories'],quality=quality,verification=verified,origin=dict(kind='unchanged saved reference'))
    archive=[ref];certified=[ref];seen={fingerprint(ref['trajectories']):ref}
    stats=dict(candidate_evaluations=0,independent_verifications=1,rejected_safety=0,rejected_terminal_speed=0,
               unresolved_candidates=0,archive_pruning=[],strategies=[],limits=config,stop_reason='candidate_families_exhausted')
    sources={f['flight_id']:f for f in flights}
    repairs={r['flight_id']:r for r in history['accepted_repairs']}
    deadline=time.monotonic()+config['max_seconds']
    orders=[OBJECTIVES[i:]+OBJECTIVES[:i] for i in range(6)]
    # Explicit changed-aircraft and reversal priorities, plus both endpoint and
    # integral/travel priorities. No weighted score appears in this search.
    for policy,order in enumerate(orders):
        seed=ref;moves=0;local_attempts=0
        quota=(config['max_candidate_evaluations']+5)//6
        while moves<config['max_moves_per_strategy'] and local_attempts<quota:
            accepted=False
            for candidate,origin in neighborhood(seed['trajectories'],sources,scenario,rules,repairs,config,policy,checker):
                if time.monotonic()>=deadline:stats['stop_reason']='runtime_budget';break
                if stats['candidate_evaluations']>=config['max_candidate_evaluations']:stats['stop_reason']='candidate_budget';break
                if local_attempts>=quota:break
                key=fingerprint(candidate)
                if key in seen:
                    record=seen[key]
                    if record and lex_key(record['quality'],order)<lex_key(seed['quality'],order):seed=record;moves+=1;accepted=True;break
                    continue
                stats['candidate_evaluations']+=1;local_attempts+=1
                q=evaluator.evaluate(candidate)
                if not q['terminal_vertical_speed_zero']:
                    stats['rejected_terminal_speed']+=1;seen[key]=None;continue
                policy_better=lex_key(q,order)<lex_key(seed['quality'],order)
                promising=not any(dominates(r['quality'],q) or objective_vector(r)==tuple(interval(q,k) for k in OBJECTIVES) for r in certified)
                if not policy_better and not promising:continue
                changed=[(d,old) for d,old in zip(candidate,seed['trajectories']) if d!=old]
                fleet={d['flight_id']:checker.compile(d) for d in candidate}
                safe=True
                for d,unused in changed:
                    trajectory=fleet[d['flight_id']]
                    if checker.zone_violation_witness(trajectory) or not checker.check_single(trajectory).ok:safe=False;break
                    for other in sorted(fleet):
                        if other==trajectory.flight_id:continue
                        if pair_violation_witness(trajectory,fleet[other],checker.H,checker.V,checker.horizon):safe=False;break
                        result=checker.check_pair(trajectory,fleet[other])
                        if not result.ok:
                            stats['unresolved_candidates']+=bool(result.unresolved);safe=False;break
                    if not safe:break
                if not safe:
                    stats['rejected_safety']+=1;seen[key]=None;continue
                if stats['independent_verifications']>=config['max_independent_verifications']-config['max_archive_size']:
                    stats['stop_reason']='verification_budget';break
                verification=ContinuousChecker(scenario,flights,rules).verify(candidate)
                stats['independent_verifications']+=1
                if not verification['verified_safe']:
                    stats['rejected_safety']+=1;stats['unresolved_candidates']+=bool(verification['unresolved_count']);seen[key]=None;continue
                record=dict(id='alt-'+key[:12],trajectories=candidate,quality=q,verification=verification,
                            origin=dict(origin,parent_id=seed['id'],strategy=order[0]))
                seen[key]=record;certified.append(record)
                if promising:
                    archive=[r for r in archive if not dominates(q,r['quality'])]+[record]
                    archive,pruned=prune_archive(archive,config['max_archive_size'])
                    if pruned:stats['archive_pruning'].append(dict(at_evaluation=stats['candidate_evaluations'],removed_ids=pruned,reason='archive capacity; objective extrema then normalized crowding'))
                if policy_better:
                    seed=record;moves+=1;accepted=True
                    if progress:progress(policy,moves,stats['candidate_evaluations'],q)
                    break
            if not accepted or stats['stop_reason'].endswith('_budget'):break
        stats['strategies'].append(dict(primary_objective=order[0],evaluations=local_attempts,accepted_moves=moves,final_seed=seed['id']))
        if stats['stop_reason'].endswith('_budget'):break
    # Global certified-metric history also excludes points dominated by a
    # capacity-pruned solution; output archive is pairwise nondominated.
    archive=[r for r in archive if not any(dominates(other['quality'],r['quality']) for other in certified if other is not r)]
    stats['verified_feasible_count']=len(certified)
    stats['archive_size']=len(archive)
    stats['reference_nondominated']=not any(dominates(r['quality'],quality) for r in certified)
    if stats['candidate_evaluations']>=config['max_candidate_evaluations']:stats['stop_reason']='candidate_budget'
    return dict(reference=ref,archive=sorted(archive,key=lambda r:objective_vector(r)),search=stats,
                verified_comparisons=[dict(id=r['id'],quality=r['quality'],origin=r['origin']) for r in certified])
