# Analysis and visualization contract, version 1.1

This file defines the interface between `rules.json`, the independent Python analyzer and standalone HTML. The integrator coordinates contract changes. Physical assumptions and sources are in [model.md](model.md).

## Configuration and mathematics

Use the exact keys from `rules.json`; profile IDs `metric`, `feet_reference`, mode IDs `nominal`, `bounded_stress`. Variants: `base`, `threat_3000`, `threat_10000`, `target_3000`, `target_10000`. The full product is 20 runs. Order follows the configuration arrays.

Version 1.1 replaces the target cylinder with a sphere: `zones.target.shape="sphere"`, `center_alt_m=0`, `target_motion="static_xyz"`. Center altitude is a finite number in meters; 0 is the agreed scenario assumption. XY remain in `scenario.target`. Configuration version 1.0 and the earlier cylindrical semantics are rejected; old reports and HTML must be regenerated.

States use SI relative to t=0; `p(t)=p0+v*t`, interval `[0,duration_s]`. For each aircraft and the drone, errors `eh(t)=ph+vh*t`, `ez(t)=pz+vz*t` come from the selected `mode.error_bounds`. The target is exact. There are no new measurements.

* Pair: `dh < H+eh_i+eh_j AND abs(dz) < V+ez_i+ez_j` simultaneously.
* Target: `d3 < target_radius+eh_i+ez_i`, with distance to `(x_target,y_target,center_alt_m)`. The target is exact; no target errors are added. The radius in base/stress is `5120+1.1*t` m; in base/nominal it is 5000 m.
* Drone: `d3 < threat_radius+eh_i+ez_i+eh_drone+ez_drone`. For both spheres, the sum of horizontal and vertical bounds is a conservative upper bound on 3D error magnitude. A stress event does not prove a realized violation.
* Altitude: `z-ez < alt_min OR z+ez > alt_max`; source bounds come from `scenario.airspace`. Equality is allowed.
* Stress speed limits are checked over the entire admissible constant-velocity range: horizontal magnitude `[max(0,speed-evh),speed+evh]`, vertical component `[vz-evz,vz+evz]`. Tangential acceleration, vertical acceleration and turn rate of every admissible baseline are zero. The turn limit depends on bank angle and speed; the tangential acceleration limit does not constrain lateral acceleration.

Physical inequalities are strict; numerical epsilon does not expand their boundaries. Numerical tolerances are used for root/residual calculations; exact tangency does not create an event. Connected violation intervals are merged only when their union is actually connected, accounting for open endpoints. Merging must not remove an isolated safe instant.

## Python API

Package `airspace`, module `airspace.analysis`:

```python
load_inputs(scenario_path) -> (scenario: dict, flights: list[dict])
load_rules(rules_path) -> dict
analyze_all(scenario: dict, flights: list[dict], rules: dict) -> dict
write_reports(analysis: dict, output_dir) -> None
```

CLI: `python3 tools/analyze_baseline.py --scenario scenario.json --rules rules.json --output-dir reports` (these are defaults relative to the project root). Standard library, Python >=3.9. Do not import the HTML generator. Validate finite numbers, unique IDs and configuration validity/support; do not silently ignore positive delays or a different uncertainty model.

`write_reports` creates `analysis.json`, `events.csv`, `summary.csv`, `sensitivity.csv` and a brief `summary.md`. JSON numbers are stored without premature rounding; NaN/Infinity are forbidden. Output is deterministic, without a changing timestamp. CSV includes profile/mode/variant/run IDs. The sum of event durations may include overlaps and is not called the duration of unsafe flight.

## Root JSON and HTML payload

```javascript
DATA = {duration_s, scenario, flights, rules, analysis};
analysis = {
  schema_version: "1.1", duration_s: 1200,
  runs: [/* Run */],
  // Additional provenance/sensitivity/limitations metadata is allowed.
};
```

HTML reads precomputed intervals from `analysis.runs`. It does not recalculate conflicts. Position, displayed-distance and zone-size formulas are allowed for visualization. The generated HTML includes all configuration and reports and works through file:// without a network. An example payload is in `tests/fixtures/analysis_example.json`, explicitly synthetic and replaced with real results during integration.

The map displays both zones as sections at the selected aircraft's altitude: `sqrt(R_eff²−(z−z_center)²)` when `abs(z−z_center)<R_eff`; otherwise there is no section. The aircraft card shows 3D target distance and horizontal distance separately.

## Run

