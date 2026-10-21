# Second-pass nominal quality contract, version 2.0

The reference under `reports/planned/` and every first-pass artifact under
`reports/improved/` are preserved byte for byte. New authoritative segments,
quality, verification, endpoint bounds, search counters and summaries live in
`reports/improved_second/`. Source inputs, nominal rules, original horizontal
velocities and the closed [0,1200] s horizon are unchanged. There is no airport,
landing, horizontal-maneuver or uncertainty-expansion model here.

## Reproduce

```sh
python3 tools/improve_second.py
python3 tools/generate_baseline.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_comparison_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_quality_ui.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_second_ui.cjs
```

CLI defaults resolve from the repository independently of cwd. Search options:
`--search-config`, `--output-dir`, `--reference-dir`, `--first-dir`. The default
experiment is `experiments/quality_second.json`. Output must be separate from
earlier solution directories. Existing alternatives need no planning rerun to
regenerate the offline `baseline.html`. Generator `--first-pass-only` omits
second-pass data, `--reference-only` omits both quality experiments, and
`--baseline-only` preserves the original baseline-only presentation.

## Necessary endpoint bounds, independently derived

`airspace/endpoint_bounds.py` evaluates every original aircraft endpoint directly
from the source affine equations and checks all 780 unordered pairs using exact
rational predicates. It does not use the planner, repair history, sampled CSV or
continuous conflict detector. A separate Decimal enumeration in tests confirms
exactly these two conflicting terminal pairs:

| Pair | Horizontal distance squared m², exact | Original vertical difference m |
| --- | --- | ---: |
| F018 / F034 | 549511954/25 | 0 |
| F030 / F039 | 1172328173/50 | 0 |

Both squared distances are strictly below 9260². Fixed horizontal velocities
make those endpoint horizontal distances immutable. Write delta_i for an
aircraft's signed terminal altitude change. Because both baseline vertical
differences are zero, safety at T requires `abs(delta_i-delta_j) >= 300` for each
pair. Triangle inequality gives `abs(delta_i)+abs(delta_j) >= 300` and
`max(abs(delta_i),abs(delta_j)) >= 150`. The pairs share no aircraft, so adding
both pair inequalities gives **Dtotal >= 600 m**, while either gives
**Dmax >= 150 m**. Equality is permitted by the unchanged separation rule.

These bounds are necessary for any trajectory under the current fixed-XY model,
regardless of the searched family. They do not establish attainability through
the earlier horizon. Full continuous verification is required for that claim.
The total bound was attained in the first pass; the second pass explicitly
tries both ±150 m orientations for each pair and both pairs together.

The reusable bound function derives thresholds, deficits and disjoint pairs
from the supplied inputs. For nonzero baseline vertical differences the deficit
is `max(0,V-abs(original_dz))`. Overlapping pairs are not double-counted: only a
deterministic disjoint matching contributes to the total bound. This need not be
the strongest bound for another scenario. Exact rational strings accompany
numeric display values. The constants 150 and 600 are computed scenario results,
not universal settings. Bound gaps use the selected plan's endpoint metrics;
zero gap alone is meaningful only for an independently verified feasible plan.

## Seven-objective semantics

`airspace.quality.OBJECTIVES` now minimizes, in order:

1. Maximum original-endpoint deviation Dmax.
2. Total original-endpoint deviation Dtotal.
3. Maximum altitude excursion from baseline E.
4. Accumulated altitude deviation A.
5. Total vertical travel L.
6. Changed-aircraft count N.
7. Vertical-direction reversals R.

The exact segment integrals, relevant root splitting, certified irrational-root
bounds and segmentation-independent reversals retain the
[first-pass definitions](quality-improvement.md). Maximum excursion now enters
`dominates` rather than remaining diagnostic. Dominance is weak-all and
strict-one across **all seven**, using exact metric bounds, with no epsilon.
A trade-off with lower excursion and higher accumulated deviation does not
establish dominance. Maximum excursion is measured against original altitude at
the same time, not ground elevation. Endpoint deviation is not airport arrival.

