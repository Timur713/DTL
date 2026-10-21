# Selected submission: safe nominal rerouting

Forty aircraft retain their horizontal routes over 1200 s. Safety means horizontal
separation >=9260 m OR vertical separation >=300 m, exclusion from the drone and
ground-target spheres (radius 5000 m), and altitude 3000–12000 m. These are stated
research assumptions. Point aircraft, exact states, no delays or wind; the drone
continues beyond the target. Generic motion limits come from the unchanged rules.

**Selected plan: `pass2-b8f763f4b8b0`.** Open [the offline viewer](../baseline.html)
and choose **Show recommended plan**. Every aircraft remains present, with continuous
position/velocity, original horizontal motion and zero final vertical speed.

| Result | Value |
| --- | ---: |
| Nominal violations / unresolved checks | 0 / 0 |
| Complete pair checks | 780 |
| Maximum / total original-endpoint deviation | 150 / 600 m |
| Maximum temporary altitude excursion | 6150 m |
| Accumulated altitude deviation | 1.34487e+07 m·s |
| Vertical travel / changed aircraft / reversals | 60600 m / 15 / 13 |

Two disjoint terminal-conflict pairs require at least 300 m relative displacement
each: total deviation >=600 m and maximum individual deviation >=150 m. The
selected plan attains both necessary bounds, proving those two metrics optimal
**under fixed horizontal motion**, not global trajectory optimality. We use seven
Pareto objectives rather than a fitted weighted score; other trade-offs remain
available in the viewer.

Large climbs have a geometric cause: at horizontal closest approach, F031
must clear the sphere above the altitude floor, requiring at least
5679.451 m excursion. This is a lower bound, not a complete solution.
The endpoint-optimal plan also has no positive uniform altitude-error guarantee:
opposing 1 m errors can reduce a binding 300 m separation to 298 m. The separate
304.8 m threshold recheck finds
16 events. Neither experiment changes the primary rules.

**Data:** `trajectories.csv` contains 48,040 rows for all
40 aircraft at 1 s intervals plus every segment join. `segments.json` is
authoritative; `maneuvers.csv` lists acceleration segments. `rules.json` is shared
by planner/checker; its affine-motion metadata describes the baseline, while the
serialized segment model explicitly defines maneuver dynamics. `verification.json`
uses exact rational polynomial sign decomposition, including quartic sphere
distances; samples alone never establish safety. `manifest.json` records hashes.

**Reproduce from the project root:** `python3 tools/build_submission.py --html --package`.
This verifies/exports the saved solution and packages the project without rerunning
search. Full search commands and reasoning: [submission guide](../docs/submission.md).
No landing, post-horizon, aircraft-specific performance or bounded-stress safety is
claimed. Equality is safe by definition; robustness needs a different objective.
