# Nominal vertical planning result

Status: **verified_safe**.

All 40 aircraft retained over [0, 1200] s; metric / nominal / base rules unchanged.
Initial baseline: 12 violations; final: 0 violations and 0 unresolved checks.
Independent final checks: 780 aircraft pairs and 40 full-horizon aircraft motion/altitude/zone checks.
Search: 7959 candidate attempts, 21 accepted repairs; stop reason: verified_safe.
Changed aircraft: F002, F004, F011, F012, F013, F018, F020, F023, F026, F027, F030, F031, F034, F037, F038.

## Terminal destinations

Original horizontal motion is retained. Remaining distance is spatial distance to the original t=T endpoint, not an arrival-delay estimate.

| Aircraft | Terminal altitude deviation (m) | Remaining destination distance (m) |
| --- | ---: | ---: |
| F013 | 900.000000 | 900.000000 |
| F018 | 5700.000000 | 5700.000000 |
| F023 | 900.000000 | 900.000000 |
| F030 | 300.000000 | 300.000000 |
| F034 | 6300.000000 | 6300.000000 |

## Verification and limitations

Authoritative controls: segments.json. Continuous sign checks use exact rational polynomial arithmetic and certified Sturm root isolation, including quartic sphere expressions. Sampling in trajectories.csv is diagnostic only.
The final checker rereads segments.json independently of search caches. Any unresolved check prevents verified_safe. Numerical root brackets and rational witnesses are in verification.json.
The deterministic search is bounded and prioritizes feasibility. It is neither exhaustive nor globally optimal. A failed search does not prove infeasibility. Only nominal kinematics are covered; bounded stress, aerodynamics and real-world certification are outside this result.
No safety conclusion applies beyond the configured horizon. Baseline artifacts and HTML are not modified.
