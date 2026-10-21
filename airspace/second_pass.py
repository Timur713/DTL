"""Seven-objective, multi-start, bounded second-pass nominal search."""
from fractions import Fraction as Q
from itertools import combinations,product,zip_longest
import time
from .analysis import _keys
from .checker import ContinuousChecker,fingerprint,number
from .quality import OBJECTIVES,QualityEvaluator,dominates,interval,lex_key
from .endpoint_bounds import endpoint_bounds,endpoint_gaps
from .improve import append_transition,pair_violation_witness
from .planner import _schedule,baseline_fleet
from .vertical import VerticalTrajectory,VerticalSegment


def validate_config(c):
    _keys(c,('schema_version','max_candidate_evaluations','max_independent_verifications','max_archive_size','max_seconds',
             'max_moves_per_job','candidates_per_turn','seed_ids','target_aircraft','terminal_times_s','peak_offsets_m',
             'start_times_s','return_times_s','nearby_offsets_m','time_shifts_s'),path='second-pass config')
    if c['schema_version']!='2.0':raise ValueError('Unsupported second-pass configuration')
    for key in ('max_candidate_evaluations','max_independent_verifications','max_archive_size','max_moves_per_job','candidates_per_turn'):
        if type(c[key]) is not int or c[key]<1:raise ValueError('Invalid '+key)
    if c['max_independent_verifications']<=c['max_archive_size']+len(c['seed_ids']):raise ValueError('Insufficient reserved verification budget')
    if number(c['max_seconds'],'max_seconds')<=0:raise ValueError('Invalid runtime guard')
    for key in ('seed_ids','target_aircraft'):
        if not isinstance(c[key],list) or not c[key] or any(not isinstance(v,str) or not v for v in c[key]) or len(set(c[key]))!=len(c[key]):raise ValueError('Invalid '+key)
    for key in ('terminal_times_s','peak_offsets_m','start_times_s','return_times_s','nearby_offsets_m','time_shifts_s'):
        if not isinstance(c[key],list) or not c[key]:raise ValueError('Invalid '+key)
        for v in c[key]:number(v,key)
    if any(v<0 for key in ('terminal_times_s','start_times_s','return_times_s') for v in c[key]):raise ValueError('Negative time')


def level_schedule(source,peak,start,return_start,terminal,scenario,rules):
    """Two level-to-level transitions with an arbitrary final offset, no jumps."""
    start=start if isinstance(start,Q) else number(start,'start')
    peak=peak if isinstance(peak,Q) else number(peak,'peak')
    terminal=terminal if isinstance(terminal,Q) else number(terminal,'terminal')
    T=number(rules['duration_s'],'T')
    if not 0<=start<T:raise ValueError('Invalid start')
    controls=[]
    if start:controls.append(VerticalSegment(float(start),0))
    def transition(distance):
        if not distance:return Q(0)
        segments,duration=_schedule(source,distance,0,None,rules)
        elapsed=Q(0)
        for seg in segments:
            dt=min(number(seg.duration_s,'dt'),duration-elapsed)
            if dt>0:controls.append(VerticalSegment(float(dt),seg.az_mps2));elapsed+=dt
            if elapsed==duration:break
        return duration
    end=start+transition(peak)
    if return_start is None:
        if terminal!=peak:raise ValueError('Terminal offset differs from held peak')
    else:
        ret=return_start if isinstance(return_start,Q) else number(return_start,'return_start')
        if ret<end:raise ValueError('Return before climb complete')
        if ret>end:controls.append(VerticalSegment(float(ret-end),0))
        end=ret+transition(terminal-peak)
    if end>T:raise ValueError('Beyond horizon')
    if end<T:controls.append(VerticalSegment(float(T-end),0))
    return VerticalTrajectory(source,controls,scenario,rules).to_dict()


def interleave(*iterators):
    sentinel=object()
    for group in zip_longest(*iterators,fillvalue=sentinel):
        for item in group:
            if item is not sentinel:yield item


