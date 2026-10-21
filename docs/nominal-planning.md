# Nominal planning and verification contract, version 1.0

This separate pipeline plans all source aircraft using the existing
[vertical model](vertical-model.md). Its scope is **metric / nominal / base**
over the complete closed horizon from `rules.duration_s`. It preserves the
source horizontal position/velocity, all aircraft, source files, `rules.json`,
baseline reports and baseline HTML. It does not integrate a new model into HTML.
The baseline's `maneuvers_implemented=false` flag describes the baseline
pipeline; its thresholds, geometry and numerical assumptions are unchanged.

## Reproduction and APIs

Python 3.9+, standard library, from the project root:

```sh
python3 tools/plan_nominal.py
```

The script's default paths resolve relative to the project root independently
of cwd. Options: `--scenario`, `--rules`, `--output-dir` (default
`reports/planned`), `--max-candidates` (20000), `--max-repairs` (40),
`--sample-step-s` (positive integer, default 1). Exit 0 means verified safe;
exit 1 means bounded search incomplete, with outputs and remaining findings;
exit 2 means invalid input or an I/O failure. No search failure proves the
absence of a solution among all possible maneuvers. Sample spacing changes only
the diagnostic CSV, not the plan or continuous verification.

```python
from airspace.planner import plan_fleet
from airspace.checker import ContinuousChecker

result = plan_fleet(scenario, flights, rules)
# Always revalidate a saved list of authoritative trajectory definitions:
verification = ContinuousChecker(scenario, flights, rules).verify(
    result["trajectories"])
assert verification["verified_safe"]  # only when both finding counts are zero
```

`ContinuousChecker.compile` independently derives immutable polynomial pieces
from one serialized vertical trajectory. `check_single` checks its altitude,
motion and zones; `check_pair` checks one complete-horizon aircraft pair.
`verify_document` validates the complete saved envelope and its input fingerprint.
`verify` validates that the fleet contains every source ID exactly once, then
checks all aircraft and every unordered pair. Unknown IDs, duplicate/missing
IDs, wrong versions/units/modes, altered source states/provenance, incomplete
coverage, unsupported keys, bool numerics and nonfinite numbers are rejected.
Malformed inputs raise `ValueError`; they cannot produce a safety certificate.

## Independent continuous checker

The checker imports neither `VerticalTrajectory` nor baseline conflict
calculation functions. It reuses only the baseline's input/configuration
validation. It independently integrates serialized constant-acceleration
segments into **absolute-time rational polynomials**. Positions/velocities at
joins follow from integration, rather than independently rounded join states.
It does not trust trajectory-constructor validity, planner acceptance, search
caches or sampled CSV. Raw, well-formed but dynamically invalid controls yield
motion/altitude violations, rather than being assumed admissible.

At every segment boundary of either participant, a pair's interval is split.
For each piece, horizontal relative motion is affine and vertical relative
motion is quadratic. Aircraft separation is the strict conjunction:

```text
rx² + ry² - H² < 0
rz - V < 0
-rz - V < 0
```

Here H/V come from `rules.profiles[metric]`. Sphere entry is the strict
polynomial inequality `rx²+ry²+rz²-R²<0`. Squaring the quadratic vertical term
produces a polynomial of degree up to **four**. The target uses the configured
center altitude and fixed XY; the drone uses its unchanged source motion,
including after passing target XY. A sphere does not become an infinite
vertical cylinder. Nothing is clipped at the visual XY frame.

Altitude violations are `z-alt_min<0` or `alt_max-z<0`. Vertical speed is the
polynomial derivative; both signed speed and acceleration bounds are checked.
Horizontal speed is checked using its squared magnitude against squared
nonnegative configured bounds. Horizontal acceleration, bank and turn rate
are identically zero under the fixed-XY-velocity model, and their nonnegative
configured bounds are validated. Speed limits refer to horizontal magnitude,
not total 3D speed. Altitude and motion boundary equality is allowed.
Acceleration can jump: its following control applies at a join, with the final
control including T. Position/velocity remain continuous. There is no jerk,
thrust, aerodynamic or joint flight-envelope model beyond these assumptions.

