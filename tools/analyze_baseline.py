#!/usr/bin/env python3
"""Generate independent baseline reports from any current working directory."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airspace.analysis import analyze_all, load_inputs, load_rules, write_reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "scenario.json")
    parser.add_argument("--rules", type=Path, default=ROOT / "rules.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    try:
        scenario, flights = load_inputs(args.scenario)
        analysis = analyze_all(scenario, flights, load_rules(args.rules))
        write_reports(analysis, args.output_dir)
    except (ValueError, OSError) as exc:
        parser.exit(2, "Analysis failed: %s\n" % exc)
    print("Wrote %d runs to %s" % (len(analysis["runs"]), args.output_dir.resolve()))


if __name__ == "__main__":
    main()
