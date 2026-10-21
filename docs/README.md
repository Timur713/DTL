# Repository map

For a quick review, open [the compact animation](../email_delivery/START_HERE.html)
locally, then read [the approach and task-to-artifact mapping](submission.md).
The submitted plan is **`pass2-b8f763f4b8b0`**. Historical plans are experiments,
not additional submissions. [AGENTS.md](../AGENTS.md) defines contributor rules.

## Where things belong

| Path | Purpose |
| --- | --- |
| [Root README](../README.md) | Scenario, chosen rules, main results and limits |
| [Original assignment](../Task1_details.pdf), [flights](../flights.csv), [scenario](../scenario.json) | Immutable source inputs |
| [rules.json](../rules.json) | Shared safety and motion configuration |
| [email_delivery/](../email_delivery/) | Six-file reviewer package, including the offline `START_HERE.html` |
| [DTL_email.zip](../DTL_email.zip) | Ready-to-email copy of those six files |
| [submission/](../submission/README.md) | Selected controls, sampled trajectories, certificate, proofs and hashes |
| [airspace/](../airspace/) | Calculation library; no HTML dependency |
| [tools/](../tools/) | CLI commands, exporters, HTML templates and presentation JavaScript |
| [tests/](../tests/) | Mathematical, integration, export and browser tests |
| [experiments/](../experiments/) | Search budgets, experimental score and final selection policy |
| [reports/](../reports/) | Reproducible baseline and historical search outputs |
| [baseline.html](../baseline.html) | Full research viewer: source events, search replay and Pareto alternatives |
| [examples/](../examples/) | Small vertical-motion input example |

The original paths are retained for reproducible provenance. Generated artifacts
are tracked so reviewers can inspect the result without running searches. Caches,
dependencies, credentials and the optional duplicate full-project ZIP are ignored.

## Calculation and presentation flow

1. `airspace/analysis.py` loads source data and rules and analyzes original linear
   trajectories. `tools/analyze_baseline.py` writes baseline reports.
2. `airspace/vertical.py` defines continuous vertical motion. `planner.py` searches
   for a feasible plan; `improve.py` and `second_pass.py` search for better plans.
3. `checker.py` independently verifies serialized controls, using exact polynomial
   reasoning in `polynomial.py`. It checks continuous intervals, not CSV samples.
4. `quality.py` computes maneuver metrics; `endpoint_bounds.py` and `evidence.py`
   provide scenario-specific proofs and sensitivity witnesses. `alternatives.py`
   prepares verified comparisons; `replay.py` reconstructs accepted search steps.
5. `tools/build_submission.py` exports the selected plan under
   [experiments/submission.json](../experiments/submission.json) to `submission/`.
   `tools/build_email.py` independently rechecks the selected and source routes,
   then builds the compact HTML and six-file ZIP.
6. `tools/generate_baseline.py` builds the full research HTML from the template,
   presentation scripts and Python results. JavaScript renders controls and
   precomputed events; it does not implement a second conflict checker.

## Current result versus research history

| Location | Meaning |
| --- | --- |
| `submission/segments.json` | Authoritative controls for the submitted solution |
| `submission/verification.json` | Original independent nominal certificate |
| `submission/evidence.json` | Quality, bounds, sensitivity and selected-plan evidence |
| `submission/manifest.json` | Hashes of exported delivery files |
| `email_delivery/verification.json` | Compact wrapper; the original certificate is under `certificate` |
| `reports/summary.md`, `reports/analysis.json` | Original trajectory analysis across configured comparisons |
| `reports/planned/` | First feasible reference plan |
| `reports/improved/` | First quality-improvement experiment |
| `reports/improved_second/` | Second pass and endpoint-bound-attaining alternatives |

## Read the reasoning

- **Rules:** [model and primary sources](model.md), [target sphere decision](target-zone-decision.md).
- **Formats and dynamics:** [contracts](contracts.md), [vertical model](vertical-model.md).
- **Search development:** [feasible planning](nominal-planning.md),
  [first improvement](quality-improvement.md), [second pass](second-pass-quality.md).
- **Review:** [submission rationale](submission.md), [five-minute defense](defense.md),
  [validation record](validation.md), [comparison UI](comparison-ui.md).
- **History only:** [checkpoint project guide](project-guide.md). Its results
  describe an earlier stage; use the root README for the current submission.

## Reproduce without rerunning the searches

Python 3.9+ and its standard library are sufficient:

```sh
python3 tools/build_submission.py
python3 tools/build_email.py --github-url https://github.com/Timur713/DTL
python3 tools/generate_baseline.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

To reproduce the research searches, run `tools/plan_nominal.py`,
`tools/improve_nominal.py` and `tools/improve_second.py` in that order before
exporting. These commands regenerate their report directories. Search runtime
caps may change the explored prefix; verifying the saved selected plan does not
rerun a search. Full browser commands are in [the submission guide](submission.md#reproduce).
Open the HTML files locally after cloning; GitHub's file viewer shows their source.
