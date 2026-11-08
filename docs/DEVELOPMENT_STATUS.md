# Engineering and profile status

Updated 2026-11-08 UTC. Measured experiments, software checks and live integration
checks are different evidence. The [evidence index](EVIDENCE_INDEX.md) links the
primary artifacts and their limitations.

## Current engineering evidence

| Project | Completed work and evidence |
| --- | --- |
| AsklepiosMed | Head Engineer, June 2022–July 2026: platform architecture, React interfaces, Express APIs, PostgreSQL workflows, access controls and service operations. Continued project development after July 2026 added LLM writing and multilingual NLP workflows with structured outputs, checks, retries, fallback handling and editorial review. |
| ForgeRL / ForgeBench | Prospective 162-episode, six-policy transfer pilot; separate 1,296-attempt exposed-catalog follow-up. The native explorer exposes recorded patches, tests, costs and policy comparisons. The learned router has no demonstrated general advantage. |
| Inference Systems Lab | Separate 16,384-request factorial study on RTX 4090 and A100, two model sizes and four repeats, following the original 1,536-request pilot. Shared-prefix caching produced 1.23–1.47× throughput at concurrency 32 in these synthetic workloads. Output parity failed; semantic quality was not evaluated. |
| MTA-Scan | Monitored public-feed pipeline, retained daily exports, official-alert revision history and gated temporal proxy forecasts. The November 7 audit verified 44 daily exports and a 28-day evaluation window. Forecasts estimate future feed-predicted spacing, not observed passenger wait or official disruptions. |
| MRI reconstruction | Thesis and public evidence companion. Historical aggregate tables and plots are reproducible; independent CPU ensemble diagnostics are separate from the original reconstruction solver. |

## Completed verification in this pass

- 10 portfolio checks, 44 demo JavaScript checks and 17 Python checks passed.
  The Python checks include three new regressions for Graph explanation accuracy.
- The production Graph explanation module was corrected and deployed. Low
  normalized amounts and moderate channel priors no longer receive unsupported
  "far above baseline" or "high-risk channel" descriptions. Scores and model
  inputs were unchanged. A fresh synthetic request confirmed the corrected output.
- All five demo entry or health routes responded successfully. Controlled SMT
  requests exercised certified SAT, failed certification, domain rejection, false
  UNSAT claims and certified UNSAT. DeID masked an explicitly fictional email;
  Keep and Undo were exercised in the interface.
- Forge recorded repair inspection showed its stored 4/4 tests. One separate
  fresh curated live trial passed 5/5 final checks, using one provider attempt,
  1,357 tokens and $0.000099 in accounted cost. It is an integration check and
  does not alter any benchmark result.
- MTA displayed 8/8 fresh feeds and active temporal forecasts; changing the line
  filter changed the displayed observations and ranked entries. The map rendered.
- The homepage menu worked at a 390-pixel viewport, including Escape and focus
  restoration, with no horizontal overflow. This is not a claim that every demo
  was manually tested on every mobile viewport.
- All 18 unique external homepage links checked returned HTTP 200 after replacing
  the obsolete Forge report endpoint with the current v0.3 pilot PDF. LinkedIn
  was checked through the signed-in profile interface separately.

These checks cover the exercised paths. No new GPU training or research benchmark
was run as part of this presentation update.

## Profile alignment and release

- LinkedIn and the GitHub profile now use Machine Learning Engineer / Applied AI
  & ML Systems positioning, the Head Engineer title and matching role dates.
- The sole primary CV was edited and saved in Jobright, retaining its one-page
  format. Jobright's fresh analysis reported Excellent / A with zero listed fixes;
  that is a document-analysis score, not a hiring prediction.
- The prepared portfolio emphasizes platform ownership, LLM/NLP applications,
  agent evaluation and measured inference work. It retains real project imagery
  and adds the original measured inference-throughput figure.
- Every prepared CV button points to the single canonical PDF. The build versions
  the PDF and its preview by content hash to avoid stale cached downloads. The
  sharing page remains /cv/; there is no second CV or alternate generator.
- The revised site is built and staged on the VPS. Final publication is pending
  receipt of the current native Jobright PDF export: the browser export did not
  provide an accessible file to upload. The existing public PDF has not been
  silently replaced with a differently generated document.

Release steps remaining: receive the native PDF, verify its text and one-page
layout, replace the canonical PDF and its preview, rerun the relevant build
checks, and publish the synchronized release. Verify the public PDF hash and
every CV button after publication.

## Further evidence to build

Prioritize measured adoption and operational outcomes when those measurements
exist. For research, use broader untouched task families, matched controls and
predeclared evaluation before making broader performance claims. Preserve failed
runs and negative results; public summaries must continue to distinguish current
implementation, recorded findings and ongoing unpublished research.
