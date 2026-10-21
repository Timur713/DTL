# Baseline trajectories: rules and conflicts

40 aircraft and a drone follow their original constant velocities for 1200 s. An aircraft is a point with a protected volume. The selected separation reference is **9260 m horizontally or 300 m vertically**, with a 304.8 m alternative for sensitivity analysis. The drone and target are surrounded by spheres with a radius of 5 km; the target sphere's center is assumed to be at altitude 0 m. The zones apply throughout the horizon, and their radii are scenario assumptions. Aircraft altitudes are restricted to 3000–12000 m; leaving the XY frame is allowed. The drone continues flying after passing the target XY. Sources and rationale are in the [model](docs/model.md) and [target sphere decision](docs/target-zone-decision.md); parameters are in [rules.json](rules.json).

**Open [baseline.html](baseline.html)** by double-clicking: no server, internet connection or library installation is needed. Select a profile, error mode and radii. Selecting an event in the list or timeline pauses time inside its interval and zooms to its participants. Seeking, playback speeds, trails, aircraft selection and zoom are retained. Current participants are highlighted automatically; both zones are displayed as sphere sections at the selected aircraft's altitude. The card shows the target distance in 3D and horizontally.

## Reproduction

Python 3.9+, standard library:

```sh
python3 tools/generate_baseline.py
```

The command recalculates reports and embeds them in HTML. Analysis only: `python3 tools/analyze_baseline.py`. Both scripts work from any cwd when invoked by absolute path. Arguments: `--scenario`, `--rules`; the generator also accepts `--output`, `--reports-dir`, and the analyzer accepts `--output-dir`.

## Results with 5 km radii

| Profile / mode | Events | Pairs | Drone | Target | Altitude |
| --- | ---: | ---: | ---: | ---: | ---: |
| 300 m / nominal | 12 | 3 | 5 | 4 | 0 |
| 304.8 m / nominal | 33 | 24 | 5 | 4 | 0 |
| 300 m / bounded_stress | 38 | 24 | 7 | 5 | 2 |
| 304.8 m / bounded_stress | 38 | 24 | 7 | 5 | 2 |

In nominal mode, F012, F013, F023 and F026 enter the target sphere. F020 at altitude 8100 m does not enter the 5 km sphere; its pair event with F038 remains and starts at approximately 280.313 s, the first event of the primary profile. Target radii of 3/5/10 km produce respectively 0/4/14 nominal target events, without initial violations.

In stress mode, each aircraft and the drone have errors `e_h=100+t` m, `e_z=20+0.1t` m from the t=0 snapshot. The exact target's sphere is expanded only by the aircraft's `e_h+e_z`: `R_eff=5120+1.1*t` m; a possible event involving F037 appears. The drone sphere accounts for errors of both objects. This indicates possible loss of guarantee, not probability. F031/F040 at the nominally allowed 3000 m have an initial risk of falling below the boundary under these errors. Baseline motion checks pass.

All **20 variants**: [summary](reports/summary.md), [JSON](reports/analysis.json), [event CSV](reports/events.csv), [sensitivity](reports/sensitivity.csv), [summary CSV](reports/summary.csv). Events, unique pairs and affected aircraft are counted separately.

## Method and validation

The [analyzer](airspace/analysis.py) solves strict quadratic/linear inequalities continuously; equality is safe. HTML reads precomputed intervals according to the [contract](docs/contracts.md).

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

**63 tests (43 baseline/integration and 20 vertical-model tests) and two browser suites passed.** Browser validation commands, spherical target checks and source-file checksums are in the [validation record](docs/validation.md).

The baseline does not implement maneuvers. Generic jet limits are assumptions; actual aircraft types, wind, delays and wake turbulence are not modeled. The stress sphere is conservative. Minima of different distances may occur at different times; the sum of overlapping event durations is not the duration of unsafe flight.

## Separate vertical trajectory model

[`airspace/vertical.py`](airspace/vertical.py) provides piecewise constant vertical acceleration with unchanged source horizontal velocity, continuous position/velocity, full-segment motion/altitude validation, arbitrary-time evaluation and serialization. Its [model and API contract](docs/vertical-model.md) is separate from the baseline; only nominal kinematics are supported. It does not check conflict safety or change baseline reports/HTML.

```sh
python3 tools/example_vertical.py
```

This regenerates [`examples/F020_vertical.json`](examples/F020_vertical.json): a climb from 8100 to 8300 m, a level hold and return to 8100 m with zero vertical speed by 280 s, then original level flight to 1200 s. The example is an API demonstration; conflict safety remains unchecked. The Python test command above includes the vertical model tests.

## Working on the project

General rules for development, model changes, validation and collaboration are in [AGENTS.md](AGENTS.md). Source inputs and reproducible HTML/reports are tracked in Git; caches and local dependencies are excluded.
