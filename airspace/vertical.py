"""Nominal vertical maneuvers, separate from the affine baseline detector.

All propagation and limit comparisons use exact rationals of decimal inputs.
Public state/segment outputs use finite SI floats. See docs/vertical-model.md.
"""

from bisect import bisect_right
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
import math

from .analysis import STATE_KEYS, _keys, _validate_rules, _validate_scenario


SCHEMA_VERSION = "1.0"
MODEL = "piecewise_constant_vertical_acceleration"
UNITS = "SI: m, s, m/s, m/s^2"


def _rational(value, name):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number (not bool)")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be finite and representable")
    return Fraction(str(value))


def _float(value):
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("Computed state is not representable as a finite float") from exc
    if not math.isfinite(result):
        raise ValueError("Computed state is not representable as a finite float")
    return result


def _fingerprint(flight, scenario, rules):
    text = json.dumps(dict(flight=flight, scenario=scenario, rules=rules),
                      sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LimitViolation(ValueError):
    """A continuously checked kinematic/altitude limit failed at time_s."""

    def __init__(self, constraint, time_s, value, lower, upper):
        self.constraint = constraint
        self.time_s = _float(time_s)
        self.value = _float(value)
        self.lower = _float(lower)
        self.upper = _float(upper)
        super().__init__(f"{constraint} at t={self.time_s:g} s: {self.value:g} "
                         f"outside [{self.lower:g}, {self.upper:g}]")


def _within(constraint, time, value, lower, upper):
    if not lower <= value <= upper:
        raise LimitViolation(constraint, time, value, lower, upper)


@dataclass(frozen=True)
class VerticalSegment:
    """A positive duration and constant vertical acceleration, in SI units."""

    duration_s: float
    az_mps2: float

    def __post_init__(self):
        if _rational(self.duration_s, "duration_s") <= 0:
            raise ValueError("duration_s must be positive")
        _rational(self.az_mps2, "az_mps2")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, definition):
        _keys(definition, ("duration_s", "az_mps2"), path="segment")
        return cls(**definition)


@dataclass(frozen=True)
class TrajectoryState:
    x_m: float
    y_m: float
    alt_m: float
    vx_mps: float
    vy_mps: float
    vz_mps: float

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class _Piece:
    start: Fraction
    end: Fraction
    z: Fraction
    vz: Fraction
    az: Fraction

    def vertical_at(self, time):
        dt = time - self.start
        return self.z + self.vz * dt + self.az * dt * dt / 2, self.vz + self.az * dt


