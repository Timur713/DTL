# Safe passage — approach, results and next steps

**The problem and chosen rules.** Forty aircraft must keep flying for 20 minutes
while avoiding each other, a moving drone and a ground target. I reviewed
[FAA](https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap5_section_5.html)/[ICAO](https://store.icao.int/en/manual-on-implementation-vertical-separation-doc-9574)
separation references and EUROCONTROL/NASA work on conflict detection. I chose
9260 m horizontal OR 300 m vertical separation. The 300 m value is our metric
convention; 304.8 m is checked separately. The drone and target each have a 5 km
protected sphere; target altitude is assumed zero. These choices define a research
model, not a certified aviation system.

Aircraft stay at 3000–12000 m. Limits are 200–260 m/s horizontal speed, 15 m/s
vertical speed and 0.5 m/s² vertical acceleration. Equality is allowed. The planner
and independent checker both use rules.json.

**Start simple and make the problem visible.** The original routes have 12 conflict
events. I first allowed altitude changes only: X and Y follow the original routes,
while Z changes smoothly. This preserves forward progress and makes safety easier
to check. No aircraft is removed or teleported.

**Define what a better solution means.** I tested a weighted score,
`J = Σₖ wₖ mₖ/sₖ`, combining several costs. Its result depended too much on the
chosen weights and scales. I kept it as an experiment and compared seven measures
separately, including final-position error, climb size and total vertical travel.
This shows the trade-offs instead of hiding them in one number.

**Find a bound, then reach it.** Two separate pairs need 300 m vertical separation
at 20:00. Splitting that into −150 m and +150 m gives the smallest possible largest
end-position error: **150 m**, with **600 m total** across the fleet. The submitted
plan reaches both bounds when horizontal routes are fixed. It is not optimal in
every other measure: 15 aircraft maneuver, the largest altitude change is 6150 m,
and total vertical travel is 60.6 km.

**Check the whole flight.** A separate checker tests all 780 pairs, both spheres,
motion limits and segment joins continuously, including between animation frames.
Result: **40 aircraft, zero nominal violations, zero unresolved checks**. Every
aircraft finishes with zero vertical speed.

**What I would do next.** Allow turns and horizontal speed changes to see whether
flying around the drone reduces large climbs. Improve the scoring formula using
clear priorities for extra time, altitude change and maneuver smoothness. Add
safety margins for measurement errors and execution delays, then recheck the
whole flight.

**Limits.** The result assumes exact states and execution, point aircraft, flat
geometry, no wind or delays. Opposing 1 m altitude errors can reduce a binding
300 m separation to 298 m. No landing, safety after 20 minutes or overall global
optimum is claimed.

**Open START_HERE.html after extracting the ZIP.** It opens on “The endpoint
result” and works offline. trajectories.csv has 48,040 rows;
segments.json holds the controls; verification.json holds evidence and hashes.

Full source, independent checker, tests and search experiments: https://github.com/Timur713/DTL
