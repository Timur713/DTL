#!/usr/bin/env python3
"""Recompute the analysis/reports and generate the self-contained offline viewer."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airspace.analysis import analyze_all, load_inputs, load_rules, write_reports


def load_data(scenario_path, duration_s=1200):
    """Read the unchanged source states through the independent analysis loader."""
    scenario, flights = load_inputs(scenario_path)
    return dict(duration_s=duration_s, scenario=scenario, flights=flights)


def generate(scenario_path, output_path, rules_path=ROOT / 'rules.json',
             reports_dir=ROOT / 'reports'):
    scenario_path, rules_path = Path(scenario_path), Path(rules_path)
    rules = load_rules(rules_path)
    data = load_data(scenario_path, rules['duration_s'])
    analysis = analyze_all(data['scenario'], data['flights'], rules)
    write_reports(analysis, reports_dir)
    data.update(rules=rules, analysis=analysis)
    source_paths = {
        'scenario': scenario_path,
        'flights': scenario_path.parent / data['scenario']['flights_file'],
        'rules': rules_path,
    }
    data['source_sha256'] = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in source_paths.items()
    }
    template = (ROOT / 'tools' / 'baseline.template.html').read_text(encoding='utf-8')
    if template.count('__BASELINE_DATA__') != 1:
        raise ValueError('The HTML template must contain exactly one data placeholder.')
    # Escape HTML script delimiters even if future source IDs contain markup.
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=output_path.parent, suffix='.html.tmp',
                                         delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(template.replace('__BASELINE_DATA__', payload))
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return len(data['flights'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', type=Path, default=ROOT / 'scenario.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'baseline.html')
    parser.add_argument('--rules', type=Path, default=ROOT / 'rules.json')
    parser.add_argument('--reports-dir', type=Path, default=ROOT / 'reports')
    args = parser.parse_args()
    count = generate(args.scenario, args.output, args.rules, args.reports_dir)
    print(f'Created {args.output.resolve()} — {count} flights; '
          f'fresh analysis and reports: {args.reports_dir.resolve()}')


if __name__ == '__main__':
    main()