class VerticalTrajectory:
    """Build and validate a full-horizon nominal trajectory from a source flight.

    Segments cover rules.duration_s exactly. Starting states are derived, never
    supplied independently. Acceleration may jump; position/velocity cannot.
    Invalid definitions or unsupported semantics raise ValueError; exceeded
    limits raise LimitViolation. Construction does not check conflict safety.
    """

    def __init__(self, flight, segments, scenario, rules, *, mode_id="nominal"):
        if mode_id != "nominal":
            raise ValueError("Vertical trajectories support only nominal mode")
        # Reuse baseline input/configuration validation without changing its API.
        _validate_rules(rules)
        _validate_scenario(scenario, [flight])
        if rules["units"] != "SI: m, s, m/s, m/s^2; angles explicitly labelled":
            raise ValueError("Unsupported rules units")
        if scenario.get("units") != "SI: meters, seconds, m/s. Origin at airspace center, x east, y north.":
            raise ValueError("Unsupported or missing scenario units")
        if not isinstance(segments, (list, tuple)) or not segments:
            raise ValueError("segments must be a nonempty list or tuple of VerticalSegment")
        if any(type(segment) is not VerticalSegment for segment in segments):
            raise ValueError("Every segment must be a VerticalSegment")
        initial = tuple(_rational(flight[key], key) for key in STATE_KEYS)
        horizon = _rational(rules["duration_s"], "duration_s")
        limits = {key: _rational(value, key) for key, value in rules["motion_limits"]["aircraft"].items()
                  if type(value) in (int, float)}
        bounds = scenario["airspace"]
        zmin, zmax = (_rational(bounds[key], key) for key in ("alt_min_m", "alt_max_m"))
        # Squared comparison avoids rounding hypot at a strict speed boundary.
        speed2 = initial[3] ** 2 + initial[4] ** 2
        low, high = limits["horizontal_speed_min_mps"], limits["horizontal_speed_max_mps"]
        if not low ** 2 <= speed2 <= high ** 2:
            raise LimitViolation("horizontal_speed_mps", Fraction(0), math.hypot(float(initial[3]), float(initial[4])), low, high)
        # Horizontal acceleration, turn rate and bank are identically zero.
        # Their configured bounds are nonnegative (checked by _validate_rules).
        pieces, time, z, vz = [], Fraction(0), initial[2], initial[5]
        for index, segment in enumerate(segments):
            duration = _rational(segment.duration_s, f"segments[{index}].duration_s")
            az = _rational(segment.az_mps2, f"segments[{index}].az_mps2")
            end = time + duration
            if end > horizon:
                raise ValueError("Segments extend beyond rules.duration_s")
            _within("vertical_acceleration_mps2", time, az,
                    -limits["vertical_acceleration_abs_max_mps2"], limits["vertical_acceleration_abs_max_mps2"])
            piece = _Piece(time, end, z, vz, az)
            # vz is affine: extrema occur at endpoints. z is quadratic:
            # endpoints plus a possible interior root of vz exhaust its extrema.
            candidates = [time, end]
            if az:
                extremum = time - vz / az
                if time < extremum < end:
                    candidates.append(extremum)
            for candidate in candidates:
                altitude, vertical_speed = piece.vertical_at(candidate)
                _within("altitude_m", candidate, altitude, zmin, zmax)
                _within("vertical_speed_mps", candidate, vertical_speed,
                        -limits["vertical_speed_abs_max_mps"], limits["vertical_speed_abs_max_mps"])
                for value in (altitude, vertical_speed, initial[0] + initial[3] * candidate,
                              initial[1] + initial[4] * candidate):
                    _float(value)
            pieces.append(piece)
            z, vz = piece.vertical_at(end)
            time = end
        if time != horizon:
            raise ValueError("Segments must cover exactly [0, rules.duration_s]")
        self._flight_id = flight["flight_id"]
        self._initial = initial
        self._segments = tuple(segments)
        self._pieces = tuple(pieces)
        self._starts = tuple(piece.start for piece in pieces)
        self._horizon = horizon
        # Snapshot inputs as canonical JSON; caller mutations cannot change it.
        self._initial_json = json.dumps({key: flight[key] for key in STATE_KEYS}, sort_keys=True, allow_nan=False)
        self._source_sha256 = _fingerprint(flight, scenario, rules)

    @property
    def flight_id(self):
        return self._flight_id

    @property
    def duration_s(self):
        return _float(self._horizon)

    @property
    def segments(self):
        return self._segments

    def state_at(self, time_s):
        """Evaluate on the closed horizon; no extrapolation or time clamping."""
        time = _rational(time_s, "time_s")
        if not 0 <= time <= self._horizon:
            raise ValueError("time_s must be inside [0, duration_s]")
        piece = self._pieces[bisect_right(self._starts, time) - 1]
        z, vz = piece.vertical_at(time)
        x0, y0, unused_z0, vx, vy, unused_vz0 = self._initial
        return TrajectoryState(*map(_float, (x0 + vx * time, y0 + vy * time, z, vx, vy, vz)))

    def position_at(self, time_s):
        state = self.state_at(time_s)
        return state.x_m, state.y_m, state.alt_m

    def velocity_at(self, time_s):
        state = self.state_at(time_s)
        return state.vx_mps, state.vy_mps, state.vz_mps

    def segment_definitions(self):
        """Derived SI coefficients for inspection/future segment-aware checks.

        At a join the following segment applies; the last includes duration_s.
        The authoritative serialization retains durations, avoiding independent
        rounded join states. These float coefficients are diagnostic outputs.
        """
        return [dict(start_s=_float(p.start), end_s=_float(p.end), alt_start_m=_float(p.z),
                     vz_start_mps=_float(p.vz), az_mps2=_float(p.az)) for p in self._pieces]

    def to_dict(self):
        return dict(schema_version=SCHEMA_VERSION, model=MODEL, units=UNITS, mode_id="nominal",
                    flight_id=self.flight_id, duration_s=self.duration_s,
                    initial_state=json.loads(self._initial_json),
                    segments=[s.to_dict() for s in self.segments],
                    source_sha256=self._source_sha256)

    @classmethod
    def from_dict(cls, definition, *, flight, scenario, rules):
        """Reload against original inputs/configuration and revalidate limits."""
        _keys(definition, ("schema_version", "model", "units", "mode_id", "flight_id", "duration_s",
                           "initial_state", "segments", "source_sha256"), path="trajectory")
        for key, expected in (("schema_version", SCHEMA_VERSION), ("model", MODEL), ("units", UNITS), ("mode_id", "nominal")):
            if type(definition[key]) is not str or definition[key] != expected:
                raise ValueError(f"Unsupported trajectory {key}")
        if not isinstance(definition["segments"], list):
            raise ValueError("Serialized segments must be a list")
        segments = [VerticalSegment.from_dict(s) for s in definition["segments"]]
        result = cls(flight, segments, scenario, rules, mode_id=definition["mode_id"])
        if definition["flight_id"] != result.flight_id:
            raise ValueError("Serialized flight_id does not match source flight")
        if _rational(definition["duration_s"], "duration_s") != result._horizon:
            raise ValueError("Serialized duration differs from configured horizon")
        _keys(definition["initial_state"], STATE_KEYS, path="initial_state")
        if tuple(_rational(definition["initial_state"][key], key) for key in STATE_KEYS) != result._initial:
            raise ValueError("Serialized initial state differs from source flight")
        if definition["source_sha256"] != result._source_sha256:
            raise ValueError("Serialized provenance differs from original flight/scenario/rules")
        return result
