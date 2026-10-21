# Validation of the integrated result

## Reviewer presentation refinement — October 21, 2026

The compact viewer now places its three guided questions above the workspace,
compares original/planned altitude simultaneously, labels map objects with
altitude, enlarges the altitude profile and exposes fleet maneuver costs. Live
distance readings are diagnostics, not a new safety detector. Choosing an aircraft
updates its explanation; whole-flight and current-time figures are distinguished.

Five compact-package Python tests passed, including byte-identical rebuilding.
The extended compact browser suite passed on desktop/mobile, checking both live
altitudes against CSV, comparison without losing time/selection, all 40 aircraft,
the contextual explanations, displayed distance geometry, playback and offline
links. The baseline and analysis browser suites also passed again. Desktop/mobile
screenshots were inspected. The compact suite additionally passed on the isolated
six-file ZIP extraction; original inputs, rules and saved controls are unchanged.
The full 140-test calculation run below was not repeated for this presentation-only
change. Reproduction uses `tools/build_email.py` and the commands in the compact
delivery section below.

## Repository publication check — October 21, 2026

After adding the [repository map](README.md) and explicit reviewer/agent entry
points, the complete Python suite passed: **140 tests in 445.580 s**. All seven
browser suites passed again: baseline, analysis, reference comparison, first-pass
quality, second-pass quality, selected submission and compact email presentation.
The commands are documented in [submission.md](submission.md#reproduce).

Local documentation links, both delivery manifests and the compact ZIP's CRC and
six-file contents were checked. All 74 protected source/configuration and saved
solution files remain byte-identical. Staged input and trajectory bytes also
match the working files. CSV Git attributes preserve those bytes without newline
conversion. `git diff --cached --check` passes; caches and local dependencies are
excluded. The redundant full-project ZIP was removed and is now ignored; its
optional exporter remains available. No trajectories, thresholds or safety
formulas were changed by this repository cleanup.

## Compact email delivery — October 21, 2026

`DTL_email.zip` contains exactly **six files at its root**, approximately 675 KB:
`START_HERE.html`, `README.md`, `trajectories.csv`, `rules.json`, `segments.json`,
`verification.json`. The dedicated presentation opens on the selected safe plan,
not the original unsafe routes. It includes the full-project link
`https://github.com/Timur713/DTL`; it does not upload or publish the repository.
The CSV, shared rules and authoritative controls match the selected submission
byte for byte. The report preserves its certificate, quality and proof witnesses.

Five new Python package tests pass: six-file/hash/certificate coherence, ZIP
contents/size, exact known geometry of plotting bands, output-directory and
GitHub-URL validation, and byte-identical package reproduction. The new browser
suite passes: all 40 motions at six times against Python CSV, original/safe
switching, all three guided moments, all 40 aircraft selections, endpoint geometry,
profile synchronization, playback/pause/speeds/seeking, camera/keyboard controls,
all relative file links, GitHub link, no horizontal mobile overflow, no network
requests and no JS errors. Desktop/mobile screenshots were inspected. Original
baseline and analysis browser suites were also rerun successfully.

```sh
python3 tools/build_email.py --github-url https://github.com/Timur713/DTL
python3 -m unittest discover -s tests -p 'test_email.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_email_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
```

Screenshots: `/tmp/dtl-email-desktop.png`, `/tmp/dtl-email-mobile.png`. These tests
extend the 135-test full Python run and previous six browser suites below; the
full Python suite was not repeated for the separate email presentation. Its
numerical safety model and selected motion are unchanged.

## Final selected delivery — October 21, 2026

The final selected plan is `pass2-b8f763f4b8b0`. A fresh independent continuous
check confirms all 40 aircraft, all 780 pairs, zones, altitude, motion limits and
segment joins over [0,1200] s: **zero nominal violations, zero unresolved checks**.
All terminal vertical speeds are zero. The selected authoritative controls and
earlier experiment artifacts were preserved; the delivery is a separate export.

- **Full Python suite: 135 tests, PASS**, 442.334 s. This includes the previous
  124 tests and 11 evidence/delivery tests. The 11 evidence tests were also rerun
  successfully after tightening metadata/input validation.
- **All six browser suites: PASS** — baseline, analysis, reference comparison,
  first-pass quality, second-pass quality, and final submission. The submission
  suite additionally checks exact embedded evidence agreement, selected-plan
  identity, preservation of time/selection, terminal pair geometry, the large-climb
  witness tour, delivered links, desktop/mobile layout, no network requests and
  no JS errors. The final submission suite was rerun against regenerated HTML.
- **Delivery export: PASS** — all 40 IDs at every output time, 48,040 rows,
  horizon endpoints and every segment join. All six state columns at each join
  agree with the separate vertical trajectory implementation.
- **Geometry: PASS** — exact 3-4-5 sphere example, tangent pass, lower branch
  exactly at the altitude floor, clipped CPA at the horizon, unsupported vertical
  source motion and certified irrational square-root enclosures. The real F031
  witness was independently recomputed directly from source affine XY states.
- **Sensitivity: PASS** — a fresh complete nominal recheck of unchanged controls
  at the configured alternative V=304.8 m yields **16 pair events, zero unresolved**.
  Exact opposing 1 m endpoint altitude errors produce 298 m separation in the two
  binding pairs. These are diagnostics; no bounded-stress execution guarantee is
  inferred.
- **Preservation: PASS** — SHA-256 checks confirm all **74 protected files** from
  the start of final integration remain byte-identical: the three source inputs,
  rules, and all reference/first-pass/second-pass solution artifacts.
- **Packaging: PASS** — ZIP CRC and all delivery manifest hashes checked; no Git
  internals, caches or local dependencies included. An isolated extracted project
  regenerated every selected delivery file byte for byte from another cwd.
- **Documentation/layout: PASS** — root README is 424 words; local Markdown links
  resolve; desktop (1440 px) and mobile (390 px) screenshots were reviewed.
  `git diff --check` passes.

Commands actually run for this final milestone:

```sh
python3 tools/build_submission.py --html --package
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_evidence.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_comparison_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_quality_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_second_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_submission_ui.cjs
```

Screenshots inspected: `/tmp/dtl-submission-desktop.png` and
`/tmp/dtl-submission-mobile.png`. They are local validation evidence; the delivered
animation is the self-contained HTML. Scope, proof limits, the assignment-to-file
mapping and reproduction are in [submission.md](submission.md). Earlier milestone
validation below is retained as history.

Checked on October 21, 2026. Environment: Python 3.9.6, Node.js 25.2.1, Playwright and local Google Chrome on macOS. The result is standalone `baseline.html` with source data, shared configuration and actual analyzer reports; the synthetic example is not used in production.

## Reproducible checks

From the project root:

```sh
python3 tools/generate_baseline.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
npm install --prefix /tmp/dtl-baseline-check --no-save playwright
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
```

Generation and analysis use only the Python standard library. Node/Playwright are needed solely for browser tests. `CHROME_PATH` overrides the browser path, `SCREENSHOT_PATH` saves a screenshot; `HTML_PATH` allows testing another HTML file.

- **37 mathematical/analytical tests — PASS.** Checks cover conflicts between integer seconds, tangencies and near-tangent cases, zero relative velocity, strict boundaries, conflicts at t=0 and the horizon endpoint, nonoverlapping horizontal/vertical intervals, both vertical profiles, growing errors, monotonicity, constant minima, motion limits, input validation, CLI and determinism. Six new checks cover the target sphere: analytical entry/exit and 3D minimum, tangency and passing above the sphere, vertical entry from the boundary, configured center altitude, growth of vertical error alone and independent line/sphere intersection for all nominal runs.
- **6 integration tests — PASS.** Checks cover the reference 3/24 pairs, inclusion of all nominal intervals in stress, expansion of violation sets as radii increase, CSV/JSON and report reproducibility, and exact agreement of HTML with current data/rules/calculations. Running the generator from a different cwd reproduces byte-identical HTML and JSON.
- **Baseline browser suite — PASS.** All 40 aircraft, initial/final coordinates, seeking and trails, pause, 1×/10×/30×/60× speeds, frame independence, retention of objects outside boundaries, drone passage through target XY, selection, distances, zoom and pan.
- **Analysis browser suite — PASS.** All 20 runs, counter agreement with JSON, open interval boundaries, automatic highlighting of current participants without event selection, list/filters/timeline, navigation with pause and participant display, zone geometry and stress during seeking, optional metrics, safe string display, 390 px width, no network requests or JS errors. Additional checks cover absence of a target section at F020's altitude, an actual canvas command with a 4000 m radius at altitude 3000 m, zero section at/above the sphere boundary, 3D distance in the card, target event metrics and expansion of its radius to 6440 m at the end of the stress horizon.

The latest complete run after switching to the target sphere: **43 tests, OK**. Both browser suites were run against the final HTML, rather than only the synthetic example.

Screenshots of the final page on desktop (1440 px) and mobile (390 px), with the F012/target event selected, were reviewed: the sphere section, 3D distance card and event list agree; there is no horizontal overflow.

## English translation verification

Documentation, project instructions, UI text and accessibility labels, configuration labels, fixture labels and generated report prose now use English. The HTML declares `lang="en"` and formats numbers with `en-US`. The original task PDF and source inputs were already in English and were retained unchanged.

After regeneration, **all 43 Python tests and both browser suites passed**. Browser checks also verify the English page language, number formatting, playback label and absence of Cyrillic UI text across all 20 runs. Desktop and mobile screenshots of the English viewer were reviewed; the layout has no horizontal overflow.

Compared with the pre-translation Git revision `260315e`, all **20 runs / 643 events**, metrics, thresholds, summaries, endpoint flags and motion checks match exactly. The only change in `reports/analysis.json` is the input fingerprint, because translated display labels are part of `rules.json`. The three CSV reports and all three source files remain byte-identical. The configuration and synthetic fixture differ only in display labels; the analyzer's Python syntax tree differs only in string literals. A project-wide text scan found no remaining Cyrillic text or Russian locale settings, and local documentation links were checked.

## Switch to the target sphere, version 1.1

The 20 recalculated runs contain **643 events**. Base/metric/nominal: 12 events (3 pairs, 5 drone, 4 target); base/metric/stress: 38 (24 pairs, 7 drone, 5 target, 2 altitude). An independent line-projection and chord-length method confirms nominal target event times for all radii. Comparing old and new reports, every event outside the `aircraft_target` type matched exactly across all 20 runs.

F020 does not violate the 5 km sphere, but retains its pair event with F038 from t≈280.313 s. In nominal mode, F012/F013/F023/F026 enter the target sphere; stress additionally flags F037. Source data and trajectories are preserved. The decision and its assumptions are in [target-zone-decision.md](target-zone-decision.md).

## Previous independent audit of version 1.0

Before switching to the target sphere, the model agent independently of the analyzer author read the version 1.0 formulas and reports with a cylindrical target. Its independent calculation from interval boundaries confirmed all **20 runs / 827 events**, participants, types, endpoint flags and **1825 minimum metrics**. The maximum time discrepancy from the main solver was about `1.03e-11` s. An additional 5000 random quadratic cases × 81 rational points were checked. These historical numbers do not apply to the current version 1.1 reports. This is an independent diagnostic check, not formal verification; the repeatable test suite is in `tests/`.

The audit identified two validation issues: sensitivity lists could disagree with actual profiles/variants, and bool could be accepted as numerical zero. Fixes were added with negative tests. They did not change results: all five report files remained byte-identical.

## Separate vertical model

On October 21, 2026, all **63 Python tests passed**: the existing 43 checks
and 20 new tests in `tests/test_vertical.py`. The new tests use independently
known positions/velocities, check continuous segment joins and exact limit
boundaries, and detect a short altitude excursion at t=0.25 s between integer
samples. They also check all 40 source level flights, unchanged horizontal
motion outside the XY frame, unsupported inputs/modes, serialization with
provenance, and deterministic F020 example generation from another cwd.

`python3 tools/example_vertical.py` regenerated
`examples/F020_vertical.json`. F020 reaches 8300 m, holds, and returns to
8100 m with vz=0 by 280 s; its original horizontal motion and 1200 s destination
are retained. This checks nominal kinematics/altitude only. Conflict safety
and bounded-stress applicability are not established.

`python3 tools/generate_baseline.py` reproduced byte-identical baseline HTML
and all five reports; both browser suites passed against the regenerated HTML.
The source SHA-256 checksums below still match. Configuration and baseline
calculations were not changed. The separate model's contract and API are in
[vertical-model.md](vertical-model.md).

Coordinator review reran all 63 Python tests and both browser suites successfully.
An additional deterministic diagnostic (seed 20261021) compared 4300 states
across 100 valid schedules with an independent acceleration-step formula,
`z(t)=z0+vz0*t+sum(delta_az*max(0,t-t_join)^2/2)`, and checked 100 JSON
round trips. All comparisons passed. Source inputs, rules and baseline artifacts
remain byte-identical to the preceding Git revision. This diagnostic supplements
the continuous extrema checks; it is not a sampled proof of conflict safety.
The API example still violates F020/F038 separation: at t=300 s their horizontal
distance is approximately 6059.272 m and their vertical distance is 0 m.

## Nominal planning and independent verification

The added pipeline was run on all 40 source aircraft with unchanged
`metric / nominal / base` rules. Its independent checker reproduces the
**12 baseline events** (3 pair, 5 drone, 4 target), including event times and
strict endpoint flags. The completed bounded search used **7959 candidate
attempts and 21 repair steps**, affecting 15 distinct aircraft. A fresh checker
reread the saved authoritative segments and checked every aircraft plus all
**780 unordered pairs over the full [0,1200] s horizon**: **0 nominal violations,
0 unresolved checks**. The actual records are in
[`reports/planned/summary.md`](../reports/planned/summary.md) and
[`verification.json`](../reports/planned/verification.json).

Five aircraft have nonzero terminal distance from the original endpoint:
F013 900 m, F018 5700 m, F023 900 m, F030 300 m, F034 6300 m. These are signed
upward altitude deviations with identical absolute remaining 3D distance;
all horizontal deviations are zero. No arrival-delay estimate is made.
The feasible example is not asserted to be optimal.

Commands actually run:

```sh
python3 tools/plan_nominal.py
python3 tools/plan_nominal.py --output-dir /tmp/dtl-plan-reproduce
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/generate_baseline.py
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
```

**91 Python tests passed**: all 63 existing tests, 21 new checker/polynomial
checks and 7 planner/output checks. The polynomial suite includes independently
constructed factor oracles, repeated and very close roots, quartic sphere
entry/tangency, strict boundaries, between-sample accelerated violations and
forced numerical-budget exhaustion. Planner checks include known feasible
returns, terminal holds, explicit failure under bounded search, deterministic
exports, CLI invocation from another cwd, complete saved-fleet verification,
monotonic/plateau search accounting and sampled-state comparison against the
separately implemented vertical trajectory evaluator. The seven planner tests
were rerun after strengthening CSV and repair-history assertions and passed.

A second complete CLI search reproduced the same authoritative segment JSON,
sampled CSV, verification JSON, baseline verification and summary byte for byte.
After the rejection-witness optimization, search instrumentation was updated;
all six final artifacts also reproduced byte-identically when exported again
from the final authoritative controls and search records.

Both browser suites passed against the regenerated baseline. Its five reports,
HTML, `rules.json` and all source files remain byte-identical to the preceding
revision. Source SHA-256 checksums below still match. No HTML integration was
performed. The exact rational sign-decomposition method, reporting brackets,
root budgets, cache scope, bounded search family and new output contract are
specified in [nominal-planning.md](nominal-planning.md). The result covers only
nominal model kinematics, not bounded stress or behavior after T.

## Offline final-plan comparison and accepted-history replay

The offline HTML now includes Baseline / Final plan / Search replay views,
synchronized altitude and vertical-speed profiles, maneuver phases, the
accepted-history graph/details and a table of all 15 changed aircraft. Only
Final plan has the final verified status; every replay step is labeled a
potentially unsafe search candidate. Planned/replay controls are locked to
metric / nominal / base. Baseline alternative profiles, bounded stress and
radii are preserved and restored when returning to Baseline.

`airspace.replay` reconstructed all 22 fleet states (0–21) from the actual saved
repair parameters using the unchanged schedule helper. Independent continuous
checks agree with all recorded removed/introduced counts. Step 20 replaces
F004/F031 with F004/F034 while one pair event remains; step 21 removes it.
The final reconstructed controls equal `segments.json` exactly, and the final
verification equals the independently checked saved result. No rejected
candidate's unrecorded controls or ranking were invented.

Commands actually run:

```sh
python3 tools/generate_baseline.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright SCREENSHOT_DIR=/tmp node tests/check_comparison_ui.cjs
python3 tools/generate_baseline.py --baseline-only --output /tmp/dtl-baseline-only.html --reports-dir /tmp/dtl-baseline-only-reports
```

**All 99 Python tests and all three browser suites passed.** The eight new Python
checks cover reconstruction, every iteration's counts, unchanged-version reuse,
final-control/verification equality, actual plateau participants, known profile
values and phases, maxima versus terminal offsets, deterministic embedded data,
and rejection of stale/tampered saved history. The existing integration test
regenerated byte-identical HTML from another cwd.

The comparison browser suite checks 12 versus 0 events; all 40 final aircraft
against the saved Python CSV at six times; synchronized profiles, phase and
velocity display; all 22 replay steps; separate iteration/time controls;
changed-aircraft selection and canvas halos; precomputed event navigation;
planned-altitude sphere sections; all 15 table rows and five terminal offsets;
nominal selector locking and restoration of baseline stress settings; playback,
pause, rewind and keyboard seeking; desktop and 390 px mobile layouts; and no
network requests or JavaScript errors. A separate browser smoke check confirmed
that `--baseline-only` loads offline without comparison data or script errors.
Desktop profile and full mobile screenshots were reviewed.

SHA-256 checks against the start-of-task snapshot confirm that the planner,
checker, polynomial kernel, vertical model, planning CLI, rules, source inputs
and **all six files under `reports/planned/` remain byte-identical**. The five
baseline report files remain byte-identical to Git HEAD. Only the visualization,
additive replay data, preparation code, tests and documentation were extended.
`reports/replay.json` and the HTML embed the saved-file checksums and canonical
source/configuration fingerprint. The additive contract and reproduction options
are in [comparison-ui.md](comparison-ui.md).

## Continuous quality and bounded Pareto improvement

Reproduction and validation commands:

```sh
python3 tools/improve_nominal.py
python3 tools/generate_baseline.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_comparison_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright SCREENSHOT_DIR=/tmp node tests/check_quality_ui.cjs
```

The saved bounded run stopped at 360 candidate evaluations, with 29 independent
full verifications (including eight export checks), 21 certified feasible
schedules including the reference, eight retained alternatives and three
capacity-pruning operations. Limits are 360 evaluations, 48 full verifications,
eight archive members, six moves per strategy and a cooperative 300 s search
guard. No global optimality is established. The full contract, mathematical
guarantees, configurations and actual metric table are in
[quality-improvement.md](quality-improvement.md) and
[the saved summary](../reports/improved/summary.md).

Seventeen additional Python tests cover independently known absolute integrals,
altitude crossings/tangency and irrational-root bounds, redundant segmentation,
reversals across holds, exact frozen reference scales, terminal speed, malformed
inputs, strict six-objective dominance, uncertainty, coordinated rational-offset
returns, neighborhood construction, bounded deterministic search and byte-identical
exports in two temporary directories, capacity pruning and the entire saved
archive. Every saved alternative is rechecked independently with zero violations,
zero unresolved checks and zero terminal vertical speed. All saved aggregate
quality bounds have identical exact rational endpoints.

The fourth browser suite covers all nine solution selections, seven raw metrics
and Python reference deltas, frozen experimental scores, saved motion for all
40 aircraft at four times per solution, terminal zero speeds, reference profile
overlays, verification status, scatter interaction, separate reference replay,
nominal scope and baseline stress restoration, retained selection/time/playback,
390 px mobile layout, offline requests and JavaScript errors.

**All 116 Python tests and all four browser suites passed.** The full Python
suite completed in 210.273 s, including regeneration from another cwd and
byte-identical HTML comparison. Desktop and mobile quality-panel screenshots
were visually reviewed. The playback-switch check evaluates the switch within
one browser task so normal elapsed playback between automation calls cannot
be mistaken for a time reset. `git diff --check` and updated documentation links
also passed.

Start-of-task SHA-256 checks confirm the source inputs, rules, original planner,
continuous checker, polynomial kernel, vertical model, original planning CLI and
all six `reports/planned/` artifacts are unchanged. The five baseline report
files remain byte-identical to Git HEAD. New quality artifacts are separate;
replay and original nominal rules retain their semantics.

## Input file integrity

SHA-256 matches before and after the work:

| File | SHA-256 |
| --- | --- |
| flights.csv | `ee45cda176b4018d3fa5da42033c2db80bdeaf44f90c2f4efc15865781cc03d6` |
| scenario.json | `f507f609cd2e12e2c4a6d1137e7dbf6094ec9579b2163fc0b7bda29c02104241` |
| Task1_details.pdf | `f558659c10eb897636201bc82da087b7baf7e96ea61d8aa9e7d18d6c6b4c914a` |

HTML also contains SHA-256 hashes of the current scenario/flights/rules. The full report stores a fingerprint of canonical inputs and rules. Checks establish consistency between the declared model and implementation; source routes have not been corrected and their safety is not claimed. Detailed applicability limits are in `model.md`.

## Targeted second pass: endpoint bounds and seven-objective archive

Commands actually run:

```sh
python3 tools/improve_second.py
python3 tools/generate_baseline.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_comparison_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright SCREENSHOT_DIR=/tmp node tests/check_quality_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright SCREENSHOT_DIR=/tmp node tests/check_second_ui.cjs
```

The experiment stopped at the 3000-candidate cap, before the cooperative 900 s
runtime guard. It performed 82 full independent verifications, including four
seed checks and ten serialized-export checks, and certified 72 schedules.
Ten second-pass alternatives were retained; no capacity pruning was needed.
Every saved plan has zero nominal violations, zero unresolved checks and exactly
zero terminal vertical speed. UI generation and tests perform further fresh
checks outside those experiment counters.

The independent source-endpoint enumeration and separate Decimal test confirm
exactly F018/F034 and F030/F039 as disjoint terminal-conflict pairs. Triangle
inequality gives necessary bounds Dtotal >=600 m and Dmax >=150 m. A full-horizon
verified witness attains both; this establishes scenario-specific optimality
for these two endpoint metrics only. The frozen four-term experimental score
configuration and reference denominators remain unchanged after adding maximum
excursion as the seventh minimized objective.

Eight additional Python tests cover independent endpoint enumeration, changed
thresholds and nonzero baseline differences, non-double-counting overlapping
pairs, equality boundaries, continuous level-transition endpoints/velocity,
invalid inputs/budgets, excursion dominance versus frozen score, archive extrema,
small-budget multi-start deterministic search and byte-identical exports,
and fresh complete verification/quality/gaps/dominance of every saved second-pass
plan. The updated earlier tests preserve first-pass reproduction and assert
seven-objective semantics. A separate rerun of the deterministic-export test
passed after summary-generation refactoring.

All five browser suites passed. The new fifth suite checks all three solution
generations, seven objective axes, Python endpoint bounds/gaps and attained-bound
status, changed-aircraft counts, the four targeted excursion diagnostics,
Python dominance relationships, synchronized profiles, retained aircraft/time,
mobile horizontal table scrolling and standalone file:// operation. The expanded
quality suite checks all 19 displayed solutions against their saved segment
files, for all 40 aircraft at four times each, plus playback/selection retention
and the unchanged reference search replay. Baseline suites retain all 20 runs,
12 primary baseline events and zero independently verified planned events.
Desktop/mobile screenshots were reviewed. An intrinsic-width overflow in the
longer solution selector was found by the mobile smoke check and fixed.

SHA-256 checks confirm all 41 protected source/rules/experiment/reference and
first-pass artifacts remain byte-identical to the start-of-task snapshot.
The five baseline calculation reports remain byte-identical to Git HEAD.
Updated documentation links and `git diff --check` pass. The actual metric table,
dominated earlier IDs and search-family limitations are documented in
[second-pass-quality.md](second-pass-quality.md) and the
[generated summary](../reports/improved_second/summary.md).

**All 124 Python tests passed in 405.384 s, and all five browser suites passed.**
