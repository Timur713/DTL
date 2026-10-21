"""Deterministic bounded vertical repair search; final verification is uncached."""
from fractions import Fraction as Q
import math

from .checker import ContinuousChecker, merge_events, number
from .vertical import VerticalSegment, VerticalTrajectory


def baseline_fleet(scenario, flights, rules):
    return [VerticalTrajectory(f, [VerticalSegment(rules["duration_s"], 0)], scenario, rules).to_dict()
            for f in sorted(flights, key=lambda f: f["flight_id"])]


def _schedule(flight, offset, start, return_start, rules):
    """Trapezoidal vz: ramp, optional constant rate, brake, hold, optional mirror."""
    distance = abs(Q(offset))
    lim = rules["motion_limits"]["aircraft"]
    amax = number(lim["vertical_acceleration_abs_max_mps2"], "acceleration")
    vmax = number(lim["vertical_speed_abs_max_mps"], "speed")
    if not amax or not vmax:
        raise ValueError("No vertical maneuver authority")
    ramp = Q(20 if distance < amax * 30**2 else 30)
    acceleration = min(amax, vmax/ramp, distance/ramp**2)
    peak = acceleration*ramp
    cruise = (distance-acceleration*ramp**2)/peak
    sign = 1 if offset > 0 else -1
    up = [(ramp, sign*acceleration)]
    if cruise:
        up.append((cruise, Q(0)))
    up.append((ramp, -sign*acceleration))
    duration = 2*ramp+cruise
    controls = []
    if start:
        controls.append((Q(start), Q(0)))
    controls.extend(up)
    end = Q(start)+duration
    if return_start is not None:
        if return_start < end:
            raise ValueError("Return overlaps transition")
        if return_start > end:
            controls.append((Q(return_start)-end, Q(0)))
        controls.extend((dt, -az) for dt, az in up)
        end = Q(return_start)+duration
    horizon = number(rules["duration_s"], "duration_s")
    if end > horizon:
        raise ValueError("Schedule exceeds horizon")
    if end < horizon:
        controls.append((horizon-end, Q(0)))
    # The existing trajectory API is authoritative: it validates the actual
    # decimal controls, including any conversion effects in nondefault configs.
    return [VerticalSegment(float(dt), float(az)) for dt, az in controls], duration


