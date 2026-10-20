"""Continuous strict-inequality detector; no HTML/generator dependencies.

Polynomial coefficients and discriminant signs use exact rational arithmetic
on the canonical decimal representations of input numbers. Roots use 80-digit
Decimal arithmetic and the stable q formula. Numerical tolerances never alter
physical thresholds or join intervals across a safe point.
"""

import csv
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from pathlib import Path


EVENT_TYPES = ("aircraft_aircraft", "aircraft_threat", "aircraft_target", "altitude", "motion")
STATE_KEYS = ("x_m", "y_m", "alt_m", "vx_mps", "vy_mps", "vz_mps")
ERROR_KEYS = ("position_horizontal_m", "position_vertical_m", "velocity_horizontal_mps", "velocity_vertical_mps")


def _keys(value, required, optional=(), path="object"):
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % path)
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError("%s: missing keys %s; unsupported keys %s" % (path, sorted(missing), sorted(extra)))


def _number(value, path, minimum=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("%s must be a finite number" % path)
    if minimum is not None and value < minimum or positive and value <= 0:
        raise ValueError("%s is outside the supported range" % path)
    return value


def _finite_tree(value, path="input"):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("%s contains a nonfinite number" % path)
    if isinstance(value, dict):
        for key, item in value.items():
            _finite_tree(item, path + "." + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite_tree(item, "%s[%s]" % (path, index))


def _same(value, expected, path):
    # bool subclasses int in Python, but is a different JSON/input type. Walk
    # containers as well so [False, 0, 0] cannot impersonate a zero wind vector.
    if isinstance(expected, bool):
        matches = type(value) is bool and value == expected
    elif isinstance(expected, (int, float)):
        matches = type(value) in (int, float) and value == expected
    elif isinstance(expected, list):
        matches = isinstance(value, list) and len(value) == len(expected)
        if matches:
            for index, (actual_item, expected_item) in enumerate(zip(value, expected)):
                _same(actual_item, expected_item, "%s[%d]" % (path, index))
    elif isinstance(expected, dict):
        matches = isinstance(value, dict) and value.keys() == expected.keys()
        if matches:
            for key, expected_item in expected.items():
                _same(value[key], expected_item, path + "." + key)
    else:
        matches = type(value) is type(expected) and value == expected
    if not matches:
        raise ValueError("Unsupported %s: %r (expected %r)" % (path, value, expected))


def _semantics(section, expected, numeric=(), optional=(), path="rules"):
    _keys(section, tuple(expected) + tuple(numeric), optional, path)
    for key, expected_value in expected.items():
        _same(section[key], expected_value, path + "." + key)


def _validate_scenario(scenario, flights):
    _finite_tree(scenario, "scenario")
    _finite_tree(flights, "flights")
    _keys(scenario, ("airspace", "target", "hostile_object", "snapshot_time_s"),
          ("units", "flights_file"), "scenario")
    _same(scenario["snapshot_time_s"], 0, "scenario.snapshot_time_s")
    airspace = scenario["airspace"]
    _keys(airspace, ("x_min_m", "x_max_m", "y_min_m", "y_max_m", "alt_min_m", "alt_max_m"), path="scenario.airspace")
    for key, value in airspace.items():
        _number(value, "scenario.airspace." + key)
    for low, high in (("x_min_m", "x_max_m"), ("y_min_m", "y_max_m"), ("alt_min_m", "alt_max_m")):
        if airspace[low] >= airspace[high]:
            raise ValueError("scenario.airspace.%s must be below %s" % (low, high))
    _keys(scenario["target"], ("x_m", "y_m"), ("note",), "scenario.target")
    for key in ("x_m", "y_m"):
        _number(scenario["target"][key], "scenario.target." + key)
    _keys(scenario["hostile_object"], STATE_KEYS, ("type", "note"), "scenario.hostile_object")
    for key in STATE_KEYS:
        _number(scenario["hostile_object"][key], "scenario.hostile_object." + key)
    if "type" in scenario["hostile_object"]:
        _same(scenario["hostile_object"]["type"], "drone", "scenario.hostile_object.type")
    if not isinstance(flights, list) or not flights:
        raise ValueError("flights must be a nonempty list")
    ids = set()
    for index, flight in enumerate(flights):
        path = "flights[%d]" % index
        _keys(flight, ("flight_id",) + STATE_KEYS, path=path)
        flight_id = flight["flight_id"]
        if not isinstance(flight_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", flight_id) or "__" in flight_id:
            raise ValueError("%s.flight_id must be a nonempty simple identifier without '__'" % path)
        if flight_id in ids or flight_id in ("THREAT", "TARGET"):
            raise ValueError("Duplicate/reserved flight_id: " + flight_id)
        ids.add(flight_id)
        for key in STATE_KEYS:
            _number(flight[key], path + "." + key)


def _validate_rules(rules):
    _finite_tree(rules, "rules")
    _keys(rules, ("schema_version", "duration_s", "units", "defaults", "profiles", "modes", "uncertainty",
                  "zones", "motion_limits", "delays", "comparison", "assumptions", "sensitivity", "sources"), path="rules")
    _same(rules["schema_version"], "1.1", "rules.schema_version")
    _number(rules["duration_s"], "rules.duration_s", positive=True)
    _keys(rules["defaults"], ("profile_id", "mode_id", "variant_id"), path="rules.defaults")
    for list_key, ids in (("profiles", {"metric", "feet_reference"}), ("modes", {"nominal", "bounded_stress"})):
        entries = rules[list_key]
        if not isinstance(entries, list) or len(entries) != len(ids) or {e.get("id") for e in entries if isinstance(e, dict)} != ids:
            raise ValueError("rules.%s must contain exactly %s" % (list_key, sorted(ids)))
    for profile in rules["profiles"]:
        _keys(profile, ("id", "horizontal_m", "vertical_m"), ("label",), "profile")
        for key in ("horizontal_m", "vertical_m"):
            _number(profile[key], "profile." + key, positive=True)
    for mode in rules["modes"]:
        _keys(mode, ("id", "severity", "error_bounds"), ("label",), "mode")
        _same(mode["severity"], "nominal_violation" if mode["id"] == "nominal" else "possible_violation", "mode.severity")
        _keys(mode["error_bounds"], ERROR_KEYS, path="mode.error_bounds")
        for key in ERROR_KEYS:
            _number(mode["error_bounds"][key], "mode.error_bounds." + key, minimum=0)
            if mode["id"] == "nominal" and mode["error_bounds"][key] != 0:
                raise ValueError("nominal mode requires zero error bounds")
    _semantics(rules["uncertainty"], {
        "applies_to": ["aircraft", "threat"], "target_exact": True,
        "horizontal_set": "euclidean_disk", "vertical_set": "symmetric_interval",
        "reference_time_s": 0, "reset_on_frame": False,
        "horizontal_formula": "position_horizontal_m + velocity_horizontal_mps * t",
        "vertical_formula": "position_vertical_m + velocity_vertical_mps * t",
        "sphere_error_bound": "horizontal_plus_vertical", "pair_combination": "sum_of_individual_bounds",
        "interpretation": "deterministic_bounds_not_probabilities"}, path="rules.uncertainty")
    _keys(rules["zones"], ("aircraft", "threat", "target", "altitude", "horizontal_airspace"), path="rules.zones")
    _semantics(rules["zones"]["aircraft"], {"shape": "relative_cylinder", "thresholds_from": "profile",
        "violation": "horizontal_distance < horizontal_m AND absolute_vertical_distance < vertical_m"}, path="rules.zones.aircraft")
    _semantics(rules["zones"]["threat"], {"shape": "sphere", "violation": "distance_3d < effective_radius",
        "stress_expansion": "e_h_aircraft + e_z_aircraft + e_h_threat + e_z_threat"}, ("radius_m",), path="rules.zones.threat")
    _semantics(rules["zones"]["target"], {"shape": "sphere", "violation": "distance_3d < effective_radius",
        "stress_expansion": "e_h_aircraft + e_z_aircraft"}, ("radius_m", "center_alt_m"), path="rules.zones.target")
    _number(rules["zones"]["target"]["center_alt_m"], "rules.zones.target.center_alt_m")
    for zone in ("target", "threat"):
        _number(rules["zones"][zone]["radius_m"], "rules.zones." + zone + ".radius_m", positive=True)
    _semantics(rules["zones"]["altitude"], {"bounds_from": "scenario.airspace", "min_key": "alt_min_m",
        "max_key": "alt_max_m", "allowed_boundary_inclusive": True, "applies_to": "aircraft",
        "stress_rule": "z - e_z < alt_min_m OR z + e_z > alt_max_m"}, path="rules.zones.altitude")
    _semantics(rules["zones"]["horizontal_airspace"], {"bounds_from": "scenario.airspace", "safety_constraint": False,
        "retain_objects_outside": True}, path="rules.zones.horizontal_airspace")
    motion = rules["motion_limits"]
    _semantics(motion, {"model": "generic_jet_assumption", "maneuvers_implemented": False,
        "checks_apply_to": "all_admissible_constant_velocity_aircraft_trajectories_in_selected_mode",
        "stress_horizontal_speed_interval": "[max(0, norm(v_xy) - velocity_horizontal_mps), norm(v_xy) + velocity_horizontal_mps]",
        "stress_vertical_speed_interval": "[vz - velocity_vertical_mps, vz + velocity_vertical_mps]",
        "velocity_error_constant_over_horizon": True, "baseline_acceleration_mps2": [0, 0, 0],
        "baseline_turn_rate_radps": 0}, ("aircraft",), path="rules.motion_limits")
    limits = motion["aircraft"]
    limit_keys = ("horizontal_speed_min_mps", "horizontal_speed_max_mps", "horizontal_acceleration_abs_max_mps2",
                  "vertical_speed_abs_max_mps", "vertical_acceleration_abs_max_mps2", "bank_abs_max_deg", "gravity_mps2")
    _semantics(limits, {
        "horizontal_acceleration_definition": "absolute_derivative_of_horizontal_speed_not_total_horizontal_vector_acceleration",
        "turn_rate_formula": "g * tan(bank_abs_max_deg * pi / 180) / horizontal_speed_mps",
        "turn_rate_unit": "rad/s", "wind_mps": [0, 0, 0]}, limit_keys, path="rules.motion_limits.aircraft")
    for key in limit_keys:
        _number(limits[key], "rules.motion_limits.aircraft." + key, minimum=0)
    if limits["horizontal_speed_min_mps"] > limits["horizontal_speed_max_mps"] or limits["bank_abs_max_deg"] >= 90 or limits["gravity_mps2"] <= 0:
        raise ValueError("Unsupported motion limit range")
    _semantics(rules["delays"], {"observation_s": 0, "communication_s": 0, "execution_s": 0,
        "positive_delays_supported": False}, path="rules.delays")
    _semantics(rules["comparison"], {"distance_violation_operator": "strict_less_than", "equality_is_safe": True,
        "horizon_closed": True, "method": "continuous_affine_motion_quadratic_intervals", "epsilon_is_physical_buffer": False,
        "epsilon_policy": "numerical_root_residual_only_never_expand_or_shrink_safety_thresholds"},
        ("time_epsilon_s", "distance_epsilon_m"), path="rules.comparison")
    for key in ("time_epsilon_s", "distance_epsilon_m"):
        _number(rules["comparison"][key], "rules.comparison." + key, minimum=0)
    _semantics(rules["assumptions"], {
        "motion": "p(t) = p0 + v*t for all aircraft and threat over [0,1200]",
        "coordinate_system": "local_cartesian_east_north_geometric_altitude", "target_motion": "static_xyz",
        "threat_after_target_xy": "continue_same_velocity_and_altitude", "vehicle_geometry": "point_with_protected_volume",
        "aircraft_destination": "original_baseline_position_at_duration_s"}, ("excluded", "unknown"), path="rules.assumptions")
    sensitivity = rules["sensitivity"]
    _semantics(sensitivity, {"method": "one_parameter_at_a_time", "run_product": ["profiles", "modes", "variants"]},
               ("vertical_m", "threat_radius_m", "target_radius_m", "variants", "expected_run_count"), path="rules.sensitivity")
    for key in ("vertical_m", "threat_radius_m", "target_radius_m"):
        if not isinstance(sensitivity[key], list) or not sensitivity[key]:
            raise ValueError("rules.sensitivity.%s must be a nonempty list" % key)
        for value in sensitivity[key]:
            _number(value, "rules.sensitivity." + key, positive=True)
    variant_keys = {"base": None, "threat_3000": "threat_radius_m", "threat_10000": "threat_radius_m",
                    "target_3000": "target_radius_m", "target_10000": "target_radius_m"}
    variants = sensitivity["variants"]
    if not isinstance(variants, list) or len(variants) != 5 or {v.get("id") for v in variants if isinstance(v, dict)} != set(variant_keys):
        raise ValueError("Unsupported sensitivity variants")
    for variant in variants:
        _keys(variant, ("id", "overrides"), ("label",), "variant")
        key = variant_keys[variant["id"]]
        _keys(variant["overrides"], () if key is None else (key,), path="variant.overrides")
        if key:
            _number(variant["overrides"][key], "variant.overrides." + key, positive=True)
    actual_values = {
        "vertical_m": {_q(profile["vertical_m"]) for profile in rules["profiles"]},
        "threat_radius_m": {_q(rules["zones"]["threat"]["radius_m"])},
        "target_radius_m": {_q(rules["zones"]["target"]["radius_m"])},
    }
    for variant in variants:
        for key, value in variant["overrides"].items():
            actual_values[key].add(_q(value))
    for key, actual in actual_values.items():
        advertised = [_q(value) for value in sensitivity[key]]
        if len(advertised) != len(set(advertised)) or set(advertised) != actual:
            raise ValueError("rules.sensitivity.%s must list each actually analyzed value exactly once" % key)
    _same(sensitivity["expected_run_count"], 20, "rules.sensitivity.expected_run_count")
    for key, ids in (("profile_id", {p["id"] for p in rules["profiles"]}),
                     ("mode_id", {m["id"] for m in rules["modes"]}), ("variant_id", set(variant_keys))):
        if rules["defaults"][key] not in ids:
            raise ValueError("Unknown default " + key)


def _read_json(path):
    def bad_constant(value):
        raise ValueError("Nonfinite JSON number: " + value)
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, parse_constant=bad_constant, object_pairs_hook=unique_object)


def load_inputs(scenario_path):
    """Load scenario and its CSV, resolving flights_file beside scenario JSON."""
    scenario_path = Path(scenario_path)
    scenario = _read_json(scenario_path)
    if not isinstance(scenario, dict) or not isinstance(scenario.get("flights_file"), str) or not scenario["flights_file"]:
        raise ValueError("scenario.flights_file must be a nonempty path")
    flights = []
    with (scenario_path.parent / scenario["flights_file"]).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["flight_id"] + list(STATE_KEYS):
            raise ValueError("CSV columns must be flight_id," + ",".join(STATE_KEYS))
        for line_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed CSV row %d" % line_number)
            try:
                flights.append(dict(flight_id=row["flight_id"], **{key: float(row[key]) for key in STATE_KEYS}))
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid numeric CSV row %d" % line_number) from exc
    _validate_scenario(scenario, flights)
    return scenario, flights


def load_rules(rules_path):
    rules = _read_json(rules_path)
    _validate_rules(rules)
    return rules


def _q(value):
    return value if isinstance(value, Fraction) else Fraction(str(value))


def _decimal(value):
    return Decimal(value.numerator) / Decimal(value.denominator)


@dataclass(frozen=True)
class Interval:
    start_s: float
    end_s: float
    start_inclusive: bool
    end_inclusive: bool

    def contains(self, time_s):
        return (time_s > self.start_s or time_s == self.start_s and self.start_inclusive) and (
            time_s < self.end_s or time_s == self.end_s and self.end_inclusive)


def strict_quadratic_intervals(a, b, c, duration_s):
    """Maximal intervals where a*t*t+b*t+c < 0 on the closed horizon.

    Exact coefficient/discriminant signs distinguish tangency from a narrow
    crossing. Roots are open; clipping to the horizon preserves true endpoint
    membership. In particular -k*(t-r)^2<0 produces two separate intervals.
    """
    a, b, c, horizon = map(_q, (a, b, c, duration_s))
    with localcontext() as context:
        context.prec = 80
        zero, end = Decimal(0), _decimal(horizon)
        neg_inf, pos_inf = Decimal("-Infinity"), Decimal("Infinity")
        if not a:
            if not b:
                raw = [(neg_inf, pos_inf)] if c < 0 else []
            else:
                root = _decimal(-c / b)
                raw = [(neg_inf, root)] if b > 0 else [(root, pos_inf)]
        else:
            discriminant = b * b - 4 * a * c
            if discriminant < 0:
                raw = [(neg_inf, pos_inf)] if a < 0 else []
            elif discriminant == 0:
                root = _decimal(-b / (2 * a))
                raw = [(neg_inf, root), (root, pos_inf)] if a < 0 else []
            else:
                da, db, dc = map(_decimal, (a, b, c))
                sqrt_d = _decimal(discriminant).sqrt()
                qroot = -(db + (sqrt_d if b >= 0 else -sqrt_d)) / 2
                roots = sorted((qroot / da, dc / qroot))
                raw = [(roots[0], roots[1])] if a > 0 else [(neg_inf, roots[0]), (roots[1], pos_inf)]
        result = []
        for left, right in raw:
            lo, hi = max(zero, left), min(end, right)
            left_closed = left < zero
            right_closed = right > end
            if lo < hi:
                result.append(Interval(float(lo), float(hi), left_closed, right_closed))
        return result


def intersect_intervals(first, second):
    result = []
    for a in first:
        for b in second:
            lo, hi = max(a.start_s, b.start_s), min(a.end_s, b.end_s)
            if lo < hi:
                result.append(Interval(lo, hi, a.contains(lo) and b.contains(lo), a.contains(hi) and b.contains(hi)))
    return sorted(result, key=lambda interval: (interval.start_s, interval.end_s))


def _norm_intervals(position, velocity, threshold, duration_s):
    position, velocity = list(map(_q, position)), list(map(_q, velocity))
    intercept, slope = map(_q, threshold)
    a = sum(v * v for v in velocity) - slope * slope
    b = 2 * (sum(p * v for p, v in zip(position, velocity)) - intercept * slope)
    c = sum(p * p for p in position) - intercept * intercept
    return strict_quadratic_intervals(a, b, c, duration_s)


def _relative(a, b):
    return ([_q(a[k]) - _q(b[k]) for k in STATE_KEYS[:3]],
            [_q(a[k]) - _q(b[k]) for k in STATE_KEYS[3:]])


def separation_intervals(a, b, horizontal_m, vertical_m, duration_s, error_bounds=None):
    """Pair geometry helper, also used by the independent analytic fixtures."""
    errors = error_bounds or dict.fromkeys(ERROR_KEYS, 0)
    h = (_q(horizontal_m) + 2 * _q(errors[ERROR_KEYS[0]]), 2 * _q(errors[ERROR_KEYS[2]]))
    z = (_q(vertical_m) + 2 * _q(errors[ERROR_KEYS[1]]), 2 * _q(errors[ERROR_KEYS[3]]))
    r, w = _relative(a, b)
    horizontal = _norm_intervals(r[:2], w[:2], h, duration_s)
    upper = strict_quadratic_intervals(0, w[2] - z[1], r[2] - z[0], duration_s)
    lower = strict_quadratic_intervals(0, -w[2] - z[1], -r[2] - z[0], duration_s)
    return intersect_intervals(intersect_intervals(horizontal, upper), lower)


def _affine(intercept, slope=0):
    return {"intercept_m": float(intercept), "slope_mps": float(slope)}


def _representative(interval):
    time_s = interval.start_s + (interval.end_s - interval.start_s) / 2
    if not interval.contains(time_s):
        time_s = math.nextafter(interval.start_s, interval.end_s)
    if not interval.contains(time_s):
        raise ValueError("Violation interval is too narrow for a representable interior time")
    return time_s


def _distance_min(position, velocity, interval, representative):
    # Exact rational minimizer first; evaluate final nominal metric at full precision.
    position, velocity = list(map(_q, position)), list(map(_q, velocity))
    speed_squared = sum(v * v for v in velocity)
    time_s = representative if not speed_squared else max(interval.start_s, min(interval.end_s,
        float(-sum(p * v for p, v in zip(position, velocity)) / speed_squared)))
    value = math.sqrt(float(sum((p + v * _q(time_s)) ** 2 for p, v in zip(position, velocity))))
    return {"value_m": value, "time_s": time_s, "attained": interval.contains(time_s)}


def _distance_metrics(position, velocity, interval):
    representative = _representative(interval)
    metrics = {"horizontal_min": _distance_min(position[:2], velocity[:2], interval, representative)}
    metrics["vertical_min"] = _distance_min(position[2:], velocity[2:], interval, representative)
    metrics["distance_3d_min"] = _distance_min(position, velocity, interval, representative)
    return metrics


def _event(run, mode, event_type, rule_id, participants, flight_ids, interval, thresholds, metrics):
    return {
        "type": event_type, "rule_id": rule_id, "participants": list(participants), "flight_ids": list(flight_ids),
        "run_id": run["id"], "profile_id": run["profile_id"], "mode_id": run["mode_id"], "variant_id": run["variant_id"],
        "start_s": interval.start_s, "end_s": interval.end_s,
        "start_inclusive": interval.start_inclusive, "end_inclusive": interval.end_inclusive,
        "initial_violation": interval.start_s == 0 and interval.start_inclusive,
        "continues_at_horizon": interval.end_s == run["duration_s"] and interval.end_inclusive,
        "severity": mode["severity"], "representative_s": _representative(interval),
        "duration_s": interval.end_s - interval.start_s, "thresholds": thresholds, "metrics": metrics}


def _motion_checks(flight, errors, limits):
    speed = math.hypot(flight["vx_mps"], flight["vy_mps"])
    speed_low = max(0, speed - errors["velocity_horizontal_mps"])
    speed_high = speed + errors["velocity_horizontal_mps"]
    vertical_low = flight["vz_mps"] - errors["velocity_vertical_mps"]
    vertical_high = flight["vz_mps"] + errors["velocity_vertical_mps"]
    # All admissible velocities are constant. The most restrictive coordinated
    # turn bound occurs at the largest admissible horizontal speed.
    omega_limit = limits["gravity_mps2"] * math.tan(math.radians(limits["bank_abs_max_deg"])) / speed_high if speed_high else None
    definitions = (
        ("horizontal_speed", "m/s", speed_low, speed_high, limits["horizontal_speed_min_mps"], limits["horizontal_speed_max_mps"]),
        ("horizontal_acceleration", "m/s^2", 0, 0, -limits["horizontal_acceleration_abs_max_mps2"], limits["horizontal_acceleration_abs_max_mps2"]),
        ("vertical_speed", "m/s", vertical_low, vertical_high, -limits["vertical_speed_abs_max_mps"], limits["vertical_speed_abs_max_mps"]),
        ("vertical_acceleration", "m/s^2", 0, 0, -limits["vertical_acceleration_abs_max_mps2"], limits["vertical_acceleration_abs_max_mps2"]),
        ("bank", "deg", 0, 0, -limits["bank_abs_max_deg"], limits["bank_abs_max_deg"]),
        ("turn_rate", "rad/s", 0, 0, -omega_limit if omega_limit is not None else None, omega_limit),
    )
    checks = []
    for rule_id, units, low, high, allowed_low, allowed_high in definitions:
        check = {"flight_id": flight["flight_id"], "rule_id": rule_id, "units": units,
                 "observed_min": low, "observed_max": high, "allowed_min": allowed_low, "allowed_max": allowed_high,
                 "passes": (allowed_low is None or low >= allowed_low) and (allowed_high is None or high <= allowed_high)}
        if rule_id == "turn_rate":
            check["bound_speed_mps"] = speed_high
            check["bound_formula"] = "g*tan(bank_abs_max_deg*pi/180)/max_admissible_horizontal_speed"
            if not speed_high:
                check["note"] = "Zero-speed constant trajectory: zero turn; rate bound has no finite upper bound."
        checks.append(check)
    return checks


def _analyze_run(scenario, flights, rules, profile, mode, variant):
    duration = rules["duration_s"]
    bounds = scenario["airspace"]
    errors = mode["error_bounds"]
    ph, pz, vh, vz = (_q(errors[key]) for key in ERROR_KEYS)
    thresholds = {"horizontal_m": profile["horizontal_m"], "vertical_m": profile["vertical_m"],
                  "threat_radius_m": rules["zones"]["threat"]["radius_m"], "target_radius_m": rules["zones"]["target"]["radius_m"],
                  "target_alt_m": rules["zones"]["target"]["center_alt_m"],
                  "alt_min_m": bounds["alt_min_m"], "alt_max_m": bounds["alt_max_m"]}
    thresholds.update(variant["overrides"])
    run = {"id": "__".join((profile["id"], mode["id"], variant["id"])), "profile_id": profile["id"],
           "mode_id": mode["id"], "variant_id": variant["id"], "duration_s": duration, "thresholds": thresholds, "events": []}
    events = run["events"]
    pair_thresholds = {"horizontal": _affine(_q(profile["horizontal_m"]) + 2 * ph, 2 * vh),
                       "vertical": _affine(_q(profile["vertical_m"]) + 2 * pz, 2 * vz)}
    for a, b in combinations(flights, 2):
        intervals = separation_intervals(a, b, profile["horizontal_m"], profile["vertical_m"], duration, errors)
        position, velocity = _relative(a, b)
        ids = [a["flight_id"], b["flight_id"]]
        for interval in intervals:
            events.append(_event(run, mode, "aircraft_aircraft", "aircraft_separation", ids, ids, interval,
                                 pair_thresholds, _distance_metrics(position, velocity, interval)))
    all_checks = []
    for flight in flights:
        flight_id = flight["flight_id"]
        for zone, obj, event_type, rule_id, radius in (
                ("threat", scenario["hostile_object"], "aircraft_threat", "threat_sphere",
                 (_q(thresholds["threat_radius_m"]) + 2 * (ph + pz), 2 * (vh + vz))),
                ("target", {**scenario["target"], "alt_m": thresholds["target_alt_m"], "vx_mps": 0, "vy_mps": 0, "vz_mps": 0},
                 "aircraft_target", "target_sphere", (_q(thresholds["target_radius_m"]) + ph + pz, vh + vz))):
            position, velocity = _relative(flight, obj)
            for interval in _norm_intervals(position, velocity, radius, duration):
                events.append(_event(run, mode, event_type, rule_id, [flight_id, zone.upper()], [flight_id], interval,
                    {"radius": _affine(*radius)}, _distance_metrics(position, velocity, interval)))
        z0, vertical = _q(flight["alt_m"]), _q(flight["vz_mps"])
        altitude_thresholds = {"alt_min_m": bounds["alt_min_m"], "alt_max_m": bounds["alt_max_m"], "error_vertical": _affine(pz, vz)}
        for rule_id, coefficient, constant in (
                ("altitude_min", vertical - vz, z0 - pz - _q(bounds["alt_min_m"])),
                ("altitude_max", -vertical - vz, _q(bounds["alt_max_m"]) - z0 - pz)):
            for interval in strict_quadratic_intervals(0, coefficient, constant, duration):
                representative = _representative(interval)
                metrics = {}
                for name, minimum in (("altitude_min", True), ("altitude_max", False)):
                    if vertical == 0:
                        time_s = representative
                    else:
                        time_s = interval.start_s if (vertical > 0) == minimum else interval.end_s
                    metrics[name] = {"value_m": float(z0 + vertical * _q(time_s)), "time_s": time_s, "attained": interval.contains(time_s)}
                events.append(_event(run, mode, "altitude", rule_id, [flight_id], [flight_id], interval, altitude_thresholds, metrics))
        checks = _motion_checks(flight, errors, rules["motion_limits"]["aircraft"])
        all_checks.extend(checks)
        for check in checks:
            if not check["passes"]:
                events.append(_event(run, mode, "motion", check["rule_id"], [flight_id], [flight_id],
                    Interval(0.0, float(duration), True, True), {key: value for key, value in check.items() if key not in ("flight_id", "passes")}, {}))
    events.sort(key=lambda event: (event["start_s"], event["end_s"], event["type"], event["participants"], event["rule_id"]))
    counters = Counter()
    for event in events:
        identity = (event["type"], tuple(event["participants"]))
        event["id"] = "__".join([run["id"], event["type"]] + event["participants"] + [str(counters[identity])])
        counters[identity] += 1
    affected = sorted({flight_id for event in events for flight_id in event["flight_ids"]})
    pairs = {tuple(sorted(event["flight_ids"])) for event in events if event["type"] == "aircraft_aircraft"}
    initial = [event["id"] for event in events if event["initial_violation"]]
    run["summary"] = {"event_count": len(events), "aircraft_pair_count": len(pairs), "affected_flight_count": len(affected),
                      "affected_flight_ids": affected, "initial_event_count": len(initial),
                      "counts_by_type": {event_type: sum(event["type"] == event_type for event in events) for event_type in EVENT_TYPES},
                      "first_event_s": min((event["start_s"] for event in events), default=None),
                      "total_event_duration_s": math.fsum(event["duration_s"] for event in events)}
    run["initial_state"] = {"has_violations": bool(initial), "event_ids": initial}
    run["motion_checks"] = {"all_pass": all(check["passes"] for check in all_checks), "scope": "constant_velocity_baseline", "checks": all_checks}
    return run


def analyze_all(scenario, flights, rules):
    """Analyze every configured profile × mode × radius variant, deterministically."""
    _validate_scenario(scenario, flights)
    _validate_rules(rules)
    flights = sorted(flights, key=lambda flight: flight["flight_id"])
    canonical = json.dumps({"scenario": scenario, "flights": flights, "rules": rules}, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
    runs = [_analyze_run(scenario, flights, rules, profile, mode, variant)
            for profile in rules["profiles"] for mode in rules["modes"] for variant in rules["sensitivity"]["variants"]]
    analysis = {"schema_version": "1.1", "duration_s": rules["duration_s"], "runs": runs,
                "provenance": {"analyzer": "airspace.analysis", "input_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                               "flight_count": len(flights), "method": "continuous_affine_motion_quadratic_intervals",
                               "arithmetic": "exact rational coefficient/discriminant signs; stable 80-digit decimal roots; unrounded binary64 output"},
                "limitations": [
                    "Only the given constant-velocity baseline is analyzed; maneuvers and conflict resolution are not implemented.",
                    "Stress events are deterministic possible violations, not probabilities or realized violations.",
                    "Both spheres use conservative sums of horizontal and vertical error bounds; the target is exact, so only aircraft errors expand its sphere.",
                    "Each time has an admissible error possibility; one fixed error realization need not violate throughout an entire event.",
                    "Metrics are nominal center distances minimized separately on the event closure; their minima may occur at different times.",
                    "Total event duration sums overlapping events and is not unsafe flight duration.",
                    "XY bounds do not discard trajectories. The threat continues unchanged after passing target XY.",
                    "The selected generic-jet and geometric rules do not establish operational or regulatory compliance."]}
    _finite_tree(analysis, "analysis")
    return analysis


def _json_cell(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _summary_row(run):
    summary = run["summary"]
    return {"run_id": run["id"], "profile_id": run["profile_id"], "mode_id": run["mode_id"], "variant_id": run["variant_id"],
            **run["thresholds"], **{key: value for key, value in summary.items() if key != "counts_by_type"},
            **{event_type + "_count": summary["counts_by_type"][event_type] for event_type in EVENT_TYPES},
            "motion_all_pass": run["motion_checks"]["all_pass"]}


def _csv_write(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_cell(value) if isinstance(value, (list, dict, bool)) else value for key, value in row.items()})


def write_reports(analysis, output_dir):
    """Write full JSON, typed event CSV and comparable per-run summaries."""
    _finite_tree(analysis, "analysis")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    event_fields = ["run_id", "profile_id", "mode_id", "variant_id", "id", "type", "rule_id", "participants", "flight_ids",
                    "start_s", "end_s", "start_inclusive", "end_inclusive", "initial_violation", "continues_at_horizon",
                    "severity", "representative_s", "duration_s", "thresholds", "metrics"]
    _csv_write(output_dir / "events.csv", event_fields, [{key: event[key] for key in event_fields} for run in analysis["runs"] for event in run["events"]])
    summary_rows = [_summary_row(run) for run in analysis["runs"]]
    summary_fields = list(summary_rows[0])
    _csv_write(output_dir / "summary.csv", summary_fields, summary_rows)
    by_id = {run["id"]: run for run in analysis["runs"]}
    sensitivity_rows = []
    for run, row in zip(analysis["runs"], summary_rows):
        base = by_id["__".join((run["profile_id"], run["mode_id"], "base"))]
        nominal = by_id["__".join((run["profile_id"], "nominal", run["variant_id"]))]
        metric = by_id["__".join(("metric", run["mode_id"], run["variant_id"]))]
        changed = [key for key in ("threat_radius_m", "target_radius_m") if run["thresholds"][key] != base["thresholds"][key]]
        row = {**row, "changed_parameter": changed[0] if changed else "none", "base_run_id": base["id"],
               "delta_events_vs_base": run["summary"]["event_count"] - base["summary"]["event_count"],
               "nominal_run_id": nominal["id"], "delta_events_vs_nominal": run["summary"]["event_count"] - nominal["summary"]["event_count"],
               "metric_run_id": metric["id"], "delta_pairs_vs_metric": run["summary"]["aircraft_pair_count"] - metric["summary"]["aircraft_pair_count"],
               "delta_events_vs_metric": run["summary"]["event_count"] - metric["summary"]["event_count"]}
        sensitivity_rows.append(row)
    _csv_write(output_dir / "sensitivity.csv", list(sensitivity_rows[0]), sensitivity_rows)
    lines = ["# Baseline motion analysis", "", "Continuous horizon [0, %s] s; %s aircraft; %s runs. Maneuvers are not implemented." %
             (analysis["duration_s"], analysis.get("provenance", {}).get("flight_count", "?"), len(analysis["runs"])), "",
             "Distance violations use strict inequalities: equality at the threshold is safe. In bounded_stress, events indicate a possible loss of guarantee within the selected error bounds, not a probability or an actual violation.", "",
             "| Run | Events | Unique pairs | Aircraft | Initial | Pairs / drone / target / altitude / motion |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    for run in analysis["runs"]:
        s = run["summary"]
        lines.append("| %s | %s | %s | %s | %s | %s |" % (run["id"], s["event_count"], s["aircraft_pair_count"],
            s["affected_flight_count"], s["initial_event_count"], " / ".join(str(s["counts_by_type"][kind]) for kind in EVENT_TYPES)))
    lines.extend(["", "## Initial violations with base radii", ""])
    for run in analysis["runs"]:
        if run["variant_id"] == "base":
            initial = ["%s (%s)" % ("/".join(event["participants"]), event["rule_id"]) for event in run["events"] if event["initial_violation"]]
            lines.append("- `%s`: %s." % (run["id"], "; ".join(initial) if initial else "none"))
    lines.extend(["", "## Interpretation and format", "",
        "Changing V from 300 to 304.8 m includes altitude differences of exactly 300 m. Threat and target radii vary one at a time; sensitivity.csv contains the full sensitivity analysis with differences relative to base/nominal/metric.", "",
        "Motion checks cover every aircraft: horizontal speed, its tangential derivative, vertical speed/acceleration, zero bank for the straight baseline, and zero turn rate with the coordinated-turn bound g·tan(bank)/v. Stress checks cover the full admissible range of constant velocities. These checks do not validate future maneuvers.", "",
        "analysis.json contains all events, effective affine thresholds, and complete motion_checks. events.csv stores thresholds and metrics as JSON fields; flags are true/false, and an empty scalar field means null. summary.csv and sensitivity.csv contain one row per run. IDs are preserved across all CSV files.", "",
        "Times and distances in machine-readable reports are not rounded. Metric minima refer to nominal centers over the closure of the event interval; attained distinguishes an attained minimum from an infimum. Different components may reach their minima at different times. The sum of event durations includes overlaps and is not the duration of unsafe flight.", "",
        "XY bounds do not exclude objects. The target and threat have spherical zones active throughout the horizon. Target XY coordinates come from scenario; the center altitude comes from rules.zones.target.center_alt_m (target_alt_m in each run). The drone continues unchanged after passing target XY. Altitude bounds come from scenario. All stress events have severity=possible_violation; both spheres use a conservative affine bound on 3D error. Only the aircraft e_h+e_z is included for the exact target; both objects contribute errors for the drone. Errors are measured from t=0 and do not reset.", "",
        "The rules are research assumptions. Regulatory compliance, aircraft-specific flight envelopes, delays, actual accuracy, and the safety of a future plan have not been established.", ""])
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