def neighborhood(seed,sources,scenario,rules,repairs,config,checker,bounds,kind):
    current={d['flight_id']:d for d in seed['trajectories']}
    quality={r['flight_id']:r for r in seed['quality']['per_aircraft']}
    targets=config['target_aircraft']
    def emit(updates,label,parameters):
        return [updates.get(fid,current[fid]) for fid in sorted(current)],dict(kind=label,aircraft=sorted(updates),parameters=parameters)
    def terminals():
        half=checker.V/2
        pairs=[p['aircraft'] for p in bounds['disjoint_pairs']]
        # Complete endpoint balancing first, both pair orientations explicitly.
        for signs,t in product(product((1,-1),repeat=len(pairs)),config['terminal_times_s']):
            updates={};params=[]
            try:
                for (a,b),sign in zip(pairs,signs):
                    for fid,goal in ((a,-sign*half),(b,sign*half)):
                        if Q(str(quality[fid]['terminal_altitude_offset_m']))==goal:continue
                        updates[fid]=append_transition(current[fid],sources[fid],goal,t,scenario,rules)
                        params.append(dict(flight_id=fid,target_offset_m=float(goal),start_s=t))
            except ValueError:continue
            if updates:yield emit(updates,'balanced disjoint terminal pairs',params)
        for pair in pairs:
            for sign,t in product((1,-1),config['terminal_times_s']):
                updates={}
                try:
                    for fid,goal in zip(pair,(-sign*half,sign*half)):
                        if Q(str(quality[fid]['terminal_altitude_offset_m']))!=goal:updates[fid]=append_transition(current[fid],sources[fid],goal,t,scenario,rules)
                except ValueError:continue
                if updates:yield emit(updates,'balanced terminal pair',dict(pair=pair,sign=sign,start_s=t))
    def peaks():
        def aircraft_candidates(fid):
            old=quality[fid]['max_altitude_excursion_m']
            # Try the nearest smaller peaks first; huge failing jumps should
            # not consume every starting point's local budget.
            offsets=sorted(config['peak_offsets_m'],key=lambda z:(z>=old,abs(z-old),z))
            r=repairs.get(fid,{})
            times=list(dict.fromkeys(([r['return_start_s']] if r.get('return_start_s') is not None else [])+config['return_times_s']))
            for peak,start,ret in product(offsets,config['start_times_s'],times):
                try:d=level_schedule(sources[fid],peak,start,ret,quality[fid]['terminal_altitude_offset_m'],scenario,rules)
                except ValueError:continue
                yield emit({fid:d},'target peak and timing',dict(flight_id=fid,peak_m=peak,start_s=start,return_start_s=ret))
        yield from interleave(*(aircraft_candidates(fid) for fid in targets))
    def coordinated():
        # Replace a blocked target together with up to two nearest blocking
        # aircraft. Only changed obligations are checked; fresh full verification
        # is still required before any acceptance.
        for index,ret in product(range(len(config['peak_offsets_m'])),config['return_times_s']):
            for fid in targets:
                old=quality[fid]['max_altitude_excursion_m']
                peak=sorted(config['peak_offsets_m'],key=lambda z:(z>=old,abs(z-old),z))[index]
                try:d=level_schedule(sources[fid],peak,0,ret,quality[fid]['terminal_altitude_offset_m'],scenario,rules)
                except ValueError:continue
                compiled=checker.compile(d)
                if checker.zone_violation_witness(compiled) or not checker.check_single(compiled).ok:continue
                blockers=[]
                for other in sorted(current):
                    if other!=fid and not checker.check_pair(compiled,checker.compile(current[other])).ok:blockers.append(other)
                if not 1<=len(blockers)<=2:continue
                for shift in config['nearby_offsets_m']:
                    updates={fid:d}
                    try:
                        for other in blockers:
                            old=quality[other];peak2=old['max_altitude_excursion_m']+shift
                            r=repairs.get(other,dict(start_s=max(0,ret-300),return_start_s=ret+100))
                            ret2=r['return_start_s'] if r['return_start_s'] is not None else ret+100
                            updates[other]=level_schedule(sources[other],peak2,r['start_s'],ret2,old['terminal_altitude_offset_m'],scenario,rules)
                    except ValueError:continue
                    yield emit(updates,'target with blocking neighbors',dict(target=fid,peak_m=peak,return_start_s=ret,neighbors=blockers,offset_change_m=shift))
        # Collective excursion reduction preserves relative altitude ordering
        # where possible, unlike one-at-a-time peak changes.
        for delta,ret in product(config['nearby_offsets_m'],config['return_times_s']):
            updates={}
            try:
                for fid in targets:
                    updates[fid]=level_schedule(sources[fid],quality[fid]['max_altitude_excursion_m']+delta,0,ret,
                                                quality[fid]['terminal_altitude_offset_m'],scenario,rules)
            except ValueError:continue
            yield emit(updates,'collective large-climb change',dict(offset_change_m=delta,return_start_s=ret))
    def broad():
        baseline={d['flight_id']:d for d in baseline_fleet(scenario,list(sources.values()),rules)}
        for fid in sorted(current):
            if not quality[fid]['changed']:continue
            yield emit({fid:baseline[fid]},'restore aircraft',dict(flight_id=fid))
            r=repairs.get(fid)
            if not r:continue
            for shift in config['nearby_offsets_m']:
                try:d=level_schedule(sources[fid],r['offset_m']+shift,r['start_s'],r['return_start_s'],
                                     quality[fid]['terminal_altitude_offset_m'],scenario,rules)
                except ValueError:continue
                yield emit({fid:d},'broader offset',dict(flight_id=fid,offset_change_m=shift))
            for dt in config['time_shifts_s']:
                ret=r['return_start_s']
                try:d=level_schedule(sources[fid],r['offset_m'],r['start_s'],None if ret is None else ret+dt,
                                     quality[fid]['terminal_altitude_offset_m'],scenario,rules)
                except ValueError:continue
                yield emit({fid:d},'broader timing',dict(flight_id=fid,return_shift_s=dt))
    if kind=='endpoint':yield from terminals()
    elif kind=='excursion':yield from interleave(peaks(),coordinated())
    else:yield from interleave(broad(),peaks(),terminals(),coordinated())


