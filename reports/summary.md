# Baseline motion analysis

Continuous horizon [0, 1200] s; 40 aircraft; 20 runs. Maneuvers are not implemented.

Distance violations use strict inequalities: equality at the threshold is safe. In bounded_stress, events indicate a possible loss of guarantee within the selected error bounds, not a probability or an actual violation.

| Run | Events | Unique pairs | Aircraft | Initial | Pairs / drone / target / altitude / motion |
| --- | ---: | ---: | ---: | ---: | --- |
| metric__nominal__base | 12 | 3 | 13 | 0 | 3 / 5 / 4 / 0 / 0 |
| metric__nominal__threat_3000 | 11 | 3 | 12 | 0 | 3 / 4 / 4 / 0 / 0 |
| metric__nominal__threat_10000 | 18 | 3 | 18 | 0 | 3 / 11 / 4 / 0 / 0 |
| metric__nominal__target_3000 | 8 | 3 | 9 | 0 | 3 / 5 / 0 / 0 / 0 |
| metric__nominal__target_10000 | 22 | 3 | 21 | 0 | 3 / 5 / 14 / 0 / 0 |
| metric__bounded_stress__base | 38 | 24 | 25 | 2 | 24 / 7 / 5 / 2 / 0 |
| metric__bounded_stress__threat_3000 | 35 | 24 | 24 | 2 | 24 / 4 / 5 / 2 / 0 |
| metric__bounded_stress__threat_10000 | 43 | 24 | 26 | 2 | 24 / 12 / 5 / 2 / 0 |
| metric__bounded_stress__target_3000 | 33 | 24 | 25 | 2 | 24 / 7 / 0 / 2 / 0 |
| metric__bounded_stress__target_10000 | 49 | 24 | 28 | 2 | 24 / 7 / 16 / 2 / 0 |
| feet_reference__nominal__base | 33 | 24 | 24 | 0 | 24 / 5 / 4 / 0 / 0 |
| feet_reference__nominal__threat_3000 | 32 | 24 | 23 | 0 | 24 / 4 / 4 / 0 / 0 |
| feet_reference__nominal__threat_10000 | 39 | 24 | 25 | 0 | 24 / 11 / 4 / 0 / 0 |
| feet_reference__nominal__target_3000 | 29 | 24 | 24 | 0 | 24 / 5 / 0 / 0 / 0 |
| feet_reference__nominal__target_10000 | 43 | 24 | 27 | 0 | 24 / 5 / 14 / 0 / 0 |
| feet_reference__bounded_stress__base | 38 | 24 | 25 | 2 | 24 / 7 / 5 / 2 / 0 |
| feet_reference__bounded_stress__threat_3000 | 35 | 24 | 24 | 2 | 24 / 4 / 5 / 2 / 0 |
| feet_reference__bounded_stress__threat_10000 | 43 | 24 | 26 | 2 | 24 / 12 / 5 / 2 / 0 |
| feet_reference__bounded_stress__target_3000 | 33 | 24 | 25 | 2 | 24 / 7 / 0 / 2 / 0 |
| feet_reference__bounded_stress__target_10000 | 49 | 24 | 28 | 2 | 24 / 7 / 16 / 2 / 0 |

## Initial violations with base radii

- `metric__nominal__base`: none.
- `metric__bounded_stress__base`: F031 (altitude_min); F040 (altitude_min).
- `feet_reference__nominal__base`: none.
- `feet_reference__bounded_stress__base`: F031 (altitude_min); F040 (altitude_min).

## Interpretation and format

Changing V from 300 to 304.8 m includes altitude differences of exactly 300 m. Threat and target radii vary one at a time; sensitivity.csv contains the full sensitivity analysis with differences relative to base/nominal/metric.

Motion checks cover every aircraft: horizontal speed, its tangential derivative, vertical speed/acceleration, zero bank for the straight baseline, and zero turn rate with the coordinated-turn bound g·tan(bank)/v. Stress checks cover the full admissible range of constant velocities. These checks do not validate future maneuvers.

analysis.json contains all events, effective affine thresholds, and complete motion_checks. events.csv stores thresholds and metrics as JSON fields; flags are true/false, and an empty scalar field means null. summary.csv and sensitivity.csv contain one row per run. IDs are preserved across all CSV files.

Times and distances in machine-readable reports are not rounded. Metric minima refer to nominal centers over the closure of the event interval; attained distinguishes an attained minimum from an infimum. Different components may reach their minima at different times. The sum of event durations includes overlaps and is not the duration of unsafe flight.

XY bounds do not exclude objects. The target and threat have spherical zones active throughout the horizon. Target XY coordinates come from scenario; the center altitude comes from rules.zones.target.center_alt_m (target_alt_m in each run). The drone continues unchanged after passing target XY. Altitude bounds come from scenario. All stress events have severity=possible_violation; both spheres use a conservative affine bound on 3D error. Only the aircraft e_h+e_z is included for the exact target; both objects contribute errors for the drone. Errors are measured from t=0 and do not reset.

The rules are research assumptions. Regulatory compliance, aircraft-specific flight envelopes, delays, actual accuracy, and the safety of a future plan have not been established.
