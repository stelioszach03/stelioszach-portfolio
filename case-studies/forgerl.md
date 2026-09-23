# ForgeRL — inspectable model-call decisions for Python repair

[Open the workbench](https://stelioszach.com/demos/forgerl/) · [Source](https://github.com/stelioszach03/forgerl) · [Experiment protocol](https://github.com/stelioszach03/forgerl/blob/main/docs/METHODOLOGY.md) · [Recorded comparisons](https://stelioszach.com/demos/forgerl/#experiments)

ForgeRL is a bounded repair-agent workbench built around a specific question: can visible test feedback help a controller allocate a small number of model calls? A user selects an authored Python regression task and can inspect the candidate patch, test outcomes, decision trace, token usage and estimated cost.

## Contribution

The implementation combines a task catalog, model-driven repair loop, finite fitted-Q controller, isolated executor, durable queue and spending ledger, and a browser inspector. The configured hosted models are IBM Granite 4.0 H Small and OpenAI GPT-OSS 120B through Runpod. Their weights remain frozen; learning applies to the controller's routing actions. This is not language-model fine-tuning or a new foundation model.

The catalog contains 24 authored tasks across separate training, validation and test families. Public checks guide the repair. Held-out checks assess a final candidate without exposing their inputs or expected outputs to the model or public UI. Passing those finite checks does not establish general correctness.

## Quick walkthrough

1. Open a recorded run in **Workbench**. Confirm whether it is recorded evidence or a fresh live run.
2. Compare **Public tests** with **Held-out tests**. A visible pass can still fail held-out checks.
3. Read **Patch**, **Tests** and **Trace** to connect the selected action, generated edit and observed outcome. Export the patch or JSON trace explicitly.
4. Open **Experiments** to compare the recorded policies on matched tasks, including failed runs, coverage and limitations.
5. When the service reports live inference available, choose a curated task and available policy to start a new run. The public interface does not accept arbitrary source uploads or repository URLs.

## Engineering decisions

| Decision | Reason | Source to inspect |
| --- | --- | --- |
| Separate the generated candidate from trusted expected outputs | Candidate code cannot read the reference answer through the test interface | [`forgerl/sandbox.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/sandbox.py) |
| Execute candidates in constrained, network-isolated rootless containers through an executor boundary | Keep generated code away from the web process, provider key and ordinary host privileges | [`forgerl/sandbox.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/sandbox.py) |
| Reserve inference cost durably before a provider call | Process restarts and unknown billing outcomes must not silently reset the allowance | [`forgerl/store.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/store.py) |
| Fit finite Q-values from observed training transitions | Separate a learned routing policy from frozen language-model inference; keep unsupported states explicit | [`forgerl/controller.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/controller.py) |
| Record decisions, patches, test outcomes and provider accounting | Make an apparently successful repair inspectable and preserve failure evidence | [`forgerl/orchestrator.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/orchestrator.py) |
| Keep missing measurements blank and mark unavailable inference | An empty result or exhausted allowance must not look like a measured success | [`static/app.js`](https://github.com/stelioszach03/forgerl/blob/main/static/app.js) |

The public application uses FastAPI, SQLite/WAL and a dependency-free HTML/CSS/JavaScript interface. The web service and executor run on the portfolio VPS; hosted inference is a separate, explicitly budgeted provider dependency. A working single VPS is not a highly available deployment, and container constraints are not a guarantee that arbitrary hostile code is safe.

## Evaluation design

The initial protocol compares fixed-fast, deliberate-only, heuristic and adaptive policies with an equal three-call cap. Fixed baselines also stop when their visible tests pass. Training, validation and test defect families are disjoint; prospective evaluation uses fresh provider calls rather than recycling training branches.

The predeclared pilot requests three seeds. The production artifact is selected by the protocol before evaluation, rather than chosen afterward for the best outcome. Six unique held-out tasks from two families are repeated across the seeds, so repeated episodes are not independent new tasks. Missing coverage, failed provider calls and unsuccessful patches remain visible in the recorded artifacts.

Consult the live **Experiments** view and repository protocol for the actual completed coverage, results and provenance. This case study does not assert a policy win, solve rate or cost reduction before those artifacts support it. Provider-reported token counts underpin conservative cost estimates; estimates and retained billing reservations are not provider invoices.

## Boundaries

- This is an authored Python regression suite, not SWE-bench, arbitrary GitHub repair or demonstrated general autonomous software engineering.
- The finite controller has sparse state coverage. Unsupported states can fall back to the documented heuristic, and that selection source is recorded.
- Hidden test success is a finite evaluation outcome, not a correctness proof or evidence of clinical, financial or security suitability.
- Provider seeds are requested settings; hosted generation is not guaranteed to be bitwise reproducible.
- The small pilot cannot establish broad policy superiority, even if a point estimate favors one controller.
- Live requests stop when the finite serving allowance is unavailable. Recorded evidence remains accessible without pretending to be fresh inference.

Failed hypotheses and unsuccessful patches belong in the same evidence record as successful repairs.
