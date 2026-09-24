# Evidence-led development status

Updated 2026-09-24 UTC. This is an implementation record and dependency backlog,
not a list of completed research results. A release, an offline test and a model
experiment are different kinds of evidence.

## Current portfolio selection

| Project | Current evidence | Public presentation |
| --- | --- | --- |
| ForgeRL / ForgeBench | v0.2: 300 evaluation + 180 training episodes; v0.2.1 software; two test families | Selected project, stored-run dashboard, technical report |
| MTA-Scan | Live public feed interface; 216-row constructed replay; bounded raw history collection started 2026-09-24 UTC | Selected project; no validated disruption forecast |
| MRI reconstruction | BSc thesis and supporting numerical reports; source publication audit in progress | Selected thesis; no public reproducible source release yet |
| AsklepiosMed | Donated deployed application; former pro bono role; scoped public case study | Selected engineering project; source and member records private |
| Inference Systems Lab | New streaming measurement client tested against local fixtures; separate historical Colab measurements | Repository under development; no new GPU serving comparison claimed |
| TrustQueryNet | Historical multi-seed tables, negative/uncertain comparisons, unresolved near-duplicate audit and code/result mismatch | Secondary experimental work; unpublished, not clinical validation |
| LLM-SMT | Verifier, adapters and offline tests; no completed full model sweep | Secondary prototype; unsupported result publication assets removed |
| DeID | Review workflow, offline regressions, deterministic generated fixtures | Secondary engineering demo; no anonymity guarantee |
| Graph Fraud / EuroSAT | Synthetic prototype / completed coursework | Supporting archives; not selected flagship projects |
| DynaDiff-VLBI | Historical measurements with disclosed geometry-ordering issue | Paused; no new imaging claim |

## Shipped engineering changes in this development pass

- MTA adapter 2.1.1 stops treating same-trip ETA revisions and vehicle timestamps
  as measured headways. Fresh snapshot pairs estimate arrival spacing, with
  identity/direction checks and separate new database/model defaults. The old
  derived state and replay artifacts are preserved separately.
- MTA history runs independently of the demo. Original protobuf snapshots and
  poll failures are retained with timestamps and hashes. A daily export service
  creates typed Parquet and a verified manifest for completed UTC days. Raw
  retention is bounded to 7 days / 2 GiB / 150,000 polls; Parquet to 90 days /
  10 GiB. The first limiting policy wins, and a 2 GiB filesystem reserve applies.
  Day-one collection is not a longitudinal dataset or uninterrupted-uptime claim.
- The serving benchmark records per-request status, first text-chunk latency,
  stream-chunk gaps, available token counts, concurrency and settings. Its local
  fixture tests do not constitute GPU measurements. Chunk gaps are not necessarily
  token-level timings.
- DeID's oversized synthetic notes are generated on demand. LLM-SMT's tracked
  bytecode and unsupported publication figures/PDF are removed from the current
  tree, with source history preserved.
- The website adds a linked evidence strip, the existing ForgeBench technical
  report, two CV editions and a logical AsklepiosMed architecture diagram.

## Next development gates

