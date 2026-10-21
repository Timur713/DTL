# Offline comparison and accepted-search replay, version 1.0

Open **`baseline.html`** locally. Regenerate it from the current saved solution:

```sh
python3 tools/generate_baseline.py
```

This command recalculates the unchanged baseline reports, reads
`reports/planned/segments.json`, `verification.json` and `search.json`, and
prepares `reports/replay.json` before embedding everything in the HTML. It does
**not** run the planner, change rules or write any saved planning output.
Python 3.9+ and the standard library are sufficient. The HTML requires no
server, network, CDN or adjacent assets; `tools/comparison.js` is embedded at
generation time, rather than loaded externally by the browser.

Options include `--planned-dir` (default project `reports/planned`), alongside
the existing `--scenario`, `--rules`, `--reports-dir`, `--output` arguments.
Default paths work independently of cwd. Use `--baseline-only` to omit the
saved comparison for another scenario or a baseline-only export. A missing,
stale or inconsistent saved plan fails comparison generation; it is never
silently presented as verified under different data or rules.

## Views and controls

- **Baseline** shows original source motion and preserves all 20 combinations
  of profiles, nominal/bounded-stress modes and radius variants. A saved
  nominal comparison card explicitly compares **12 baseline events with zero
  verified final events**, independently of alternative baseline settings.
- **Final plan** shows the saved aircraft's vertical segments, unchanged XY
  motion and Python-precomputed final intervals. Only this view has the final
  independently verified safety badge: zero nominal violations and unresolved
  checks over [0,1200]. Profile/mode/radius selectors are locked to
  `metric / nominal / base`. Their previous baseline values return on switching
  back to Baseline. No planned bounded-stress or alternative-radius result is
  implied.
- **Search replay** shows accepted steps 0–21, with step 0 the original fleet.
  Selecting a step pauses playback, retains simulation time, selects and
  highlights its changed aircraft, and replaces the fleet and precomputed
  event intervals. Every replay view, including step 21, is labeled
  **search candidate, potentially unsafe**. The final safety badge is reserved
  for Final plan even though step 21's controls match it exactly.

Simulation time remains a separate variable from search iteration. Playback,
reset, seeking, aircraft selection, zoom, trails and physical sphere sections
work in all views. The drone's source motion and target center remain unchanged.
Event navigation jumps to a Python-provided violating witness, not an invented
closest-approach time. Current-event highlighting uses the selected fleet's
precomputed intervals. Replay interval roots are approximations of certified
rational brackets; details preserve the exact brackets. JavaScript does not
implement conflict detection or infer safety from pixels or plotted samples.

The selected-aircraft charts overlay baseline and planned **altitude** and
**vertical speed**, with phase shading and a synchronized time cursor and
motion marker. In Baseline view the overlay is the final nominal plan; in
replay it is the selected intermediate schedule. Baseline settings outside the
saved nominal scope suppress these overlays and explain how to return to the
supported comparison. Clicking a chart or using its arrow/Home/End keys seeks
simulation time without changing search iteration. Maximum altitude deviation,
terminal altitude offset and remaining spatial destination distance are
Python-computed quantities. Altitude is in km, vertical speed in m/s; phase
bounds are in seconds. No arrival-delay estimate is displayed.

The search graph and numbered controls show remaining zone and pair event
counts per accepted iteration. The detail card shows the actual changed ID,
signed offset, start/transition/return completion times, removed incident
zone/pair counts, introduced pair counts and remaining counts. Removed counts
mean the old incident intervals replaced by a schedule, not a claim that every
replacement interval has different participants. At step 20 F004 replaces the
F004/F031 blocking event with F004/F034: one pair event remains. Step 21 changes
F034 and removes it. The short strategy explanation covers altitude/timing
search, zone priority, temporary pair conflicts and this equal-count move.

