"""fraud-graph — score one transaction against a live in-memory transaction graph.

The point of the demo is the *feature layer*, not the model. Each incoming payment
is turned into 14 features that only exist because the sender and receiver have a
history: velocity in the last 10 minutes, whether this counterparty pair is new,
whether a reverse edge already exists (circular transfer), flow asymmetry, shared
counterparties, account age. Those come from a NetworkX graph that is being updated
as you use the page.

Two scores are returned side by side and both are shown in the UI:

  heuristic_score  hand-weighted logistic combination of the same 14 features
  model_score      a small PyTorch MLP (14 -> 42 -> 21 -> 1) run on CPU

HONESTY, because this is a portfolio piece and the numbers are easy to misread:
  * The transaction stream is SYNTHETIC, produced by app/services/simulator.py.
  * The MLP's training labels come from a RULE over that synthetic stream
    (train_model.py::_label_rule), not from any real fraud outcome. Its held-out
    accuracy on those labels would measure rule imitation, not real fraud
    detection. No verified held-out accuracy is exposed by this service.
  * No real financial data is involved anywhere.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from async_worker import run_serialized

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))

from app.services.graph_store import GraphStore, TxEvent  # noqa: E402
from app.services.scoring import FraudScoringService  # noqa: E402
from app.services.simulator import generate_stream  # noqa: E402

MODEL_PATH = str(HERE / "artifacts" / "models" / "edge_model.pt")
SEED_EVENTS = int(os.getenv("FG_SEED_EVENTS", "4000"))
SEED_RNG = int(os.getenv("FG_SEED_RNG", "42"))
MAX_EVENTS = int(os.getenv("FG_MAX_EVENTS", "20000"))
# Visitor traffic mutates the graph. NetworkX never prunes, so without a ceiling
# the process would grow without bound for as long as the demo is up. When the
# ceiling is hit the store is rebuilt from the same deterministic seed, which also
# means the demo always looks the same to the next visitor.
MAX_NODES = int(os.getenv("FG_MAX_NODES", "20000"))
# Reseed after this many visitor-scored payments. This is a demo-quality control,
# not a memory one. Scoring writes into the graph, so the curated examples wear out:
# once someone has scored "sudden spike to a new counterparty", that pair is no
# longer new and the next visitor sees a materially weaker result for the same
# click. Rebuilding from the deterministic seed keeps the landing experience honest
# without taking the live-state behaviour away from anyone mid-session.
RESEED_AFTER = int(os.getenv("FG_RESEED_AFTER", "150"))
MAX_BODY_BYTES = int(os.getenv("FG_MAX_BODY_BYTES", "16384"))
QUEUE_WAIT_S = float(os.getenv("FG_QUEUE_WAIT_S", "8"))

EXAMPLES = json.loads((HERE / "data" / "examples.json").read_text())["examples"]

app = FastAPI(
    title="fraud-graph",
    description="Graph-feature transaction scoring on a synthetic stream.",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# GraphStore and the NetworkX graph underneath it are plain mutable objects with no
# internal locking, and torch inference shares the process. One scorer at a time.
_score_slot = asyncio.Semaphore(1)

store = GraphStore(max_events=MAX_EVENTS)
scorer = FraudScoringService(store=store, model_path=MODEL_PATH)
_rebuilds = 0
_visitor_events = 0


def _seed_graph() -> None:
    """Fill the graph with deterministic synthetic history, ending at "now".

    Scoring a payment against an empty graph is meaningless: every pair is new,
    every velocity is zero, and the graph features are all identically 0.

    The timestamp shift is not cosmetic. `generate_stream` anchors its first event
    at now-20min and then steps forward by ~1-7.5 s per event, so at n=4000 the
    stream runs roughly 4.7 hours into the FUTURE. Fed in unmodified that produces
    a graph where every account is under an hour old (so `sender_new_account` and
    `receiver_new_account` fire on everything) and the 10-minute velocity window
    covers a window that has not happened yet. Sliding the whole stream back so its
    last event lands at "now" gives account ages spread over hours and a velocity
    feature that means what its name says.
    """
    global store, scorer
    store.clear()
    stream = generate_stream(n=SEED_EVENTS, seed=SEED_RNG)
    shift = stream[-1].timestamp_utc - datetime.now(timezone.utc)
    for event in stream:
        event.timestamp_utc = event.timestamp_utc - shift
        scorer.score(event)


class ScoreRequest(BaseModel):
    sender_id: str = Field(min_length=1, max_length=64)
    receiver_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0, le=1e9)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    channel: Literal["wire", "ach", "card", "crypto", "cash"] = "wire"
    country_from: str = Field(default="US", min_length=2, max_length=2)
    country_to: str = Field(default="US", min_length=2, max_length=2)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return JSONResponse(
            {"detail": f"request body exceeds {MAX_BODY_BYTES} bytes"}, status_code=413
        )
    response = await call_next(request)
    response.headers["X-Service"] = "fraud-graph"
    return response


@app.exception_handler(RequestValidationError)
async def quiet_validation_errors(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
                for err in exc.errors()
            ]
        },
    )


@app.on_event("startup")
def startup() -> None:
    if scorer.model is None:
        # FraudScoringService swallows a failed load and falls back to heuristics
        # only. That would still answer 200 while quietly dropping the entire model
        # half of the demo, so fail loudly instead.
        raise RuntimeError(
            f"edge model not loaded from {MODEL_PATH}. "
            "Fix: .venv/bin/python train_model.py --output artifacts/models/edge_model.pt"
        )
    _seed_graph()


@app.get("/health", response_class=PlainTextResponse, tags=["meta"])
def health() -> str:
    return "ok"


def _examples_snapshot() -> dict:
    return {
        "examples": EXAMPLES,
        "graph": store.summary(),
        "model": {
            "path": Path(MODEL_PATH).name,
            "architecture": "EdgeMLP 14 -> 42 -> 21 -> 1, ReLU, CPU inference",
            "training_data": "synthetic stream, labels from a rule (not real fraud outcomes)",
            "blend": "final = max(heuristic, 0.85*heuristic + 0.15*model)",
        },
        "limits": {"max_nodes": MAX_NODES, "seed_events": SEED_EVENTS,
                   "reseed_after": RESEED_AFTER},
    }


def _graph_snapshot() -> dict:
    summary = store.summary()
    summary["rebuilds"] = _rebuilds
    summary["visitor_events"] = _visitor_events
    summary["reseed_after"] = RESEED_AFTER
    return summary


async def _serialized_snapshot(function) -> dict:
    try:
        return await run_serialized(_score_slot, function, queue_timeout=QUEUE_WAIT_S)
    except asyncio.TimeoutError:
        raise HTTPException(503, "scorer busy, retry shortly") from None


@app.get("/api/examples", tags=["demo"])
async def examples() -> dict:
    return await _serialized_snapshot(_examples_snapshot)


@app.get("/api/graph", tags=["demo"])
async def graph_summary() -> dict:
    return await _serialized_snapshot(_graph_snapshot)


def _score(req: ScoreRequest) -> dict:
    global _rebuilds, _visitor_events
    event = TxEvent(
        tx_id=f"WEB-{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
        sender_id=req.sender_id,
        receiver_id=req.receiver_id,
        amount=float(req.amount),
        currency=req.currency.upper(),
        channel=req.channel,
        country_from=req.country_from.upper(),
        country_to=req.country_to.upper(),
        timestamp_utc=datetime.now(timezone.utc),
    )
    payload = scorer.score(event)

    _visitor_events += 1
    if _visitor_events >= RESEED_AFTER or store.graph.number_of_nodes() > MAX_NODES:
        _seed_graph()
        _rebuilds += 1
        _visitor_events = 0

    payload["graph"] = store.summary()
    payload["graph"]["rebuilds"] = _rebuilds
    payload["graph"]["visitor_events"] = _visitor_events
    payload["graph"]["reseed_after"] = RESEED_AFTER
    return payload


@app.post("/api/score", tags=["demo"])
async def score(req: ScoreRequest) -> dict:
    try:
        return await run_serialized(_score_slot, _score, req, queue_timeout=QUEUE_WAIT_S)
    except asyncio.TimeoutError:
        raise HTTPException(503, "scorer busy, retry shortly") from None


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(HERE / "static" / "index.html")
