#!/usr/bin/env python3
"""Verify and export the selected solution; optionally rebuild HTML and package it."""
import argparse
import csv
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airspace.analysis import _keys, _read_json, load_inputs, load_rules
from airspace.checker import ContinuousChecker, fingerprint, number
from airspace.endpoint_bounds import endpoint_bounds, endpoint_gaps
from airspace.evidence import endpoint_error_witnesses, sphere_excursion_bounds, vertical_reference_sensitivity
from airspace.polynomial import at, derivative
from airspace.quality import QualityEvaluator, interval


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_config(config):
    _keys(config, ('schema_version', 'selection', 'tie_break_objectives', 'sample_step_s',
        'include_all_segment_joins', 'endpoint_altitude_error_probe_m', 'vertical_reference_sensitivity'), path='submission config')
    if config['schema_version'] != '1.0' or config['selection'] != 'attain_both_endpoint_bounds_then_lexicographic':
        raise ValueError('Unsupported submission selection')
    expected = ['max_altitude_excursion_m', 'accumulated_altitude_deviation_m_s', 'vertical_travel_m',
                'changed_aircraft_count', 'reversal_count']
    if config['tie_break_objectives'] != expected:
        raise ValueError('Unsupported tie-break policy')
    if type(config['sample_step_s']) is not int or config['sample_step_s'] < 1:
        raise ValueError('Sample step must be a positive integer')
    if config['include_all_segment_joins'] is not True or config['vertical_reference_sensitivity'] is not True:
        raise ValueError('Submission requires joins and reference sensitivity')
    if number(config['endpoint_altitude_error_probe_m'], 'error probe') <= 0:
        raise ValueError('Error probe must be positive')


def choose_entry(catalog, bounds, config):
    candidates = []
    for entry in catalog['entries']:
        quality = entry['quality']
        if all(interval(quality, key) == (Q(str(bounds[bound])),)*2 for key, bound in (
                ('max_endpoint_deviation_m', 'max_endpoint_deviation_lower_bound_m'),
                ('total_endpoint_deviation_m', 'total_endpoint_deviation_lower_bound_m'))):
            candidates.append(entry)
    if not candidates:
        raise ValueError('No saved candidate attains both certified endpoint bounds')
    return min(candidates, key=lambda e: tuple(interval(e['quality'], key) for key in config['tie_break_objectives'])+(e['id'],))


