# Portfolio demo services

Inspectable runtime adapters for the four [live portfolio demos](https://stelioszach.com/#demos). These small applications wrap selected code from the linked projects. They are demonstrations, not validated medical or financial decision systems.

| Service | What runs | Source project |
| --- | --- | --- |
| `smt-verify` | A bounded Z3 verifier for structured constraints and candidate answers. No paid language-model generation. | [LLM + SMT](https://github.com/stelioszach03/llm-smt-verifiable-reasoning) |
| `deid` | English entity detection with spaCy and regex rules, followed by explicit transformation policies. Detection can miss identifiers. | [De-identification studio](https://github.com/stelioszach03/deid-privacy-studio) |
| `fraud-graph` | Transaction graph features, heuristic scoring and a small CPU PyTorch model. The stream and training labels are synthetic. | [Public deployed implementation](fraud-graph/) |
| `mta-scan` | Public MTA feed collection, streaming features and anomaly scoring, plus a separately labelled frozen replay. | [NYC subway anomaly detection](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection) |

Use fabricated examples only. The text demo does not guarantee anonymization. Fraud scores are not fraud probabilities, and successive graph runs change their shared synthetic history. The subway replay is a small sanity evaluation, not a benchmark or official MTA incident annotation.

## Workspace controls

- The constraint workspace keeps structured inputs and actual solver responses inspectable; recorded outcomes are not generated benchmark claims.
- The transaction workspace separates current graph-derived features, scoring explanations and selected in-memory run snapshots. Sequential scoring changes synthetic history, so comparing two runs is not a controlled counterfactual.
- The de-identification workspace exposes detections, transformation policies and review filters. Edits invalidate stale results; the output still requires human review.
- The subway workspace separates live observations, window statistics and frozen replay. Search/score/route filters narrow map observations, while window-wide totals stay labelled. An explicit export preserves the successful snapshot's window; it does not export tile credentials. Mobile map panning can be enabled and locked again to return control to page scrolling.

The optional subway Mapbox setup is deployment-only: copy `mta-scan/static/map-config.example.json` to `map-config.json` and configure an origin-restricted public token with `styles:read`, `fonts:read` and `styles:tiles`. Never use a secret token. The blank template is published; runtime configuration is excluded. Without valid configuration, the map uses OpenStreetMap. The native Mapbox GL renderer uses the self-hosted CSP build and worker. If vector rendering is unavailable, the workspace can use its labelled Leaflet fallback. Map style selection changes the basemap, not the underlying observations or model. Provider attribution and the Mapbox logo remain visible when applicable. Map resources and SDK usage requests reach the active provider under its terms; provider SDK caching or usage storage is separate from the application.

## Run locally

Use Python 3.11 or later and a **separate virtual environment for each service**. Runtime dependency sets differ; do not combine them into one environment. For example, from this directory:

```sh
cd smt-verify
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn service:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The other services expose the same ASGI entry point, `service:app`, from their own directories. Run one at a time or choose different ports. Production nginx/systemd configuration and runtime state are deliberately excluded; this is not a turnkey public-deployment package.

Reverse-proxy routing matters: when serving a demo beneath `/demos/<name>/`, its service prefix must take precedence over generic image/font extension rules. In nginx, a prefix location marked `^~` prevents a broader regex location from intercepting vendored SVG or other static assets. Otherwise the adapter can return an asset successfully while the public URL returns404. Configure the actual upstream and path rewriting for your deployment; production configuration and credentials are not included here.

Additional setup:

- **De-identification:** install the matching English spaCy model after the requirements: `.venv/bin/python -m spacy download en_core_web_sm`. The recorded runtime used model 3.8.0 with spaCy 3.8.7. Startup fails if the model is unavailable.
- **Fraud graph:** on Linux, install the CPU PyTorch wheel before the remaining requirements: `.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1`. Then install `requirements.txt`. The included 8,806-byte checkpoint is trained on synthetic rule-generated labels; it is not an external fraud benchmark. `train_model.py` is included for inspection; no training is run by the tests or CI. Load only trusted model files.
- **Subway monitor:** to inspect the UI/replay without collecting external feeds, start with `MTA_COLLECTOR_ENABLED=0 .venv/bin/python -m uvicorn service:app --host 127.0.0.1 --port 8000`. The live view will correctly remain unavailable. Normal collector startup uses public MTA feeds. Runtime SQLite/model state defaults to a local `var/` directory, which is not source-controlled. Basemap providers may receive browser tile requests; map/data attribution is retained.

### MTA measurement correction (adapter 2.1.1)

Live `headway_sec` now means the estimated arrival gap between the nearest two distinct upcoming trips at the same route, exact stop and direction. Only the first snapshot for a trip pair is scored during a collector process (a bounded four-hour deduplication window); ETA revisions and reordered predictions do not create additional train observations. Restarting clears this in-memory pair cache and feature history. This is not observed train-passage ground truth. Missing trip IDs, canceled/deleted trips, skipped/no-data stops, vehicle timestamps, stale/missing feed timestamps and differential feeds are excluded.

The earlier algorithm subtracted changes in the earliest ETA, which could mistake a revision for a train passage. Its data and checkpoint are preserved separately: the corrected defaults use `mta-arrival-gaps-v2.db` and `model-arrival-gaps-v2.pkl`. Do not override `MTA_DB_PATH` to the old database. The constructed 216-row replay remains unchanged and does not validate this new live measurement. [GTFS-Realtime field semantics](https://gtfs.org/documentation/realtime/reference/) distinguish trip predictions from vehicle observation timestamps.

Departure-only predictions are excluded rather than mixed with arrival estimates. HTTP responses have a 4 MiB decoded-body limit and bounded phase/deadline checks. Live/stale status follows current source and collection-cycle freshness; the age of the last newly scored pair is reported separately, so an unchanged pair does not falsely mark fresh feeds stale. Partial feed coverage is explicit.

Run the offline collector regressions after installing the MTA runtime dependencies:

```sh
mta-scan/.venv/bin/python -m unittest discover -s mta-scan/tests -p 'test_*.py'
```

The pinned requirement files describe the recorded runtime. The lightweight CI below does **not** validate fresh installations of every heavy model dependency on every OS.

## Portable checks

From `demo-services/`, with Node.js 24 and Python 3.11 or later:

```sh
npm ci
npm test
npm run test:python
npm run test:syntax
```

The cancellation tests verify that a cancelled request cannot release a still-running worker's serialization slot and that worker failures release it correctly. Source checks parse Python/JSON and verify the exact included synthetic checkpoint. The Node syntax check parses inline browser scripts and vendored JavaScript without executing browser code. The dev-only jsdom suite exercises the SMT and fraud interfaces with recorded synthetic API fixtures, including request locking, error handling, retry behavior and input/output safety.

The DeID/MTA browser suites are separate:

```sh
npx playwright install chromium
npm run test:browser
```

The suites use local static assets and synthetic API responses. External map/style/tile/usage requests are blocked or fulfilled with local fixtures; no deployed API, billing request or model is used. They check input/result isolation, text-safe rendering, Unicode spans, state changes and mobile fit using Chromium. Native-map coverage runs the real Mapbox GL SDK with software WebGL and intercepted fixtures. The earlier raster-map suite remains explicit fallback coverage, rather than being presented as a native renderer test. CI installs Chromium with its Linux system dependencies in a separate bounded job.

These checks do not install spaCy, PyTorch, River or Z3; train models; call live MTA feeds; or run full ASGI/model integration. Those heavier service acceptance steps remain separate. The browser suite is bounded regression coverage, not a complete accessibility certification or physical-device test.

## Optional service-contract checks

These tests are kept in `service-tests/`, outside minimal CI discovery. Use separate environments: DeID and fraud use a vendored package named `app`, while SMT uses `cegvr`; another project checkout must not satisfy those imports.

SMT's contract tests exercise the actual ASGI endpoint and local Z3 solver with
synthetic SAT/UNSAT examples. They verify that incomplete assignments return
`REJECTED_DOMAIN` before solver construction, strings/floats receive a malformed
candidate response, and native integer/boolean domain checks remain distinct:

```sh
python3 -m venv smt-verify/.venv
smt-verify/.venv/bin/python -m pip install -r service-tests/requirements-smt.txt
smt-verify/.venv/bin/python -m unittest discover -s service-tests -p test_smt_candidate_contract.py -v
```

The two candidate-contract modules are pinned to reviewed upstream commit
`dc7b9de89f3a507705b259c870af82eda763621f`; see [NOTICE](NOTICE). These checks make
no LLM/provider requests and do not execute a research study.

DeID's four contract checks use the regex path without installing spaCy weights or running application startup:

```sh
python3 -m venv deid/.venv
deid/.venv/bin/python -m pip install -r service-tests/requirements-deid.txt
deid/.venv/bin/python -m unittest discover -s service-tests -p test_deid_review_backend.py
```

Fraud's ASGI and neighborhood checks require its CPU runtime dependencies but do not train a model or call a deployed service:

```sh
python3 -m venv fraud-graph/.venv
fraud-graph/.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1
fraud-graph/.venv/bin/python -m pip install -r service-tests/requirements-fraud.txt
fraud-graph/.venv/bin/python -m unittest discover -s service-tests -p 'test_fraud*.py'
```

The neighborhood fixture checks actual bounded graph edges and snapshot/reset timing. These optional service checks are distinct from model-quality evaluation or production acceptance.

## Data, provenance and licensing

`SOURCE_MANIFEST.json` identifies the published file bytes. Each service retains its upstream MIT notice, and Leaflet retains its own licence. MTA data provenance is documented in `mta-scan/data/SOURCES.md`; those data and tile-provider rights are not relicensed by the website's MIT grant. Fabricated examples and the tiny synthetic model are explicitly labelled. See [NOTICE](NOTICE).

No environment files, credentials, user submissions, live databases, rolling feed state, logs, virtual environments or private repositories are included.
