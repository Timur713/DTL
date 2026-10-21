# Working on DTL_task

## Navigation and current result

- `docs/README.md` is the repository map, including module responsibilities and reproduction order.
- `email_delivery/START_HERE.html` is the reviewer entry point; `DTL_email.zip` is its six-file email attachment.
- `submission/` is the selected result, plan `pass2-b8f763f4b8b0`; start with its `README.md`, `segments.json`, `verification.json` and `manifest.json`.
- `reports/` preserves baseline and search history, not multiple competing submissions. `baseline.html` is the full research viewer.
- Preserve existing paths: saved experiment provenance and tests refer to them. Do not edit generated presentation or delivery files directly; use their builders in `tools/`.
- The optional `DTL_submission.zip` is ignored because it duplicates the full repository. Keep the compact email ZIP tracked.

## Purpose and sources of truth

The project studies trajectory conflicts involving 40 aircraft, a drone and a target zone. It is a research model, not a certified air traffic control system. Use English for user communications, project documentation, the UI, comments and reports; identifiers and code also use English.

Before making changes, read `README.md`, `rules.json`, `docs/model.md`, `docs/contracts.md` and the relevant decisions in `docs/`. Check `git status` and the current files: the discussion may describe an earlier version. Direct user instructions take precedence over this document.

- `Task1_details.pdf`, `flights.csv`, `scenario.json` are source inputs. Do not modify them for algorithmic convenience. Save new trajectories and experiments separately.
- `rules.json` is the executable baseline configuration; `docs/model.md` explains its meaning and assumptions. Do not independently duplicate numerical values across calculation modules.
- `docs/contracts.md` defines the format of baseline reports and HTML. A new model must have an explicit contract; do not present unsupported semantics as existing behavior.
- `reports/` and `baseline.html` are reproducible outputs tracked in Git. Make changes in the calculation code/template, then regenerate the artifacts.

## Accepted decisions

The current primary study is `metric / nominal / base`, with a horizontal threshold of 9260 m, a vertical threshold of **300 m** and a horizon of 1200 s. The 304.8 m profile and `bounded_stress` are comparisons. Do not silently make a new mode the primary one.

- A pair violates separation only when `dh < H` and `abs(dz) < V` hold simultaneously. Equality is safe; altitude boundaries are also allowed.
- The drone and target zones are **spheres** with a radius of 5000 m in the base variant. The target center uses XY from the scenario and altitude `zones.target.center_alt_m=0`. Decision: `docs/target-zone-decision.md`. Earlier conclusions for an infinite target cylinder do not apply.
- Source trajectories are linear, including the drone's motion after passing the target XY. Retain objects outside the XY frame; the frame is not a safety constraint.
- Use SI units and east, north, geometric altitude axes; state angle units explicitly. An aircraft is a point with a protected volume.
- `bounded_stress` uses deterministic bounds on initial-state errors, growing from t=0 without resetting when seeking. It indicates possible loss of guarantee, not a probability or an observed violation. Applicability of these errors to new dynamics requires a separate justification.
- The horizontal acceleration limit bounds the derivative of **horizontal speed magnitude**, not the full vector acceleration in a turn. Generic jet limits are assumptions; do not describe them as characteristics of a particular aircraft type.

These decisions may change at the user's request. Record the reason, contract impact and results. Do not change thresholds or geometry to make conflicts disappear. Distinguish original task requirements, external standards, our assumptions and computed results; verify primary sources for new external claims.

## Calculation code and interface

- Python 3.9+, standard library for calculations and CLI. Justify any additional dependency. Default CLI paths must work independently of cwd.
- Mathematics belongs in `airspace/`; `tools/` contains CLI and generation code. Calculation modules must not depend on HTML or the generator.
- HTML uses precomputed Python results. Do not duplicate the conflict detector in JavaScript. Preserve standalone `file://` operation without a network.
- Validate finite numbers, types, units, IDs, versions and parameter support. `bool` is not a numerical parameter. Reject unsupported modes explicitly.
- JSON/CSV must be deterministic, without NaN/Infinity or arbitrary timestamps. Preserve input and configuration provenance.
- Safety checks must be continuous in time. Sampling by seconds or frames is suitable for plots and diagnostics, but does not prove the absence of violations between samples.
- For maneuvers, preserve position and velocity continuity and check limits throughout each segment and at joins. Do not replace a physical turn with a polyline containing instantaneous velocity changes.
- If a method cannot prove an interval admissible, return explicit `unresolved`/uncertainty. Do not turn numerical error into a physical margin or threshold change.
- Distinguish “an admissible example was found,” “the checked candidates did not work” and “the absence of a solution was proved.” An unsuccessful search does not prove infeasibility.

## Validation and reproduction

For calculation changes, add meaningful tests with independently known answers: strict boundaries, tangency, a short violation between samples, horizon start/end, segment joins and limiting speeds/accelerations. Check regressions against real inputs. Do not write tests that merely repeat the implementation.

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/generate_baseline.py
```

For changes to HTML, its data or the contract, run both browser suites:

```sh
npm install --prefix /tmp/dtl-baseline-check --no-save playwright
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_baseline.cjs
PLAYWRIGHT_MODULE=/tmp/dtl-baseline-check/node_modules/playwright node tests/check_analysis_ui.cjs
```

Set the Chrome path with `CHROME_PATH` if needed. Details and source-file SHA-256 checksums: `docs/validation.md`. After changing formulas/configuration, regenerate affected reports; after changing baseline data/template, regenerate HTML too. Check that documentation matches actual results. For text-only changes, checking links and the diff is sufficient.

## Git and collaboration

- Work in small, complete changes. Before finishing, check `git diff --check`, the diff and `git status`. Do not include others' changes in a commit without understanding their origin.
- Do not revert, delete or overwrite others' work. Do not rewrite history or publish/configure remotes without a corresponding task.
- Do not commit caches, virtual environments, node_modules, local settings or secrets. Commit source inputs, test examples, documentation and reproducible outputs.
- Start subagents only with explicit user permission or applicable instructions. Give each full context, completion criteria and nonoverlapping write areas. The coordinator changes shared contracts and informs all affected contributors.
- In a shared working directory, subagents do not make Git commits without a separate assignment: that is the coordinator's responsibility. Do not leave temporary files in the project.
- In the final response, state what was done, reproduction commands, checks actually run and material limitations. Do not claim checks passed if they were not run.