def prune(archive,limit):
    if len(archive)<=limit:return archive,[]
    extrema=set();crowd={r['id']:0.0 for r in archive}
    for k in OBJECTIVES:
        rows=sorted(archive,key=lambda r:(interval(r['quality'],k),r['id']))
        lo,hi=rows[0]['quality'][k],rows[-1]['quality'][k]
        if hi==lo:continue
        extrema.add(rows[0]['id']);crowd[rows[0]['id']]=crowd[rows[-1]['id']]=float('inf')
        for i in range(1,len(rows)-1):crowd[rows[i]['id']]+=(rows[i+1]['quality'][k]-rows[i-1]['quality'][k])/(hi-lo)
    kept=sorted(archive,key=lambda r:(r['id'] not in extrema,-crowd[r['id']],r['id']))[:limit]
    ids={r['id'] for r in kept}
    return kept,[r['id'] for r in archive if r['id'] not in ids]


def search(scenario,flights,rules,starts,history,config,progress=None):
    validate_config(config)
    checker=ContinuousChecker(scenario,flights,rules);evaluator=QualityEvaluator(scenario,flights,rules)
    if checker.horizon!=1200 or any(number(f['vz_mps'],'vz') for f in flights):raise ValueError('Second pass requires 1200 s and initially level sources')
    sources={f['flight_id']:f for f in flights}
    if not set(config['target_aircraft'])<=set(sources):raise ValueError('Unknown target aircraft')
    if not set(config['seed_ids'])<=set(starts):raise ValueError('Missing configured search seed')
    stats=dict(candidate_evaluations=0,independent_verifications=0,archive_pruning=[],rejected_safety=0,unresolved_candidates=0,
               stop_reason='job_families_exhausted',limits=config,jobs=[],seed_ids=config['seed_ids'])
    certified=[];seen={};archive=[]
    for key in config['seed_ids']:
        doc=starts[key];v=ContinuousChecker(scenario,flights,rules).verify_document(doc);stats['independent_verifications']+=1
        q=evaluator.evaluate(doc['trajectories'])
        if not v['verified_safe'] or not q['terminal_vertical_speed_zero']:raise ValueError('Invalid seed '+key)
        r=dict(id=key,trajectories=doc['trajectories'],quality=q,verification=v,origin=dict(kind='immutable earlier seed'))
        certified.append(r);seen[fingerprint(r['trajectories'])]=r
    for r in certified:
        if not any(dominates(o['quality'],r['quality']) for o in certified if o is not r):archive.append(r)
    bounds=endpoint_bounds(scenario,flights,rules);repairs={r['flight_id']:r for r in history['accepted_repairs']}
    orders=[OBJECTIVES[i:]+OBJECTIVES[:i] for i in range(len(OBJECTIVES))]
    jobs=[]
    # Round-robin all starting points and priorities, preserving early diversity.
    for priority,order in enumerate(orders):
        for record in certified:
            kind='endpoint' if priority<2 else 'excursion' if priority==2 else 'broad'
            jobs.append(dict(seed=record,order=order,kind=kind,moves=0,evaluations=0,iterator=None,done=False))
    deadline=time.monotonic()+config['max_seconds'];stopped=False
    def vector(q):return tuple(interval(q,k) for k in OBJECTIVES)
    while not stopped and any(not j['done'] for j in jobs):
        for j in jobs:
            if j['done']:continue
            if j['iterator'] is None:j['iterator']=iter(neighborhood(j['seed'],sources,scenario,rules,repairs,config,checker,bounds,j['kind']))
            for unused in range(config['candidates_per_turn']):
                if time.monotonic()>=deadline:stats['stop_reason']='runtime_budget';stopped=True;break
                if stats['candidate_evaluations']>=config['max_candidate_evaluations']:stats['stop_reason']='candidate_budget';stopped=True;break
                try:candidate,origin=next(j['iterator'])
                except StopIteration:j['done']=True;break
                key=fingerprint(candidate)
                if key in seen:
                    r=seen[key]
                    if r and lex_key(r['quality'],j['order'])<lex_key(j['seed']['quality'],j['order']):
                        j['seed']=r;j['moves']+=1;j['iterator']=None
                        if j['moves']>=config['max_moves_per_job']:j['done']=True
                        break
                    continue
                stats['candidate_evaluations']+=1;j['evaluations']+=1
                q=evaluator.evaluate(candidate)
                if not q['terminal_vertical_speed_zero']:seen[key]=None;continue
                better=lex_key(q,j['order'])<lex_key(j['seed']['quality'],j['order'])
                promising=not any(dominates(r['quality'],q) or vector(r['quality'])==vector(q) for r in certified)
                if not better and not promising:continue
                old={d['flight_id']:d for d in j['seed']['trajectories']}
                fleet={d['flight_id']:checker.compile(d) for d in candidate};safe=True
                for d in candidate:
                    fid=d['flight_id']
                    if d==old[fid]:continue
                    t=fleet[fid]
                    if checker.zone_violation_witness(t):safe=False;break
                    unary=checker.check_single(t)
                    if not unary.ok:stats['unresolved_candidates']+=bool(unary.unresolved);safe=False;break
                    for other in sorted(fleet):
                        if fid==other:continue
                        if pair_violation_witness(t,fleet[other],checker.H,checker.V,checker.horizon):safe=False;break
                        pair=checker.check_pair(t,fleet[other])
                        if not pair.ok:stats['unresolved_candidates']+=bool(pair.unresolved);safe=False;break
                    if not safe:break
                if not safe:stats['rejected_safety']+=1;seen[key]=None;continue
                if stats['independent_verifications']>=config['max_independent_verifications']-config['max_archive_size']:
                    stats['stop_reason']='verification_budget';stopped=True;break
                v=ContinuousChecker(scenario,flights,rules).verify(candidate);stats['independent_verifications']+=1
                if not v['verified_safe']:
                    stats['rejected_safety']+=1;stats['unresolved_candidates']+=bool(v['unresolved_count']);seen[key]=None;continue
                r=dict(id='pass2-'+key[:12],trajectories=candidate,quality=q,verification=v,
                       origin=dict(origin,parent_id=j['seed']['id'],priority=j['order'][0],at_evaluation=stats['candidate_evaluations']))
                seen[key]=r;certified.append(r)
                if promising:
                    archive=[a for a in archive if not dominates(q,a['quality'])]+[r]
                    archive,removed=prune(archive,config['max_archive_size'])
                    if removed:stats['archive_pruning'].append(dict(at_evaluation=stats['candidate_evaluations'],removed_ids=removed))
                if better:
                    j['seed']=r;j['moves']+=1;j['iterator']=None
                    if j['moves']>=config['max_moves_per_job']:j['done']=True
                if progress:progress(stats,r)
                if better:break
            if stopped:break
    archive=[a for a in archive if not any(dominates(b['quality'],a['quality']) for b in certified if b is not a)]
    stats['archive_size']=len(archive);stats['verified_feasible_count']=len(certified)
    stats['jobs']=[dict(start_seed=config['seed_ids'][i%len(config['seed_ids'])],priority=j['order'][0],moves=j['moves'],evaluations=j['evaluations'],final_seed=j['seed']['id'],stop='moves_cap' if j['moves']>=config['max_moves_per_job'] else 'family_exhausted' if j['done'] else stats['stop_reason']) for i,j in enumerate(jobs)]
    return dict(archive=sorted(archive,key=lambda r:vector(r['quality'])),search=stats,endpoint_bounds=bounds,
                verified_comparisons=[dict(id=r['id'],quality=r['quality'],origin=r['origin']) for r in certified])