### Numerical guarantees and limits

`airspace/polynomial.py` interprets each int/float input through its canonical
decimal representation and uses `Fraction` for polynomial coefficients,
integration, sign comparisons and root counts. No physical threshold is
expanded, shrunk or replaced by a floating tolerance.

1. Exact Bernstein coefficient bounds can prove a polynomial nonnegative
   throughout an interval, making the strict conjunction impossible. A
   polynomial proved strictly negative throughout needs no root partition.
2. Multiply the remaining constraint polynomials and remove repeated factors
   using exact polynomial GCD. For pair checks this product has degree at most
   six; a sphere expression has degree at most four.
3. A Sturm sequence counts all distinct roots. Rational bisection isolates
   every interior root in disjoint rational brackets, including repeated roots
   of the original product. Exact rational roots found during bisection are
   represented as points. Interval endpoint roots are handled separately.
4. Between successive roots, the sign of every constraint is invariant. An
   exact rational test point in each such cell therefore proves its sign over
   that whole cell. This is a sign-decomposition proof, **not time sampling**.
   At a product root at least one strict inequality is equality, so that instant
   is safe for this conjunction. Exact endpoint predicates determine closure.
5. Join-adjacent events merge only if they belong to the same rule/participants
   and their shared join is included in at least one piece. Two violations
   separated by a safe tangent instant remain two events.

Default isolation budgets are 36 bracket bits (absolute width <=2^-36 s),
maximum bisection depth 160 and 10000 nodes per polynomial problem. Close
roots are separated even when closer than the bracket width target; no small
interval is discarded. Exhaustion yields explicit `unresolved` for that
obligation and interval. Any unresolved result prevents `verified_safe`.
The root-width target controls reporting accuracy only, not safety thresholds.

Event `start_s/end_s` and witness times are float display values. Their
`start_bracket/end_bracket` contain `lower_exact/upper_exact` rational strings
(the authoritative certified brackets) plus approximate floats. Events have
strict/inclusive endpoint flags and an exact rational violating witness
`witness_exact`. Endpoint display values must not be treated as exact roots.
A certificate of zero findings comes from the complete sign decomposition,
not from extrapolation of these display values. Rational arithmetic avoids
roundoff ambiguity for the defined decimal model; this is not a guarantee for
unknown true states, floating-point integrations elsewhere or real aircraft.

## Bounded vertical search

The planner starts with all source level trajectories. It operates only on
initially level aircraft; other initial vertical states are supported by the
checker/model but have no search family here. Deterministic ordering is by
first event time, then rule/IDs. For pair participants it first tries aircraft
not previously changed, then source ID.

Each candidate replaces one source aircraft's schedule with an initial level
leg, acceleration ramp, optional constant vertical rate, braking ramp, elevated
or lowered level hold, and optional mirrored return. It may instead retain the
terminal altitude. Original horizontal motion never changes. Offset candidates
are positive then negative multiples of the selected vertical separation
threshold, increasing in magnitude and confined to altitude bounds. Ramp time
is 20 s for displacements smaller than `amax*30²`, otherwise 30 s; acceleration
is bounded by the configured acceleration, speed/ramp and displacement/ramp².
A constant-rate leg supplies the remaining displacement.

For each offset, start times are deduplicated in this order: a late start
`max(0,floor(event_start_lower-transition_duration-30))`, 0, half that late
start rounded down, 30, 60, 90, 120 s. Return starts after the current event's
certified upper end rounded up plus 30 s, or after ascent completion, whichever
is later. Return is tried first when it fits, then terminal hold. The 30 s
schedule slack is a search heuristic, **not a changed safety buffer**. Actual
decimal controls must pass the existing vertical model and the independent
checker; no heuristic establishes clearance.

