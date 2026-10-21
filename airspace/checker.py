"""Independent nominal continuous verification of serialized vertical schedules.

This module does not call VerticalTrajectory propagation or its limit checks,
no baseline conflict detector is used, and sampled CSV is never an input.
"""
from dataclasses import dataclass, replace
from fractions import Fraction as Q
from itertools import combinations
import hashlib
import json
import math

from .analysis import STATE_KEYS, _keys, _validate_rules, _validate_scenario
from .polynomial import (Boundary, IsolationUnresolved, NegativeCell, add, at,
                         derivative, mul, negative_cells, scale, trim)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def number(value, name):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be numeric, excluding bool")
    try:
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    except OverflowError as exc:
        raise ValueError(f"{name} is not representable") from exc
    return Q(str(value))


@dataclass(frozen=True)
class Piece:
    start: Q
    end: Q
    z: tuple  # polynomial in absolute simulation time
    az: Q


@dataclass(frozen=True)
class Compiled:
    flight_id: str
    x: tuple
    y: tuple
    pieces: tuple
    signature: str

    def piece_at(self, time):
        return next(p for p in self.pieces if p.start <= time < p.end or time == self.pieces[-1].end == p.end)


@dataclass(frozen=True)
class Event:
    type: str
    rule_id: str
    participants: tuple
    cell: NegativeCell

    def to_dict(self):
        return dict(type=self.type, rule_id=self.rule_id, participants=list(self.participants), **self.cell.to_dict())


@dataclass(frozen=True)
class Result:
    events: tuple = ()
    unresolved: tuple = ()

    @property
    def ok(self):
        return not self.events and not self.unresolved


def merge_events(events):
    out = []
    for event in sorted(events, key=lambda e: (e.type, e.rule_id, e.participants, e.cell.start.midpoint)):
        if out:
            last, a, b = out[-1], out[-1].cell, event.cell
            if ((last.type, last.rule_id, last.participants) == (event.type, event.rule_id, event.participants)
                    and a.end.low == a.end.high == b.start.low == b.start.high
                    and (a.end_inclusive or b.start_inclusive)):
                out[-1] = replace(last, cell=replace(a, end=b.end, end_inclusive=b.end_inclusive))
                continue
        out.append(event)
    return tuple(sorted(out, key=lambda e: (e.cell.start.midpoint, e.type, e.participants, e.rule_id)))