For historical reproduction, `LEGACY_OBJECTIVES` and an explicit objectives
argument preserve the old first-pass six-objective planner/archive behavior.
The earlier segment files, metric values, original archive flags and frozen
experimental score configuration are unchanged. The experimental J uses its
original four terms, weights and denominators even though the new objective
order includes excursion. It never ranks candidates or filters either archive.

## Search family, diversity and bounded work

The search starts from the reference and three selected first-pass alternatives:
endpoint-focused `alt-5c0a7daf73c4`, reference-dominating
`alt-c0db93e2592c`, and fewer-aircraft/reversals `alt-3b0cd621b8fc`.
Seven rotated lexicographic priorities run round-robin over these starts, with
12 candidate attempts per turn and at most five improving moves per job. An
admitted trade-off may worsen other objectives; no endpoint-focused metric
ceiling is imposed on the other starts.

Neighborhoods explicitly balance the disjoint terminal pairs at ±V/2; retain a
level prefix then transition continuously; replace large climbs of F004, F018,
F031 and F034 using discrete peak/start/return choices; and repair one or two
blocking neighboring aircraft together. Collective changes to all four large
climbs, restoration of original aircraft and broader offset/time perturbations
retain other trade-offs. Aircraft are interleaved; nearby smaller peak changes
are tried before large failing reductions. The config records every grid.
Schedules comprise level-to-level constant-acceleration ramps and optional
constant-rate legs/holds. Their return can end at a specified nonzero offset.
Position and velocity stay continuous, original XY motion stays unchanged,
limits apply throughout, and terminal vertical speed must equal zero exactly.
Initially nonlevel sources are explicitly unsupported by this search family.

The default caps are **3000 candidate evaluations**, **200 independent complete
verifications**, **32 archive members**, and a **900 s cooperative search guard**.
Seed checks and a reserved final export tail are included in the full-check
budget. The time guard is checked between bounded operations, not as a hard
real-time interrupt, and seed/export checks add wall time. Candidate generation
is finite; coordinated blockers may require several continuous checks before
yielding a candidate. A wall-clock stop can alter the explored prefix across
machines. Candidate/order/serialization are deterministic otherwise; a small
candidate-limited reproduction test compares complete exports byte for byte.

Unchanged unary/pair checks are reused. Exact witness evaluations can reject a
candidate but never certify safety. Before admission or use as a new seed, every
candidate receives fresh complete continuous verification of 40 aircraft, all
780 pairs, both spheres, altitude, motion limits and joins. A violation or
unresolved obligation rejects it. Serialized export is reread and verified again.
The polynomial checker is unchanged, including quartic sphere expressions.

The archive filters with seven-objective dominance against the complete
certified metric history, including capacity-pruned records. Capacity pruning
prioritizes objective minima, then normalized crowding, with deterministic ID
ties; all removed IDs are recorded. A small capacity can discard even extrema.
Search caps, per-job stops and the overall stopping reason are exported.
Identical control hashes are skipped. Identical certified metric-enclosure
vectors can also suppress a non-improving candidate as a search-diversity
heuristic; equality of uncertain enclosures is not claimed to prove exact
algebraic equality or dominance. This affects which candidates are explored,
not safety certification or the proved endpoint bounds.
Earlier plans remain visible regardless of subsequent dominance. No failure
proves infeasibility and no unattained metric is claimed globally optimal.

## Artifacts and offline UI

Schema 2.0 `catalog.json` records source/reference/first-catalog checksums,
objective names, unchanged experimental score config, segment file checksums,
continuous metrics, reference deltas, endpoint gaps, parent aircraft-count delta,
verification and search provenance. Each `alternatives/pass2-*/` directory has
`segments.json`, `quality.json` and `verification.json`. `endpoint_bounds.json`
contains the independent proof inputs; `verified_comparisons.json` retains all
certified metrics/origins; `search.json` has limits/counters/pruning/jobs;
`summary.md` compares all saved generations and lists earlier dominated IDs.

