#!/usr/bin/env python3
"""Build the six-file reviewer package and a standalone presentation viewer."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlparse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airspace.analysis import _read_json, load_inputs, load_rules
from airspace.checker import ContinuousChecker
from airspace.quality import QualityEvaluator
from airspace.replay import profile_data

FILES = ('START_HERE.html', 'README.md', 'trajectories.csv', 'rules.json', 'segments.json', 'verification.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_github_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or len(parsed.path.strip('/').split('/')) != 2 or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTPS GitHub repository URL: https://github.com/owner/repository')
    return value.rstrip('/')


def plotting_profile(definition, flight, scenario, rules):
    """Display samples, including exact-motion joins and horizontal sphere CPAs.

    Forbidden altitude bands are visualization only; the checker supplies all
    safety conclusions. Fixed XY means the same band applies to both schedules.
    """
    profile = profile_data(definition, flight, scenario, rules)
    times = set(profile['profile']['time_s'])
    horizon = rules['duration_s']
    objects = [dict(scenario['hostile_object'], radius_m=rules['zones']['threat']['radius_m']),
               dict(scenario['target'], alt_m=rules['zones']['target']['center_alt_m'],
                    vx_mps=0, vy_mps=0, vz_mps=0, radius_m=rules['zones']['target']['radius_m'])]
    for obj in objects:
        x, y = flight['x_m']-obj['x_m'], flight['y_m']-obj['y_m']
        vx, vy = flight['vx_mps']-obj['vx_mps'], flight['vy_mps']-obj['vy_mps']
        speed2 = vx*vx+vy*vy
        if speed2:
            cpa = -(x*vx+y*vy)/speed2
            times.add(min(horizon, max(0, cpa)))
            disc = (x*vx+y*vy)**2-speed2*(x*x+y*y-obj['radius_m']**2)
            if disc >= 0:
                for time in ((-(x*vx+y*vy)-math.sqrt(disc))/speed2,
                             (-(x*vx+y*vy)+math.sqrt(disc))/speed2):
                    if 0 <= time <= horizon:
                        times.add(time)
    ordered = sorted(times)
    bands = []
    for obj in objects:
        band = []
        for time in ordered:
            x = flight['x_m']+flight['vx_mps']*time-obj['x_m']-obj['vx_mps']*time
            y = flight['y_m']+flight['vy_mps']*time-obj['y_m']-obj['vy_mps']*time
            radicand = obj['radius_m']**2-x*x-y*y
            if radicand > 0:
                center = obj['alt_m']+obj['vz_mps']*time
                dz = math.sqrt(radicand)
                band.append([center-dz, center+dz])
            else:
                band.append(None)
        bands.append(band)
    # Use the separate public model for plotting, not sampled trajectory CSV.
    from airspace.vertical import VerticalTrajectory
    model = VerticalTrajectory.from_dict(definition, flight=flight, scenario=scenario, rules=rules)
    profile['profile'] = dict(time_s=ordered, alt_m=[model.state_at(t).alt_m for t in ordered],
                              threat_band_m=bands[0], target_band_m=bands[1])
    return profile


def write_readme(path, evidence, github):
    source = ('Full source, independent checker, tests and search experiments: '+github
              if github else 'Full source, independent checker, tests and search experiments will be shared separately on GitHub; the repository link accompanies the email.')
    text = f'''# Safe passage — approach, results and next steps

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
result” and works offline. trajectories.csv has {evidence['sampled_csv']['rows']:,} rows;
segments.json holds the controls; verification.json holds evidence and hashes.

{source}
'''
    path.write_text(text, encoding='utf-8')


def build(output=ROOT/'email_delivery', github_url=None):
    output = Path(output).resolve()
    github = validate_github_url(github_url)
    for protected in (ROOT, ROOT/'submission', ROOT/'reports', ROOT/'tools', ROOT/'airspace', ROOT/'docs', ROOT/'tests', ROOT/'experiments'):
        if output == protected or output in protected.parents or (protected != ROOT and protected in output.parents):
            raise ValueError('Use a separate compact-delivery directory')
    if output.exists() and any(p.name not in FILES for p in output.iterdir()):
        raise ValueError('Delivery directory contains unrelated files; choose an empty directory')
    scenario, flights = load_inputs(ROOT/'scenario.json')
    rules = load_rules(ROOT/'rules.json')
    evidence = _read_json(ROOT/'submission/evidence.json')
    document = _read_json(ROOT/'submission/segments.json')
    verification = ContinuousChecker(scenario, flights, rules).verify_document(document)
    quality = QualityEvaluator(scenario, flights, rules).evaluate(document['trajectories'])
    if verification != evidence['verification'] or quality != evidence['quality'] or not verification['verified_safe']:
        raise ValueError('Submission evidence is stale or fails independent verification')
    manifest = _read_json(ROOT/'submission/manifest.json')
    for name in ('trajectories.csv', 'rules.json', 'segments.json'):
        if digest(ROOT/'submission'/name) != manifest['files'][name]:
            raise ValueError('Submission checksum mismatch: '+name)
    # Freshly verify the original routes without importing the planner.
    from copy import deepcopy
    original = deepcopy(document)
    for trajectory in original['trajectories']:
        trajectory['segments'] = [dict(duration_s=rules['duration_s'], az_mps2=0)]
    baseline = ContinuousChecker(scenario, flights, rules).verify_document(original)
    if baseline['unresolved_count'] or baseline['violation_count'] != evidence['original_baseline_event_count']:
        raise ValueError('Baseline conflict evidence mismatch')
    source_by_id = {f['flight_id']:f for f in flights}
    profiles = {d['flight_id']:plotting_profile(d, source_by_id[d['flight_id']], scenario, rules) for d in document['trajectories']}
    data = dict(schema_version='1.0', github_url=github, selected_id=evidence['selected_id'],
        scenario=scenario, flights=flights, rules=rules, duration_s=rules['duration_s'],
        verification=verification, quality=quality, profiles=profiles,
        baseline=baseline, endpoint_bounds=evidence['endpoint_bounds'],
        excursion_bounds=evidence['excursion_bounds'], sensitivity=evidence['vertical_reference_sensitivity'],
        endpoint_error_probe=evidence['endpoint_error_probe'], rows=evidence['sampled_csv']['rows'])
    template = (ROOT/'tools/email.template.html').read_text(encoding='utf-8')
    script = (ROOT/'tools/email.js').read_text(encoding='utf-8')
    if template.count('__EMAIL_DATA__') != 1 or template.count('__EMAIL_SCRIPT__') != 1:
        raise ValueError('Email template placeholder mismatch')
    html = template.replace('__EMAIL_SCRIPT__', script).replace('__EMAIL_DATA__',
        json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c'))
    output.mkdir(parents=True, exist_ok=True)
    (output/'START_HERE.html').write_text(html, encoding='utf-8')
    write_readme(output/'README.md', evidence, github)
    for name in ('trajectories.csv', 'rules.json', 'segments.json'):
        (output/name).write_bytes((ROOT/'submission'/name).read_bytes())
    report = dict(schema_version='email-delivery-1.0', selected_id=evidence['selected_id'],
        certificate=verification, quality=quality, source_inputs=dict(scenario=scenario, flights=flights),
        endpoint_bounds=evidence['endpoint_bounds'], excursion_bounds=evidence['excursion_bounds'],
        endpoint_error_probe=evidence['endpoint_error_probe'],
        vertical_reference_sensitivity=evidence['vertical_reference_sensitivity'],
        source_file_sha256=evidence['input_file_sha256'], github_url=github,
        file_sha256={name:digest(output/name) for name in FILES if name != 'verification.json'},
        scope=evidence['scope'])
    (output/'verification.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
    return data


def package(output=ROOT/'email_delivery', destination=ROOT/'DTL_email.zip'):
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (Path(output)/name).read_bytes())
    return Path(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'email_delivery')
    parser.add_argument('--github-url', default=None)
    args = parser.parse_args()
    try:
        data = build(args.output_dir, args.github_url)
        archive = package(args.output_dir)
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc)+'\n')
    print(f'Created {archive}: exactly {len(FILES)} files, {archive.stat().st_size:,} bytes; selected {data["selected_id"]}')


if __name__ == '__main__':
    main()
