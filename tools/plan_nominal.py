#!/usr/bin/env python3
"""Plan, independently verify and export the nominal fleet (no HTML changes)."""
import argparse
import csv
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from airspace.analysis import load_inputs, load_rules
from airspace.checker import ContinuousChecker, at, fingerprint, number
from airspace.polynomial import derivative
from airspace.planner import plan_fleet


def write_outputs(plan, scenario, flights, rules, output, sample_step_s=1):
    if type(sample_step_s) is not int or sample_step_s < 1:
        raise ValueError("sample_step_s must be a positive integer")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fleet = plan["trajectories"]
    authoritative = dict(schema_version="1.0", model="nominal_vertical_fleet", profile_id="metric",
                         mode_id="nominal", variant_id="base", duration_s=rules["duration_s"],
                         trajectories=fleet, source_sha256=fingerprint(dict(scenario=scenario, flights=flights, rules=rules)))
    text = json.dumps(authoritative, indent=2, sort_keys=True, allow_nan=False) + "\n"
    (output / "segments.json").write_text(text, encoding="utf-8")
    # Verify the actual JSON bytes that downstream consumers will load, using a
    # new checker with no search caches; CSV sampling cannot affect this result.
    loaded = json.loads((output / "segments.json").read_text(encoding="utf-8"))
    checker = ContinuousChecker(scenario, flights, rules)
    verification = checker.verify_document(loaded)
    verification["segments_file_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    compiled = {d["flight_id"]: checker.compile(d) for d in loaded["trajectories"]}
    horizon = number(rules["duration_s"], "horizon")
    times = [Q(t) for t in range(0, int(horizon)+1, sample_step_s)]
    if times[-1] != horizon:
        times.append(horizon)
    with (output / "trajectories.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "flight_id", "x_m", "y_m", "alt_m", "vx_mps", "vy_mps", "vz_mps"])
        for time in times:
            for fid in sorted(compiled):
                trajectory = compiled[fid]
                piece = trajectory.piece_at(time)
                writer.writerow([float(time), fid, float(at(trajectory.x, time)), float(at(trajectory.y, time)),
                    float(at(piece.z, time)), float(at(derivative(trajectory.x), time)),
                    float(at(derivative(trajectory.y), time)), float(at(derivative(piece.z), time))])
    destinations = []
    sources = {f["flight_id"]: f for f in flights}
    for fid, trajectory in sorted(compiled.items()):
        f = sources[fid]
        destination_z = number(f["alt_m"], "z")+number(f["vz_mps"], "vz")*horizon
        dz = at(trajectory.piece_at(horizon).z, horizon)-destination_z
        destinations.append(dict(flight_id=fid, terminal_altitude_m=float(at(trajectory.piece_at(horizon).z, horizon)),
                                 terminal_altitude_deviation_m=float(dz), horizontal_destination_distance_m=0,
                                 remaining_destination_distance_m=float(abs(dz))))
    verification["destinations"] = destinations
    verification["sampled_csv"] = dict(step_s=sample_step_s, rows=len(times)*len(fleet), establishes_safety=False)
    for name, content in (("verification.json", verification), ("baseline_verification.json", plan["initial_verification"]),
                          ("search.json", plan["search"])):
        (output / name).write_text(json.dumps(content, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    changed = sorted({r["flight_id"] for r in plan["search"]["accepted_repairs"]})
    deviations = [d for d in destinations if d["remaining_destination_distance_m"]]
    lines = ["# Nominal vertical planning result", "",
        f"Status: **{'verified_safe' if verification['verified_safe'] else 'bounded_search_incomplete'}**.", "",
        f"All {len(fleet)} aircraft retained over [0, {rules['duration_s']}] s; metric / nominal / base rules unchanged.",
        f"Initial baseline: {plan['initial_verification']['violation_count']} violations; final: {verification['violation_count']} violations and {verification['unresolved_count']} unresolved checks.",
        f"Independent final checks: {verification['pair_checks']} aircraft pairs and {verification['aircraft_checks']} full-horizon aircraft motion/altitude/zone checks.",
        f"Search: {plan['search']['candidate_attempts']} candidate attempts, {len(plan['search']['accepted_repairs'])} accepted repairs; stop reason: {plan['search']['stop_reason']}.",
        f"Changed aircraft: {', '.join(changed) or 'none'}.", "", "## Terminal destinations", "",
        "Original horizontal motion is retained. Remaining distance is spatial distance to the original t=T endpoint, not an arrival-delay estimate.", "",
        "| Aircraft | Terminal altitude deviation (m) | Remaining destination distance (m) |", "| --- | ---: | ---: |"]
    lines.extend(f"| {d['flight_id']} | {d['terminal_altitude_deviation_m']:.6f} | {d['remaining_destination_distance_m']:.6f} |" for d in deviations)
    if not deviations:
        lines.append("| All aircraft | 0 | 0 |")
    lines += ["", "## Verification and limitations", "",
        "Authoritative controls: segments.json. Continuous sign checks use exact rational polynomial arithmetic and certified Sturm root isolation, including quartic sphere expressions. Sampling in trajectories.csv is diagnostic only.",
        "The final checker rereads segments.json independently of search caches. Any unresolved check prevents verified_safe. Numerical root brackets and rational witnesses are in verification.json.",
        "The deterministic search is bounded and prioritizes feasibility. It is neither exhaustive nor globally optimal. A failed search does not prove infeasibility. Only nominal kinematics are covered; bounded stress, aerodynamics and real-world certification are outside this result.",
        "No safety conclusion applies beyond the configured horizon. Baseline artifacts and HTML are not modified."]
    if verification["events"] or verification["unresolved"]:
        lines += ["", "## Remaining findings", ""]
        lines.extend(f"- {e['type']} {','.join(e['participants'])}: {e['start_s']:.9f}–{e['end_s']:.9f} s" for e in verification["events"])
        lines.extend(f"- Unresolved: {u}" for u in verification["unresolved"])
    (output / "summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return verification


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "scenario.json")
    parser.add_argument("--rules", type=Path, default=ROOT / "rules.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/planned")
    parser.add_argument("--max-candidates", type=int, default=20000)
    parser.add_argument("--max-repairs", type=int, default=40)
    parser.add_argument("--sample-step-s", type=int, default=1)
    args = parser.parse_args()
    try:
        scenario, flights = load_inputs(args.scenario)
        rules = load_rules(args.rules)
        if args.sample_step_s < 1:
            raise ValueError("sample-step-s must be positive")
        plan = plan_fleet(scenario, flights, rules, max_candidates=args.max_candidates, max_repairs=args.max_repairs,
                          progress=lambda trials, repairs, remaining, fid: print(
                              f"Repair {repairs}: {fid}; {remaining} events remain after {trials} candidates", flush=True))
        result = write_outputs(plan, scenario, flights, rules, args.output_dir, args.sample_step_s)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Planning failed: {exc}\n")
    print(f"{plan['search']['status']}: {result['aircraft_count']} aircraft, {result['violation_count']} violations, "
          f"{result['unresolved_count']} unresolved; outputs: {args.output_dir.resolve()}")
    return 0 if result["verified_safe"] else 1


if __name__ == "__main__":
    sys.exit(main())
