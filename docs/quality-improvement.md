# First-pass nominal vertical quality alternatives

This describes the preserved first-pass six-objective experiment. The current
second-pass search and UI use seven objectives, including maximum excursion;
see [second-pass-quality.md](second-pass-quality.md). The first-pass CLI explicitly
retains its original six objectives for reproduction.

The saved solution in `reports/planned/` is an immutable reference. This milestone
adds a separate improvement search and comparison artifacts in `reports/improved/`.
Source inputs, nominal safety rules, fixed horizontal velocities and the 1200 s
horizon are unchanged. Airports, landing, arrival delay, horizontal maneuvers and
bounded-stress planning are outside this contract.

## Reproduction

```sh
python3 tools/improve_nominal.py
python3 tools/generate_baseline.py
```

Defaults resolve relative to the project, independently of the working directory.
The first command reads the saved reference, accepted repair history and separate
`experiments/quality_search.json` and `experiments/quality_score.json` configurations.
It searches, independently verifies and exports alternatives. The second verifies
the saved alternatives again and embeds them in standalone `baseline.html`;
no search rerun is needed to regenerate HTML. `--reference-only` omits quality
alternatives while preserving reference/replay; `--baseline-only` retains the
original baseline-only viewer. The improvement CLI supports `--output-dir` and
`--search-config`; use `--help` for other paths.

## Continuous metrics and API

`QualityEvaluator(scenario, flights, rules).evaluate(definitions)` in
`airspace/quality.py` accepts all 40 authoritative trajectory definitions exactly
once. It compiles the segment equations independently of sampled CSV. Define
`d_i(t)=z_i(t)-z_i_baseline(t)` with the original linear baseline. Metrics are:

| Metric | Definition | Unit |
| --- | --- | --- |
| Maximum endpoint deviation | `max_i abs(d_i(T))` | m |
| Total endpoint deviation | `sum_i abs(d_i(T))` | m |
| Accumulated altitude deviation | `sum_i integral abs(d_i(t)) dt` | m·s |
| Vertical travel | `sum_i integral abs(vz_i(t)) dt` | m |
| Changed aircraft | Number with a nonzero deviation polynomial on any segment | count |
| Vertical-direction reversals | Changes between successive nonzero signs of vertical velocity | count |
| Maximum altitude excursion | `max_i,t abs(d_i(t))` (diagnostic, outside dominance) | m |

Endpoint deviations are distances from each original endpoint at T, not airport
arrival distances. Horizontal endpoints are unchanged, so their 3D distance is
the absolute altitude difference. Excursion measures departure from the original
altitude at the same time, rather than absolute altitude above ground.

For reversals, a climb followed by a level hold and descent counts once. Level
segments contribute no sign, repeated identical signs merge across all joins,
and an isolated zero velocity does not itself create a reversal. Splitting
identical motion into more segments cannot change the count. An entirely level
aircraft has zero reversals, even if its segment representation is redundant.

Deviation is quadratic and vertical speed is linear on each constant-acceleration
segment. Integrals split at all relevant roots and use rational antiderivatives;
excursion checks endpoints and derivative roots. Rational crossings are exact.
Irrational quadratic roots use certified rational Sturm enclosures (64-bit target,
200 subdivision-depth cap). The integral excludes root brackets from its lower
bound and bounds their contribution above using Bernstein bounds times bracket
width. Failure to isolate propagates an error, rather than a sampled answer.
Every aggregate has `bounds` containing exact rational lower/upper strings;
numeric fields are midpoint display values. All saved fleet metrics in this run
have equal exact bounds. Reusable metric evaluation does not itself certify
conflict safety; the separate continuous checker does that.

`dominates(a,b,LEGACY_OBJECTIVES)` reproduces first-pass six-objective dominance
(the current default uses seven objectives, including excursion): no worse in every objective and
strictly better in at least one. It proves comparisons with rational bounds;
overlapping uncertain enclosures do not establish dominance. No tolerance,
rounded display value or experimental score enters this
decision. Equal objective vectors are deduplicated.

## Bounded search and guarantees

Six deterministic lexicographic strategies rotate the six objective priorities,
starting independently from the saved reference. These are search preferences,
not Pareto dominance. First-improving moves can explore a different trade-off
even if that move worsens another metric. Neighborhood families include:

- Late level-to-level returns with zero or ±one-separation terminal offsets,
  including coordinated returns for aircraft whose original endpoints overlap.
- Offset, start and return-time perturbations of recorded maneuvers, and omitted
  returns, retaining fixed horizontal motion.
- Restoration of original aircraft; when a single pair blocks restoration,
  coordinated reassignment of the other aircraft's maneuver.

The level-transition constructor preserves the existing prefix, position and
velocity at the cut, then uses bounded acceleration ramps and a level hold.
Existing segment validation checks altitude/motion limits and continuity. Every
candidate must have exactly zero terminal vertical speed. This implementation
requires initially level source aircraft, as present in this dataset; unsupported
initial vertical speeds are rejected explicitly.

