# Safe rerouting under a moving threat

**Email review:** [six-file compact package](DTL_email.zip), or open
[START_HERE.html](email_delivery/START_HERE.html). It starts on the safe plan,
with three guided comparisons. Full project: [GitHub](https://github.com/Timur713/DTL).

**Review route:** this page → [approach and task requirements](docs/submission.md)
→ [selected evidence](submission/README.md). For code review or an automated agent,
start with the [repository map](docs/README.md) and [AGENTS.md](AGENTS.md).

Forty aircraft share a local Cartesian airspace with a drone flying toward a ground
target. We simulate **1200 s (20 minutes)**. Aircraft remain present and keep their
original horizontal velocities; continuous vertical maneuvers resolve conflicts
while keeping them close to their original endpoints. The drone continues past
the target. The source snapshot and scenario are unchanged.

**Rules and rationale.** Aircraft separation is **9260 m horizontally OR 300 m
vertically**: a conditional 5 NM aviation reference and an explicit metric
convention, not a regulatory-compliance claim. Drone and target exclusions are
**5000 m spheres**, choosing the task's permitted 3D interpretation and a
several-kilometre buffer. Target altitude is assumed zero. Aircraft altitude is
**3000–12000 m**, horizontal speed 200–260 m/s, vertical speed ≤15 m/s and vertical
acceleration ≤0.5 m/s². Equality is allowed. Shared [rules.json](rules.json),
[sources and assumptions](docs/model.md) define the model; the XY box is a display
region. Generic motion limits are assumptions rather than aircraft-specific data.

**Result.** The [compact viewer](email_delivery/START_HERE.html) opens on the
submitted solution; [baseline.html](baseline.html) retains the full research UI.
All 40 aircraft pass continuous nominal verification: **12 original
events → 0 violations, 0 unresolved checks**, including all **780 pairs**.
Every aircraft ends with zero vertical speed. Maximum/total original-endpoint
deviation is **150/600 m**, attaining independently proved lower bounds under
fixed horizontal motion. Maximum temporary excursion is 6150 m; geometric analysis
shows at least 5679.45 m is necessary for one aircraft. Other maneuver costs remain
bounded-search results. Seven Pareto objectives expose trade-offs without relying
on the experimental weighted score.

**Deliverables.** [Trajectory CSV](submission/trajectories.csv) has **48,040 rows**
for all aircraft at 1 s intervals plus every segment join. [Segments](submission/segments.json)
are authoritative; [verification](submission/verification.json), [quality](submission/quality.json),
[proofs and sensitivity](submission/evidence.json), and [file hashes](submission/manifest.json)
provide evidence. [Submission guide](docs/submission.md) maps each task requirement
to its artifact and explains the approach. The viewer is self-contained and offline.

**Reproduce** with Python 3.9+ and the standard library:

```sh
python3 tools/build_email.py --github-url https://github.com/Timur713/DTL
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The first command rechecks the saved selected plan and creates the six-file
`DTL_email.zip`, including the compact offline viewer. It does not rerun searches. Full search
and browser-test commands are in the [submission guide](docs/submission.md).

**Limits.** Exact states, point aircraft, local flat geometry, no wind or execution
delays; no aircraft-specific aerodynamics, landing or guarantee after 1200 s.
Nominal safety is sensitive to threshold equality: opposing 1 m terminal altitude
errors can reduce separation from 300 to 298 m; a separate 304.8 m threshold check
finds 16 events. Baseline uncertainty comparisons remain available, but do not
certify uncertain maneuver execution. Historical experiments are preserved in the
[historical project guide](docs/project-guide.md).
