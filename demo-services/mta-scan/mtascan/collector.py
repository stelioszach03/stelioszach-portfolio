"""Live ingestion from the MTA's public GTFS-Realtime feeds.

NO API KEY. The MTA dropped key requirements for the subway realtime feeds
(https://api.mta.info/ — "Accounts and API keys are no longer required"). The
only header sent is a descriptive User-Agent. Verified against all eight
line-family endpoints; see tests/test_live_feeds.py.

WHAT CHANGED VERSUS THE UPSTREAM COLLECTOR
------------------------------------------
The original wrote one row per (route, stop) per 30-second cycle whether or
not anything had happened — roughly 5 000 rows a minute, 7 million a day, for
data that mostly repeated the previous cycle. That is the mechanism behind the
37 GB incident in the project's README.

Here a row is written only when the earliest upcoming arrival at a route-stop
*advances past the one we were already tracking* — that is, when a train
actually cleared the stop. The gap between the old and the new arrival is the
headway, which is the quantity being modelled in the first place. Write volume
drops by roughly two orders of magnitude and every row now means something.

FAILURE IS NORMAL, NOT EXCEPTIONAL
----------------------------------
Feeds go down, return 5xx, or ship a protobuf we cannot parse. None of that is
allowed to take the demo with it: each feed is fetched independently, failures
are recorded per feed and surfaced through /api/health, and the service keeps
serving the last known window with an explicit "last updated" stamp.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from google.transit import gtfs_realtime_pb2  # type: ignore

from .config import Settings
from .features import FeatureEngine
from .scoring import ModelBundle, save_bundle, score_feature_row
from .store import Store


log = logging.getLogger("mtascan.collector")

FEED_BASE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds"

FEEDS: list[tuple[str, str]] = [
    ("1234567", f"{FEED_BASE}/nyct%2Fgtfs"),
    ("ACE", f"{FEED_BASE}/nyct%2Fgtfs-ace"),
    ("BDFM", f"{FEED_BASE}/nyct%2Fgtfs-bdfm"),
    ("G", f"{FEED_BASE}/nyct%2Fgtfs-g"),
    ("JZ", f"{FEED_BASE}/nyct%2Fgtfs-jz"),
    ("NQRW", f"{FEED_BASE}/nyct%2Fgtfs-nqrw"),
    ("L", f"{FEED_BASE}/nyct%2Fgtfs-l"),
    ("SI", f"{FEED_BASE}/nyct%2Fgtfs-si"),
]


@dataclass
class FeedStatus:
    label: str
    ok: bool = False
    http_status: int | None = None
    entities: int = 0
    error: str | None = None
    latency_ms: float | None = None
    last_success_epoch: int | None = None


@dataclass
class CycleResult:
    started_epoch: int
    duration_ms: float
    feeds: list[FeedStatus] = field(default_factory=list)
    arrivals_seen: int = 0
    observations: int = 0
    tracked_route_stops: int = 0
    error: str | None = None

    @property
    def feeds_ok(self) -> int:
        return sum(1 for feed in self.feeds if feed.ok)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_utc": _iso(self.started_epoch),
            "started_epoch": self.started_epoch,
            "duration_ms": round(self.duration_ms, 1),
            "feeds_ok": self.feeds_ok,
            "feeds_total": len(self.feeds),
            "arrivals_seen": self.arrivals_seen,
            "observations_written": self.observations,
            "tracked_route_stops": self.tracked_route_stops,
            "error": self.error,
            "feeds": [
                {
                    "label": feed.label,
                    "ok": feed.ok,
                    "http_status": feed.http_status,
                    "entities": feed.entities,
                    "latency_ms": round(feed.latency_ms, 1) if feed.latency_ms else None,
                    "error": feed.error,
                    "last_success_utc": _iso(feed.last_success_epoch),
                }
                for feed in self.feeds
            ],
        }


def _iso(epoch: int | None) -> str | None:
    if not epoch:
        return None
    return (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def parse_arrivals(content: bytes) -> Iterable[tuple[str, str, int]]:
    """Yield (route_id, stop_id, arrival_epoch) from a GTFS-RT payload."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)
    for entity in feed.entity:
        if entity.HasField("trip_update"):
            route_id = entity.trip_update.trip.route_id or ""
            for update in entity.trip_update.stop_time_update:
                stop_id = update.stop_id or ""
                arrival = update.arrival.time if update.HasField("arrival") else 0
                departure = update.departure.time if update.HasField("departure") else 0
                stamp = int(arrival or departure or 0)
                if route_id and stop_id and stamp:
                    yield route_id, stop_id, stamp
        elif entity.HasField("vehicle"):
            vehicle = entity.vehicle
            route_id = vehicle.trip.route_id or ""
            stop_id = vehicle.stop_id or ""
            stamp = int(vehicle.timestamp or 0)
            if route_id and stop_id and stamp:
                yield route_id, stop_id, stamp