The generator rereads and independently verifies every displayed solution,
recomputes continuous quality/gaps/J, checks file/source provenance and retained
second-pass nondominance, and recalculates dominance across all displayed
reference/first-pass/second-pass points. Earlier archive membership is preserved
separately from current comparison membership. Search counters/archive size refer
to the second-pass experiment; the combined comparison additionally retains the
three nondominated first-pass trade-offs. Additive `DATA.quality_alternatives`
becomes version 2.0, exported as `reports/quality_ui.json`; baseline and reference
search replay contracts remain unchanged.

The solution selector labels all three generations. All seven raw metrics,
reference differences, endpoint bounds/gaps, changed-aircraft counts and targeted
excursions are shown. Profiles retain baseline/reference/selected overlays.
Time, playback and aircraft selection survive solution changes. All seven
objectives are available as scatter axes; coincident points remain coincident,
with the selector/table/keyboard providing unambiguous access. On mobile, wide
tables scroll horizontally. Planned views remain metric/nominal/base; baseline
profile/stress controls and original search replay remain available. JavaScript
only evaluates saved motion and renders Python-prepared metrics/events.

## Actual second-pass result

The saved experiment reached the **3000-candidate cap**, before the 900 s guard,
with **82 full independent verifications**, **72 certified schedules including
four seeds**, **10 retained second-pass alternatives**, and **zero capacity
pruning operations**. The cap interrupted unfinished jobs; other jobs stopped at
their five-move cap or exhausted their finite neighborhood. All saved plans have
zero nominal violations, zero unresolved checks and zero terminal vertical speed.

| Plan | Dmax m | Dtotal m | Excursion m | A m·s | Travel m | Changed | Reversals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| First-pass endpoint plan | 300 | 600 | 6300 | 13745400 | 61200 | 15 | 14 |
| pass2-b8f763f4b8b0 | 150 | 600 | 6150 | 13448700 | 60600 | 15 | 13 |
| pass2-46de10ecbe7a | 300 | 600 | 6150 | 13443300 | 60300 | 14 | 13 |

The first second-pass row attains both necessary endpoint bounds through fresh
complete verification: **Dmax=150 m and Dtotal=600 m are optimal under this
scenario's fixed-horizontal model**. Relative to the first-pass endpoint plan,
excursion decreases 150 m (2.38%), accumulated deviation 296700 m·s (2.16%),
and travel 600 m (0.98%), with one fewer reversal and the same aircraft count.
It changes F039 and restores F020, rather than requiring a net additional
changed aircraft. This does not prove the smallest possible changed-aircraft
count. F004/F018/F031 still have 5700 m excursions in this witness; F034 decreases
from 6300 to 6150 m. Their timings and neighboring schedules were also searched.

The other row has the lowest saved accumulated deviation, 13443300 m·s, a
302100 m·s reduction (2.20%) from the first-pass set minimum, and reduces travel
by 900 m relative to that first-pass endpoint plan. Its maximum endpoint gap is
150 m; total gap is zero. The lowest vertical travel across the complete saved
sets is **46200 m in both passes**, so the experiment did not improve that set
minimum. Individual alternatives expose different combinations of these metrics.

Under seven-objective dominance, saved second-pass points dominate the reference
and these five first-pass alternatives:

- `alt-5c0a7daf73c4`
- `alt-5572c56163d0`
- `alt-72f75f97885d`
- `alt-c0db93e2592c`
- `alt-3b0cd621b8fc`

`alt-9c31f3faad7d`, `alt-82fd0cda3e29` and `alt-efc2a9f64481` remain nondominated
by the saved second-pass set. The generated summary lists exact dominating IDs.
Earlier files and their original membership flags remain unchanged.

Except for the two attained endpoint bounds, these are observed improvements,
not global optima. The search did not exhaust all timing/peak combinations,
multiple-turn coordinated repairs or arbitrary continuous-acceleration histories.
Its piecewise level-to-level family, configured grids, five moves per job and
3000-candidate cap constrain the conclusions. In particular no minimum excursion,
travel, changed-aircraft count or reversal count is proved.
