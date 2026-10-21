# Second-pass nominal quality alternatives

Earlier reference and first-pass artifacts are unchanged. Endpoint bounds derive from the current scenario; they are not universal constants. Every saved second-pass alternative passed fresh full continuous verification with zero violations/unresolved checks and zero terminal vertical speed.

| Plan | Dmax m | Dtotal m | Excursion m | A m·s | Travel m | Changed | Reversals | Dmax gap m | Dtotal gap m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| reference | 6300.000000 | 14100.000000 | 6300.000000 | 19809900.000000 | 47700.000000 | 15 | 10 | 6150 | 13500 |
| alt-5c0a7daf73c4 | 300.000000 | 600.000000 | 6300.000000 | 13745400.000000 | 61200.000000 | 15 | 14 | 150 | 0 |
| alt-5572c56163d0 | 900.000000 | 1500.000000 | 6300.000000 | 14208900.000000 | 60300.000000 | 15 | 13 | 750 | 900 |
| alt-72f75f97885d | 900.000000 | 2400.000000 | 6300.000000 | 14663400.000000 | 59400.000000 | 15 | 12 | 750 | 1800 |
| alt-9c31f3faad7d | 6300.000000 | 8400.000000 | 6300.000000 | 17273400.000000 | 53400.000000 | 15 | 11 | 6150 | 7800 |
| alt-82fd0cda3e29 | 6300.000000 | 8700.000000 | 6300.000000 | 17352900.000000 | 53100.000000 | 15 | 11 | 6150 | 8100 |
| alt-efc2a9f64481 | 6300.000000 | 13500.000000 | 6300.000000 | 19500900.000000 | 48300.000000 | 15 | 11 | 6150 | 12900 |
| alt-c0db93e2592c | 6300.000000 | 14100.000000 | 6300.000000 | 19758300.000000 | 47100.000000 | 14 | 9 | 6150 | 13500 |
| alt-3b0cd621b8fc | 6300.000000 | 15000.000000 | 6300.000000 | 20254200.000000 | 46200.000000 | 13 | 7 | 6150 | 14400 |
| pass2-b8f763f4b8b0 | 150.000000 | 600.000000 | 6150.000000 | 13448700.000000 | 60600.000000 | 15 | 13 | 0 | 0 |
| pass2-46de10ecbe7a | 300.000000 | 600.000000 | 6150.000000 | 13443300.000000 | 60300.000000 | 14 | 13 | 150 | 0 |
| pass2-7339a328aa4b | 900.000000 | 2400.000000 | 6150.000000 | 14502932.312819 | 59400.000000 | 15 | 13 | 750 | 1800 |
| pass2-d4a31b6da836 | 900.000000 | 2400.000000 | 6150.000000 | 14679098.979486 | 58800.000000 | 15 | 11 | 750 | 1800 |
| pass2-019bdc6ace89 | 900.000000 | 2400.000000 | 6300.000000 | 14592698.979486 | 59100.000000 | 14 | 11 | 750 | 1800 |
| pass2-aa4a3e2ac226 | 1200.000000 | 3300.000000 | 6150.000000 | 14998832.312819 | 58500.000000 | 14 | 11 | 1050 | 2700 |
| pass2-cfef44a4554e | 1200.000000 | 3300.000000 | 6150.000000 | 15012998.979486 | 57900.000000 | 14 | 9 | 1050 | 2700 |
| pass2-953a7e7faf70 | 1200.000000 | 3300.000000 | 6150.000000 | 15028598.979486 | 57900.000000 | 13 | 9 | 1050 | 2700 |
| pass2-9eda3b947447 | 6300.000000 | 14100.000000 | 6300.000000 | 19728300.000000 | 47100.000000 | 14 | 9 | 6150 | 13500 |
| pass2-6329f0951863 | 6300.000000 | 15000.000000 | 6300.000000 | 20062200.000000 | 46200.000000 | 13 | 7 | 6150 | 14400 |

Both endpoint lower bounds attained by a fully verified plan: True. Only metrics with a valid attained lower bound are proven optimal; no other global optimality is claimed.

Evaluations 3000/3000; full verifications 82/200; archive 10/32; runtime guard 900 s; stop candidate_budget; pruning operations 0.

## Earlier plans dominated by saved second-pass alternatives

- reference: pass2-9eda3b947447
- alt-5c0a7daf73c4: pass2-b8f763f4b8b0, pass2-46de10ecbe7a
- alt-5572c56163d0: pass2-46de10ecbe7a
- alt-72f75f97885d: pass2-019bdc6ace89
- alt-9c31f3faad7d: none
- alt-82fd0cda3e29: none
- alt-efc2a9f64481: none
- alt-c0db93e2592c: pass2-9eda3b947447
- alt-3b0cd621b8fc: pass2-6329f0951863

Seven raw objectives determine dominance. The unchanged frozen experimental J is never a ranking/filter criterion. Search is limited to configured level-to-level constant-acceleration schedules, terminal balancing, discrete peak/time grids and bounded coordinated neighbor repairs. Round-robin seeds/priorities preserve trade-off diversity. A failed candidate or exhausted budget does not prove infeasibility. The cooperative guard is checked between operations; seed checks and final export verification add a bounded tail. Pruned IDs and per-job stopping reasons are in search.json.

## Achieved improvements and trade-offs

Endpoint-optimal witness pass2-b8f763f4b8b0: Dmax=150 m, Dtotal=600 m. Compared with first-pass endpoint plan alt-5c0a7daf73c4, excursion 6300 -> 6150 m, A 1.37454e+07 -> 1.34487e+07 m*s, travel 61200 -> 60600 m, changed 15 -> 15, reversals 14 -> 13. Added aircraft: F039; restored aircraft: F020. A minimum changed-aircraft count is not proved.

- Lowest saved maximum excursion across each set, possibly different plans: first pass 6300.000000; second pass 6150.000000; difference -150.000000. These are observed set minima, not global optimality claims.
- Lowest saved accumulated deviation across each set, possibly different plans: first pass 13745400.000000; second pass 13443300.000000; difference -302100.000000. These are observed set minima, not global optimality claims.
- Lowest saved vertical travel across each set, possibly different plans: first pass 46200.000000; second pass 46200.000000; difference 0.000000. These are observed set minima, not global optimality claims.