| ID | Work | Depends on | Acceptance before promotion |
| --- | --- | --- | --- |
| F-01 | v0.3 public VERIFY action | Implemented development harness | Green original checks → supplemental failure → repair exercised in isolated executor; hidden grading final-only |
| F-02 | Independent authored families | F-01 | 18–25 distinct repository families; at least 5–6 untouched test families; all starter/reference pairs validated |
| F-03 | External generalization track | Source audit | Immutable upstream commits, redistributable licenses/notices, isolated tests, provenance and no unlicensed data |
| F-04 | New exploration and simple learned baseline | F-01–03 | Observable-only features, action support and propensity logging; training/validation/test separated; no fitting on inspected v0.2 tests |
| F-05 | Freeze v0.3 experiment | F-02–04 | Models/providers, budgets, seeds, retry rules, estimands, missing-run handling and analysis committed before execution |
| F-06 | v0.3 report and possible preprint | F-05 + actual experiments | Raw traces and reproducible comparison; negative results retained; draft reviewed before submission |
| M-01 | Verify first completed-day Parquet | Historical collection | Real day hash, row count, poll coverage and timestamps checked; no synthetic replacement for missing intervals |
| M-02 | Operational coverage view | M-01 | Last collection/export, missing intervals, growth and caps visible with read-only access |
| M-03 | Static GTFS + NYCT extensions | Provenance review | Versioned static joins and extension bindings; missing fields stay null |
| M-04 | Alerts and weak labels | M-03 | Alert revision/timing/route semantics recorded; sample labels reviewed and described as noisy/delayed |
| M-05 | Temporal evaluation protocol | Retained history + M-04 | Chronological split, horizon embargo, day/route coverage, no future-alert leakage |
| M-06 | Forecasting baselines | M-05 | 10/20/30-minute horizons; seasonal/linear/boosting baselines, calibration, event metrics and route-hour false alarms |
| M-07 | Graph-temporal comparison | M-05–06 | Versioned topology, upstream-lag baseline, controlled ablations and uncertainty; publish wins or failures |
| M-08 | Real historical replay | M-01, M-05 | Recorded interval with provenance/model version; actual observations distinct from weak labels |
| R-01 | Recover MRI source in staging | Source located | Original worktree unchanged; intended module names restored in a clean copy; CPU invariants pass |
| R-02 | MRI publication provenance | R-01 | Third-party notices and exact code provenance; dataset/checkpoint terms resolved; no restricted data or identifiers |
| R-03 | MRI reproducibility release | R-02 | Environment/configs/evaluation commands map to thesis tables; fresh reproducible run or explicit document-only scope |
| I-01 | Serving client and metric semantics | Implemented | Offline SSE fixtures cover partial/error/usage-only streams; unavailable metrics stay null |
| I-02 | Controlled server manifest | I-01 | Exact model revision, quantization, vLLM/container, GPU, decoding and settings recorded |
| I-03 | Representative workloads | I-02 | Versioned prompt-length mix, licensing, warm/cold cache definitions and seeds; synthetic smoke set kept separate |
| I-04 | GPU telemetry | I-02 | Timestamped NVML samples; integration tested; no utilization/VRAM inferred from HTTP timing |
| I-05 | Finite GPU pilot | I-02–04 | Declared spending ceiling, automatic shutdown, persisted raw logs; no continuously running GPU |
| I-06 | Controlled serving comparisons | I-05 | Baseline/batching/cache/quantization/speculation at predeclared concurrency; output quality and missing/failed requests reported |
| I-07 | Stored-results interface | I-06 | Plots derived from real artifacts; no paid visitor-triggered inference |
| T-01 | TrustQuery overlap review | Dataset access | Exact and perceptual candidates adjudicated before claiming leakage-free external testing |
| T-02 | TrustQuery corrected-code rerun | T-01 | Re-run current MC-dropout implementation; distinguish historical tables; two backbones/two noise regimes/five seeds only with budget and fixed protocol |
| S-01 | LLM-SMT feasibility pilot | Fixed models/provider/budget | Small real pilot logs tokens/cost/solver outcomes; planned 7,500-run matrix not reported as completed |
| S-02 | Final LLM-SMT study or archive | S-01 | Predeclared full evaluation within budget; otherwise preserve honest prototype and keep off the homepage |
| D-01 | DeID entity evaluation | Licensed annotated fixture set | Precision/recall/F1 by entity, Unicode/overlap cases, long-document throughput and p95 latency; synthetic labels disclosed |
| P-01 | Pin only evidence-ready projects | Relevant releases | Existing four selected repos retained; MRI/inference promoted only when their evidence exists |
| P-02 | Synchronize public claims | Every release | README, demo, portfolio, CV and profile distinguish implementation, recorded result, draft and future work |

Detailed Forge tasks live in the [ForgeBench v0.3 backlog](https://github.com/stelioszach03/forgerl/blob/main/docs/forgebench/V03_BACKLOG.md).
MTA deployment, retention and recovery steps live in its
[historical collection runbook](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection/blob/main/docs/HISTORICAL_COLLECTION.md).

## Rules for evidence and resources

Preserve failed runs and negative findings. Remove unsupported assertions; do not
improve a portfolio by selecting only successful outcomes. No preprint submission,
clinical validation, general superiority, adoption impact or new GPU result is
claimed merely because the corresponding software or protocol exists.

New paid experiments require a concrete protocol and finite resource ceiling.
The public Forge dashboard is read-only and has no model credential. The medical
association source and production records are not inputs to public research.
Months of temporal evaluation require elapsed collection time; new datasets and
external code require their own provenance review.