All 15 changed aircraft appear in a scrollable table. “Max deviation in final
motion” includes excursions that return to the original altitude; “Accepted
search max” includes earlier recorded accepted versions. Neither column claims
to cover the 7938 rejected candidates, whose complete controls were not logged.
Five highlighted rows have terminal offsets: F013 +900 m, F018 +5700 m,
F023 +900 m, F030 +300 m, F034 +6300 m. Their remaining destination distances
are the absolute offsets because horizontal endpoints are identical.

## Python reconstruction and data contract

`airspace.replay.prepare_replay(scenario, flights, rules, planned_dir)` prepares
an additive `DATA.planning` payload with schema version `1.0`. The baseline
analysis/report schema stays `1.1`.

1. Validate the saved final envelope, source fingerprints and its segment-file
   hash. Independently recompute final verification and compare every core
   field with saved `verification.json`.
2. Start with all 40 original level trajectories. For each accepted repair,
   invoke the existing unchanged `_schedule` helper with its recorded offset,
   initial time and return time. No candidate search or guessed decision is run.
3. Replace that aircraft's schedule only. Continuously verify each full fleet,
   using the checker cache for unchanged obligations. Check the recorded
   removed/introduced counts and plateau flags against the actual findings.
   An unresolved intermediate result prevents replay export.
4. Require the last reconstructed authoritative controls to equal all sorted
   trajectories in `segments.json`, and its verification to equal the
   independently recomputed saved-plan result.
5. Derive phase coefficients, exact maximum deviations and terminal distances
   in Python. Profile samples use a 5 s plotting grid plus joins and interior
   extrema. Samples are not a safety proof. Playback evaluates the prepared
   local segment equations at arbitrary time, rather than interpolating sampled
   CSV rows.

Payload fields:

```text
schema_version, configuration, source_sha256, saved_sha256,
flight_ids, versions, steps, changed_aircraft,
final_matches_saved, final_verification, history_scope, event_time_semantics
```

`versions` contains 61 reused trajectory versions (40 originals plus 21
repairs). Each has `flight_id`, local `segments` with start/end, starting z/vz,
az, phase kind and label; a diagnostic `profile` with `time_s/alt_m/vz_mps`
arrays; exact-computation-derived maximum/terminal/destination values.

Each step contains `index`, recorded `repair` or null, derived `timing` or
null, a 40-element `fleet_versions` index vector aligned with `flight_ids`,
zone/pair/total/unresolved counts and a UI `run`. The run adapts Python checker
intervals to the existing event list/timeline fields without fabricating
unavailable distance minima. Certified bracket fields and exact witnesses are
retained. Replay state counts do not change with simulation time. The current
remaining `(zone,pair)` counts are:

```text
0:(9,3)  1:(9,2)  2:(8,2)  3:(7,3)  4:(6,4)  5:(6,3)
6:(5,4)  7:(5,3)  8:(4,4)  9:(4,3) 10:(4,2) 11:(3,5)
12:(3,4) 13:(3,3) 14:(2,2) 15:(1,2) 16:(0,4) 17:(0,3)
18:(0,2) 19:(0,1) 20:(0,1) 21:(0,0)
```

The payload and HTML are deterministic, without timestamps. Provenance stores
canonical source/configuration and the three saved-file SHA-256 hashes.
`changed_aircraft` summarizes final excursions, accepted-history maxima,
terminal offsets/distances and the corresponding repair steps. No unrecorded
rejected candidate, search ranking, optimization result or delay is invented.

## Validation

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_comparison_ui.cjs
```

Browser tests need Playwright installed under the chosen module path and local
Chrome; `CHROME_PATH` overrides its executable. The new suite accepts `HTML_PATH`
and optional `SCREENSHOT_DIR` for desktop/mobile captures. See
[validation.md](validation.md) for the checks actually performed. Nominal model
verification remains subject to the existing [planning contract](nominal-planning.md);
this visualization adds no safety guarantee for other modes or beyond T.
