# Vertical trajectory contract, version 1.0

This separate nominal kinematic model adds climb/descent, constant vertical rate,
level flight and return using piecewise constant vertical acceleration. It does
not modify the source data, baseline rules, baseline analyzer, reports or HTML.
The baseline `maneuvers_implemented=false` flag continues to describe the affine
baseline pipeline. The vertical model reads its numerical limits from the same
configuration; it has its own schema and is not an analysis report or UI payload.

A separate [nominal planner and independent continuous checker](nominal-planning.md)
now use this API; conflict detection remains outside `airspace.vertical` itself.

## Mathematics and validation

Use SI units and the source east/north/geometric-altitude coordinate system.
Each trajectory begins at the original aircraft position and velocity at t=0.
Horizontal motion remains `x=x0+vx0*t`, `y=y0+vy0*t` throughout the closed
configured horizon. For a segment starting at `t_i`, with `dt=t-t_i`:

```text
z(t)  = z_i + vz_i*dt + az_i*dt²/2
vz(t) = vz_i + az_i*dt
vx(t) = vx0; vy(t) = vy0
```

Each segment has positive duration. Durations must sum exactly to
`rules.duration_s`; gaps, overlaps and implicit continuation are not supported.
Starting altitude and vertical velocity of each segment are derived from the
preceding endpoint, ensuring position and velocity continuity. At a join the
following segment applies; the final segment includes the horizon endpoint.
Acceleration may jump at joins, including entry and exit from level flight.
There is no configured jerk constraint, aerodynamic model or thrust model.

Construction checks the entire trajectory, including t=0, all joins and the
horizon endpoint. `motion_limits.aircraft` supplies horizontal speed, vertical
speed and vertical acceleration limits; `scenario.airspace` supplies altitude
bounds according to the existing altitude rule. All limit boundaries are
inclusive. Horizontal acceleration, bank and turn rate are identically zero
and satisfy their configured nonnegative limits. The speed limit concerns
horizontal speed magnitude, rather than total 3D speed. Leaving the XY frame
does not remove or invalidate an aircraft.

For each segment, vertical speed is affine, so endpoints exhaust its extrema.
Altitude is quadratic, so endpoints and an interior `vz=0` point exhaust its
extrema. The implementation uses exact rational arithmetic on the canonical
decimal representations of input numbers, including the speed-squared check.
It never samples to establish admissibility and adds no numerical safety
margin. This proves these kinematic/altitude inequalities for the defined
decimal model; public float outputs are rounded for interoperability. Inputs
and computed outputs must be finite and representable. If construction cannot
complete validation, it raises an error and returns no admissible trajectory.

Zero acceleration with nonzero vz means constant-rate climb/descent; level
flight requires both az=0 and vz=0. The API accepts nonzero initial vz. It
does not impose a final altitude or velocity automatically: a return schedule
must be supplied by the caller and checked against the intended destination.

Only `nominal` mode, configuration schema 1.1, the existing SI declarations,
zero wind and zero delays are supported. Baseline configuration validation is
reused. `bounded_stress` is rejected: applying its errors to acceleration
commands requires separate justification. Conflict detection, safety against
other aircraft/the drone/the target, planning and optimization are not part of
this API. Do not feed this model into the affine baseline detector or describe
kinematic validity as conflict safety.

## Python API

Standard library, Python 3.9+; calculations live in `airspace/vertical.py`:

```python
from airspace.analysis import load_inputs, load_rules
from airspace.vertical import VerticalSegment, VerticalTrajectory
from tools.example_vertical import build_example

scenario, flights = load_inputs("scenario.json")
rules = load_rules("rules.json")
trajectory = build_example(scenario, flights, rules)
state = trajectory.state_at(120)       # TrajectoryState, all six SI components
position = trajectory.position_at(120) # (x_m, y_m, alt_m)
velocity = trajectory.velocity_at(120) # (vx_mps, vy_mps, vz_mps)
coefficients = trajectory.segment_definitions()
definition = trajectory.to_dict()
flight = next(f for f in flights if f["flight_id"] == trajectory.flight_id)
restored = VerticalTrajectory.from_dict(
    definition, flight=flight, scenario=scenario, rules=rules)

# General constructor: validated full-horizon level flight.
level = VerticalTrajectory(flight, [VerticalSegment(rules["duration_s"], 0)],
                           scenario, rules, mode_id="nominal")
```

