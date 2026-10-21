# Five-minute walkthrough

Open `baseline.html`. The four buttons at the top provide a short live tour.

**0:00 — Define the problem before showing the algorithm.**
“I treated this as a 20-minute en-route conflict-resolution problem. I chose
explicit 3D danger zones, separation and kinematic limits, and kept the original
inputs. Every aircraft remains in the simulation, even beyond the map boundary.”
Point to the shared rules and the statement of assumptions.

**0:40 — Show what actually goes wrong.**
Click **Inspect an original conflict**. “The source routes have 12 violation
events under the primary rules. A crossing in the map alone is insufficient:
position, altitude and time must coincide within the protected volume.”
The event list and timeline show Python-computed continuous intervals.

**1:15 — Explain the solution and its evidence.**
Click **Show recommended plan**. “The planner proposes bounded vertical
acceleration schedules. A separate checker reads the serialized schedules and
checks all 780 pairs, both spheres, altitude and motion limits continuously.
The result has zero violations and zero unresolved checks. CSV is an output for
inspection, not the safety proof.” Select an aircraft profile to show continuous
position/velocity and a return. Explain that the fixed horizontal velocity makes
progress along the original route explicit.

**2:00 — Show a result that does not depend on arbitrary weights.**
Click **Inspect optimal endpoints**. “Two disjoint pairs are horizontally too
close at 1200 s. Each needs 300 m relative vertical separation. The triangle
inequality therefore forces at least 600 m total deviation and 150 m worst
individual deviation. Opposing ±150 m offsets attain both bounds in a fully
checked plan. Those endpoint metrics are optimal within the fixed-horizontal
model. Other costs remain trade-offs.”

**2:50 — Explain the surprising result instead of hiding it.**
Click **Explain the large climb**. “A 6150 m temporary excursion initially looks
like a poor solution. But the drone has a 5 km sphere centered at altitude 4 km,
and aircraft cannot descend below 3 km. On F031's fixed route, sphere geometry
requires at least a 5679.45 m climb. Large maneuvers are partly the price of the
vertical-only model. That suggests evaluating horizontal avoidance next.”

**3:40 — Explain what nominal safety does not establish.**
“The endpoint optimum uses equality at the 300 m threshold. Opposing 1 m altitude
errors can reduce that separation to 298 m. A continuous 304.8 m threshold
comparison finds 16 events. I report this sensitivity rather than claiming
real-world robustness. Robustness would require a justified execution-error
model and a different trade-off with deviation.”

**4:20 — Close with reproducibility and judgment.**
Show the trajectory, rules and verification links. “There is one clearly selected
submission, a complete trajectory file for all aircraft, shared rules, hashes,
tests and an offline viewer. Earlier feasible and Pareto plans remain available
to expose the trade-offs. The next extension is broader maneuvers and explicit
uncertainty, not a claim that this research model is certified ATC.”

## Likely questions

- **Why no airports?** The assignment defines destination as the original
  straight-line continuation over the 20-minute horizon. No airport assignments
  or landing model are supplied.
- **Why not return every aircraft exactly?** Two original endpoint pairs violate
  separation. Requiring exact endpoints for all at T would contradict safety.
- **Why this particular “best” plan?** It attains the two proved endpoint bounds;
  the tie-break policy then considers excursion and maneuver costs. The policy
  is explicit, and other Pareto solutions are shown.
- **Is it globally optimal?** Only the two attained endpoint metrics are proved
  optimal under fixed XY. Excursion, travel, workload proxies and arbitrary
  horizontal maneuvers are not globally optimized.
- **Is the 304.8 m result a failure?** It is a different declared threshold.
  The primary 300 m certificate and its exact assumptions remain explicit.
  Sensitivity identifies where the guarantee ends.
- **Is vertical travel fuel consumption?** No. Aircraft types, mass and thrust
  models are unknown. Travel and reversals are transparent proxies.
- **How did AI help?** AI-assisted implementation and review are allowed by the
  assignment. Defend the explicit assumptions, independent checks, analytical
  bounds and reproducible artifacts rather than relying on generated assertions.
