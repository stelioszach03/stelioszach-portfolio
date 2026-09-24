# Evidence-led development status

Updated 2026-09-24 UTC. This record distinguishes implemented software, completed
measurements and remaining research. A release, an offline test and a model
experiment are different kinds of evidence.

## Completed execution evidence

| Work | Actual outcome and scope |
| --- | --- |
| Forge transfer pilot | 162/162 frozen episodes. Primary test: supervised return 17/18; fitted-Q, strong-only and escalation 16/18; cheap and hand-written 15/18. Six test families, one seed; no superiority claim. All traces and a six-page technical report are [published](https://github.com/stelioszach03/forgerl/tree/main/artifacts/forgebench/v0.3-pilot1). Shared VERIFY is not learned. |
| GPU serving | 1,536 measured requests, 24 stages, three paired cache sweeps on one RTX 4090. No request errors or fixed-output-length mismatches; only 210/768 paired text hashes match. [Raw measurements and report](https://github.com/stelioszach03/colab-speculative-decoding-speed-lab/tree/main/artifacts/controlled-pilot-v1); no lossless or output-quality claim. Pod terminated; provider reports $0.225616 for the whole allocation. |
| MRI publication | [Evidence package v0.2.0](https://github.com/stelioszach03/mri-reconstruction-evidence/releases/tag/v0.2.0): eight unchanged historical aggregates, deterministic CPU analysis, independent NumPy ensemble diagnostics, numeric figures and source/license audit. Twenty CPU tests and Python3.9/3.12 CI pass. The new diagnostic example is synthetic. Solver, images and weights excluded; no fresh MRI inference. |
| MTA collection | Autonomous history, schema2 Parquet export/retry and temporal workers deployed. At 2026-09-24 21:45 UTC, the public temporal snapshot contained256 completed five-minute windows spanning21h15m and39 stable route/direction groups. Actual 15/30-minute chronological feasibility metrics are visible; seasonal values remain null without a24-hour lag. Public forecasts stay empty until at least14days plus freshness/coverage/evaluation gates. Request-start/response-availability semantics were corrected prospectively; legacy rows remain preserved and conservatively interpreted. [Protocol](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection/blob/main/docs/TEMPORAL_EVALUATION.md). No longitudinal or official-incident result. |
| DeID evaluation | 500 fixed external synthetic records: strict mapped-label P39.29%, R41.17%, F1 40.21%, 90.57% gold-label coverage. [Unfavorable results and Unicode/latency checks](https://github.com/stelioszach03/deid-privacy-studio/tree/main/artifacts/external-synthetic-v1-run1) retained. No clinical or live-adapter accuracy claim. |
| TrustQuery inputs | Recovered 14,185 historical candidate pairs reconcile with metadata. A new [HAM-only pixel audit](https://github.com/stelioszach03/TrustQueryNet/blob/main/artifacts/ham-pixel-audit/v1-2026-09-24/REPORT.md) decoded all 10,015 images, finding two identical-pixel pairs within the same persisted split/lesion; zero exact-pixel or metadata-lesion groups span splits. ISIC image comparison and external independence remain unresolved. No retraining or revised model accuracy is claimed. |
| LLM-SMT feasibility | [750 recorded cells](https://github.com/stelioszach03/llm-smt-verifiable-reasoning/releases/tag/openrouter-pilot-v1): 739 completed executions and 11 deadline stops, on 50 public synthetic tasks × three requested seeds × five arms. Core-ranked repair and no-feedback both certified 55/90 SAT assignments; no advantage established. Direct Z3 solved all 500 source problems without model calls. Accounted API cost $0.867535 includes rounding and uncertain reserves; full 7,500-episode study not run. |

## Current portfolio selection

| Project | Current evidence | Public presentation |
| --- | --- | --- |
| ForgeRL / ForgeBench | Preserved v0.2 study plus 162-episode prospective transfer pilot | Selected project; nativev0.3/v0.2 explorer, recorded step replay and separate bounded live trial |
| MTA-Scan | Live public feed interface; 216-row constructed replay; bounded raw history collection started 2026-09-24 UTC | Selected project; no validated disruption forecast |
| MRI reconstruction | BSc thesis and public aggregate-evidence package; solver source withheld | Selected thesis with reproducible table/plot analysis and independent CPU ensemble diagnostics |
| AsklepiosMed | Donated deployed application; former pro bono role; scoped public case study | Selected engineering project; source and member records private |
| Inference Systems Lab | Controlled single-GPU serving measurements; historical Colab results separate | Selected measured systems project with limits and raw evidence |
| TrustQueryNet | Historical multi-seed tables, negative/uncertain comparisons, measured HAM input/split audit; cross-ISIC near duplicates and corrected-code rerun unresolved | Secondary experimental work; unpublished, not clinical validation |
| LLM-SMT | Actual 750-cell feasibility pilot, complete trajectories, cost/token reconciliation and a null primary comparison; full sweep not run | Completed secondary experimental snapshot, kept off the selected-project homepage; no repair-superiority claim |
| DeID | Review workflow plus fixed external synthetic evaluation exposing weak detection | Secondary engineering demo; no anonymity guarantee |
| Graph Fraud / EuroSAT | Synthetic prototype / completed coursework | Original repositories private and archived; deployed Graph adapter source remains in the public portfolio repository |
| DynaDiff-VLBI | Historical measurements with disclosed geometry-ordering issue | Private and archived; no new imaging claim |

## Shipped engineering changes in this development pass

- Native Forgev0.3/v0.2 explorer and separate curated live trial deployed. One authorized production smoke solved5/5 final checks with1,212 tokens; CoreWeave reported$0.00007946, conservatively rounded to$0.000080 in the original ledger. This is an integration check, not new benchmark evidence. Exactly one request/charge; all13 live security checks passed.
- Seven unselected repositories are now private and archived, with private Git bundle backups: EuroSAT, Graph Fraud, LimitForge, AML Graph, DoubleX Ledger, Realtime Fraud and DynaDiff-VLBI. The active Graph demo links to its public deployed adapter; archives are not advertised as public projects.

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
- LLM-SMT's actual pilot accounts for all paid batch candidates, withholds full
  solver witnesses from model feedback, rejects silent candidate type coercion
  and preserves provider uncertainty. The related live SMT verifier now returns
  structured domain failures for incomplete assignments and rejects strings or
  floats as integer candidates. Nine pinned-runtime ASGI checks, seven portable
  checks and six actual public requests passed; other demo health routes remained
  healthy. Only the two reviewed verifier modules were deployed.
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
The public Forge process has no model credential or executor access. Recorded browsing is free; the optional fixed live trial uses a separate private broker and the original durable spending ledger. The medical
association source and production records are not inputs to public research.
Months of temporal evaluation require elapsed collection time; new datasets and
external code require their own provenance review.