```javascript
{
  id: "metric__nominal__base",
  profile_id: "metric", mode_id: "nominal", variant_id: "base",
  thresholds: {
    horizontal_m: 9260, vertical_m: 300,
    threat_radius_m: 5000, target_radius_m: 5000, target_alt_m: 0,
    alt_min_m: 3000, alt_max_m: 12000
  },
  events: [/* Event */],
  summary: {
    event_count: 0, aircraft_pair_count: 0,
    affected_flight_count: 0, affected_flight_ids: [],
    initial_event_count: 0,
    counts_by_type: {aircraft_aircraft: 0, aircraft_threat: 0,
      aircraft_target: 0, altitude: 0, motion: 0},
    first_event_s: null,
    total_event_duration_s: 0
  },
  initial_state: {has_violations: false, event_ids: []},
  motion_checks: {all_pass: true, scope: "constant_velocity_baseline",
    checks: [/* flight_id, rule_id, units, observed_min, observed_max,
                allowed_min, allowed_max, passes */]}
}
```

`aircraft_pair_count` is the number of unique unordered pairs of type aircraft_aircraft only, not the total event count. `affected_flight_ids` covers all event types, excluding THREAT/TARGET. Every motion violation also creates an Event so it can be displayed in the UI; a missing lower/upper bound in a motion check is null.

## Event

```javascript
{
  id: "metric__nominal__base__aircraft_aircraft__F018__F034__0",
  type: "aircraft_aircraft", rule_id: "aircraft_separation",
  participants: ["F018", "F034"], flight_ids: ["F018", "F034"],
  profile_id: "metric", mode_id: "nominal", variant_id: "base",
  start_s: 10, end_s: 14,
  start_inclusive: false, end_inclusive: false,
  initial_violation: false, continues_at_horizon: false,
  severity: "nominal_violation",
  representative_s: 12,
  duration_s: 4,
  thresholds: {
    horizontal: {intercept_m: 1000, slope_mps: 0},
    vertical: {intercept_m: 300, slope_mps: 0}
  },
  metrics: {
    horizontal_min: {value_m: 0, time_s: 12, attained: true},
    vertical_min: {value_m: 0, time_s: 12, attained: true},
    distance_3d_min: {value_m: 0, time_s: 12, attained: true}
  }
}
```

These numbers illustrate a synthetic case, not the actual F018/F034 event. Types: aircraft_aircraft, aircraft_threat, aircraft_target, altitude, motion. `participants` uses `THREAT`, `TARGET` for special objects; for altitude/motion it contains only the aircraft. `rule_id` distinguishes lower/upper altitude bounds and individual motion limits.

An event uses only relevant thresholds/metrics: horizontal and vertical for pairs, radius for both spheres, alt_min_m/alt_max_m and affine error_vertical for altitude, limit names and observed ranges for motion. The target uses `rule_id="target_sphere"`; horizontal_min, vertical_min and distance_3d_min are measured relative to its center. Center altitude is recorded in `run.thresholds.target_alt_m` and summary CSVs. Altitude uses altitude_min/altitude_max metrics of the same form; motion may have empty metrics because results are in motion_checks and thresholds. Additional diagnostic fields are allowed. The UI must not assume all metrics exist.

All distances in metrics are **nominal center distances**, minimized separately over the closure of the event interval. `attained` indicates whether the minimum is attained within the interval itself; otherwise the value is an infimum. Minima of different components may occur at different times and do not jointly prove a conflict. `representative_s` is an interior point for UI navigation, usually the midpoint, not necessarily the CPA time.

Stress events have severity=possible_violation even if part of the interval also contains a nominal violation. To display a confirmed nominal violation, the UI may compare **precomputed intervals** from the corresponding nominal run. This is not repeated geometric detection. Nominal and stress events are not added as independent events of one mode.

The interval is always clipped to `[0,duration_s]`; inclusivity is calculated from the actual violation condition at endpoints. If a violation continues at t=1200, end_inclusive=true and continues_at_horizon=true. A safe equality root is excluded. An initial violation has start=0, start_inclusive=true, initial_violation=true. The UI compares time to stored endpoints/flags without physical tolerances.

## Verifiable examples

`tests/fixtures/detection_examples.json` contains separate mathematical inputs and expected intervals: entry/exit, tangency, altitude equality, constant conflict, horizon clipping and nonoverlapping horizontal/vertical intervals. These are independent simple expectations, not a snapshot of the main detector's output.

For real data at base/nominal, the expected counts are 3 aircraft pairs in metric and 24 in feet_reference; these pairs have no initial violations. This checks calculations, rather than providing a target for fitting rules. The full report also accounts for threat, target, altitude and dynamics.

Sphere example: target `(0,0,0)`, R=5000, aircraft `(-6000,0,3000)` with velocity `(200,0,0)`, T=60. The expected target interval is `(10,50)` s, with a 3D minimum of 3000 m at t=30. At altitude 5000 m the same trajectory only touches the sphere and creates no event; at 8100 m it passes above it. For a stationary aircraft `(0,0,5100)` with only vertical error `20+0.1*t`, the stress interval at T=1200 is `(800,1200]`.

## Additive saved-plan comparison payload

