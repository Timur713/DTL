#!/usr/bin/env python3
"""Generate an F020 climb/hold/return API example; conflict safety is unchecked."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airspace.analysis import load_inputs, load_rules
from airspace.vertical import VerticalSegment, VerticalTrajectory


def build_example(scenario, flights, rules):
    """An illustrative schedule, not a search for a conflict-free maneuver."""
    flight = next((f for f in flights if f["flight_id"] == "F020"), None)
    if flight is None:
        raise ValueError("The example requires source flight F020")
    if flight["vz_mps"] != 0:
        raise ValueError("The example requires initial level flight")
    acceleration = rules["motion_limits"]["aircraft"]["vertical_acceleration_abs_max_mps2"]
    # Four 20 s ramps at the configured acceleration; 100 s elevated hold.
    # The default case gains 200 m with peak |vz|=10 m/s, then returns.
    scheduled = 100 + 4 * 20 + 100
    remaining = rules["duration_s"] - scheduled
    if remaining <= 0:
        raise ValueError("Example horizon must exceed 280 s")
    if acceleration <= 0:
        raise ValueError("The example requires positive vertical acceleration")
    segments = [VerticalSegment(duration, az) for duration, az in (
        (100, 0), (20, acceleration), (20, -acceleration), (100, 0),
        (20, -acceleration), (20, acceleration), (remaining, 0))]
    return VerticalTrajectory(flight, segments, scenario, rules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "scenario.json")
    parser.add_argument("--rules", type=Path, default=ROOT / "rules.json")
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "F020_vertical.json")
    args = parser.parse_args()
    try:
        scenario, flights = load_inputs(args.scenario)
        trajectory = build_example(scenario, flights, load_rules(args.rules))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(trajectory.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Example failed: {exc}\n")
    print(f"Wrote {trajectory.flight_id} to {args.output.resolve()}; conflict safety NOT checked")


if __name__ == "__main__":
    main()
