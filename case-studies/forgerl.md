# ForgeRL / ForgeBench — inspectable routing for coding agents

[Evidence dashboard](https://stelioszach.com/demos/forgerl/) · [Source](https://github.com/stelioszach03/forgerl) · [v0.2 protocol](https://github.com/stelioszach03/forgerl/blob/main/docs/forgebench/PROTOCOL.md) · [Recorded comparisons](https://stelioszach.com/demos/forgerl/bench.html#comparison)

ForgeRL studies a concrete systems question: how should a bounded coding agent allocate model calls after visible test feedback? ForgeBench supplies authored repository tasks, controlled routing comparisons and a public dashboard connecting every recorded outcome to its prompts, edits, tests and accounting.

## Contribution

The latest [prospective transfer pilot](https://github.com/stelioszach03/forgerl/blob/main/artifacts/forgebench/v0.3-pilot1/report/pilot-report.md) completed all 162 prespecified episodes after its protocol and controllers were committed. It adds 24 authored tasks in eight new families and three separate licensed source-derived mutation tasks, with six policies. The six fresh primary test families yield 18 tasks per policy: strong-only 16/18, cheap-only 15/18, escalation 16/18, hand-written 15/18, fitted-Q 16/18 and the simpler observed-return baseline 17/18. These single-seed observations do not establish superiority. VERIFY is a shared rule, not learned; the report preserves failed final tests and the verifier's missed failures. The stable live explorer below remains the separately reported v0.2 study.

I built the multi-file repair harness, task catalog, finite fitted-Q router, isolated executor, durable spending ledger and read-only evidence dashboard. The research system and public application are separate: an operator starts budgeted experiments; visitors inspect stored artifacts without starting inference or submitting code.

ForgeBench v0.2 contains **50 authored scenarios across 10 miniature Python repository families**. The 30 training, 10 validation and 10 held-out test scenarios have disjoint families. Tasks cover bug fixing, multi-file changes, feature implementation, refactoring, failing tests and linked multi-requirement scenarios. Each has an explicit success criterion, visible failing reproduction, hidden checks and a reference implementation. All 50 fixtures have been checked in the isolated Docker executor; fixture verification is separate from model performance.

The controlled research profile uses **GPT-OSS 20B and GPT-OSS 120B through OpenRouter**, pinned to the CoreWeave FP4 provider with automatic fallback disabled. These are configured research treatments, not a claim that every published task was evaluated on both models. Actual models, provider configuration and completed coverage are recorded with each study. Language-model weights remain unchanged; learning applies to the routing controller.

## Quick walkthrough

1. Read the **Results** table and success-versus-cost chart. Check actual coverage before comparing policies; missing values remain blank.
2. Open **Tasks & traces** and filter by task category or split. Inspect the task criterion, visible checks and linked source files.
3. Choose an available recorded run. Follow its **Trajectory**: prompts, supplied context, model responses, patches, sandbox calls, errors, retries, switches, rollbacks and final grading.
4. Compare **Patch**, **Test outcomes**, **Final files** and **All metrics**. A visible pass can still fail hidden checks.
5. Open the full run JSON or patch artifact. A task without a published run is explicitly unevaluated; the interface never fabricates an execution.

## Engineering decisions

| Decision | Reason | Source to inspect |
| --- | --- | --- |
| Keep research execution separate from the public API | Visitors can inspect evidence without consuming an inference budget | [`forgerl/bench/api.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/bench/api.py) |
| Execute candidate modules in constrained, network-isolated rootless containers | Keep generated code away from the web process, provider credentials and ordinary host privileges | [`forgerl/bench/sandbox.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/bench/sandbox.py) |
| Reserve cost durably before a provider call | Restarts and unknown billing outcomes must not reset the shared allowance | [`forgerl/store.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/store.py) |
| Fit Q-values on training transitions and freeze the controller before evaluation | Separate learned routing from unchanged model weights and expose unsupported-state fallback | [`forgerl/bench/router.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/bench/router.py) |
| Record prompts, candidates, decisions and actual execution outcomes | Make both successful and unsuccessful repairs inspectable | [`forgerl/bench/engine.py`](https://github.com/stelioszach03/forgerl/blob/main/forgerl/bench/engine.py) |
| Retain partial coverage, null measurements and failed requests | Incomplete evidence must not look like an evaluated success | [`static/bench.js`](https://github.com/stelioszach03/forgerl/blob/main/static/bench.js) |

The public application uses FastAPI, a sealed read-only SQLite archive and a dependency-free HTML/CSS/JavaScript interface on the portfolio VPS. The private research ledger uses SQLite/WAL under a separate runtime identity. Inference is a separate, explicitly budgeted hosted dependency. No continuously rented GPU is required to serve recorded experiments.

## Evaluation design

Five policies share the same maximum of six model calls and ten routing decisions: **strong-only**, **cheap-only**, **cheap-to-strong on failure**, **hand-written routing** and **adaptive ForgeRL routing**. Available actions are retry, repair, escalate, rollback and stop. All policies stop when visible checks pass or their bounds are exhausted. Hidden checks run only after routing ends and never feed another repair decision.

The dashboard reports task success, hidden-test pass rate, cost, tokens, latency, orchestrated tool calls, attempts, visible regressions, success after repair and escalation frequency. A reference-scope edit proxy is explicitly distinguished from proven unnecessary edits. Recorded failure labels describe observable events, such as a repeated candidate or a visible pass followed by hidden failure; they do not infer a model's private reasoning.

The completed v0.2 release contains 300/300 evaluation episodes and 180/180 training episodes across seeds 17, 29 and 43. On the held-out test split, the recorded successes were 24/30 strong-only, 27/30 cheap-only, 26/30 escalate-on-failure, 27/30 hand-written-router and 25/30 adaptive-router. These descriptive results cover two held-out families; retained provider failures, related variants and the small family count limit interpretation. Study artifacts preserve the predeclared configuration, task and controller hashes, provider settings and every trajectory. Reported usage charges and conservative reservations are distinguished; neither is a claim about GPU time or credit-purchase fees. No general policy advantage is claimed.

The [v0.1 single-module pilot](https://stelioszach.com/demos/forgerl/index.html#experiments) remains archived as a separate experiment. Its results are not pooled with the v0.2 repository benchmark.

## Boundaries

- These are authored miniature repositories, not SWE-bench, arbitrary GitHub issue repair or demonstrated general autonomous software engineering. The multi-requirement category does not establish real-world long-horizon capability.
- Hidden checks are withheld from model context during an evaluation. Their reproducible definitions exist in the source release, so this is not a contamination-resistant private benchmark.
- Sparse controller states can require a declared static fallback. Model endpoints and requested seeds do not guarantee bitwise reproducibility or a fixed checkpoint revision.
- Test success is a finite evaluation outcome, not proof of general correctness. Related variants and the small number of held-out families limit statistical generalization.
- A single VPS is not a highly available deployment, and container constraints do not establish that arbitrary hostile code is safe.

Successful patches, negative outcomes and incomplete experiments belong in the same evidence record.
