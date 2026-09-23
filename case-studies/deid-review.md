# DeID Studio — making model output reviewable

[Open the synthetic-text demo](https://stelioszach.com/demos/deid/) · [Adapter and interface](../demo-services/deid/) · [Library prototype](https://github.com/stelioszach03/deid-privacy-studio) · [Recorded checks](evidence/deid-review.json)

An English text-redaction prototype that lets a reviewer inspect detections, keep a false positive, apply a suggested transformation or redact a missed span. The output updates locally, and exported review metadata distinguishes model suggestions from human decisions.

## Problem and contribution

A detector can return plausible-looking output while missing an identifier or mislabelling ordinary text. A single transformed paragraph hides those errors. The engineering goal was to expose the decisions and let the reviewer correct the draft without treating a model prediction as a privacy guarantee.

The project work spans the Python adapter, browser review state, Unicode handling and regression checks. It uses the existing DeID policy engine and a pretrained spaCy English model; it does **not** introduce a newly trained NER model or a new de-identification method. The public adapter is smaller than the upstream library: database, file-upload and asynchronous-job features are not part of this demo.

## Quick walkthrough

1. Open the demo and use a supplied **synthetic** example. In Source → Text, append `Review marker qzvxreview.` before choosing **Analyse text**.
2. In Review, uncheck an email detection to keep its original text. Watch the output and kept-span warning change. Check it again to apply the configured transformation.
3. Return to Source → Text, select `qzvxreview`, and choose **Redact selection**. The added span is labelled manual. Use **Undo** to restore the previous draft.
4. Open Preview → Export → **Download review JSON**. It includes the current output, pending decisions and `review_required: true`. Copy review metadata instead when you want labels and decisions without output text.

This is an interaction demonstration, not a model-quality test. Never submit real personal or confidential records.

## Decisions worth inspecting

| Engineering decision | Why it matters | Code to inspect |
| --- | --- | --- |
| Return an exact replacement for each detected span, then verify reconstruction against the engine's output | The browser can remove or reapply a transformation without reproducing policy logic or receiving the salt | [`_analyse`](../demo-services/deid/service.py) |
| Use Unicode codepoint offsets across Python and JavaScript; convert textarea selection boundaries | An emoji before an entity must not shift the highlighted or redacted text | [`validateResult`, `manual`, `boundary`](../demo-services/deid/static/index.html) |
| Reject invalid, overlapping or inconsistent spans | An inconsistent response cannot become an apparently usable review draft | [Adapter contract tests](../demo-services/service-tests/test_deid_review_backend.py) |
| Keep review decisions local and invalidate them when source or policy changes | An old response cannot overwrite a newer document; changing a decision does not trigger another inference request | [`invalidate`, `analyse`, `decide`](../demo-services/deid/static/index.html) |
| Keep “reviewed” separate from “anonymous” | Confirmed detections do not prove that undetected identifiers are absent; retained originals are visible in export warnings | [`metadata`, `render`](../demo-services/deid/static/index.html) |

Source, output and decisions remain in browser memory until cleared or the page exits. Clipboard and downloads require explicit actions. The server processes submitted text in memory without deliberate request-body persistence; inference may finish after a browser disconnects. This design is for a public prototype, not a secure-document processing service.

## Evidence and reproduction

The [recorded evidence](evidence/deid-review.json) separates the tested workflow bytes from the later favicon-only HTML change. That later export also passed [GitHub CI](https://github.com/stelioszach03/stelioszach-portfolio/actions/runs/35802120871). There are three distinct kinds of check:

- **Contract tests:** four Python tests cover replacement reconstruction in all four modes, Unicode offsets, overlap rejection and inconsistent output. These use the regex path and do not evaluate spaCy accuracy.
- **Browser regressions:** five review workflows passed in Chromium and WebKit, plus three earlier Chromium regressions for text-safe rendering, stale responses and error/limit handling. Browser API responses are synthetic fixtures. Mobile widths checked were 320, 375 and 390 CSS pixels; this is browser emulation, not physical-device certification.
- **Live acceptance, 23 September 2026 UTC:** one synthetic request in each browser reached the real API and observed both spaCy and regex detections. Keep/apply, manual redaction, undo and explicit export worked. This verifies the deployed path; two requests do not measure accuracy, throughput or reliability over time.

From the portfolio repository, use Node.js 24 and Python 3.11 or later:

```sh
cd demo-services
npm ci
npx playwright install chromium webkit
node --test --test-concurrency=1 tests/ui/deid-review-ui.test.mjs
UI_BROWSER=webkit node --test --test-concurrency=1 tests/ui/deid-review-ui.test.mjs
node --test --test-name-pattern='^DeID' tests/ui/workspace-ui.test.mjs

python3 -m venv deid/.venv
deid/.venv/bin/python -m pip install -r service-tests/requirements-deid.txt
deid/.venv/bin/python -m unittest discover -s service-tests -p test_deid_review_backend.py
```

On Linux, Playwright may require system libraries; its `install --with-deps` option installs those through the operating system package manager. Package and browser installation require network access. The tests themselves use local synthetic fixtures and do not call the deployed API. For actual model startup and local inference, follow the separate [service setup](../demo-services/README.md#run-locally); the contract environment above intentionally omits spaCy weights.

## What the evidence does not establish

There is no representative labelled corpus or per-label precision/recall result for this adapter. Statistical NER can mislabel names, dates and organisations; patterns miss unfamiliar identifier formats. Adding a manual redaction improves that document's draft but does not train the model. Salted hashes remain pseudonyms and can be linkable within the process lifetime. Kept originals and undetected information may remain in exported output.

No clinical validation, regulatory certification, complete anonymisation, production accuracy or measured reviewer-productivity gain is claimed.
