# Submission guide and reasoning

The original assignment is [Task1_details.pdf](../Task1_details.pdf). It asks for
safe movement of all aircraft over **20 minutes**, explicit choices of safety
rules and dynamics, progress toward original destinations, trajectory data,
shared configuration, convincing validation and a README of one page or less.
It permits 2D or 3D protected zones and leaves the maneuver family to us. Its
optional “276 km in 15 minutes” calculation is a typo: 230 m/s × 1200 s is 20 minutes.

## What to open and submit

**For email, use [DTL_email.zip](../DTL_email.zip).** Its six files sit directly
at the archive root: `START_HERE.html`, `README.md`, `trajectories.csv`,
`rules.json`, `segments.json`, and `verification.json`. The new presentation
opens on the selected safe plan with a top-view animation, synchronized altitude
profile, original/result comparison and three guided moments. Full source and
experiment history belong in [GitHub](https://github.com/Timur713/DTL), rather
than the email attachment. Rebuild the compact package with:

```sh
python3 tools/build_email.py --github-url https://github.com/Timur713/DTL
```

The rest of this guide documents the full research project and its larger,
optional archive. The compact email export preserves the selected motion,
trajectory CSV and rules byte for byte; its `verification.json` combines the
same certificate with proof/sensitivity witnesses, source snapshots and hashes.

Open [baseline.html](../baseline.html) and click **Show recommended plan**. The
baseline is initially visible so the original problem remains inspectable. The
three numbered buttons guide a reviewer through an original conflict, the
endpoint proof and the reason for the large climb. Alternative profiles and error
modes apply to baseline predictions; saved maneuver certificates are nominal only.

The recommended plan is `pass2-b8f763f4b8b0`, chosen from saved second-pass plans
that attain both endpoint lower bounds. Ties prefer smaller maximum excursion,
then accumulated altitude deviation, vertical travel, changed aircraft and
reversals. This transparent policy is in [experiments/submission.json](../experiments/submission.json).
It uses no fitted scalar score. It chooses the best saved plan under that policy,
not an optimum for all seven quality metrics.

| Assignment requirement | Delivered artifact |
| --- | --- |
| Analyze the snapshot, threat and target | [Model](model.md), [original conflicts](../reports/summary.md) |
| Keep all aircraft moving for 1200 s | [Authoritative segment controls](../submission/segments.json) |
| Trajectory file for every aircraft | [CSV](../submission/trajectories.csv): 48,040 rows; all 40 IDs at every output time |
| Shared safety and motion configuration | [rules.json](../rules.json), byte-identical [delivery copy](../submission/rules.json) |
| Evidence of safety under chosen rules | [Independent verification](../submission/verification.json), [tests](../tests/) |
| Quality and trade-offs | [Continuous metrics](../submission/quality.json), seven-objective viewer |
| Plot/animation | [Offline interactive HTML](../baseline.html) with profiles, event replay and Pareto scatter |
| Short README and reproducibility | [Root README](../README.md), commands below |
| Explain ambiguity and known limits | This guide, [model](model.md), [target decision](target-zone-decision.md) |

The optional full-project ZIP contains the complete runnable project, including inputs, source code,
tests, previous experiments, selected delivery and offline viewer. It excludes
Git internals, caches, local packages and settings. `submission/manifest.json`
records delivery-file hashes. Original inputs, original nominal rules and earlier
reference/first-pass/second-pass solution files remain unchanged.
This larger archive is generated on demand and is not tracked in Git; the compact
email ZIP is tracked. See the [repository map](README.md) for code and report navigation.

A short [five-minute walkthrough and likely questions](defense.md) accompanies
the reviewer tour. It distinguishes scenario assumptions, computed results,
proved bounds and unimplemented extensions.

## Why these choices

We use 3D spheres for the drone and target because the task explicitly allows 3D
geometry. The target's ground altitude is assumed zero. A point aircraft has a
protected separation volume; it is not a physical fuselage model. A 5 km radius
is a scenario assumption. A 9260 m / 300 m separation reference is justified and
qualified in [model.md](model.md); it is not asserted to apply universally in ATC.

The maneuver family retains horizontal speed and heading. That preserves forward
progress along every original route and allows simple, continuous acceleration
segments to be verified rigorously. Position and velocity are continuous; vertical
acceleration is bounded and can change at segment joins. No jerk/thrust model is
claimed. Horizontal acceleration, bank and turn rate are zero for these schedules.
Aircraft are retained outside the displayed XY box, which is not treated as a
safety boundary. No airport destinations are invented.

Exact return to every original endpoint at 1200 s is incompatible with separation:
two endpoint pairs would still be horizontally and vertically too close. The task
requires progress toward destinations, so we permit and report the smallest
attained terminal deviations rather than removing aircraft or changing the rules.

The baseline detector and the serialized-maneuver checker are separate from the
planner. Safety is assessed continuously. Affine XY and quadratic Z give quartic
squared sphere distances; exact rational coefficients and Sturm root isolation
partition sign-invariant time intervals. All pairs, zones, limits and joins are
checked. Numerical exhaustion is `unresolved` and prevents acceptance. CSV and
animation samples are diagnostics, never the proof of absence of conflicts.

We first search for feasibility, then compare multiple verified alternatives using
seven raw quality objectives. A solution dominates another only if it is no worse
in every objective and strictly better in at least one. The historical weighted
score remains an experiment, not a planner objective or archive filter.

## Three findings worth defending

**1. The two endpoint metrics are provably optimal in the fixed-XY model.** At
1200 s, F018/F034 and F030/F039 have horizontal distances approximately 4688 m and
4842 m and identical baseline altitudes within each pair. Each needs at least
300 m relative altitude displacement. The triangle inequality gives at least
300 m total displacement per pair and 150 m maximum individual displacement.
The pairs are disjoint, so fleet total is at least 600 m. The recommended plan
attains 150 m maximum and 600 m total through opposing ±150 m offsets. These are
scenario-derived bounds, not values hardcoded into the planner's safety rules.
[Independent proof inputs](../submission/endpoint_bounds.json) are exported.

**2. Large climbs expose a structural cost of vertical-only avoidance.** For
horizontal distance `dh < R`, the upper boundary of a sphere is
`z_center + sqrt(R²-dh²)`. If its lower boundary is below the altitude floor, the
aircraft must pass above it. At horizontal closest approach at approximately
442.4066 s, F031 must reach at least 8679.4505295 m from its initial 3000 m:
maximum excursion is therefore at least 5679.4505295 m in any safe fixed-XY plan.
The recommended fleet maximum is 6150 m, about 8.3% above this necessary bound.
This gap is not a certificate of closeness for other quality metrics, nor proof
that equality is dynamically attainable. Each exact rational witness and certified
square-root enclosure is in [excursion_bounds.json](../submission/excursion_bounds.json).

**3. Optimal nominal endpoints leave no positive uniform altitude-error margin.**
The binding terminal pairs have exactly 300 m separation. Opposing altitude errors
of 1 m can reduce that to 298 m. This is an exact endpoint counterexample, not a
probability calculation or full trajectory-error model. A separate full continuous
recheck of unchanged controls using the already configured 304.8 m vertical
reference finds 16 pair events and zero unresolved checks. Both experiments leave
the primary 300 m rules unchanged. See [error witness](../submission/endpoint_error_probe.json)
and [alternative-threshold verification](../submission/vertical_reference_sensitivity.json).
This exposes a real trade-off: additional robustness requires accepting additional
deviation, different trajectories or different operational assumptions.

The strongest next research extension would compare horizontal reroutes with these
proved vertical costs, and optimize clearance/recovery under an explicitly justified
uncertainty model. Another longer search over the same timing grid cannot address
all limitations of the maneuver family.

## Relation to external research

Sources checked on October 21, 2026. The implementation is our own; no external
algorithm's safety guarantee is inherited.

- [Dias and Rey, 2022](https://arxiv.org/abs/2203.11990) study conflict avoidance
  together with trajectory recovery. This supports evaluating recovery costs
  rather than stopping after a feasible avoidance maneuver. Their speed/heading
  model differs from our vertical-only family.
- [Irvine and Barret / EUROCONTROL, 2023](https://www.eurocontrol.int/publication/adapting-air-traffic-conflict-resolution-algorithm-meet-real-world-requirements)
  explicitly discuss returning to flight-plan routes, fuel/CO₂ or workload ranking,
  and trajectory uncertainty. Our deviation/travel/reversal measures are transparent
  proxies, not fuel consumption or measured controller workload.
- [NASA DAIDALUS reference manual](https://nasa.github.io/daidalus/) separates
  detection, maneuver guidance, kinematic limits and sensor uncertainty. We retain
  that architectural distinction without adopting its thresholds or claiming
  MOPS/TCAS compliance.

## Reproduce

Python 3.9+ with the standard library. Paths resolve from the project, including
when scripts are invoked by absolute path from another working directory.

```sh
# Reverify/export the selected saved plan, rebuild HTML and make the delivery ZIP.
python3 tools/build_submission.py --html --package

# Full Python suite.
python3 -m unittest discover -s tests -p 'test_*.py' -v

# Optional: reproduce the historical searches, in dependency order.
python3 tools/plan_nominal.py
python3 tools/improve_nominal.py
python3 tools/improve_second.py
python3 tools/build_submission.py --html --package
```

The saved searches use deterministic candidate/verification budgets. A cooperative
runtime cap can change the explored prefix on slower machines. Saved-plan export,
verification and packaging do not rerun search and are deterministic. Diagnostic
CSV rows include the uniform grid, both horizon endpoints and every segment join;
`time_exact_s` preserves the exact rational timestamp.

Browser testing requires local Chrome and Playwright; these are not runtime
dependencies of the viewer. `CHROME_PATH` overrides the Chrome executable.

```sh
npm install --prefix /tmp/dtl-baseline-check --no-save playwright
export PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright
node tests/check_baseline.cjs
node tests/check_analysis_ui.cjs
node tests/check_comparison_ui.cjs
node tests/check_quality_ui.cjs
node tests/check_second_ui.cjs
node tests/check_submission_ui.cjs
node tests/check_email_ui.cjs
```

## Limits

The guarantee is conditional on exact initial states and execution, chosen
separation geometry, flat local coordinates and generic kinematic limits. Aircraft
types/mass, wind, communication/execution delays, wake turbulence, weather, terrain,
pressure altitude and flight-envelope coupling are unknown. No landing, real-world
certification, fuel optimum, safety after 1200 s or bounded-stress maneuver safety
is claimed. Baseline stress results cannot simply be transferred to maneuvering
trajectories. Only the two attained endpoint bounds establish optimality; other
metrics remain bounded-search results. Complete validation is in [validation.md](validation.md).
