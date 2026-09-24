"""MTA-Scan — live subway anomaly detection, one process.

    uvicorn service:app --host 127.0.0.1 --port 18404

The whole demo is this file plus the `mtascan` package: an API, a static
frontend, and a background collector that polls the MTA's public GTFS-Realtime
feeds, scores headways with an online model, and writes into a hard-bounded
SQLite window. No database server, no message broker, no API key, no GPU, no
torch.

THE FOUR ENDPOINTS THAT MATTER
------------------------------
GET /api/health    liveness, plus feeds / storage / model / retention detail
GET /api/state     one call, everything the page needs to render immediately
GET /api/anomalies the ranked live list, filterable
GET /api/replay    the frozen labelled evaluation with its sample size attached

/api/replay is the answer to "a recruiter opens this on a quiet Tuesday and the
network is behaving": measured results are on screen in the first second,
without waiting for New York to misbehave.

NOTHING HERE FAILS LOUDLY
-------------------------
If the MTA is down, the collector records the failure per feed and the API
keeps serving the last known window with an explicit age. There is no code path
that renders a blank screen or leaks a stack trace: unhandled exceptions become
a JSON body with a request id, and /api/state degrades field by field.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from mtascan.collector import FEEDS, Collector
from mtascan.config import get_settings
from mtascan.scoring import load_or_new, save_bundle
from mtascan.stops import load_routes, load_stops
from mtascan.store import Store


logging.basicConfig(
    level=os.environ.get("MTA_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# httpx logs a line per request at INFO: eight feeds every 30 s is 23 000
# lines a day of "HTTP/1.1 200 OK" in the journal, which buries the one line
# that matters when a feed actually breaks.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("mtascan.service")

SETTINGS = get_settings()
STARTED_AT = time.time()

DATASET_CAVEAT = (
    "Representative labelled replay: 216 rows, 16 positive, 3 routes, 6 stops, 3 incidents. "
    "A sanity evaluation, not a benchmark, and not official MTA incident annotation."
)


# --------------------------------------------------------------------------
# process-wide singletons
# --------------------------------------------------------------------------
_store: Store | None = None
_collector: Collector | None = None
_collector_task: asyncio.Task | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store(SETTINGS.db_path)
    return _store


def _iso(epoch: float | int | None) -> str | None:
    if not epoch:
        return None
    return (
        datetime.fromtimestamp(float(epoch), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _now() -> int:
    return int(time.time())


def _window_seconds(window: str) -> int:
    text = (window or "").strip().lower()
    try:
        if text.endswith("m"):
            return max(60, min(48 * 3600, int(float(text[:-1]) * 60)))
        if text.endswith("h"):
            return max(60, min(48 * 3600, int(float(text[:-1]) * 3600)))
    except ValueError:
        pass
    return SETTINGS.default_window_sec


# --------------------------------------------------------------------------
# background collection
# --------------------------------------------------------------------------
async def _collector_loop(collector: Collector) -> None:
    """One cycle every poll_seconds, each in a worker thread.

    The cycle is blocking (eight HTTP fetches, protobuf parsing, scoring), so
    it runs via to_thread — a slow MTA response must never stall the API's
    event loop and make the page look dead.
    """
    # First cycle immediately, so the demo has data as soon as possible.
    while True:
        try:
            result = await asyncio.to_thread(collector.run_cycle)
            log.info(
                "cycle %d: feeds %d/%d, %d arrivals, %d observations, %.0f ms",
                collector.cycles,
                result.feeds_ok,
                len(result.feeds),
                result.arrivals_seen,
                result.observations,
                result.duration_ms,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("collector loop error (continuing)")
        await asyncio.sleep(max(5.0, SETTINGS.poll_seconds))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _collector, _collector_task

    db = store()
    log.info("storage at %s (%s)", SETTINGS.db_path, _human_bytes(db.file_bytes()))

    # Apply the caps once at boot: if the process died mid-window, or the box
    # was off for a week, the first thing that happens is a cleanup.
    try:
        report = db.enforce_limits(
            retention_sec=SETTINGS.retention_sec,
            max_rows=SETTINGS.max_rows,
            max_bytes=SETTINGS.max_db_bytes,
        )
        log.info("startup retention pass: %s", json.dumps(report))
    except Exception:
        log.exception("startup retention pass failed")

    bundle = load_or_new(SETTINGS.model_path)
    _collector = Collector(settings=SETTINGS, store=db, bundle=bundle)

    if SETTINGS.collector_enabled:
        _collector_task = asyncio.create_task(_collector_loop(_collector))
        log.info("collector started: %d feeds every %.0fs", len(FEEDS), SETTINGS.poll_seconds)
    else:
        log.warning("collector disabled (MTA_COLLECTOR_ENABLED=0) — serving stored data only")

    try:
        yield
    finally:
        if _collector_task is not None:
            _collector_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _collector_task
        if _collector is not None:
            with contextlib.suppress(Exception):
                save_bundle(SETTINGS.model_path, _collector.bundle)
        db.close()


app = FastAPI(
    title="MTA-Scan",
    version=SETTINGS.version,
    description="Live anomaly detection on NYC subway headways from public GTFS-Realtime feeds.",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    """A stack trace is never the demo. Log it, hand back something renderable."""
    incident = uuid.uuid4().hex[:12]
    log.exception("unhandled error on %s [%s]", request.url.path, incident)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "The request failed. The page keeps showing the last known data.",
            "incident_id": incident,
        },
    )


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


# What fraction of tracked route-stops must have a usable baseline before the
# live ranking is worth reading. Not 1.0: stops that have just appeared are
# always somewhere in the tail, so demanding all of them would never go warm.
WARM_READY_FRACTION = 0.80


def _model_maturity(
    *,
    rows_seen: int,
    drift_events: int,
    mae_ema: float | None,
    history: dict[str, float] | None,
) -> dict[str, Any]:
    """Report whether the live ranking is worth reading yet.

    The signal is the occupancy of the per-stop feature windows, NOT
    ``rows_seen``. Two reasons, both measured:

    1. ``rows_seen`` is a network-wide total while every saturating term in the
       score is per-stop. 20 000 rows over 20 000 stops is one headway each and
       a ranking of pure ties; the same total over 1 600 stops is a usable
       model. A row threshold cannot tell those apart.
    2. ``rows_seen`` is restored from the model checkpoint on restart, but the
       feature windows are **in-memory and are not**. After a restart the
       counter is as high as ever while every window is empty and every score
       is back at 1.00 — so a row-based gate would report "warm" over exactly
       the red map it exists to warn about.

    Measured cold start (rows grouped by the stop's observation index at the
    time it was scored): 0.0 % of 1st observations sit at exactly 1.00, 38.4 %
    of 2nd, 35.1 % of 3rd, 8.5 % of 4th, 0.0 % of 5th. The spike is entirely
    in the window where the stop has too little history for a real MAD.
    """
    history = history or {}
    keys = int(history.get("keys", 0) or 0)
    ready = int(history.get("ready", 0) or 0)
    ready_fraction = float(history.get("ready_fraction", 0.0) or 0.0)
    mean_history = float(history.get("mean_history", 0.0) or 0.0)

    warm = keys > 0 and ready_fraction >= WARM_READY_FRACTION

    if warm:
        note = None
    elif keys == 0:
        note = (
            "No live history yet — the collector has not completed a cycle with "
            "usable headways. The measured replay below is unaffected."
        )
    else:
        note = (
            f"Still learning: {ready} of {keys} route-stops "
            f"({ready_fraction * 100:.0f} %) have enough history for a baseline, "
            f"averaging {mean_history:.1f} headways each. Each stop is scored against "
            "its own rolling baseline, so until it has a few the deviation saturates "
            "and the score pins to 1.00 — expect the live ranking to be mostly ties. "
            "The measured replay below is unaffected."
        )

    return {
        "rows_seen": rows_seen,
        "drift_resets": drift_events,
        "mae_ema_sec": round(mae_ema, 1) if mae_ema is not None else None,
        "route_stops_tracked": keys,
        "route_stops_with_baseline": ready,
        "baseline_ready_pct": round(ready_fraction * 100, 1),
        "mean_headways_per_route_stop": round(mean_history, 2),
        "warm_at_ready_pct": round(WARM_READY_FRACTION * 100, 1),
        "maturity": "warm" if warm else "learning",
        "maturity_note": note,
    }


# --------------------------------------------------------------------------
# /api/health
# --------------------------------------------------------------------------
@app.get("/api/health", tags=["health"])
def health() -> dict[str, Any]:
    """Cheap liveness probe — no MTA call, no heavy query."""
    return {
        "ok": True,
        "service": "mta-scan",
        "version": SETTINGS.version,
        "measurement": "first_snapshot_predicted_arrival_gap_v2",
        "measurement_note": "Gap between two distinct upcoming trips; not an observed train passage or incident label.",
        "uptime_sec": int(time.time() - STARTED_AT),
    }


@app.get("/api/health/deep", tags=["health"])
def health_deep() -> dict[str, Any]:
    """Everything an operator would want: feeds, storage, retention, model."""
    db = store()
    now = _now()
    checks: dict[str, Any] = {}
    status = "ok"

    # --- storage, and the limits that keep it that way -------------------
    try:
        oldest, newest = db.time_span()
        used = db.file_bytes()
        checks["storage"] = {
            "ok": True,
            "engine": "sqlite",
            "path": str(SETTINGS.db_path),
            "rows": db.count(),
            "bytes": used,
            "bytes_human": _human_bytes(used),
            "oldest_utc": _iso(oldest),
            "newest_utc": _iso(newest),
            "window_hours": round((newest - oldest) / 3600.0, 2) if oldest and newest else 0.0,
            "limits": {
                "retention_hours": SETTINGS.retention_hours,
                "max_rows": SETTINGS.max_rows,
                "max_bytes": SETTINGS.max_db_bytes,
                "max_bytes_human": _human_bytes(SETTINGS.max_db_bytes),
                "pct_of_size_cap": round(100.0 * used / SETTINGS.max_db_bytes, 1),
            },
            "last_cleanup": db.get_meta("last_cleanup"),
        }
        if used > SETTINGS.max_db_bytes:
            checks["storage"]["ok"] = False
            status = "degraded"
    except Exception as exc:
        checks["storage"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        status = "degraded"

    # --- live feeds -------------------------------------------------------
    collector = _collector
    if collector is None or not SETTINGS.collector_enabled:
        checks["feeds"] = {"ok": False, "enabled": False, "detail": "collector disabled"}
        status = "degraded" if status == "ok" else status
    elif collector.last_cycle is None:
        checks["feeds"] = {"ok": True, "enabled": True, "state": "warming_up", "cycles": 0}
    else:
        cycle = collector.last_cycle
        age = now - cycle.started_epoch
        checks["feeds"] = {
            "ok": cycle.feeds_ok > 0,
            "enabled": True,
            "state": "live" if age <= SETTINGS.stale_after_sec else "stale",
            "cycles": collector.cycles,
            "last_cycle_age_sec": age,
            **cycle.as_dict(),
        }
        if cycle.feeds_ok == 0:
            status = "degraded"

    # --- geometry ---------------------------------------------------------
    stops, _ = load_stops(str(SETTINGS.stops_path))
    checks["gtfs_static"] = {"ok": bool(stops), "stops": len(stops), "path": str(SETTINGS.stops_path)}
    if not stops:
        status = "degraded"

    # --- model ------------------------------------------------------------
    if collector is not None:
        telemetry = collector.bundle.telemetry
        checks["model"] = {
            "ok": True,
            "kind": "river PARegressor + HalfSpaceTrees + ADWIN (CPU, no labels)",
            "rows_seen": telemetry.rows_seen,
            "rows_scored": telemetry.rows_scored,
            "drift_events": telemetry.drift_events,
            "mae_ema_sec": round(telemetry.mae_ema, 2),
            "last_batch_scored": telemetry.last_batch_scored,
            "checkpoint": str(SETTINGS.model_path),
            "checkpoint_bytes": (
                SETTINGS.model_path.stat().st_size if SETTINGS.model_path.exists() else 0
            ),
        }
    else:
        checks["model"] = {"ok": False, "detail": "not initialised"}

    return {
        "status": status,
        "version": SETTINGS.version,
        "checks": checks,
        "timestamp_utc": _iso(now),
    }


# --------------------------------------------------------------------------
# /api/state — the single call the page renders from
# --------------------------------------------------------------------------
@app.get("/api/state", tags=["live"])
def state(
    response: Response,
    window: str = Query(default="30m", description="Look-back window, e.g. 15m, 1h, 6h"),
    route_id: str = Query(default="All"),
    top: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    """One request, everything: counters, map points, ranked anomalies, status.

    Deliberately assembled server-side. A demo that needs six round-trips to
    show anything spends its first two seconds looking broken.
    """
    response.headers["Cache-Control"] = "no-store"
    db = store()
    now = _now()
    seconds = _window_seconds(window)
    since = now - seconds

    stops, _ = load_stops(str(SETTINGS.stops_path))
    routes_meta = load_routes(str(SETTINGS.routes_path))

    stats = db.window_stats(since_epoch=since)
    last_observed = stats.get("last_observed_ts")
    age = (now - last_observed) if last_observed else None

    # --- liveness, stated rather than implied ---------------------------
    collector = _collector
    cycles = collector.cycles if collector else 0
    if not SETTINGS.collector_enabled:
        live_state, note = "paused", "Live collection is switched off; showing stored data."
    elif last_observed is None:
        live_state = "warming_up"
        note = (
            "Collecting. The first headway needs two consecutive sightings of a stop, "
            f"so the map fills in about a minute (cycle {cycles})."
        )
    elif age is not None and age <= SETTINGS.stale_after_sec:
        live_state, note = "live", None
    else:
        live_state = "stale"
        note = (
            f"The MTA feeds have not produced a new observation for {age // 60} min. "
            "Showing the last known data."
        )

    feeds_ok = feeds_total = 0
    if collector and collector.last_cycle:
        feeds_ok = collector.last_cycle.feeds_ok
        feeds_total = len(collector.last_cycle.feeds)

    # --- map layer -------------------------------------------------------
    features: list[dict[str, Any]] = []
    for row in db.peak_per_stop(since_epoch=since, route_id=route_id):
        stop = stops.get(str(row["stop_id"]))
        if not stop:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [stop["lon"], stop["lat"]]},
                "properties": {
                    "stop_id": row["stop_id"],
                    "stop_name": stop["stop_name"],
                    "route_id": row["route_id"],
                    "route_color": routes_meta.get(str(row["route_id"]), {}).get("color", "#4b5563"),
                    "anomaly_score": round(float(row["anomaly_score"]), 4),
                    "headway_sec": round(float(row["headway_sec"]), 1),
                    "predicted_headway_sec": (
                        round(float(row["predicted_headway_sec"]), 1)
                        if row["predicted_headway_sec"] is not None
                        else None
                    ),
                    "residual_sec": (
                        round(float(row["residual"]), 1) if row["residual"] is not None else None
                    ),
                    "reasons": row["reasons"],
                    "observed_utc": _iso(row["observed_ts"]),
                },
            }
        )

    return {
        "generated_utc": _iso(now),
        "window": {"label": window, "seconds": seconds, "route_id": route_id},
        "live": {
            "state": live_state,
            "note": note,
            "cycles": cycles,
            "feeds_ok": feeds_ok,
            "feeds_total": feeds_total or len(FEEDS),
            "last_observed_utc": _iso(last_observed),
            "last_observed_age_sec": age,
            "poll_seconds": SETTINGS.poll_seconds,
        },
        "counters": {
            "stations_reporting": stats["stations"],
            "route_stops_tracked": stats["route_stops"],
            "scored_rows": stats["scored_rows"],
            "anomalies": stats["anomalies"],
            "anomalies_high": stats["anomalies_high"],
            "anomaly_rate_pct": stats["anomaly_rate_pct"],
            "mean_headway_sec": stats["mean_headway_sec"],
        },
        # Model maturity, so the page can caveat early scores without a second
        # call.
        #
        # This is deliberately measured PER ROUTE-STOP, not as a total row
        # count, and the difference is not cosmetic. The dominant term in the
        # score is a floor:
        #
        #     score = max(ensemble, 0.62*station_score + 0.38*quantile_score)
        #
        # and both of those are deviations from *this stop's own* rolling
        # baseline. A stop with one recorded headway has no baseline, so the
        # deviation saturates and the score pins to 1.00. Measured on a cold
        # start on 2026-08-07: 1 530 rows spread over 1 045 route-stops is a
        # median of ONE observation per stop, and 229 rows sat in the top
        # score bin with every one of the top 200 tied at exactly 1.00.
        #
        # A total-row threshold hides exactly that case: 3 000 rows across
        # ~1 050 stops is ~3 observations each, still meaningless, but it
        # would have flipped this field to "warm" and dropped the caveat off
        # the page while the list was still degenerate. Gating on the ratio is
        # what makes the badge honest.
        #
        # Note this reads the collector's live feature windows rather than
        # anything in `stats`: `stats["route_stops"]` is scoped to whatever
        # ?window= the caller passed, so a short window would shrink the
        # denominator and flip the badge to "warm" early. The feature engine's
        # own occupancy is window-independent and restart-aware.
        "model": _model_maturity(
            rows_seen=_collector.bundle.telemetry.rows_seen if _collector else 0,
            drift_events=_collector.bundle.telemetry.drift_events if _collector else 0,
            mae_ema=_collector.bundle.telemetry.mae_ema if _collector else None,
            history=_collector.features.history_stats() if _collector else None,
        ),
        "anomalies": _serialise_anomalies(
            db.recent(since_epoch=since, route_id=route_id, min_score=0.0, limit=top), stops, routes_meta
        ),
        "map": {"type": "FeatureCollection", "features": features},
        "series": db.series_per_minute(since_epoch=since, bucket_sec=max(60, seconds // 60)),
        "score_histogram": db.score_histogram(since_epoch=since),
        "routes": db.routes_seen(since_epoch=since) or sorted(routes_meta),
        # Always present, so the page has measured results even at cycle 0.
        "replay_headline": _replay_headline(),
        "storage": {
            "rows": db.count(),
            "bytes": db.file_bytes(),
            "bytes_human": _human_bytes(db.file_bytes()),
            "retention_hours": SETTINGS.retention_hours,
            "max_bytes_human": _human_bytes(SETTINGS.max_db_bytes),
        },
        "attribution": {
            "data": "Real-time and schedule data from the MTA's public GTFS feeds (no API key required).",
            "basemap": "© OpenStreetMap contributors",
        },
    }


def _serialise_anomalies(
    rows: list[dict[str, Any]], stops: dict[str, Any], routes_meta: dict[str, Any]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        stop = stops.get(str(row["stop_id"]), {})
        headway = float(row["headway_sec"])
        predicted = row["predicted_headway_sec"]
        out.append(
            {
                "route_id": row["route_id"],
                "route_color": routes_meta.get(str(row["route_id"]), {}).get("color", "#4b5563"),
                "stop_id": row["stop_id"],
                "stop_name": stop.get("stop_name") or row["stop_id"],
                "lat": stop.get("lat"),
                "lon": stop.get("lon"),
                "headway_sec": round(headway, 1),
                "predicted_headway_sec": round(float(predicted), 1) if predicted is not None else None,
                "residual_sec": round(float(row["residual"]), 1) if row["residual"] is not None else None,
                "anomaly_score": round(float(row["anomaly_score"]), 4),
                "severity": (
                    "critical" if row["anomaly_score"] >= 0.85
                    else "elevated" if row["anomaly_score"] >= 0.6
                    else "normal"
                ),
                "reasons": row["reasons"],
                "observed_utc": _iso(row["observed_ts"]),
                "observed_epoch": int(row["observed_ts"]),
            }
        )
    return out


@app.get("/api/anomalies", tags=["live"])
def anomalies(
    response: Response,
    window: str = Query(default="30m"),
    route_id: str = Query(default="All"),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
    order: str = Query(default="score", pattern="^(score|time)$"),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    db = store()
    now = _now()
    seconds = _window_seconds(window)
    stops, _ = load_stops(str(SETTINGS.stops_path))
    routes_meta = load_routes(str(SETTINGS.routes_path))
    rows = db.recent(
        since_epoch=now - seconds,
        route_id=route_id,
        min_score=min_score,
        limit=limit,
        order=order,
    )
    return {
        "generated_utc": _iso(now),
        "window": {"label": window, "seconds": seconds},
        "filters": {"route_id": route_id, "min_score": min_score, "order": order},
        "count": len(rows),
        "items": _serialise_anomalies(rows, stops, routes_meta),
    }


# --------------------------------------------------------------------------
# Narrow-payload endpoints.
#
# /api/state is one call for the whole page, which is right for first paint but
# wasteful when a widget only needs the counters or only needs the map. These
# two serve exactly one thing each and keep the upstream repo's field names, so
# a client written against the original API keeps working.
# --------------------------------------------------------------------------
@app.get("/api/summary", tags=["live"])
def summary(response: Response, window: str = Query(default="30m")) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    db = store()
    now = _now()
    seconds = _window_seconds(window)
    stats = db.window_stats(since_epoch=now - seconds)
    last_observed = stats.get("last_observed_ts")
    age = (now - last_observed) if last_observed else None

    collector = _collector
    if not SETTINGS.collector_enabled:
        live_state = "paused"
    elif last_observed is None:
        live_state = "warming_up"
    elif age is not None and age <= SETTINGS.stale_after_sec:
        live_state = "live"
    else:
        live_state = "stale"

    return {
        "window": window,
        "stations_total": stats["stations"],
        "trains_active": stats["route_stops"],
        "anomalies_count": stats["anomalies"],
        "anomalies_high": stats["anomalies_high"],
        "anomaly_rate_perc": stats["anomaly_rate_pct"],
        "scored_rows": stats["scored_rows"],
        "mean_headway_sec": stats["mean_headway_sec"],
        "last_updated_utc": _iso(last_observed),
        "last_updated_epoch_ms": int(last_observed * 1000) if last_observed else None,
        "last_updated_age_sec": age,
        # Not in the original API, and the reason this endpoint is safe to
        # render from: a client can tell "quiet network" from "nothing works".
        "live_state": live_state,
        "feeds_ok": collector.last_cycle.feeds_ok if collector and collector.last_cycle else 0,
        "feeds_total": len(FEEDS),
        "cycles": collector.cycles if collector else 0,
    }


@app.get("/api/heatmap", tags=["live"])
def heatmap(
    response: Response,
    window: str = Query(default="30m"),
    route_id: str = Query(default="All"),
    limit: int = Query(default=1200, ge=1, le=2000),
) -> dict[str, Any]:
    """GeoJSON, highest-scoring observation per stop. Bounded by station count."""
    response.headers["Cache-Control"] = "no-store"
    db = store()
    now = _now()
    seconds = _window_seconds(window)
    stops, _ = load_stops(str(SETTINGS.stops_path))
    routes_meta = load_routes(str(SETTINGS.routes_path))

    features: list[dict[str, Any]] = []
    for row in db.peak_per_stop(since_epoch=now - seconds, route_id=route_id, limit=limit):
        stop = stops.get(str(row["stop_id"]))
        if not stop:
            continue
        observed = int(row["observed_ts"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [stop["lon"], stop["lat"]]},
                "properties": {
                    "stop_id": row["stop_id"],
                    "stop_name": stop["stop_name"],
                    "route_id": row["route_id"],
                    "route_color": routes_meta.get(str(row["route_id"]), {}).get("color", "#4b5563"),
                    "anomaly_score": round(float(row["anomaly_score"]), 4),
                    "residual": round(float(row["residual"]), 1) if row["residual"] is not None else 0.0,
                    "headway_sec": round(float(row["headway_sec"]), 1),
                    "predicted_headway_sec": (
                        round(float(row["predicted_headway_sec"]), 1)
                        if row["predicted_headway_sec"] is not None
                        else None
                    ),
                    "reasons": row["reasons"],
                    "observed_ts_utc": _iso(observed),
                    "observed_ts_epoch_ms": observed * 1000,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "timestamp": _iso(now),
        "window": {"label": window, "seconds": seconds},
        "features": features,
        "attribution": "© OpenStreetMap contributors",
    }


@app.get("/api/stops", tags=["reference"])
def stops_endpoint(response: Response, request: Request) -> Any:
    stops, etag = load_stops(str(SETTINGS.stops_path))
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {"count": len(stops), "stops": list(stops.values())}


@app.get("/api/routes", tags=["reference"])
def routes_endpoint(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    routes_meta = load_routes(str(SETTINGS.routes_path))
    seen = store().routes_seen(since_epoch=_now() - SETTINGS.retention_sec)
    return {"routes": list(routes_meta.values()), "seen_in_window": seen}


# --------------------------------------------------------------------------
# /api/replay — measured results, available before the first live cycle
# --------------------------------------------------------------------------
_REPLAY_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _replay_json(name: str) -> dict[str, Any]:
    """Load a replay artifact, cached on mtime.

    The artifacts are frozen, and every open browser tab polls /api/state every
    few seconds — each of which embeds the replay headline. Re-reading and
    re-parsing summary.json on every poll is pure waste; keying the cache on
    mtime still picks up a regenerated artifact without a restart.
    """
    path = (SETTINGS.replay_dir / name).resolve()
    if not str(path).startswith(str(SETTINGS.replay_dir.resolve()) + os.sep):
        raise HTTPException(status_code=400, detail="invalid artifact path")
    try:
        mtime = path.stat().st_mtime
    except OSError:
        raise HTTPException(status_code=404, detail=f"replay artifact missing: {name}") from None

    cached = _REPLAY_CACHE.get(name)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"replay artifact is invalid JSON: {exc}") from exc
    _REPLAY_CACHE[name] = (mtime, payload)
    return payload


def _replay_headline() -> dict[str, Any]:
    """The one-line result, always carrying its sample size."""
    try:
        summary = _replay_json("summary.json")
    except HTTPException:
        return {"available": False, "caveat": DATASET_CAVEAT}
    metrics = summary.get("metrics", {})
    online = metrics.get("online_model", {})
    zscore = metrics.get("zscore_baseline", {})
    dataset = summary.get("dataset", {})
    return {
        "available": True,
        "headline": (
            f"On a {dataset.get('rows', '?')}-row labelled replay with "
            f"{dataset.get('incidents', '?')} incidents, the online model reaches "
            f"recall@20 {online.get('recall_at_k', {}).get('r@20', 0):.2f} against "
            f"{zscore.get('recall_at_k', {}).get('r@20', 0):.3f} for a z-score baseline, "
            f"at a {online.get('false_alarm_rate', 0):.3f} false-alarm rate."
        ),
        "dataset": dataset,
        "recall_at_20": online.get("recall_at_k", {}).get("r@20"),
        "baseline_recall_at_20": zscore.get("recall_at_k", {}).get("r@20"),
        "false_alarm_rate": online.get("false_alarm_rate"),
        "incidents_detected": online.get("detected_incidents"),
        "incidents_total": online.get("total_incidents"),
        "average_lead_time_min": online.get("average_lead_time_min"),
        "caveat": DATASET_CAVEAT,
    }


@app.get("/api/replay", tags=["replay"])
def replay(response: Response) -> dict[str, Any]:
    """Everything about the frozen evaluation in one call, caveat attached."""
    response.headers["Cache-Control"] = "public, max-age=300"
    summary = _replay_json("summary.json")
    incidents = _replay_json("incidents.json").get("incidents", [])
    return {
        "dataset": summary.get("dataset", {}),
        "caveat": DATASET_CAVEAT,
        "generated_utc": summary.get("generated_utc"),
        "methods": summary.get("metrics", {}),
        "method_labels": {
            "online_model": "Online model (River PA + HalfSpaceTrees + ADWIN)",
            "zscore_baseline": "Rolling z-score",
            "ewma_baseline": "EWMA forecast error",
            "threshold_baseline": "Fixed threshold on station median",
        },
        "incidents": incidents,
        "notes": summary.get("notes", []),
        "feature_highlights": summary.get("feature_highlights", []),
    }


@app.get("/api/replay/timeline", tags=["replay"])
def replay_timeline(
    response: Response,
    incident_id: str | None = Query(default=None),
    limit: int = Query(default=400, ge=10, le=5000),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    points = _replay_json("timeline.json").get("points", [])
    if incident_id:
        points = [point for point in points if point.get("incident_id") == incident_id]
    return {"caveat": DATASET_CAVEAT, "count": len(points[:limit]), "points": points[:limit]}


@app.get("/api/replay/incidents/{incident_id}", tags=["replay"])
def replay_incident(response: Response, incident_id: str) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    for incident in _replay_json("incidents.json").get("incidents", []):
        if incident.get("incident_id") == incident_id:
            # Shallow copy: the loaded artifact is cached and must not be mutated.
            detail = dict(_replay_json(str(incident.get("detail_path"))))
            detail["caveat"] = DATASET_CAVEAT
            return detail
    raise HTTPException(status_code=404, detail=f"unknown incident: {incident_id}")


@app.get("/api/replay/plots/{name}", tags=["replay"])
def replay_plot(name: str) -> FileResponse:
    if not name.endswith(".svg") or "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="invalid plot name")
    path = SETTINGS.replay_dir / "plots" / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"unknown plot: {name}")
    return FileResponse(path, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


# --------------------------------------------------------------------------
# static frontend, mounted last so /api/* always wins
# --------------------------------------------------------------------------
STATIC_DIR = Path(SETTINGS.static_dir)
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:  # pragma: no cover - only when the frontend has not been built yet
    @app.get("/")
    def placeholder() -> dict[str, Any]:
        return {
            "service": "mta-scan",
            "detail": "API is up; no static frontend found at " + str(STATIC_DIR),
            "endpoints": ["/api/health", "/api/state", "/api/anomalies", "/api/replay"],
        }
