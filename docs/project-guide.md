# Historical project guide

This preserves the project overview at the second-pass checkpoint. For the final
selected delivery, current validation and concise entry point, see the
[root README](../README.md) and [submission guide](submission.md).

## Baseline trajectories: rules and conflicts

40 aircraft and a drone follow their original constant velocities for 1200 s. An aircraft is a point with a protected volume. The selected separation reference is **9260 m horizontally or 300 m vertically**, with a 304.8 m alternative for sensitivity analysis. The drone and target are surrounded by spheres with a radius of 5 km; the target sphere's center is assumed to be at altitude 0 m. The zones apply throughout the horizon, and their radii are scenario assumptions. Aircraft altitudes are restricted to 3000–12000 m; leaving the XY frame is allowed. The drone continues flying after passing the target XY. Sources and rationale are in the [model](../docs/model.md) and [target sphere decision](../docs/target-zone-decision.md); parameters are in [rules.json](../rules.json).

**Open [baseline.html](../baseline.html)** by double-clicking: no server, internet connection or library installation is needed. Select a profile, error mode and radii. Selecting an event in the list or timeline pauses time inside its interval and zooms to its participants. Seeking, playback speeds, trails, aircraft selection and zoom are retained. Current participants are highlighted automatically; both zones are displayed as sphere sections at the selected aircraft's altitude. The card shows the target distance in 3D and horizontally.

## Reproduction

Python 3.9+, standard library:

```sh
python3 tools/generate_baseline.py
```

The command recalculates baseline reports, reconstructs accepted search steps from the existing saved solution, and embeds comparison/replay data in HTML. It does not rerun planning or change saved trajectories. Replay data is also exported to `reports/replay.json`. Analysis only: `python3 tools/analyze_baseline.py`. Both scripts work from any cwd when invoked by absolute path. Arguments: `--scenario`, `--rules`; the generator also accepts `--output`, `--reports-dir`, `--planned-dir`, `--baseline-only`, and the analyzer accepts `--output-dir`.

## Results with 5 km radii

| Profile / mode | Events | Pairs | Drone | Target | Altitude |
| --- | ---: | ---: | ---: | ---: | ---: |
| 300 m / nominal | 12 | 3 | 5 | 4 | 0 |
| 304.8 m / nominal | 33 | 24 | 5 | 4 | 0 |
| 300 m / bounded_stress | 38 | 24 | 7 | 5 | 2 |
| 304.8 m / bounded_stress | 38 | 24 | 7 | 5 | 2 |

In nominal mode, F012, F013, F023 and F026 enter the target sphere. F020 at altitude 8100 m does not enter the 5 km sphere; its pair event with F038 remains and starts at approximately 280.313 s, the first event of the primary profile. Target radii of 3/5/10 km produce respectively 0/4/14 nominal target events, without initial violations.

In stress mode, each aircraft and the drone have errors `e_h=100+t` m, `e_z=20+0.1t` m from the t=0 snapshot. The exact target's sphere is expanded only by the aircraft's `e_h+e_z`: `R_eff=5120+1.1*t` m; a possible event involving F037 appears. The drone sphere accounts for errors of both objects. This indicates possible loss of guarantee, not probability. F031/F040 at the nominally allowed 3000 m have an initial risk of falling below the boundary under these errors. Baseline motion checks pass.

All **20 variants**: [summary](../reports/summary.md), [JSON](../reports/analysis.json), [event CSV](../reports/events.csv), [sensitivity](../reports/sensitivity.csv), [summary CSV](../reports/summary.csv). Events, unique pairs and affected aircraft are counted separately.

## Method and validation

The [analyzer](../airspace/analysis.py) solves strict quadratic/linear inequalities continuously; equality is safe. HTML reads precomputed intervals according to the [contract](../docs/contracts.md).

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

**124 Python tests and five browser suites** cover the calculation and offline UI milestones; actual validation results and source-file checksums are in the [validation record](../docs/validation.md).

The baseline does not implement maneuvers. Generic jet limits are assumptions; actual aircraft types, wind, delays and wake turbulence are not modeled. The stress sphere is conservative. Minima of different distances may occur at different times; the sum of overlapping event durations is not the duration of unsafe flight.

## Separate vertical trajectory model

[`airspace/vertical.py`](../airspace/vertical.py) provides piecewise constant vertical acceleration with unchanged source horizontal velocity, continuous position/velocity, full-segment motion/altitude validation, arbitrary-time evaluation and serialization. Its [model and API contract](../docs/vertical-model.md) is separate from the baseline; only nominal kinematics are supported. It does not check conflict safety or change baseline reports/HTML.

```sh
python3 tools/example_vertical.py
```

This regenerates [`examples/F020_vertical.json`](../examples/F020_vertical.json): a climb from 8100 to 8300 m, a level hold and return to 8100 m with zero vertical speed by 280 s, then original level flight to 1200 s. The example is an API demonstration; conflict safety remains unchecked. The Python test command above includes the vertical model tests.

## Nominal planning pipeline

```sh
python3 tools/plan_nominal.py
```