class Collector:
    """Fetch → headway extraction → online scoring → bounded store.

    Runs as a single background task inside the API process. One process means
    one memory limit, one restart policy, and no way for the writer and the
    reader to disagree about which database file they are using.
    """

    def __init__(self, *, settings: Settings, store: Store, bundle: ModelBundle) -> None:
        self.settings = settings
        self.store = store
        self.bundle = bundle
        self.features = FeatureEngine()
        # Last arrival time we have already accounted for, per (route, stop).
        self._tracked: dict[tuple[str, str], int] = {}
        self._feed_last_success: dict[str, int] = {}
        self.cycles = 0
        self.last_cycle: CycleResult | None = None
        self.started_epoch = int(time.time())

    # -- one cycle --------------------------------------------------------
    def run_cycle(self, client: httpx.Client | None = None) -> CycleResult:
        started = time.monotonic()
        started_epoch = int(time.time())
        result = CycleResult(started_epoch=started_epoch, duration_ms=0.0)

        owns_client = client is None
        if owns_client:
            client = httpx.Client(
                headers={"User-Agent": self.settings.user_agent},
                timeout=httpx.Timeout(self.settings.feed_timeout, connect=5.0),
                follow_redirects=True,
            )
        assert client is not None

        try:
            arrivals: list[tuple[str, str, int]] = []
            for label, url in FEEDS:
                status = self._fetch_feed(client, label, url, arrivals)
                result.feeds.append(status)
            result.arrivals_seen = len(arrivals)

            observations = self._extract_and_score(arrivals, started_epoch)
            result.observations = self.store.insert_observations(observations)
            result.tracked_route_stops = len(self._tracked)
        except Exception as exc:  # never let a cycle kill the service
            result.error = f"{type(exc).__name__}: {exc}"
            log.exception("collector cycle failed")
        finally:
            if owns_client:
                client.close()

        result.duration_ms = (time.monotonic() - started) * 1000.0
        self.cycles += 1
        self.last_cycle = result
        self._housekeeping(started_epoch)
        return result

    def _fetch_feed(
        self,
        client: httpx.Client,
        label: str,
        url: str,
        sink: list[tuple[str, str, int]],
    ) -> FeedStatus:
        status = FeedStatus(label=label, last_success_epoch=self._feed_last_success.get(label))
        began = time.monotonic()
        try:
            response = client.get(url)
            status.http_status = response.status_code
            status.latency_ms = (time.monotonic() - began) * 1000.0
            if response.status_code != 200:
                status.error = f"HTTP {response.status_code}"
                return status
            entities = list(parse_arrivals(response.content))
            status.entities = len(entities)
            sink.extend(entities)
            status.ok = True
            status.last_success_epoch = int(time.time())
            self._feed_last_success[label] = status.last_success_epoch
        except Exception as exc:
            status.latency_ms = (time.monotonic() - began) * 1000.0
            status.error = f"{type(exc).__name__}: {exc}"
        return status

    # -- headway extraction ----------------------------------------------
    def _extract_and_score(
        self, arrivals: list[tuple[str, str, int]], now_epoch: int
    ) -> list[dict[str, Any]]:
        """Turn a cycle's arrival predictions into scored headway observations."""
        settings = self.settings

        # Earliest still-plausible arrival per (route, stop) in this cycle.
        earliest: dict[tuple[str, str], int] = {}
        for route_id, stop_id, stamp in arrivals:
            if stamp < now_epoch - 3600 or stamp > now_epoch + 4 * 3600:
                continue
            key = (route_id, stop_id)
            current = earliest.get(key)
            if current is None or stamp < current:
                earliest[key] = stamp

        rows: list[dict[str, Any]] = []
        for key, arrival in earliest.items():
            previous = self._tracked.get(key)
            self._tracked[key] = arrival
            if previous is None:
                # First sighting: nothing to measure a gap against yet.
                continue
            headway = float(arrival - previous)
            # The front of the queue moved backwards (prediction revised) or
            # barely moved (same train, updated ETA) — not a train event.
            if headway < settings.min_headway_sec or headway > settings.max_headway_sec:
                continue

            route_id, stop_id = key
            features = self.features.compute(
                route_id=route_id,
                stop_id=stop_id,
                observed_ts=now_epoch,
                headway_sec=headway,
                event_ts=arrival,
            )
            try:
                scored = score_feature_row(self.bundle, features, learn=True)
            except ValueError:
                continue

            # The prediction is `0.65 x PARegressor + 0.35 x rolling mean`, and
            # an untrained PARegressor can return a large negative number — the
            # upstream repo's own committed replay artifacts contain a
            # predicted headway of -52.09 s. That arithmetic is deliberately
            # left alone, because the anomaly score is derived from it and
            # changing it would stop the published replay numbers reproducing.
            #
            # But a negative headway is not a physical quantity, and "predicted
            # -3821 s" on a live page reads as a broken demo rather than as a
            # cold-start artefact. So the *stored and displayed* prediction is
            # floored at zero, with the residual made consistent with it. The
            # score is untouched.
            predicted = max(0.0, float(scored["predicted_headway_sec"]))
            rows.append(
                {
                    "observed_ts": now_epoch,
                    "event_ts": arrival,
                    "route_id": route_id,
                    "stop_id": stop_id,
                    "headway_sec": headway,
                    "predicted_headway_sec": predicted,
                    "residual": headway - predicted,
                    "anomaly_score": scored["anomaly_score"],
                    "reasons": [str(reason["label"]) for reason in scored["reasons"]],
                }
            )

        self.bundle.telemetry.rows_scored += len(rows)
        self.bundle.telemetry.last_batch_scored = len(rows)
        return rows

    # -- keeping every unbounded thing bounded ----------------------------
    def _housekeeping(self, now_epoch: int) -> None:
        settings = self.settings
        if settings.cleanup_every_cycles <= 0:
            return
        if self.cycles % settings.cleanup_every_cycles != 0:
            return

        cutoff = now_epoch - settings.retention_sec
        # 1. the on-disk window
        try:
            self.store.enforce_limits(
                retention_sec=settings.retention_sec,
                max_rows=settings.max_rows,
                max_bytes=settings.max_db_bytes,
                now=now_epoch,
            )
        except Exception:
            log.exception("retention pass failed")

        # 2. in-memory per-stop state for route-stops that stopped reporting
        evicted = 0
        for key, arrival in list(self._tracked.items()):
            if arrival < cutoff:
                del self._tracked[key]
                evicted += 1
        evicted += self.features.evict_older_than(cutoff)
        if evicted:
            log.info("evicted %d stale route-stop states", evicted)

        # 3. the model checkpoint (single file, atomic rewrite)
        try:
            save_bundle(settings.model_path, self.bundle)
        except Exception:
            log.exception("model checkpoint failed")

    # -- long-running loop (used by the CLI entrypoint) -------------------
    def run_forever(self) -> None:
        with httpx.Client(
            headers={"User-Agent": self.settings.user_agent},
            timeout=httpx.Timeout(self.settings.feed_timeout, connect=5.0),
            follow_redirects=True,
        ) as client:
            while True:
                result = self.run_cycle(client)
                log.info(
                    "cycle %d: feeds %d/%d, %d arrivals, %d observations in %.0f ms",
                    self.cycles,
                    result.feeds_ok,
                    len(result.feeds),
                    result.arrivals_seen,
                    result.observations,
                    result.duration_ms,
                )
                time.sleep(max(5.0, self.settings.poll_seconds + random.uniform(-2.0, 2.0)))