def candidates(flight, event, scenario, rules):
    """Finite, deterministic family; offsets are separation-threshold multiples."""
    if flight["vz_mps"] != 0:
        return  # This search family is defined for the input level aircraft.
    step = number(next(p for p in rules["profiles"] if p["id"] == "metric")["vertical_m"], "step")
    area, horizon = scenario["airspace"], number(rules["duration_s"], "horizon")
    span = number(area["alt_max_m"], "max")-number(area["alt_min_m"], "min")
    for multiple in range(1, int(span//step)+1):
        for sign in (1, -1):
            offset = step*multiple*sign
            altitude = number(flight["alt_m"], "altitude")+offset
            if not number(area["alt_min_m"], "min") <= altitude <= number(area["alt_max_m"], "max"):
                continue
            try:
                unused, duration = _schedule(flight, offset, 0, None, rules)
            except ValueError:
                continue
            late = max(0, math.floor(event.cell.start.low-duration-30))
            starts = list(dict.fromkeys([late, 0, late//2, 30, 60, 90, 120]))
            for start in starts:
                return_time = max(Q(start)+duration, Q(math.ceil(event.cell.end.high)+30))
                returns = [return_time, None] if return_time+duration <= horizon else [None]
                for returning in returns:
                    try:
                        controls, unused = _schedule(flight, offset, start, returning, rules)
                    except ValueError:
                        continue
                    yield controls, dict(offset_m=float(offset), start_s=start,
                                         return_start_s=None if returning is None else float(returning))


def plan_fleet(scenario, flights, rules, *, max_candidates=20000, max_repairs=40, progress=None):
    for name, value in (("max_candidates", max_candidates), ("max_repairs", max_repairs)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    definitions = {d["flight_id"]: d for d in baseline_fleet(scenario, flights, rules)}
    sources = {f["flight_id"]: f for f in flights}
    checker = ContinuousChecker(scenario, flights, rules)
    initial = checker.verify(list(definitions.values()))
    current = {fid: checker.compile(d) for fid, d in definitions.items()}
    all_results = [checker.check_single(t) for t in current.values()]
    ids = sorted(current)
    all_results.extend(checker.check_pair(current[a], current[b]) for i, a in enumerate(ids) for b in ids[i+1:])
    remaining = merge_events(e for r in all_results for e in r.events)
    stats = dict(candidate_attempts=0, invalid_candidates=0, rejected_candidates=0,
                 unresolved_candidates=0, witness_rejections=0, accepted_repairs=[], max_candidates=max_candidates, max_repairs=max_repairs)
    graph_key = lambda events: tuple(sorted((e.type, e.rule_id, e.participants) for e in events))
    seen_graphs = {graph_key(remaining)}
    allow_plateau = False
    # Feasibility repair uses a lexicographically nonincreasing objective:
    # (unary zone/limit events, pair events). A zone repair may create temporary
    # pair conflicts, explicitly retained for later repairs. No unresolved
    # candidate can be accepted. When strict improvements are exhausted, one
    # equal-score move to an unseen conflict graph enables a bounded ejection
    # chain. The repair budget and graph history prevent cycling.
    # Unchanged obligations retain their results.
    while remaining and stats["candidate_attempts"] < max_candidates and len(stats["accepted_repairs"]) < max_repairs:
        accepted = False
        attempted_ids = set()
        for event in remaining:
            changed = {r["flight_id"] for r in stats["accepted_repairs"]}
            participants = sorted(event.participants, key=lambda fid: (fid in changed, fid))
            for fid in participants:
                if fid not in sources or fid in attempted_ids:
                    continue
                attempted_ids.add(fid)
                for controls, description in candidates(sources[fid], event, scenario, rules):
                    if stats["candidate_attempts"] >= max_candidates:
                        break
                    stats["candidate_attempts"] += 1
                    try:
                        candidate = VerticalTrajectory(sources[fid], controls, scenario, rules).to_dict()
                    except ValueError:
                        stats["invalid_candidates"] += 1
                        continue
                    compiled = checker.compile(candidate)
                    if checker.zone_violation_witness(compiled) is not None:
                        stats["rejected_candidates"] += 1
                        stats["witness_rejections"] += 1
                        continue
                    result = checker.check_single(compiled)
                    if not result.ok:
                        stats["rejected_candidates"] += 1
                        stats["unresolved_candidates"] += bool(result.unresolved)
                        continue
                    old_incident = [e for e in remaining if fid in e.participants]
                    old_unary = sum(e.type != "aircraft_aircraft" for e in old_incident)
                    new_events, uncertain = [], False
                    for other in ids:
                        if other == fid:
                            continue
                        result = checker.check_pair(compiled, current[other])
                        new_events.extend(result.events)
                        uncertain |= bool(result.unresolved)
                        too_many = len(new_events) > len(old_incident) or (not allow_plateau and len(new_events) == len(old_incident))
                        if uncertain or (not old_unary and too_many):
                            break
                    too_many = len(new_events) > len(old_incident) or (not allow_plateau and len(new_events) == len(old_incident))
                    next_remaining = merge_events([e for e in remaining if fid not in e.participants] + new_events)
                    plateau = not old_unary and len(new_events) == len(old_incident)
                    if uncertain or (not old_unary and too_many) or (plateau and graph_key(next_remaining) in seen_graphs):
                        stats["rejected_candidates"] += 1
                        stats["unresolved_candidates"] += uncertain
                        continue
                    definitions[fid], current[fid] = candidate, compiled
                    remaining = next_remaining
                    seen_graphs.add(graph_key(remaining))
                    allow_plateau = False
                    stats["accepted_repairs"].append(dict(flight_id=fid, plateau_move=plateau,
                        removed_unary_events=old_unary, removed_pair_events=len(old_incident)-old_unary,
                        introduced_pair_events=len(new_events), **description))
                    if progress is not None:
                        progress(stats["candidate_attempts"], len(stats["accepted_repairs"]), len(remaining), fid)
                    accepted = True
                    break
                if accepted:
                    break
            if accepted:
                break
        if not accepted:
            if not allow_plateau and stats["candidate_attempts"] < max_candidates:
                allow_plateau = True
                continue
            break
    fleet = [definitions[fid] for fid in ids]
    # Fresh instance, recompile authoritative controls and check all 780 pairs:
    # search caches and the trajectory constructor cannot certify the result.
    final = ContinuousChecker(scenario, flights, rules).verify(fleet)
    stats["cache_hits"] = checker.cache_hits
    stats["status"] = "verified_safe" if final["verified_safe"] else "bounded_search_incomplete"
    stats["stop_reason"] = ("verified_safe" if final["verified_safe"] else
        "candidate_budget" if stats["candidate_attempts"] >= max_candidates else
        "repair_budget" if len(stats["accepted_repairs"]) >= max_repairs else "candidate_family_exhausted")
    return dict(trajectories=fleet, initial_verification=initial, verification=final, search=stats)
