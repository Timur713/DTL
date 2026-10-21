# Nominal vertical quality alternatives

The reference under reports/planned/ is unchanged. Every saved alternative independently verifies all 40 aircraft over [0,1200] s with zero violations/unresolved checks and zero terminal vertical speed.

Six minimized Pareto objectives are Dmax, Dtotal, accumulated altitude deviation A, vertical travel L, changed-aircraft count N and reversals R. Maximum excursion is diagnostic. Endpoint deviations refer to the original endpoint, not airport arrival or landing.

| Plan | Pareto | Dmax m | Dtotal m | A m·s | L m | N | R | Max excursion m | Experimental J |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| reference | no | 6300.000000 | 14100.000000 | 19809900.000000 | 47700.000000 | 15 | 10 | 6300.000000 | 1.000000000 |
| alt-5c0a7daf73c4 | yes | 300.000000 | 600.000000 | 13745400.000000 | 61200.000000 | 15 | 14 | 6300.000000 | 0.172747189 |
| alt-5572c56163d0 | yes | 900.000000 | 1500.000000 | 14208900.000000 | 60300.000000 | 15 | 13 | 6300.000000 | 0.247243836 |
| alt-72f75f97885d | yes | 900.000000 | 2400.000000 | 14663400.000000 | 59400.000000 | 15 | 12 | 6300.000000 | 0.264552194 |
| alt-9c31f3faad7d | yes | 6300.000000 | 8400.000000 | 17273400.000000 | 53400.000000 | 15 | 11 | 6300.000000 | 0.892106809 |
| alt-82fd0cda3e29 | yes | 6300.000000 | 8700.000000 | 17352900.000000 | 53100.000000 | 15 | 11 | 6300.000000 | 0.897512807 |
| alt-efc2a9f64481 | yes | 6300.000000 | 13500.000000 | 19500900.000000 | 48300.000000 | 15 | 11 | 6300.000000 | 0.988430807 |
| alt-c0db93e2592c | yes | 6300.000000 | 14100.000000 | 19758300.000000 | 47100.000000 | 14 | 9 | 6300.000000 | 0.999110593 |
| alt-3b0cd621b8fc | yes | 6300.000000 | 15000.000000 | 20254200.000000 | 46200.000000 | 13 | 7 | 6300.000000 | 1.016627938 |

## Search limits and findings

Candidate evaluations: 360 / 360; independent verifications: 29 / 48; search runtime guard: 300 s; stop: candidate_budget.
Verified feasible candidates including reference: 21; retained Pareto size: 8 / 8; capacity-pruning operations: 3.
Six deterministic lexicographic strategies explore different objective priorities. Terminal transitions, altitude/time changes, original-aircraft restoration and coordinated changes are considered. Unchanged checks are reused; each admitted candidate receives a fresh complete independent verification.
Archive dominance uses all six raw objectives. Capacity pruning, if needed, preserves objective extrema then normalized crowding distance; every removed ID is reported in search.json. The experimental J never ranks the search or filters the archive.
Frozen J weights/scales are stored in experiments/quality_score.json. The reference exactly reproduces Dmax=6300, Dtotal=14100, A=19809900, L=47700 and J=1.
The wall-clock guard is checked between bounded candidate/check operations, with a final verification/export tail. Candidate and verification caps are deterministic; a runtime stop can change the explored prefix. No global optimality or infeasibility claim is made.