Candidates must have no unary motion/altitude/zone findings and no unresolved
checks against the current planned fleet. The search objective is
lexicographic `(unary event count, pair event count)`. A zone repair may
introduce explicitly retained pair conflicts, to be repaired subsequently.
Pair repairs prefer a strict reduction of the objective. If all strict
improvements in the candidate family are exhausted, an equal-score move to a
previously unseen conflict graph is allowed, enabling a bounded ejection chain
that changes a blocking aircraft next. Graph history ignores event times and
prevents revisiting the same rule/participant pattern on a plateau. The
candidate/repair caps bound the search even when this policy stalls. Final
acceptance still requires zero of both finding types for the entire fleet.

For speed, an exact violating sphere predicate at a rational endpoint,
midpoint or horizontal closest-approach time can reject a candidate early.
One such witness proves unsafety. Absence of these witnesses never accepts a
candidate: all remaining candidates require the full continuous checker.

Unchanged single-aircraft and pair results are cached by complete serialized
control signatures within an input/configuration snapshot. Replacing one
schedule invalidates only incident obligations; other findings remain valid.
The final check uses a fresh checker, rereads `segments.json` and recomputes all
40 aircraft scopes and all 780 pairs without planner caches. Feasibility takes
priority over minimizing maneuvers, terminal deviations or distance. The result
is neither exhaustive nor a global optimum, and no arrival-delay estimate is
inferred from a terminal altitude difference.

## Output contract

All outputs under `reports/planned/` are deterministic, finite JSON/CSV/Markdown,
with no timestamps:

- `segments.json`: schema `1.0`, model `nominal_vertical_fleet`, selected
  profile/mode/variant, configured duration, canonical input/configuration
  fingerprint and `trajectories` containing **all** original-ID vertical-model
  definitions. These controls are authoritative; each carries its own source
  fingerprint. This is a new contract, not baseline report schema 1.1.
- `trajectories.csv`: diagnostic `time_s,flight_id,x_m,y_m,alt_m,vx_mps,vy_mps,vz_mps`,
  ordered by time then ID, including 0 and T even if the sample step misses T.
- `verification.json`: checker/version/scope, actual thresholds, root budgets,
  fleet/segment-file hashes, all events/unresolved findings and both counts.
  `verified_safe` is true exactly when both counts are zero. Also records all
  aircraft's terminal altitude deviations and remaining destination distances,
  and marks sampled CSV as not establishing safety.
- `baseline_verification.json`: independently checked source trajectories;
  reference result is 12 events (3 pair, 5 drone, 4 target), zero unresolved.
- `search.json`: bounded search settings, candidate/rejection/repair counts,
  accepted schedules including temporary pair conflicts and plateau moves,
  cache reuse and stop reason. Intermediate schedules are not certificates.
- `summary.md`: actual findings, limits, changed aircraft and nonzero terminal
  destination distances; remaining findings are listed if search is incomplete.

The original destination is the source baseline position at T. Since XY is
unchanged, terminal spatial distance is the absolute vertical deviation from
that endpoint. The complete 3D remaining distance and signed altitude deviation
are reported, with zero horizontal deviation. A return to every original
endpoint at T would retain the F018/F034 and F030/F039 baseline pair violations
at T. Terminal altitude deviations are therefore allowed. No statement is made
about travel after T or time required to reach a destination.

## Tests and result record

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The added tests cover certified roots (including close/repeated roots), quartic
sphere entry and tangency, short accelerated pair/altitude violations between
samples, strict boundaries, segment joins, horizon endpoints, deliberately
invalid motion controls, exhausted numerical budgets, all 12 baseline events,
deterministic planning, terminal deviation, honest bounded failure, CLI
operation from another cwd, serialization/provenance and complete-fleet
independent verification of the saved real result. Actual run counts and
terminal distances are in `reports/planned/summary.md`; validation is recorded
in [validation.md](validation.md).
