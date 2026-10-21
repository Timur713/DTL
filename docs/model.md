# Model and rules for analyzing baseline motion

This is a research model of source trajectories over 1200 s. `rules.json` contains the thresholds and limits selected for the baseline analyzer and interface. The baseline has no maneuvers, optimization, conflict resolution or claims that source motion is safe. The analysis detects violations of the selected rules and shows how conclusions depend on those rules and bounded errors. A separate nominal [vertical trajectory model](vertical-model.md) now supports supplied maneuver schedules and motion/altitude validation; it does not change this baseline or check maneuver conflict safety.

## Inputs and model scope

`flights.csv` contains 40 aircraft and a single snapshot at `t=0`: Cartesian coordinates, altitude and three velocity components. `scenario.json` defines X east, Y north, a ±200 km X/Y region, altitudes of 3000–12000 m, fixed target XY and the drone state. `Task1_details.pdf` explicitly leaves the choice of protected zone sizes and aircraft characteristics to the implementer. Its sanity facts contain a typo: 230×1200=276 km corresponds to **20**, rather than 15 minutes.

Each aircraft is a point mass with a defined relative protected volume. Fuselage and wing dimensions, wake turbulence and 6DOF are not modeled. Aircraft types, mass, equipment, RVSM approval, atmospheric pressure, actual navigation/surveillance accuracy, wind and physical threat effects are unknown. These cannot be recovered from the snapshot.

Altitude is treated as a geometric model coordinate. It is not a flight level or a verified pressure altitude. Flat local geometry is assumed throughout the horizon, without geodetic correction or Earth curvature. This is an assumption of the source task; its physical error has not been assessed or included in stress bounds.

For every moving object:

```text
p(t) = p0 + v*t, 0 <= t <= 1200 s.
```

Objects outside XY boundaries are retained and participate in all checks. The XY frame is a visual region, not a mandatory safety corridor. Aircraft altitude bounds come from `scenario.airspace.alt_min_m/alt_max_m`, including boundaries. The drone is not subject to the selected generic jet speed limits or aircraft altitude limits.

The target has fixed XY=(20000,−10000) m. Its altitude is absent from the inputs; we assume `rules.zones.target.center_alt_m=0` m in the scenario coordinate system. This explicitly assumes a ground point without a terrain model. The drone flies from (−60000,50000,4000) m with velocity (96,−72,0) m/s. At `t=2500/3≈833.333333` s it passes the target XY at altitude 4000 m, then continues the same motion. At 1200 s it is at (55200,−36400,4000) m. Impact, stopping, disappearance or a trajectory change are not assumed. Each aircraft's provisional destination for a future planner is the endpoint of its original trajectory, `p0+v*1200`; currently it simply follows this straight line.

## External references and our choices

Primary official sources were checked. They explain the choice of scale and model architecture; their operational conditions are not confirmed by the inputs.