class ContinuousChecker:
    def __init__(self, scenario, flights, rules, *, mode_id="nominal", root_bits=36,
                 max_depth=160, max_nodes=10000):
        _validate_rules(rules)
        _validate_scenario(scenario, flights)
        if mode_id != "nominal":
            raise ValueError("Only metric / nominal / base verification is supported")
        if rules["units"] != "SI: m, s, m/s, m/s^2; angles explicitly labelled" or scenario.get("units") != "SI: meters, seconds, m/s. Origin at airspace center, x east, y north.":
            raise ValueError("Unsupported SI declarations")
        for name, value, minimum in (("root_bits", root_bits, 1), ("max_depth", max_depth, 0), ("max_nodes", max_nodes, 1)):
            if type(value) is not int or value < minimum:
                raise ValueError(f"Invalid {name}")
        self.scenario, self.rules = json.loads(canonical(scenario)), json.loads(canonical(rules))
        self.flights = {f["flight_id"]: json.loads(canonical(f)) for f in flights}
        self.horizon = number(rules["duration_s"], "duration_s")
        self.profile = next(p for p in rules["profiles"] if p["id"] == "metric")
        self.H, self.V = (number(self.profile[k], k) for k in ("horizontal_m", "vertical_m"))
        self.root_limits = dict(bits=root_bits, max_depth=max_depth, max_nodes=max_nodes)
        self._single_cache, self._pair_cache = {}, {}
        self.cache_hits = 0

    def compile(self, definition):
        _keys(definition, ("schema_version", "model", "units", "mode_id", "flight_id", "duration_s",
                           "initial_state", "segments", "source_sha256"), path="trajectory")
        for key, expected in (("schema_version", "1.0"), ("model", "piecewise_constant_vertical_acceleration"),
                              ("units", "SI: m, s, m/s, m/s^2"), ("mode_id", "nominal")):
            if type(definition[key]) is not str or definition[key] != expected:
                raise ValueError(f"Unsupported trajectory {key}")
        fid = definition["flight_id"]
        if not isinstance(fid, str) or fid not in self.flights:
            raise ValueError("Unknown source aircraft ID")
        flight = self.flights[fid]
        _keys(definition["initial_state"], STATE_KEYS, path="initial_state")
        initial = {k: number(definition["initial_state"][k], k) for k in STATE_KEYS}
        if any(initial[k] != number(flight[k], k) for k in STATE_KEYS):
            raise ValueError("Initial state differs from source")
        if number(definition["duration_s"], "duration_s") != self.horizon:
            raise ValueError("Wrong trajectory horizon")
        expected = fingerprint(dict(flight=flight, scenario=self.scenario, rules=self.rules))
        if definition["source_sha256"] != expected:
            raise ValueError("Trajectory provenance does not match inputs/configuration")
        segments = definition["segments"]
        if not isinstance(segments, list) or not segments:
            raise ValueError("Segments must be a nonempty list")
        pieces, time, z, vz = [], Q(0), initial["alt_m"], initial["vz_mps"]
        for segment in segments:
            _keys(segment, ("duration_s", "az_mps2"), path="segment")
            dt, az = number(segment["duration_s"], "duration_s"), number(segment["az_mps2"], "az_mps2")
            if dt <= 0 or time + dt > self.horizon:
                raise ValueError("Invalid segment duration/coverage")
            polynomial = trim((z - vz*time + az*time*time/2, vz - az*time, az/2))
            pieces.append(Piece(time, time+dt, polynomial, az))
            z, vz, time = z + vz*dt + az*dt*dt/2, vz + az*dt, time+dt
        if time != self.horizon:
            raise ValueError("Incomplete trajectory coverage")
        return Compiled(fid, trim((initial["x_m"], initial["vx_mps"])),
                        trim((initial["y_m"], initial["vy_mps"])), tuple(pieces), fingerprint(definition))

    def _check(self, polys, start, end, event_type, rule, participants, *, end_inclusive=True):
        try:
            cells = negative_cells(polys, start, end, **self.root_limits)
        except IsolationUnresolved as exc:
            return Result(unresolved=(dict(type=event_type, rule_id=rule, participants=list(participants),
                    start_s=float(start), end_s=float(end), reason=str(exc)),))
        events = tuple(Event(event_type, rule, participants,
                       replace(cell, end_inclusive=cell.end_inclusive and end_inclusive)) for cell in cells)
        return Result(events)

    def _collect(self, results):
        return Result(merge_events(e for r in results for e in r.events), tuple(u for r in results for u in r.unresolved))

    def zone_violation_witness(self, trajectory):
        """Cheap exact rejection only; absence of a witness proves nothing.

        Check rational endpoints/midpoints and horizontal CPA. A negative
        squared-distance predicate at any one time proves the candidate unsafe;
        every candidate without such a witness still needs continuous checks.
        """
        target = dict(self.scenario["target"], alt_m=self.rules["zones"]["target"]["center_alt_m"],
                      vx_mps=0, vy_mps=0, vz_mps=0)
        for label, obj, radius in (("THREAT", self.scenario["hostile_object"], self.rules["zones"]["threat"]["radius_m"]),
                                   ("TARGET", target, self.rules["zones"]["target"]["radius_m"])):
            rx = add(trajectory.x, scale((number(obj["x_m"], "x"), number(obj["vx_mps"], "vx")), -1))
            ry = add(trajectory.y, scale((number(obj["y_m"], "y"), number(obj["vy_mps"], "vy")), -1))
            horizontal = add(mul(rx, rx), mul(ry, ry))
            cpa = -horizontal[1]/(2*horizontal[2]) if len(horizontal) == 3 and horizontal[2] else Q(0)
            for piece in trajectory.pieces:
                rz = add(piece.z, scale((number(obj["alt_m"], "z"), number(obj["vz_mps"], "vz")), -1))
                for time in (piece.start, piece.end, (piece.start+piece.end)/2,
                             min(piece.end, max(piece.start, cpa))):
                    if at(horizontal, time)+at(rz, time)**2 < number(radius, "radius")**2:
                        return dict(participant=label, time_exact=str(time))
        return None

    def check_single(self, trajectory):
        if trajectory.signature in self._single_cache:
            self.cache_hits += 1
            return self._single_cache[trajectory.signature]
        fid, results = trajectory.flight_id, []
        lim = self.rules["motion_limits"]["aircraft"]
        bounds = self.scenario["airspace"]
        speed2 = trajectory.x[-1]**2 if len(trajectory.x) == 2 else Q(0)
        speed2 += trajectory.y[-1]**2 if len(trajectory.y) == 2 else Q(0)
        lo, hi = (number(lim[k], k) for k in ("horizontal_speed_min_mps", "horizontal_speed_max_mps"))
        for rule, value in (("horizontal_speed_min", speed2-lo*lo), ("horizontal_speed_max", hi*hi-speed2)):
            results.append(self._check([(value,)], 0, self.horizon, "motion", rule, (fid,)))
        # All XY accelerations, turn rates and bank angles are identically zero;
        # the input validator proves their configured upper bounds nonnegative.
        for piece in trajectory.pieces:
            z, vz, az = piece.z, derivative(piece.z), piece.az
            vmax = number(lim["vertical_speed_abs_max_mps"], "vertical_speed")
            amax = number(lim["vertical_acceleration_abs_max_mps2"], "vertical_acceleration")
            constraints = (
                ("altitude", "altitude_min", add(z, (-number(bounds["alt_min_m"], "alt_min"),))),
                ("altitude", "altitude_max", add(scale(z, -1), (number(bounds["alt_max_m"], "alt_max"),))),
                ("motion", "vertical_speed_min", add(vz, (vmax,))),
                ("motion", "vertical_speed_max", add(scale(vz, -1), (vmax,))),
                ("motion", "vertical_acceleration_min", (az+amax,)),
                ("motion", "vertical_acceleration_max", (amax-az,)))
            for kind, rule, polynomial in constraints:
                results.append(self._check([polynomial], piece.start, piece.end, kind, rule, (fid,),
                    end_inclusive=not rule.startswith("vertical_acceleration") or piece.end == self.horizon))
            for kind, label, obj, radius in (
                ("aircraft_threat", "THREAT", self.scenario["hostile_object"], self.rules["zones"]["threat"]["radius_m"]),
                ("aircraft_target", "TARGET", dict(self.scenario["target"], alt_m=self.rules["zones"]["target"]["center_alt_m"],
                    vx_mps=0, vy_mps=0, vz_mps=0), self.rules["zones"]["target"]["radius_m"])):
                rx = add(trajectory.x, scale((number(obj["x_m"], "x"), number(obj["vx_mps"], "vx")), -1))
                ry = add(trajectory.y, scale((number(obj["y_m"], "y"), number(obj["vy_mps"], "vy")), -1))
                rz = add(z, scale((number(obj["alt_m"], "z"), number(obj["vz_mps"], "vz")), -1))
                distance = add(add(mul(rx, rx), mul(ry, ry)), mul(rz, rz))
                distance = add(distance, (-number(radius, "radius")**2,))
                results.append(self._check([distance], piece.start, piece.end, kind,
                                          "threat_sphere" if label == "THREAT" else "target_sphere", (fid, label)))
        result = self._collect(results)
        self._single_cache[trajectory.signature] = result
        return result

    def check_pair(self, first, second):
        first, second = sorted((first, second), key=lambda t: t.flight_id)
        key = first.signature, second.signature
        if key in self._pair_cache:
            self.cache_hits += 1
            return self._pair_cache[key]
        rx, ry = add(first.x, scale(second.x, -1)), add(first.y, scale(second.y, -1))
        horizontal = add(add(mul(rx, rx), mul(ry, ry)), (-self.H**2,))
        cuts = sorted({p.start for t in (first, second) for p in t.pieces} | {self.horizon})
        results = []
        for a, b in zip(cuts, cuts[1:]):
            dz = add(first.piece_at(a).z, scale(second.piece_at(a).z, -1))
            polys = [horizontal, add(dz, (-self.V,)), add(scale(dz, -1), (-self.V,))]
            results.append(self._check(polys, a, b, "aircraft_aircraft", "aircraft_separation", (first.flight_id, second.flight_id)))
        result = self._collect(results)
        self._pair_cache[key] = result
        return result

    def verify_document(self, document):
        """Validate the complete planned-fleet envelope before its controls."""
        _keys(document, ("schema_version", "model", "profile_id", "mode_id", "variant_id",
                         "duration_s", "trajectories", "source_sha256"), path="planned fleet")
        for key, expected in (("schema_version", "1.0"), ("model", "nominal_vertical_fleet"),
                              ("profile_id", "metric"), ("mode_id", "nominal"), ("variant_id", "base")):
            if type(document[key]) is not str or document[key] != expected:
                raise ValueError(f"Unsupported fleet {key}")
        if number(document["duration_s"], "duration_s") != self.horizon:
            raise ValueError("Wrong fleet horizon")
        expected = fingerprint(dict(scenario=self.scenario, flights=list(self.flights.values()), rules=self.rules))
        if document["source_sha256"] != expected:
            raise ValueError("Fleet provenance does not match source inputs/configuration")
        return self.verify(document["trajectories"])

    def verify(self, definitions):
        if not isinstance(definitions, list):
            raise ValueError("Fleet definitions must be a list")
        fleet = [self.compile(d) for d in definitions]
        ids = [t.flight_id for t in fleet]
        if len(ids) != len(set(ids)) or set(ids) != set(self.flights):
            raise ValueError("Fleet must contain every source aircraft exactly once")
        fleet.sort(key=lambda t: t.flight_id)
        results = [self.check_single(t) for t in fleet]
        results.extend(self.check_pair(a, b) for a, b in combinations(fleet, 2))
        result = self._collect(results)
        counts = {kind: sum(e.type == kind for e in result.events) for kind in
                  ("aircraft_aircraft", "aircraft_threat", "aircraft_target", "altitude", "motion")}
        return dict(schema_version="1.0", checker="airspace.checker", profile_id="metric", mode_id="nominal", variant_id="base",
            duration_s=float(self.horizon), aircraft_count=len(fleet), pair_checks=len(fleet)*(len(fleet)-1)//2,
            aircraft_checks=len(fleet), verified_safe=result.ok, violation_count=len(result.events),
            unresolved_count=len(result.unresolved), counts_by_type=counts,
            events=[e.to_dict() for e in result.events], unresolved=list(result.unresolved),
            numerical_method="exact_rational_sturm_sign_cells", root_limits=self.root_limits,
            thresholds=dict(horizontal_m=float(self.H), vertical_m=float(self.V),
                threat_radius_m=self.rules["zones"]["threat"]["radius_m"], target_radius_m=self.rules["zones"]["target"]["radius_m"],
                target_alt_m=self.rules["zones"]["target"]["center_alt_m"],
                alt_min_m=self.scenario["airspace"]["alt_min_m"], alt_max_m=self.scenario["airspace"]["alt_max_m"]),
            fleet_sha256=fingerprint(sorted(definitions, key=lambda d: d["flight_id"])))