The baseline schema and all 20 runs remain unchanged. Generated HTML may also
contain `DATA.planning`, schema `1.0`, prepared by `airspace.replay` from the
saved nominal solution and accepted repair history. Its authoritative contract
is [comparison-ui.md](comparison-ui.md). Replay/final intervals come from Python;
the UI evaluates saved motion for display and does not detect conflicts.
Only Final plan view receives the independently verified nominal safety badge;
all replay steps are labeled search candidates. `--baseline-only` omits this
additive payload and retains the existing baseline viewer.

## Selected submission and evidence payload

`tools/build_submission.py` independently verifies a saved endpoint-bound-attaining
plan and exports `submission/`. Its selection configuration is separate from
safety rules. The CSV contains every aircraft at every uniform-grid time and
every segment join; rational timestamps are preserved. `segments.json` remains
authoritative. `manifest.json` contains SHA-256 file hashes, without timestamps.

When the default second-pass data and a valid delivery are present, the generator
adds `DATA.submission`, schema 1.0. It verifies delivery hashes and exact agreement
with the already independently rechecked alternative's controls, quality and
verification. The reviewer panel selects this existing alternative; it introduces
no additional trajectories, detector or quality metric implementation in JS.
Historical baseline/reference/quality payloads and initial baseline view remain.

The evidence includes an independent necessary excursion bound from horizontal
CPA and sphere geometry, certified rational square-root brackets, exact terminal
altitude-error counterexamples, and a separate full continuous recheck using the
configured alternative vertical threshold. Threshold sensitivity is not an
uncertainty model. These diagnostics do not change primary rules or extend the
nominal certificate. Details: [submission.md](submission.md).

## Additive quality alternatives

`DATA.quality_alternatives`, current schema `2.0`, is prepared and independently checked
by `airspace.alternatives`. Its contract is [quality-improvement.md](quality-improvement.md):
authoritative saved segment definitions, continuous quality bounds, Python
reference differences, verification runs, source/reference provenance and shared
profile versions. Only independently verified nominal alternatives are exposed.
The preserved first-pass archive uses six objectives. Current schema 2.0
comparison and second-pass dominance use seven, including maximum excursion;
experimental J stays outside dominance. See [second-pass-quality.md](second-pass-quality.md). Endpoint deviation has no airport-arrival semantics.
`--reference-only` omits this payload but retains saved-reference comparison and
its search replay. The original baseline schema and all 20 variants are unchanged.

## Compact email presentation, schema 1.0

`tools/build_email.py` creates `email_delivery/` and `DTL_email.zip`. The archive
contains exactly six flat files: `START_HERE.html`, `README.md`, `trajectories.csv`,
`rules.json`, `segments.json`, `verification.json`. The CSV, rules and motion
controls are byte-identical copies of the selected submission. The report retains
the original certificate in `certificate`, plus quality, source snapshots,
bound/sensitivity witnesses and hashes of the other five files. Its wrapper
schema is `email-delivery-1.0`; it is not the original checker's root schema.

The dedicated template/script embed only the submitted solution and nominal
original routes. The builder independently rechecks both fleets. The viewer opens
on the submitted plan at the F031 sphere witness time. It provides mode switching,
all 40 aircraft, playback/seeking, camera controls, an altitude profile and three
guided moments. JS propagates saved controls for display and compares time with
Python-certified intervals. It does not calculate authoritative quality or detect
conflicts. Profile sphere bands and event-root display values are diagnostic.
The map shows horizontal projections of spheres, explicitly distinguished from
infinite cylinders; the profile shows their altitude slices along the route.

`--github-url` adds the full-project link. All animation data is embedded and
works offline; file downloads remain relative to the extracted six-file folder.
The full experiment archive and existing research viewer are preserved.

The compact presentation puts its three guided questions before the workspace.
It displays original and planned altitude at the same selected time in both
trajectory modes; switching modes preserves time and aircraft selection. Both
altitude markers remain on the profile. Whole-flight end-position error and peak
altitude change are labeled separately from these live readings. The hero's
150/600 m values describe the submitted plan at 1200 s, not the selected aircraft
or current mode; the visible maneuver-cost row also describes the submitted fleet.
Nearest-zone 3D distances and pair horizontal/vertical distances are display
diagnostics computed from rendered positions. They do not classify events or
extend the continuous certificate. The event status still uses Python results.

The compact canvas defaults to a height perspective, with a Top view toggle.
Its display projection is `u = x`, `v = y + 3*z` before camera scaling; ×3 height
exaggeration is labeled. Ground stems and the alternative altitude ghost distinguish
the unchanged XY route from its vertical maneuver. Both plans share camera framing
at a given time, so mode switching cannot conceal the height difference by
recentering. A radius-R sphere projects to an ellipse with semiaxes `R` and
`sqrt(10)*R` in height view, and a circle in top view. Outlines remain projections,
not conflict tests; projected overlaps do not imply 3D proximity. The full-flight
route lines are display samples of saved controls. All authoritative states and
the continuous verification remain unchanged.
