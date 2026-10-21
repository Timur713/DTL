# Safe passage — engineering approach and results

**Scenario and safety design.** Forty aircraft must avoid each other, a moving
drone and a ground target for 1200 s. I first reviewed
[FAA](https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap5_section_5.html)/[ICAO](https://store.icao.int/en/manual-on-implementation-vertical-separation-doc-9574) separation
references and EUROCONTROL/NASA approaches to conflict detection and uncertainty.
I adopted 9260 m horizontal OR 300 m vertical separation, keeping 304.8 m as a
sensitivity comparison. The 5 km exclusion spheres, target altitude zero and
generic aircraft limits are explicit research assumptions, not universal aviation
rules. Limits: altitude 3000–12000 m, horizontal speed 200–260 m/s, vertical speed
≤15 m/s and vertical acceleration ≤0.5 m/s². Equality is allowed. Planner and
checker share rules.json.

**Establish a baseline before optimizing.** I visualized the original routes and
identified 12 violation events. I then restricted the first solver to continuous
vertical maneuvers while preserving horizontal motion. This kept forward progress
explicit and made the dynamics tractable to verify. Position and velocity remain
continuous; aircraft are never teleported or removed.

**Make “good” measurable, then test the definition.** I treated feasibility,
quality and optimality as separate questions. I proposed a normalized weighted
formula, `J = Σₖ wₖ mₖ/sₖ`, for worst/total endpoint deviation, accumulated altitude deviation and
vertical travel, with safety as a hard constraint. Its dependence on reference
scales and the observed trade-offs motivated retaining it only as an experimental
benchmark. I moved to seven-objective Pareto comparisons, also considering peak
excursion, changed aircraft and reversals, so improvements remain inspectable.

**Use mathematical bounds to guide improvement.** Two disjoint terminal pairs
need 300 m relative vertical displacement each. Triangle inequality proves lower
bounds of 150 m worst and 600 m total endpoint deviation. Coordinated ±150 m
offsets attain both in the submitted plan. This improves the first feasible
solution's 6300/14100 m endpoints. I also investigated the surprising large climbs:
sphere geometry and the altitude floor force at least 5679.45 m excursion for
F031; the submitted fleet maximum is 6150 m.

**Verify independently and challenge the guarantee.** The checker reads saved
controls and continuously checks all 780 pairs, spheres, motion limits and joins,
including quartic distance inequalities. Result: **40 aircraft, zero nominal
violations, zero unresolved checks**, zero final vertical speed. Samples alone
are insufficient evidence. Opposing 1 m altitude errors can reduce binding
separation to 298 m; the separate 304.8 m recheck finds 16 events. I report these
limits explicitly.

**Assumptions:** exact states/execution, point aircraft, flat geometry, no wind or
delays; the drone continues beyond the target and aircraft are retained when
leaving the display frame. No aircraft-specific aerodynamics, landing, post-horizon guarantee
or overall global optimum is claimed. The two endpoint optima assume fixed XY.

**Open START_HERE.html after extracting the ZIP.** It works offline.
trajectories.csv contains 48,040 rows; segments.json holds
authoritative controls; verification.json holds evidence and hashes.

Full source, independent checker, tests and search experiments: https://github.com/Timur713/DTL
