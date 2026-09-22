# Portfolio demo services

Inspectable runtime adapters for the four [live portfolio demos](https://stelioszach.com/#demos). These small applications wrap selected code from the linked projects. They are demonstrations, not validated medical or financial decision systems.

| Service | What runs | Source project |
| --- | --- | --- |
| `smt-verify` | A bounded Z3 verifier for structured constraints and candidate answers. No paid language-model generation. | [LLM + SMT](https://github.com/stelioszach03/llm-smt-verifiable-reasoning) |
| `deid` | English entity detection with spaCy and regex rules, followed by explicit transformation policies. Detection can miss identifiers. | [De-identification studio](https://github.com/stelioszach03/deid-privacy-studio) |
| `fraud-graph` | Transaction graph features, heuristic scoring and a small CPU PyTorch model. The stream and training labels are synthetic. | [Graph fraud command center](https://github.com/stelioszach03/graph-fraud-command-center) |
| `mta-scan` | Public MTA feed collection, streaming features and anomaly scoring, plus a separately labelled frozen replay. | [NYC subway anomaly detection](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection) |

Use fabricated examples only. The text demo does not guarantee anonymization. Fraud scores are not fraud probabilities, and successive graph runs change their shared synthetic history. The subway replay is a small sanity evaluation, not a benchmark or official MTA incident annotation.

## Run locally

Use Python 3.11 or later and a **separate virtual environment for each service**. Runtime dependency sets differ; do not combine them into one environment. For example, from this directory:

```sh
cd smt-verify
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn service:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The other services expose the same ASGI entry point, `service:app`, from their own directories. Run one at a time or choose different ports. Production nginx/systemd configuration and runtime state are deliberately excluded; this is not a turnkey public-deployment package.

Additional setup:

- **De-identification:** install the matching English spaCy model after the requirements: `.venv/bin/python -m spacy download en_core_web_sm`. The recorded runtime used model 3.8.0 with spaCy 3.8.7. Startup fails if the model is unavailable.
- **Fraud graph:** on Linux, install the CPU PyTorch wheel before the remaining requirements: `.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1`. Then install `requirements.txt`. The included 8,806-byte checkpoint is trained on synthetic rule-generated labels; it is not an external fraud benchmark. `train_model.py` is included for inspection; no training is run by the tests or CI. Load only trusted model files.
- **Subway monitor:** to inspect the UI/replay without collecting external feeds, start with `MTA_COLLECTOR_ENABLED=0 .venv/bin/python -m uvicorn service:app --host 127.0.0.1 --port 8000`. The live view will correctly remain unavailable. Normal collector startup uses public MTA feeds. Runtime SQLite/model state defaults to a local `var/` directory, which is not source-controlled. Basemap providers may receive browser tile requests; map/data attribution is retained.

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

The DeID/MTA browser suite is separate:

```sh
npx playwright install chromium
npm run test:browser
```

It starts an embedded loopback server on an ephemeral port, supplies synthetic API responses, and aborts all nonlocal browser requests, including map tiles. It checks input/result isolation, text-safe rendering, Unicode spans, state changes and mobile fit using real Chromium. CI installs Chromium with its Linux system dependencies in a separate bounded job. No deployed API or model is used.

These checks do not install spaCy, PyTorch, River or Z3; train models; call live MTA feeds; or run full ASGI/model integration. Those heavier service acceptance steps remain separate. The browser suite is bounded regression coverage, not a complete accessibility certification or physical-device test.

## Data, provenance and licensing

`SOURCE_MANIFEST.json` identifies the published file bytes. Each service retains its upstream MIT notice, and Leaflet retains its own licence. MTA data provenance is documented in `mta-scan/data/SOURCES.md`; those data and tile-provider rights are not relicensed by the website's MIT grant. Fabricated examples and the tiny synthetic model are explicitly labelled. See [NOTICE](NOTICE).

No environment files, credentials, user submissions, live databases, rolling feed state, logs, virtual environments or private repositories are included.
