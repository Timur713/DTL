# Validation of the integrated result

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

## Input file integrity

SHA-256 matches before and after the work:

| File | SHA-256 |
| --- | --- |
| flights.csv | `ee45cda176b4018d3fa5da42033c2db80bdeaf44f90c2f4efc15865781cc03d6` |
| scenario.json | `f507f609cd2e12e2c4a6d1137e7dbf6094ec9579b2163fc0b7bda29c02104241` |
| Task1_details.pdf | `f558659c10eb897636201bc82da087b7baf7e96ea61d8aa9e7d18d6c6b4c914a` |

HTML also contains SHA-256 hashes of the current scenario/flights/rules. The full report stores a fingerprint of canonical inputs and rules. Checks establish consistency between the declared model and implementation; source routes have not been corrected and their safety is not claimed. Detailed applicability limits are in `model.md`.