| Source and exact section | What it supports | Use here |
| --- | --- | --- |
| [FAA JO 7110.65, §5-5-4(d)(1), ERAM](https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap5_section_5.html) | A 5 NM reference is specified for ERAM below FL600; the same section gives other minima and applicability conditions. | `H=5*1852=9260` m is our common horizontal threshold. It is not a universal standard for all aircraft/conditions. |
| [FAA JO 7110.65, §4-5-1(a–c)](https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap4_section_5.html) | 1000 ft through FL410 inclusive, with qualifications for non-RVSM and other altitudes. | The `feet_reference` profile uses the exact conversion `1000*0.3048=304.8` m. FAA/RVSM applicability is not claimed. |
| [ICAO Doc 9574, 3rd edition 2012, official product description](https://store.icao.int/en/manual-on-implementation-vertical-separation-doc-9574) | The description uses 300 m (1000 ft) for VSM above FL290 and ties implementation to ICAO criteria/requirements. | The `metric` profile assumes **exactly 300 m by convention**. This is not an exact conversion from feet. The full paid document was not used and is not claimed to have been read. |
| [EUROCONTROL MTCD Ed.2, §§3.1.1.4–3.1.1.11, printed p.16/PDF p.17](https://www.eurocontrol.int/sites/default/files/publication/files/EUROCONTROL-SPEC-0139%20MTCD%20Ed%202.0.pdf) | §§4–8 allow separation configuration by airspace and dimensions, account for RVSM and deemed-separated routes; §9 requires uncertainty growth with look-ahead time; §§10–11 allow correlation and a probabilistic approach. | Thresholds are configured separately from growing uncertainty. Our linear bounds are our own choice; correlations and probability are not modeled, and compliance with the full specification is not claimed. |
| [NASA DAIDALUS v2, Introduction; Adding Sensor Uncertainty; Horizontal Direction/Speed/Vertical Speed Bands](https://nasa.github.io/daidalus/) | Separate position/velocity uncertainty models and kinematic limits: bank/turn rate and accelerations. Sensor inputs are described using standard deviations. | We adopt the idea of separating geometry, uncertainty and kinematics. Our bounds are deterministic, not standard deviations; DAIDALUS formulas, DAA thresholds and its results were not incorporated into this project. |
| [EUROCONTROL BADA, Replicate the performance of any aircraft; Access procedure](https://www.eurocontrol.int/model/bada) | A realistic model requires specifications and dedicated performance datasets; access is licensed. | Aircraft type data are unavailable, BADA is not installed and its performance data are not used. The generic jet below is our explicit assumption. |

The primary profile is `metric`: H=9260 m, V=300 m. The alternative is `feet_reference`: H=9260 m, V=304.8 m. A common metric threshold is applied at all input scenario altitudes as a research convention, rather than a literal FAA implementation. Regulatory compliance, suitability for real control or operational approval do not follow from the result.

## Violation geometry

For an aircraft pair, define relative coordinates `r=p_i−p_j`, horizontal distance `d_h=hypot(r_x,r_y)` and vertical distance `d_z=abs(r_z)`. A violation exists only when both conditions hold:

```text
d_h(t) < H  AND  d_z(t) < V.
```

This is a relative cylinder with horizontal radius H and vertical half-height V. H/V are distances between the pair's centers; do not add them again as radii of two aircraft. Safety under this rule means `d_h>=H OR d_z>=V`; equality at either threshold is safe.

The threat is a **sphere of radius 5000 m** around the drone's current 3D point: a violation is `distance_3d<R_threat`. The target is a **sphere of radius 5000 m** around the fixed point `(x_target,y_target,z_target)`, with default `z_target=0`: a violation is `sqrt((x−x_target)²+(y−y_target)²+(z−z_target)²)<R_target`. Both zones are active throughout the horizon. The radii are equal only by the initial convention; they are independent parameters. They are not damage radii, weapon power estimates or aviation standards. All violations represent entry into selected protected zones, rather than physical collisions.

The task permits a 2D or 3D target zone. The selected sphere defines a minimum spatial distance to a ground object and accounts for aircraft altitude. It replaces the earlier assumption of an infinite vertical cylinder; the brief decision is in [target-zone-decision.md](target-zone-decision.md). For example, at altitude 3000 m a 5000 m sphere has a section radius of 4000 m, while at altitude 8100 m there is no section. The radius remains a working assumption assessed through sensitivity analysis.

A separate altitude rule applies to each aircraft: `alt_min<=z<=alt_max`. Nominal `z=3000` m is allowed in this model. Threat/target checks are not restricted to the XY frame or altitude region.

## Exact mode and bounded errors

`nominal` assumes exact p0/v, zero errors and zero delays. These are actual violations **within the adopted deterministic model**, not confirmation of a real aircraft's actual position.

`bounded_stress` assigns **each aircraft and the drone** an initial horizontal position error disk of radius 100 m, a vertical interval of ±20 m, a horizontal velocity error disk of radius 1 m/s and vertical velocity error of ±0.1 m/s. The target is exact. Each object's velocity error is constant throughout the horizon; its initial error is also chosen once. Position bounds at time t are:

```text
e_h(t) = 100 + 1*t m,
e_z(t) = 20 + 0.1*t m.
```

These bounds start at the single t0 snapshot: there are no new observations, snapshot updates or resets on frames/seeking. The task's statement about knowing other objects' positions is interpreted in the baseline as access to the common nominal model; stress is a separate experiment on robustness to snapshot errors. In stress mode at t=1200, each object has e_h=1300 m and e_z=140 m. These are selected maximum errors, not RMS, σ, confidence intervals or probabilities.

Individual bounds are added for a pair:

```text
H_eff(t) = H + e_hi(t) + e_hj(t) = H + 200 + 2*t,
V_eff(t) = V + e_zi(t) + e_zj(t) = V + 40 + 0.2*t.
```

The same strict conjunction is checked with H_eff/V_eff. At an individual instant, for a disk×interval this is the exact condition for the existence of an admissible error that can violate the thresholds. A continuous possible-violation interval is the union of such possibilities over time; it does not assert that one fixed error realization violates the rule at every point of the interval. Independence here means an absence of constraints on joint error choices, not statistical independence.

For both spheres we use a deliberately conservative affine bound on 3D error magnitude. The target is exact, so only aircraft error is included for it:

```text
|delta_p| <= hypot(e_h,e_z) <= e_h+e_z =: e_3d,
R_target_eff(t) = R_target+e_3di(t)
                = R_target+120+1.1*t,
R_threat_eff(t) = R_threat+e_3di(t)+e_3d_drone(t)
                = R_threat+240+2.2*t.
```

For either zone, if `distance_3d>=R_eff`, the triangle inequality guarantees that the actual distance is at least its original R for all allowed errors: this is a **sufficient safety bound**. The converse is false. A sphere expanded by the sum of applicable e_h+e_z contains the exact Minkowski sum of the sphere and cylindrical error sets; it is not equal to that sum. A stress sphere event can therefore be a false alarm even for the admissible error set. It indicates possible loss of guarantee, not a collision probability or a proven actual violation. The affine upper bound preserves a continuous solution through quadratic inequalities. More precise geometry could be added later; the simplest verifiable sufficient bound is currently selected.

The stress altitude guarantee requires `z−e_z>=alt_min AND z+e_z<=alt_max`. Thus F031 and F040 at altitude 3000 m already have `possible_violation` at t0: the lowest admissible altitude is 2980 m. Their original nominal altitude is allowed. Do not hide these events by adding margins to source inputs or arbitrarily moving aircraft.

## Generic jet dynamics

All following values are modeling assumptions, not characteristics of unknown real types:

| Parameter | Assumed value |
| --- | --- |
| Horizontal speed | 200–260 m/s inclusive |
| Acceleration/deceleration | `abs(d norm(v_xy)/dt)<=0.5` m/s² |
| Vertical speed | `abs(v_z)<=15` m/s |
| Vertical acceleration | `abs(a_z)<=0.5` m/s² |
| Bank angle | absolute value no greater than 25° |
| Gravitational acceleration | 9.80665 m/s² |
| Wind | zero in the kinematic approximation |

Acceleration/deceleration limits the **change in horizontal speed magnitude**, rather than the magnitude of the full XY acceleration. Turning creates additional lateral acceleration. For a coordinated level turn in zero wind:

```text
|omega|max(v_h) = g*tan(25°)/v_h rad/s,
R_min(v_h) = v_h^2/(g*tan(25°)).
```

At 200–260 m/s this is 1.310044–1.007726 °/s; at 230 m/s, R_min≈11568.111 m. This is a simplified coordinated turn, not a model of thrust, aerodynamics or joint feasibility of all limiting regimes. The 0.5 m/s² tangential acceleration limit is consistent with separate lateral acceleration `g*tan25≈4.573` m/s². Accelerating from 200→260 m/s requires at least 120 s. A 15 m/s limit gives 20 s per 300 m only with an already established vertical regime; starting and ending with vz=0 at az=0.5 m/s², a triangular profile would require ≈48.990 s. Teleportation or instantaneous direction changes would not satisfy these future limits.

In the source baseline, accelerations and turn rate are zero, vz=0. Checked horizontal speed magnitudes of the input aircraft lie in [212.65,248.431854] m/s and satisfy the selected limits. In stress mode, each admissible true baseline is also straight with constant velocity error. The checked intervals are:

```text
v_h_true in [max(0,norm(v_xy)−e_vh), norm(v_xy)+e_vh],
v_z_true in [v_z−e_vz, v_z+e_vz].
```

With e_vh=1 and e_vz=0.1 all input aircraft pass: the overall range is [211.65,249.431854] m/s and vz is in [−0.1,0.1]. Accelerations and turn rate remain zero for every admissible trajectory. This is not differentiation of the growing position envelope. Future arbitrary maneuvers will require separate analysis of derivatives, segment transitions and actual feasibility; this is not currently implemented. Altitude limits are a separate check from the scenario, not duplicated dynamic constants.

## Delays and numerical accuracy

Observation, communication and execution delays are assumed zero. Positive delays are unsupported; they cannot be considered covered by bounded errors without a separate model. Neither zone sizes nor uncertainty bounds are derived from system delays.

Analysis must be continuous in time, independent of frames or sampling frequency. For relative affine motion `r=r0+w*t` and an affine positive threshold `L=a+b*t`, the condition `norm(r)<L` is equivalent to:

```text
(w·w−b²)*t² + 2*(r0·w−a*b)*t + (r0·r0−a²) < 0.
```

Use two components for XY and three for a sphere. The vertical condition splits into two strict linear inequalities. Intersect the resulting sets with each other and the closed horizon [0,1200]. Handle zero relative motion, a zero quadratic coefficient, double roots and tangency. Exact threshold tangency does not create an event; two open intervals separated by a safe point are not merged.

`time_epsilon_s=1e−9`, `distance_epsilon_m=1e−7` are small numerical calculation/residual tolerances, not physical buffers. They do not expand or shrink the selected H/V/R, turn `<` into `<=`, or merge safe gaps. Squared comparisons require appropriately scaled error: do not apply a tolerance in meters directly to m². The 4.8 m difference between vertical profiles must be preserved. Rounding displayed numbers does not change the source event or its endpoint flags; exact input arithmetic or root residual checks are preferred for ambiguous boundary cases.

## Sensitivity and verifiable examples

Both V values are checked, with five radius variants for each profile/mode combination: base (5000/5000), threat_3000 (3000/5000), threat_10000 (10000/5000), target_3000 (5000/3000), target_10000 (5000/10000). One parameter changes at a time. 5000 is already included in base; no duplicate is needed. Total: 2 profiles × 2 modes × 5 variants = **20 runs**. Results of different variants are not added as independent events of a single simulation.

The simple synthetic cases below use arbitrary SI thresholds for manual interval checks; they do not change the working rules:

| Case | Relative motion data | Expected result |
| --- | --- | --- |
| Entry and exit | T=20, H=10, V=3; r0=(20,0,0), w=(−2,0,0) | One interval (5,15), both boundaries open; 3D/XY minimum 0 at t=10. |
| Exact vertical equality | Same XY, but rz=3 and wz=0 | No event: equality at V is safe. An event appears for V=3.048. |
| Zero relative velocity inside | T=20, H=10, V=3; r0=(5,0,0), w=0 | [0,20], initial_violation=true, continues_at_horizon=true. |
| Zero relative velocity at threshold | r0=(10,0,0), w=0, same thresholds | No event. |
| Threshold at t0, then entry | T=15, H=10, V=3; r0=(10,0,0), w=(−1,0,0) | (0,15], initial=false, end inclusive; at t=15 distance is 5, motion remains inside at the horizon. |
| Entry only after horizon | T=10, H=10, V=3; r0=(20,0,0), w=(−1,0,0) | No event: only equality at T. |
| Inside at horizon | Previous case with T=15 | (10,15], continues_at_horizon=true. |
| Tangency | T=20, H=10, V=3; r0=(−10,10,0), w=(1,0,0) | No event: minimum XY=10 at t=10. |
| Stress without actual violation | Objects moving together, d_h=110, dz=0, H=100; each e_h0=10 | Nominal: none. Stress: possible loss of guarantee, H_eff=120. |

For the real source data, an independent root calculation at nominal/H=9260 found 3 unique pairs at V=300 and 24 at V=304.8, without pair violations at t0. These are reference results, not fitting targets. The three metric intervals are: F018/F034 `(422.552354175,1200]`, F020/F038 `(280.313481630,311.964821195)`, F030/F039 `(1143.506224271,1200]`. All aircraft vertical coordinates are multiples of 300 m, so changing 300→304.8 includes pairs with an altitude difference of exactly 300 m and substantially changes the event count. This is a significant property of the data and strict inequality, not numerical error. The separate analyzer must provide full counts for all types/modes; this document does not replace its report.

## Data contract for analyzer and UI

`DATA={duration_s,scenario,flights,rules,analysis}`. `rules.schema_version` and `analysis.schema_version` are strings `"1.1"`. Version 1.1 introduces a spherical target, its center altitude and corresponding 3D metrics. `analysis.runs[]` contains exactly 20 combinations. Input coordinates and velocities remain their original numerical values. The analyzer reads the configuration; the UI reads precomputed events and calculates positions with the same formula, rather than detecting events from pixels or frames. The final machine contract is defined separately in `docs/contracts.md`; definitions below specify required semantics.

A run has: `id`, `profile_id`, `mode_id`, `variant_id`, `thresholds`, `events`, `summary`, `initial_state`, `motion_checks`. The proposed ID is `profile_id__mode_id__variant_id`. Run threshold values reflect the actual selected parameters and overrides, without changing rules. Each object's error comes from the selected mode.

An event has: `id`, `type` from `aircraft_aircraft/aircraft_threat/aircraft_target/altitude/motion`, `participants` (aircraft IDs and, where needed, `THREAT`/`TARGET`), `flight_ids` (aircraft only), selected `profile_id/mode_id/variant_id`, `start_s/end_s`, `start_inclusive/end_inclusive`, `initial_violation`, `continues_at_horizon`, `severity`, `metrics`, `thresholds`, `representative_s`. For altitude/motion, `constraint` may identify the violated constraint. Events are maximal connected intervals of violation of one rule/participant set, with separate intervals where a safe gap exists.

`severity=nominal_violation` means a nominal-model violation; `possible_violation` means loss of guarantee in stress mode (including sphere conservatism). All stress events are labeled alike even where the nominal trajectory also violates the rule; comparison with a nominal run is available separately.

Threshold equality defines an open boundary. At t0/T, a boundary is closed only if the strict violation predicate actually holds there. `initial_violation` means the violation predicate holds at t0, not merely `start_s==0`. `continues_at_horizon` means the event is active at T and limited by the analysis endpoint; continuation beyond T is unchecked. An open boundary at time zero is not an initial violation.

`metrics` contains minima of **nominal geometric distances** on the interval closure: `horizontal_min`, `vertical_min`, `distance_3d_min`, where applicable, in the format `{value_m,time_s,attained}`. All three metrics are defined for the target relative to its 3D center. If the minimum occurs only at an excluded boundary, `attained=false`: this is the event's infimum. If a metric is constant on the interval, choose `representative_s` and `attained=true`; otherwise use the minimizer on the closure with the corresponding `attained`. Inapplicable metrics are absent or null according to the final contract. Minima of different components may occur at different times and do not prove simultaneous violation. `representative_s` is an interior point for UI navigation, usually the midpoint; it is not necessarily the time of all minima.

`event.thresholds` stores effective thresholds in affine form `{intercept_m,slope_mps}` in absolute time from t0: `horizontal`, `vertical` for a pair, `radius` for zones. For altitude, use scenario bounds and e_z; for motion, the measured value/interval and corresponding limit. Do not record only the threshold at representative_s and then mistakenly apply it throughout the event.

`summary` distinguishes event count, unique aircraft pair count, affected aircraft count, `counts_by_type` and initial event count. Multiple intervals for one pair mean multiple events and one unique pair. THREAT and TARGET are not counted as aircraft or aircraft pairs. `initial_state` reports the selected run's t0 violations separately from future ones; `motion_checks` reports nominal speed magnitude or the stress speed interval, vz interval, zero accelerations/turn rate and check results. A positive event count is not proof that a future planning problem is infeasible.

## Limits of conclusions and future questions

All parameters needed for the current source analysis have been selected; unknown source information is explicitly left unknown. There are no blocking questions for this stage. Selecting admissible maneuvers, joint dynamic feasibility, the criterion for returning to the destination, time/route margins and optimization priorities belong to a future planner. Until it exists, do not claim safety has been achieved, present the baseline as a safe route or promise to eliminate initial violations. The absence of nominal events proves only compliance with our source-model rules; the absence of bounded_stress events gives a sufficient guarantee only within the declared bounds, kinematics and geometry.
