"""smt-verify — a read-only HTTP wrapper around the CEGVR candidate verifier.

Serves exactly one capability: given a constraint problem and a proposed answer,
run Z3 and report whether the answer is certified, and if not, why.

Deliberately NOT served: the LLM candidate-generation half of the upstream
project. That path costs real money per call and is not exposed here.

Statelessness: nothing is written to disk, no database, no request logging of
payload contents. Each request is independent.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

from async_worker import run_serialized

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))

from cegvr.candidate.types import CandidateOutput  # noqa: E402
from cegvr.candidate.verifier import verify_linear_candidate  # noqa: E402

# ---------------------------------------------------------------------------
# Resource guards. A public endpoint that runs a solver is a DoS target, so
# every dimension that could make Z3 expensive is bounded before it is called.
# ---------------------------------------------------------------------------
MAX_BODY_BYTES = int(os.getenv("SMTV_MAX_BODY_BYTES", "32768"))
MAX_VARIABLES = int(os.getenv("SMTV_MAX_VARIABLES", "40"))
MAX_CONSTRAINTS = int(os.getenv("SMTV_MAX_CONSTRAINTS", "200"))
MAX_TERMS_PER_CONSTRAINT = int(os.getenv("SMTV_MAX_TERMS", "64"))
MAX_ABS_MAGNITUDE = int(os.getenv("SMTV_MAX_ABS_MAGNITUDE", "1000000"))
SOLVER_TIMEOUT_MS = int(os.getenv("SMTV_SOLVER_TIMEOUT_MS", "3000"))
# MUST stay at 1. The vendored verifier builds terms with z3.Int()/z3.Bool(), which use
# Z3's *global default context*. That context is not thread-safe: running two solves
# concurrently in a threadpool corrupts it and raises Z3Exception (reproduced locally with
# 8 parallel requests at MAX_CONCURRENT=2 — every one failed). Serializing solves is also
# fine for load here: the demo problems solve in well under 10 ms.
MAX_CONCURRENT_SOLVES = int(os.getenv("SMTV_MAX_CONCURRENT", "1"))
QUEUE_WAIT_S = float(os.getenv("SMTV_QUEUE_WAIT_S", "5"))

EXAMPLES = json.loads((HERE / "data" / "examples.json").read_text())["examples"]

app = FastAPI(
    title="smt-verify",
    description="Z3 verification of proposed answers to constraint problems.",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

if MAX_CONCURRENT_SOLVES != 1:
    raise RuntimeError("The shared Z3 context requires exactly one solver worker")
_solve_slots = asyncio.Semaphore(1)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return JSONResponse(
            {"detail": f"request body exceeds {MAX_BODY_BYTES} bytes"}, status_code=413
        )
    response = await call_next(request)
    response.headers["X-Service"] = "smt-verify"
    return response


# ---------------------------------------------------------------------------
# Request models. Constraints are parsed by the upstream Pydantic grammar, so
# only a fixed set of constraint kinds can ever reach the encoder. There is no
# free-form SMT-LIB input and no user-supplied code anywhere in this service.
# ---------------------------------------------------------------------------
class Bounds(BaseModel):
    lower: int | None = None
    upper: int | None = None


class VariableSpec(BaseModel):
    name: str = Field(max_length=64)
    domain: Literal["int", "bool"] = "int"
    bounds: Bounds | None = None


class VerifyRequest(BaseModel):
    variables: list[VariableSpec]
    constraints: list[dict[str, Any]]
    candidate: dict[str, Any]


def _reject(msg: str) -> HTTPException:
    return HTTPException(status_code=422, detail=msg)


def _check_size(req: VerifyRequest) -> None:
    if not req.variables:
        raise _reject("at least one variable is required")
    if len(req.variables) > MAX_VARIABLES:
        raise _reject(f"at most {MAX_VARIABLES} variables are allowed in this demo")
    if len(req.constraints) > MAX_CONSTRAINTS:
        raise _reject(f"at most {MAX_CONSTRAINTS} constraints are allowed in this demo")

    for spec in req.variables:
        b = spec.bounds
        for edge in (b.lower, b.upper) if b else ():
            if edge is not None and abs(int(edge)) > MAX_ABS_MAGNITUDE:
                raise _reject(f"bound magnitude above {MAX_ABS_MAGNITUDE}")

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 6:
            raise _reject("constraint nesting is too deep for this demo")
        if not isinstance(node, dict):
            return
        terms = node.get("terms")
        if isinstance(terms, list) and len(terms) > MAX_TERMS_PER_CONSTRAINT:
            raise _reject(f"at most {MAX_TERMS_PER_CONSTRAINT} terms per constraint")
        for key in ("rhs", "offset", "lower", "upper"):
            value = node.get(key)
            if isinstance(value, (int, float)) and abs(value) > MAX_ABS_MAGNITUDE:
                raise _reject(f"'{key}' magnitude above {MAX_ABS_MAGNITUDE}")
        if isinstance(terms, list):
            for term in terms:
                if not isinstance(term, dict):
                    raise _reject("each constraint term must be an object")
                coefficient = term.get("coefficient")
                if isinstance(coefficient, (int, float)) and abs(coefficient) > MAX_ABS_MAGNITUDE:
                    raise _reject(f"coefficient magnitude above {MAX_ABS_MAGNITUDE}")
        for key in ("constraints", "constraint"):
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    walk(item, depth + 1)
            elif isinstance(child, dict):
                walk(child, depth + 1)

    for constraint in req.constraints:
        walk(constraint)


@app.get("/health", response_class=PlainTextResponse, tags=["meta"])
def health() -> str:
    return "ok"


@app.get("/api/examples", tags=["demo"])
def examples() -> dict:
    """The pre-filled cases shown in the UI, one per verifier outcome."""
    return {
        "examples": EXAMPLES,
        "limits": {
            "max_variables": MAX_VARIABLES,
            "max_constraints": MAX_CONSTRAINTS,
            "solver_timeout_ms": SOLVER_TIMEOUT_MS,
            "max_body_bytes": MAX_BODY_BYTES,
        },
    }


@app.post("/api/verify", tags=["demo"])
async def verify(req: VerifyRequest) -> dict:
    _check_size(req)

    try:
        candidate = CandidateOutput(**req.candidate)
    except ValidationError as exc:
        raise _reject(f"malformed candidate: {exc.errors()[0]['msg']}") from exc

    problem = {
        "variables": [spec.model_dump(exclude_none=True) for spec in req.variables],
        "constraints": req.constraints,
    }

    try:
        result = await run_serialized(
            _solve_slots, verify_linear_candidate, problem, candidate,
            timeout_ms=SOLVER_TIMEOUT_MS, queue_timeout=QUEUE_WAIT_S
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="verifier busy, retry shortly") from None
    except ValueError as exc:
        # Upstream raises "Invalid constraint <id>: <full pydantic dump>". Keep the
        # useful prefix; the full dump echoes the payload back and is noise.
        raise _reject(str(exc).split(":")[0] + " — unsupported kind or malformed fields") from exc
    except Exception as exc:  # noqa: BLE001 - never leak a stack trace publicly
        raise HTTPException(status_code=422, detail=f"could not encode problem: {type(exc).__name__}") from exc

    payload = result.model_dump()
    payload["explanation"] = OUTCOMES.get(result.verified_outcome, "")
    return payload


OUTCOMES: dict[str, str] = {
    "CERTIFIED_SAT": "Z3 proved the proposed assignment satisfies every constraint.",
    "FAILED_CERTIFICATION": "The assignment is inside its declared bounds but breaks "
    "constraints. The unsat core is a conflicting subset, not necessarily minimal.",
    "REJECTED_DOMAIN": "Rejected by the pre-check: a variable is missing, extra, or "
    "outside its declared domain. The solver was never called.",
    "CERTIFIED_UNSAT": "Z3 proved no assignment can satisfy all constraints. The "
    "'unsat claim' was right.",
    "FALSE_UNSAT_CLAIM": "The claim of impossibility is wrong — here is a satisfying "
    "assignment as a counter-witness.",
    "VERIFIER_TIMEOUT": f"The solver hit the {SOLVER_TIMEOUT_MS} ms demo timeout. "
    "Unknown, not disproved.",
    "VERIFIER_UNKNOWN": "The solver returned unknown.",
}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(HERE / "static" / "index.html")
