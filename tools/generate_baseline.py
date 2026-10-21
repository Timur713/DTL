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
from airspace.replay import prepare_replay
from airspace.alternatives import prepare_alternatives, merge_second_pass
from airspace.analysis import _read_json


def load_data(scenario_path, duration_s=1200):
    """Read the unchanged source states through the independent analysis loader."""
    scenario, flights = load_inputs(scenario_path)
    return dict(duration_s=duration_s, scenario=scenario, flights=flights)


def generate(scenario_path, output_path, rules_path=ROOT / 'rules.json',
             reports_dir=ROOT / 'reports', planned_dir=ROOT / 'reports' / 'planned',
             improved_dir=ROOT / 'reports' / 'improved', score_config=ROOT / 'experiments' / 'quality_score.json',
             second_dir=ROOT / 'reports' / 'improved_second'):
    scenario_path, rules_path = Path(scenario_path), Path(rules_path)
    rules = load_rules(rules_path)
    data = load_data(scenario_path, rules['duration_s'])
    analysis = analyze_all(data['scenario'], data['flights'], rules)
    data.update(rules=rules, analysis=analysis)
    if planned_dir is not None:
        data['planning'] = prepare_replay(data['scenario'], data['flights'], rules, planned_dir)
        if improved_dir is not None:
            data['quality_alternatives'] = prepare_alternatives(data['scenario'], data['flights'], rules,
                planned_dir, improved_dir, _read_json(score_config))
            if second_dir is not None:
                data['quality_alternatives'] = merge_second_pass(data['quality_alternatives'], data['scenario'], data['flights'], rules,
                    planned_dir, improved_dir, second_dir, _read_json(score_config))
    write_reports(analysis, reports_dir)
    if planned_dir is not None:
        (Path(reports_dir) / 'replay.json').write_text(
            json.dumps(data['planning'], indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
    if 'quality_alternatives' in data:
        (Path(reports_dir) / 'quality_ui.json').write_text(json.dumps(data['quality_alternatives'], indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
    delivery = ROOT / 'submission'
    if second_dir is not None and 'quality_alternatives' in data and (delivery / 'evidence.json').exists():
        evidence = _read_json(delivery / 'evidence.json')
        manifest = _read_json(delivery / 'manifest.json')
        for name, expected in manifest['files'].items():
            path = (delivery / name).resolve()
            if delivery.resolve() not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('Submission checksum mismatch; rerun tools/build_submission.py')
        selected = next((e for e in data['quality_alternatives']['entries'] if e['id'] == evidence['selected_id']), None)
        if selected is None or selected['quality'] != evidence['quality'] or selected['verification'] != evidence['verification'] or selected['segments_sha256'] != evidence['segments_sha256']:
            raise ValueError('Submission no longer matches the independently verified solution')
        for name in ('scenario.json', 'flights.csv', 'rules.json', 'Task1_details.pdf'):
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != evidence['input_file_sha256'][name]:
                raise ValueError('Submission inputs changed; rebuild delivery')
        data['submission'] = evidence
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
    if template.count('__COMPARISON_SCRIPT__') != 1:
        raise ValueError('The HTML template must contain exactly one comparison-script placeholder.')
    template = template.replace('__COMPARISON_SCRIPT__', (ROOT / 'tools' / 'comparison.js').read_text(encoding='utf-8')+'\n'+(ROOT / 'tools' / 'quality.js').read_text(encoding='utf-8')+'\n'+(ROOT / 'tools' / 'submission.js').read_text(encoding='utf-8'))
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
    parser.add_argument('--planned-dir', type=Path, default=ROOT / 'reports' / 'planned')
    parser.add_argument('--baseline-only', action='store_true', help='Omit saved plan/replay, e.g. for a different scenario')
    parser.add_argument('--improved-dir', type=Path, default=ROOT / 'reports' / 'improved')
    parser.add_argument('--reference-only', action='store_true', help='Omit quality alternatives, retain saved reference/replay')
    parser.add_argument('--second-dir', type=Path, default=ROOT / 'reports' / 'improved_second')
    parser.add_argument('--first-pass-only', action='store_true', help='Omit second-pass alternatives')
    args = parser.parse_args()
    count = generate(args.scenario, args.output, args.rules, args.reports_dir,
                     None if args.baseline_only else args.planned_dir,
                     None if args.reference_only else args.improved_dir, ROOT / 'experiments' / 'quality_score.json',
                     None if args.first_pass_only else args.second_dir)
    print(f'Created {args.output.resolve()} — {count} flights; '
          f'fresh analysis and reports: {args.reports_dir.resolve()}')


if __name__ == '__main__':
    main()