`flight_id`, `duration_s` and immutable `segments` are read-only properties.
`state_at(t)` returns an immutable `TrajectoryState` with a `to_dict()` method.
Evaluation is stateless, including backward seeking. Negative times and times
beyond the horizon are rejected, rather than clamped or extrapolated. Numeric
inputs must be int/float, excluding bool, NaN and infinity. Unsupported keys,
IDs, versions, units and modes are rejected. Invalid definitions raise
`ValueError`; exceeded limits raise its subclass `LimitViolation` with
`constraint`, `time_s`, `value`, `lower`, `upper`. The recorded time is an
endpoint/extremum witnessing failure, not necessarily the first crossing.

`segment_definitions()` returns derived dictionaries with `start_s`, `end_s`,
`alt_start_m`, `vz_start_mps`, `az_mps2`. These finite float coefficients are
diagnostic views; rounded starts must not become new independently specified
join states. `VerticalSegment.to_dict()/from_dict()` serialize only the two
authoritative control parameters: `duration_s` and `az_mps2`.

The authoritative trajectory serialization has exactly these fields:

```text
schema_version: "1.0"
model: "piecewise_constant_vertical_acceleration"
units: "SI: m, s, m/s, m/s^2"
mode_id: "nominal"
flight_id: original source ID
duration_s: configured horizon
initial_state: original six position/velocity fields
segments: [{duration_s, az_mps2}, ...]
source_sha256: SHA-256 of canonical JSON {flight, scenario, rules}
```

The fingerprint uses sorted keys, compact separators, JSON's default ASCII
escaping and no NaN/Infinity. It identifies the full supplied source values and
configuration, not the original file bytes or the maneuver definition itself.
Reload requires the source flight/scenario/rules, compares initial state,
horizon and provenance, and reruns continuous validation. Independent start
states are never accepted. Serialization is deterministic and has no timestamp.

## F020 example

Regenerate the separate artifact from any cwd using the script's absolute path,
or from the project root:

```sh
python3 tools/example_vertical.py
```

Defaults read the project's scenario/rules and write
`examples/F020_vertical.json`. Options: `--scenario`, `--rules`, `--output`.
The schedule uses the configured maximum vertical acceleration and illustrative
20 s ramps; changed limits may invalidate it, in which case generation fails.
It is a manually supplied API demonstration, not a conflict-resolution search.
For the current configuration:

| Time (s) | Altitude (m) | Vertical speed (m/s) | Phase |
| ---: | ---: | ---: | --- |
| 0–100 | 8100 | 0 | Initial level flight |
| 120 | 8200 | +10 | Climb acceleration ends |
| 140 | 8300 | 0 | Climb braking ends |
| 140–240 | 8300 | 0 | Elevated level hold |
| 260 | 8200 | −10 | Descent acceleration ends |
| 280 | 8100 | 0 | Return braking ends |
| 280–1200 | 8100 | 0 | Original level flight |

The endpoint is the original F020 destination `(-249689.9, 38926.3, 8100)` m
with velocity `(-229.98, 38.67, 0)` m/s. **Conflict safety is not checked.**

## Validation

`tests/test_vertical.py` covers known integrated trajectories, nonzero initial
vertical speed, both sides of joins, decimal durations, all 40 source level
trajectories, inclusive limits, interior altitude tangency and short excursions
between samples, initial/final violations, configuration changes, invalid
inputs, serialization/provenance, stateless evaluation and deterministic
example generation from another cwd. Run all calculations with:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```