def export_trajectories(output, document, scenario, flights, rules, step):
    checker = ContinuousChecker(scenario, flights, rules)
    fleet = sorted((checker.compile(d) for d in document['trajectories']), key=lambda t: t.flight_id)
    times = {Q(t) for t in range(0, int(checker.horizon)+1, step)} | {checker.horizon}
    times.update(p.start for t in fleet for p in t.pieces)
    times.update(p.end for t in fleet for p in t.pieces)
    with (output/'trajectories.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['time_s', 'flight_id', 'x_m', 'y_m', 'alt_m', 'vx_mps', 'vy_mps', 'vz_mps', 'az_mps2', 'time_exact_s'])
        for time in sorted(times):
            for trajectory in fleet:
                piece = trajectory.piece_at(time)
                values = [at(trajectory.x, time), at(trajectory.y, time), at(piece.z, time),
                          at(derivative(trajectory.x), time), at(derivative(trajectory.y), time),
                          at(derivative(piece.z), time), piece.az]
                writer.writerow([float(time), trajectory.flight_id, *map(float, values), str(time)])
    with (output/'maneuvers.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['flight_id', 'start_s', 'end_s', 'az_mps2', 'start_alt_m', 'end_alt_m', 'start_vz_mps', 'end_vz_mps'])
        for trajectory in fleet:
            for piece in trajectory.pieces:
                writer.writerow([trajectory.flight_id, float(piece.start), float(piece.end), float(piece.az),
                    float(at(piece.z, piece.start)), float(at(piece.z, piece.end)),
                    float(at(derivative(piece.z), piece.start)), float(at(derivative(piece.z), piece.end))])
    return dict(rows=len(times)*len(fleet), aircraft_count=len(fleet), time_count=len(times),
                step_s=step, all_segment_joins_included=True, establishes_safety=False,
                interpretation='Diagnostic samples plus all joins; segments.json and continuous verification are authoritative.')


def build(output=ROOT/'submission', catalog_dir=ROOT/'reports/improved_second'):
    output, catalog_dir = Path(output).resolve(), Path(catalog_dir).resolve()
    for protected in (ROOT, ROOT/'reports', ROOT/'airspace', ROOT/'tools', ROOT/'docs', ROOT/'tests', ROOT/'experiments', ROOT/'examples'):
        if output == protected or output in protected.parents or (protected != ROOT and protected in output.parents):
            raise ValueError('Output must be a separate delivery directory')
    scenario, flights = load_inputs(ROOT/'scenario.json')
    rules = load_rules(ROOT/'rules.json')
    config = _read_json(ROOT/'experiments/submission.json')
    validate_config(config)
    catalog = _read_json(catalog_dir/'catalog.json')
    bounds = endpoint_bounds(scenario, flights, rules)
    if catalog.get('schema_version') != '2.0' or catalog.get('source_sha256') != bounds['source_sha256']:
        raise ValueError('Stale or unsupported source catalog')
    entry = choose_entry(catalog, bounds, config)
    source = (catalog_dir/entry['segments_file']).resolve()
    if catalog_dir not in source.parents or sha(source) != entry['segments_sha256']:
        raise ValueError('Selected trajectory path/checksum mismatch')
    document = _read_json(source)
    verification = ContinuousChecker(scenario, flights, rules).verify_document(document)
    quality = QualityEvaluator(scenario, flights, rules).evaluate(document['trajectories'])
    if not verification['verified_safe'] or not quality['terminal_vertical_speed_zero'] or quality != entry['quality']:
        raise ValueError('Selected solution failed fresh verification or quality recomputation')
    excursion = sphere_excursion_bounds(scenario, flights, rules)
    perturbation = endpoint_error_witnesses(document, scenario, flights, rules, config['endpoint_altitude_error_probe_m'])
    sensitivity = vertical_reference_sensitivity(document, scenario, flights, rules)
    output.mkdir(parents=True, exist_ok=True)
    (output/'segments.json').write_bytes(source.read_bytes())
    for name in ('rules.json', 'scenario.json', 'flights.csv'):
        (output/name).write_bytes((ROOT/name).read_bytes())
    write_json(output/'verification.json', verification)
    write_json(output/'quality.json', quality)
    write_json(output/'endpoint_bounds.json', bounds)
    write_json(output/'excursion_bounds.json', excursion)
    write_json(output/'endpoint_error_probe.json', perturbation)
    write_json(output/'vertical_reference_sensitivity.json', sensitivity)
    sampled = export_trajectories(output, document, scenario, flights, rules, config['sample_step_s'])
    base = _read_json(ROOT/'reports/planned/baseline_verification.json')
    result = dict(schema_version='1.0', selected_id=entry['id'], selection=config,
        selection_scope='Best saved endpoint-bound-attaining candidate under the documented tie-break policy; other objectives not globally optimal.',
        source_sha256=bounds['source_sha256'], segments_sha256=sha(output/'segments.json'),
        input_file_sha256={name:sha(ROOT/name) for name in ('scenario.json', 'flights.csv', 'rules.json', 'Task1_details.pdf')},
        catalog_sha256=sha(catalog_dir/'catalog.json'), quality=quality,
        verification=verification, original_baseline_event_count=base['violation_count'],
        endpoint_bounds=bounds, endpoint_gaps_m=endpoint_gaps(quality, bounds),
        excursion_bounds=excursion, endpoint_error_probe=perturbation,
        vertical_reference_sensitivity=dict(vertical_m=sensitivity['verification']['thresholds']['vertical_m'],
            violation_count=sensitivity['verification']['violation_count'],
            unresolved_count=sensitivity['verification']['unresolved_count'],
            counts_by_type=sensitivity['verification']['counts_by_type']),
        sampled_csv=sampled,
        scope=dict(profile_id='metric', mode_id='nominal', variant_id='base', duration_s=rules['duration_s'],
            airport_arrival=False, safety_after_horizon=False, bounded_stress_verified=False,
            maximum_excursion_globally_optimal=False, endpoint_metrics_globally_optimal_under_fixed_XY=True))
    write_json(output/'evidence.json', result)
    write_summary(output, result)
    names = ['segments.json', 'rules.json', 'scenario.json', 'flights.csv', 'verification.json', 'quality.json',
             'endpoint_bounds.json', 'excursion_bounds.json', 'endpoint_error_probe.json',
             'vertical_reference_sensitivity.json', 'trajectories.csv', 'maneuvers.csv', 'evidence.json', 'README.md']
    write_json(output/'manifest.json', dict(schema_version='1.0', selected_id=entry['id'],
        files={name:sha(output/name) for name in names}))
    return result


def write_summary(output, evidence):
    q, v = evidence['quality'], evidence['verification']
    w = evidence['excursion_bounds']['strongest']
    text = f'''# Selected submission: safe nominal rerouting

Forty aircraft retain their horizontal routes over 1200 s. Safety means horizontal
separation >=9260 m OR vertical separation >=300 m, exclusion from the drone and
ground-target spheres (radius 5000 m), and altitude 3000–12000 m. These are stated
research assumptions. Point aircraft, exact states, no delays or wind; the drone
continues beyond the target. Generic motion limits come from the unchanged rules.

**Selected plan: `{evidence['selected_id']}`.** Open [the offline viewer](../baseline.html)
and choose **Show recommended plan**. Every aircraft remains present, with continuous
position/velocity, original horizontal motion and zero final vertical speed.

| Result | Value |
| --- | ---: |
| Nominal violations / unresolved checks | {v['violation_count']} / {v['unresolved_count']} |
| Complete pair checks | {v['pair_checks']} |
| Maximum / total original-endpoint deviation | {q['max_endpoint_deviation_m']:g} / {q['total_endpoint_deviation_m']:g} m |
| Maximum temporary altitude excursion | {q['max_altitude_excursion_m']:g} m |
| Accumulated altitude deviation | {q['accumulated_altitude_deviation_m_s']:g} m·s |
| Vertical travel / changed aircraft / reversals | {q['vertical_travel_m']:g} m / {q['changed_aircraft_count']} / {q['reversal_count']} |

Two disjoint terminal-conflict pairs require at least 300 m relative displacement
each: total deviation >=600 m and maximum individual deviation >=150 m. The
selected plan attains both necessary bounds, proving those two metrics optimal
**under fixed horizontal motion**, not global trajectory optimality. We use seven
Pareto objectives rather than a fitted weighted score; other trade-offs remain
available in the viewer.

Large climbs have a geometric cause: at horizontal closest approach, {w['flight_id']}
must clear the sphere above the altitude floor, requiring at least
{w['excursion_lower_m']:.3f} m excursion. This is a lower bound, not a complete solution.
The endpoint-optimal plan also has no positive uniform altitude-error guarantee:
opposing 1 m errors can reduce a binding 300 m separation to 298 m. The separate
{evidence['vertical_reference_sensitivity']['vertical_m']:g} m threshold recheck finds
{evidence['vertical_reference_sensitivity']['violation_count']} events. Neither experiment changes the primary rules.

**Data:** `trajectories.csv` contains {evidence['sampled_csv']['rows']:,} rows for all
40 aircraft at 1 s intervals plus every segment join. `segments.json` is
authoritative; `maneuvers.csv` lists acceleration segments. `rules.json` is shared
by planner/checker; its affine-motion metadata describes the baseline, while the
serialized segment model explicitly defines maneuver dynamics. `verification.json`
uses exact rational polynomial sign decomposition, including quartic sphere
distances; samples alone never establish safety. `manifest.json` records hashes.

**Reproduce from the project root:** `python3 tools/build_submission.py --html --package`.
This verifies/exports the saved solution and packages the project without rerunning
search. Full search commands and reasoning: [submission guide](../docs/submission.md).
No landing, post-horizon, aircraft-specific performance or bounded-stress safety is
claimed. Equality is safe by definition; robustness needs a different objective.
'''
    (output/'README.md').write_text(text, encoding='utf-8')


def package_project(path=ROOT/'DTL_submission.zip'):
    """Deterministic archive of the explicit project deliverable directories."""
    candidates = [ROOT/name for name in ('README.md', 'AGENTS.md', '.gitignore', 'rules.json', 'scenario.json',
                  'flights.csv', 'Task1_details.pdf', 'baseline.html')]
    for directory in ('airspace', 'tools', 'tests', 'docs', 'reports', 'experiments', 'examples', 'submission'):
        candidates.extend(p for p in (ROOT/directory).rglob('*') if p.is_file()
                          and '__pycache__' not in p.parts and p.name != '.DS_Store' and p.suffix != '.pyc')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(candidates):
            if not file.is_file():
                continue
            info = zipfile.ZipInfo(str(file.relative_to(ROOT)), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, file.read_bytes())
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'submission')
    parser.add_argument('--catalog-dir', type=Path, default=ROOT/'reports/improved_second')
    parser.add_argument('--html', action='store_true', help='Regenerate the offline viewer after exporting')
    parser.add_argument('--package', action='store_true', help='Create DTL_submission.zip after export; implies --html')
    args = parser.parse_args()
    try:
        if (args.html or args.package) and (args.output_dir.resolve() != ROOT/'submission' or args.catalog_dir.resolve() != ROOT/'reports/improved_second'):
            raise ValueError('--html/--package require default output/catalog paths')
        result = build(args.output_dir, args.catalog_dir)
        if args.html or args.package:
            from tools.generate_baseline import generate
            generate(ROOT/'scenario.json', ROOT/'baseline.html')
        if args.package:
            print('Packaged', package_project())
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc)+'\n')
    print(f"Selected {result['selected_id']}: verified safe; {result['sampled_csv']['rows']} trajectory rows. Output: {args.output_dir.resolve()}")


if __name__ == '__main__':
    main()