Cached unchanged single/pair checks and exact violation witnesses accelerate
rejection. Witness times never establish safety. Every admitted candidate or new
search seed gets a fresh complete `ContinuousChecker` verification, covering all
40 aircraft, 780 pairs, sphere/altitude/motion constraints and all segment joins.
Only zero violations and zero unresolved checks qualify. Final serialized files
are reread and independently verified again before export. The existing rational
continuous checker, including quartic sphere expressions, is unchanged.

Defaults bound candidate evaluations to **360**, independent full verifications
to **48** (including reference/export checks), archive size to **8**, moves per
strategy to **6**, and a cooperative wall-clock guard to **300 s**. Each strategy
also has a share of the candidate budget. The guard is checked between bounded
operations; final verification/export takes additional time. A runtime stop can
change the explored prefix; candidate-limited runs and output serialization are
deterministic. Search lists and timing grids are recorded in the configuration.

The archive uses six-objective dominance, retaining a global metric history so
that capacity-pruned points still prevent admission of dominated candidates.
When capacity is exceeded, objective minima are prioritized, followed by
normalized crowding distance, with deterministic ID ties. If the capacity is too
small for all extrema, the deterministic capacity rule can discard some extrema.
Every removed ID is disclosed in `search.json`. This is a bounded subset of the
discovered front, not the complete feasible Pareto front or a global optimum.
The reference remains in the comparison even when dominated.

## Frozen experimental score

`experiments/quality_score.json` separately stores weights 0.60, 0.25, 0.10 and
0.05 and frozen scales 6300 m, 14100 m, 19809900 m·s and 47700 m. It evaluates
`J=.60 Dmax/6300 + .25 Dtotal/14100 + .10 A/19809900 + .05 L/47700`.
The reference must reproduce all four scales exactly before searching or loading
UI data, and therefore J=1. Alternatives never redefine the denominators. J is
an experimental comparison only: neither search ranking nor archive filtering
uses it. In particular it omits changed-aircraft and reversal counts.

## Saved results

The run stopped at the 360-candidate cap, with 29 independent full verifications,
21 verified feasible schedules including the reference, eight saved alternatives
and three capacity-pruning operations. All saved alternatives have zero nominal
violations, zero unresolved checks and zero terminal vertical speed. See
`reports/improved/summary.md` for every retained point.

| Plan | Max endpoint m | Total endpoint m | Accumulated deviation m·s | Vertical travel m | Changed | Reversals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reference | 6300 | 14100 | 19809900 | 47700 | 15 | 10 |
| alt-5c0a7daf73c4 | 300 | 600 | 13745400 | 61200 | 15 | 14 |
| alt-c0db93e2592c | 6300 | 14100 | 19758300 | 47100 | 14 | 9 |
| alt-3b0cd621b8fc | 6300 | 15000 | 20254200 | 46200 | 13 | 7 |

The first alternative reduces maximum/total endpoint deviation by 95.24%/95.74%
and accumulated deviation by 30.61%, while increasing travel by 28.30% and
reversals by four. The middle alternative dominates the reference. The last
reduces travel, changed aircraft and reversals while worsening total endpoint
and accumulated deviations; its experimental J is greater than one, yet it is
retained by the six-objective archive. All three still have a temporary maximum
excursion of 6300 m. These are admissible examples under bounded exploration;
neither global optimality nor absence of better schedules is established.

## Artifact and UI contract

`reports/improved/catalog.json` lists the reference first and eight alternatives,
six objective names, configs, limits, metric bounds, Python-computed deltas,
experimental J, verification and provenance. Each alternative directory contains
authoritative `segments.json`, `verification.json` and `quality.json`.
`verified_comparisons.json` records metrics/origin of all certified search points;
`search.json` records counters, strategy seeds and pruning; `reference_quality.json`
records unchanged reference metrics. No arbitrary timestamp is emitted.

`airspace/alternatives.py` checks schema, file paths/checksums, source/config and
reference provenance, recomputes continuous quality and full verification, and
checks retained nondominance. It creates shared motion/profile versions and
Python verification runs in additive `DATA.quality_alternatives` (schema 1.0),
also exported as `reports/quality_ui.json`. Version references are keyed by saved
trajectory hashes. Baseline and reference search replay remain unchanged.

The offline HTML switches reference/alternatives while preserving time, selected
aircraft and playback. Raw metrics, reference differences, experimental J,
verification, six selectable scatter axes and a solution table expose trade-offs.
Profiles overlay baseline, selected alternative and saved reference. Alternatives
use only metric/nominal/base; baseline stress controls remain available. Search
replay explicitly remains the original reference search, separate from quality
alternatives. JavaScript only evaluates saved motion and plots Python results;
it neither integrates authoritative metrics nor detects conflicts.
