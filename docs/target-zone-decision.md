# Ground target zone decision

**Agreed:** the target zone is a sphere of radius **5000 m** centered at the target XY coordinates from `scenario.json`. Center altitude is assumed to be **0 m** in the scenario coordinate system; target altitude is absent from the inputs. The zone applies throughout the simulation horizon, from 0 to 1200 s.

In `nominal` mode, a violation is defined by the strict condition:

```text
(x - x_target)^2 + (y - y_target)^2 + z^2 < 5000^2
```

Equality at the threshold is allowed.

**Rationale:** the task permits a three-dimensional zone around the target. A sphere defines a minimum spatial distance to a ground object and accounts for aircraft altitude. The 5 km radius is a working scenario assumption, not a regulatory distance or a physically verified damage radius. Its effect should be assessed through sensitivity analysis.

**Implementation status:** the sphere is integrated into `rules.json`, the analyzer and HTML; reports have been regenerated. Center altitude is specified by `zones.target.center_alt_m=0`. In the additional `bounded_stress` mode, the radius is conservatively expanded by the aircraft's `e_h+e_z`; the target is exact. The 300 m aircraft separation rule and selected `nominal` mode are retained. Formulas and data format are in [model.md](model.md) and [contracts.md](contracts.md).
