"""deid — stateless PHI/PII de-identification over HTTP.

Two detector layers run over the submitted text: spaCy `en_core_web_sm` for
PERSON / ORG / GPE / LOC / DATE, and a deterministic regex library for structured
identifiers (SSN, MRN, credit card, IBAN, street, ZIP, ...). Overlaps are resolved
by priority, then a per-label policy decides mask / hash / redact.

WHAT THIS SERVICE DELIBERATELY DOES NOT DO
------------------------------------------
* No database, no queue, no worker, no object storage. The upstream project has
  all of those; none are deployed here, so there is no place for submitted text
  to land.
* No persistence of request bodies. Text lives in one request handler's memory
  and is gone when the response is written.
* The hash salt is generated at process start with `secrets.token_hex` and never
  written down. Restarting the service makes every previously returned hash
  unlinkable — which is the correct property for a public toy, and the wrong one
  for a real pipeline (there you want a managed, rotated, stored salt).
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

from async_worker import run_serialized

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))

from app.deid.engine import POLICY_MAP, DeidEngine  # noqa: E402
from app.deid.recognizers import detect_entities  # noqa: E402

MAX_TEXT_CHARS = int(os.getenv("DEID_MAX_TEXT_SIZE", "6000"))
MAX_BODY_BYTES = int(os.getenv("DEID_MAX_BODY_BYTES", "32768"))
QUEUE_WAIT_S = float(os.getenv("DEID_QUEUE_WAIT_S", "8"))

# Ephemeral, per-process, never persisted. See module docstring.
SALT = secrets.token_hex(16)

EXAMPLES = json.loads((HERE / "data" / "examples.json").read_text())["examples"]

# A spaCy Language object is not safe to call from several threads at once, so
# every analysis runs through a single slot. en_core_web_sm on a 6 000-character
# note takes single-digit to low-tens milliseconds, so this is not a bottleneck.
_nlp_slot = asyncio.Semaphore(1)

ENGINES = {
    "policy": DeidEngine(POLICY_MAP, salt=SALT, default_policy="mask"),
    "mask": DeidEngine({}, salt=SALT, default_policy="mask"),
    "redact": DeidEngine({}, salt=SALT, default_policy="redact"),
    "hash": DeidEngine({}, salt=SALT, default_policy="hash"),
}

app = FastAPI(
    title="deid",
    description="Stateless PHI/PII de-identification. Nothing submitted is stored.",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return JSONResponse(
            {"detail": f"request body exceeds {MAX_BODY_BYTES} bytes"}, status_code=413
        )
    response = await call_next(request)
    response.headers["X-Service"] = "deid"
    # Belt and braces: this response contains whatever the caller sent us.
    response.headers["Cache-Control"] = "no-store"
    return response


class DeidRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    mode: str = "policy"


@app.exception_handler(RequestValidationError)
async def quiet_validation_errors(request: Request, exc: RequestValidationError):
    """Return the reason without echoing the submitted text back.

    FastAPI's default 422 body embeds the offending value under "input". On a
    service whose whole premise is not handling people's text carelessly, mirroring
    a rejected 6 000-character note back to the caller is the wrong default.
    """
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
def warm_up() -> None:
    """Load the spaCy pipeline, and refuse to serve if it is not really there.

    This guards the one failure mode that would quietly ruin the demo. Upstream,
    `recognizers._get_nlp` swallows a failed `spacy.load` and returns None, and
    `_spacy_entities` then returns an empty list — so a missing `en_core_web_sm`
    produces a service that starts cleanly, answers 200, and silently never finds
    a single PERSON / ORG / GPE. A visitor would paste a name, see it survive, and
    conclude the project does not work.

    Warming up also matters on its own: the first call costs ~148 ms against 6-7 ms
    once the model is resident.
    """
    probe = "Warm-up sentence for Jane Doe in Toronto on 01/02/2020."
    found = {e.label for e in detect_entities(probe) if e.detector == "spacy"}
    if not {"PERSON", "GPE"} & found:
        raise RuntimeError(
            "spaCy NER produced no entities on the warm-up probe. "
            "en_core_web_sm is probably not installed in this virtualenv. "
            "Fix: .venv/bin/python -m spacy download en_core_web_sm"
        )


@app.get("/health", response_class=PlainTextResponse, tags=["meta"])
def health() -> str:
    return "ok"


@app.get("/api/examples", tags=["demo"])
def examples() -> dict:
    return {
        "examples": EXAMPLES,
        "policy_map": POLICY_MAP,
        "limits": {"max_text_chars": MAX_TEXT_CHARS, "max_body_bytes": MAX_BODY_BYTES},
    }


def _analyse(text: str, mode: str) -> dict:
    engine = ENGINES[mode]
    result = engine.deidentify(text)

    # detect_entities is re-run only to recover the detector provenance
    # (spaCy vs regex) and the matched surface form, which deidentify() drops.
    by_span = {(e.start, e.end): e for e in detect_entities(text)}
    for item in result["entities"]:
        start, end = item["span"]
        source = by_span.get((start, end))
        item["detector"] = source.detector if source else "unknown"
        item["surface"] = text[start:end]
    return result


@app.post("/api/deidentify", tags=["demo"])
async def deidentify(req: DeidRequest) -> dict:
    if req.mode not in ENGINES:
        raise HTTPException(422, f"mode must be one of {sorted(ENGINES)}")
    text = req.text
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(413, f"text exceeds {MAX_TEXT_CHARS} characters")
    if not text.strip():
        return {"original_len": 0, "result_text": "", "entities": [], "time_ms": 0}

    try:
        return await run_serialized(_nlp_slot, _analyse, text, req.mode, queue_timeout=QUEUE_WAIT_S)
    except asyncio.TimeoutError:
        raise HTTPException(503, "analyser busy, retry shortly") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(HERE / "static" / "index.html")