This separately plans and independently verifies all 40 aircraft, then writes authoritative segments, diagnostic sampled trajectories, verification results, search history and a short summary under [`reports/planned/`](../reports/planned/summary.md). The checker handles accelerated vertical motion continuously, including quartic sphere distances. Terminal altitude deviation is permitted and remaining destination distance is reported; no arrival-delay estimate is made. Baseline inputs, rules, reports and HTML are preserved.

The saved result has **zero nominal violations and zero unresolved checks**, after 7959 candidates and 21 repair steps affecting 15 aircraft. Five terminal altitude deviations are reported in the summary; all horizontal destinations are preserved.

The [planning/checker contract](../docs/nominal-planning.md) explains numerical guarantees, bounded search limits, output formats and reproduction options. A verified-safe result requires zero nominal violations and zero unresolved checks over the complete horizon. Bounded search failure does not prove infeasibility. The saved result is now integrated into the offline comparison viewer.

## Offline final comparison and search strategy

Open **[baseline.html](../baseline.html)**. Baseline / Final plan switches preserve simulation time, playback and selection. The saved nominal comparison shows **12 → 0 events**. Altitude and vertical-speed overlays, maneuver phases, maximum excursions and remaining destination distances expose vertical changes that a top view cannot show.

Search replay covers accepted steps **0–21**, separately from simulation time. Click a step to inspect its fleet and changed aircraft, remaining zone/pair counts and repair details. Intermediate views are labeled potentially unsafe search candidates; only Final plan has the verified final status. Step 20's equal-count pair replacement is explained. A table includes all 15 changed aircraft and the five terminal altitude offsets.

Planned/replay views are locked to metric / nominal / base. All baseline profile/stress/radius functionality remains available. The [comparison contract and instructions](../docs/comparison-ui.md) describe reconstruction, data provenance and controls. Regenerate with `python3 tools/generate_baseline.py`; no planning rerun is needed.

Additional browser checks:

```sh
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_comparison_ui.cjs
```

## Verified quality alternatives

```sh
python3 tools/improve_nominal.py
python3 tools/generate_baseline.py
```

The separate bounded multiobjective search preserves the saved reference and
writes eight independently verified alternatives under
[`reports/improved/`](../reports/improved/summary.md). In [baseline.html](../baseline.html),
select a solution to compare raw continuous metrics and reference differences,
altitude/vertical-speed profiles and raw objective scatter plots. Time, playback
and aircraft selection survive solution changes. Reference search replay and
baseline stress/profile controls remain available.

The endpoint-focused alternative reduces maximum endpoint deviation **6300 → 300 m**,
total endpoint deviation **14100 → 600 m**, and accumulated deviation
**19809900 → 13745400 m·s**, with travel **47700 → 61200 m** and reversals **10 → 14**.
Another reduces changed aircraft **15 → 13** and reversals **10 → 7**, with higher
total endpoint and accumulated deviations. These distances concern the original
endpoint at 1200 s, not airport arrival. Every saved alternative has zero nominal
violations, zero unresolved checks and zero terminal vertical speed.

The [quality contract](../docs/quality-improvement.md) explains exact segment
integrals, segmentation-independent reversals, certified six-objective dominance,
frozen experimental J, artifact formats and limits. This run used 360 candidate
evaluations and 29 independent verifications, retained eight alternatives and
recorded three capacity-pruning operations. It establishes no global optimum.

```sh
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_quality_ui.cjs
```

## Targeted second pass

```sh
python3 tools/improve_second.py
python3 tools/generate_baseline.py
```

The separate [second-pass experiment](../docs/second-pass-quality.md) uses seven
Pareto objectives, including maximum altitude excursion, and preserves every
reference/first-pass solution artifact. Its configurable limits start at 3000
candidate evaluations, 200 full verifications, 32 retained points and a 900 s
cooperative search guard. New artifacts are in
[`reports/improved_second/`](../reports/improved_second/summary.md).

The offline viewer compares all three generations with seven raw metrics,
endpoint bounds/gaps, added/restored aircraft and targeted temporary excursions.
The unchanged experimental weighted score remains comparison-only. Endpoint
bounds derive independently from the two disjoint terminal pairs: 600 m total
and 150 m maximum. A fully verified second-pass candidate attains both, proving
optimality for those endpoint metrics under this scenario's fixed-horizontal
model. Other quality metrics remain bounded-search results. The endpoint-optimal saved
plan reduces maximum excursion **6300 → 6150 m**, accumulated deviation
**13745400 → 13448700 m·s**, and travel **61200 → 60600 m** relative to the
first-pass endpoint plan, with **15 changed aircraft** and **13 reversals**.
The run retained 10 alternatives after 3000 evaluations and 82 full verifications;
no capacity pruning was needed. Five first-pass alternatives are now dominated;
three remain trade-offs. The overall saved minimum travel remains 46200 m.

## Working on the project

General rules for development, model changes, validation and collaboration are in [AGENTS.md](../AGENTS.md). Source inputs and reproducible HTML/reports are tracked in Git; caches and local dependencies are excluded.
