"""The rolling window on disk — SQLite, and the limits that keep it small.

WHY SQLITE AND NOT TIMESCALEDB
------------------------------
The upstream project runs TimescaleDB in Docker. For a portfolio demo on a
shared 16 GB box that is three problems dressed as one solution: another
daemon to supervise, another ~500 MB of RSS, and a hypertable whose retention
policy is a background job you have to remember to create. The demo never
queries more than the last 48 hours and never needs more than one writer, so
the whole database is a single file with three indexes.

WHY THE LIMITS ARE THE POINT
----------------------------
The original README documents an incident where unbounded writes consumed
37 GB. On this box the blast radius is bigger: the same disk carries the
portfolio site and three other demos, so filling it takes all of them down.
So the window is bounded three independent ways, and the tightest one wins:

  1. **age**   — nothing older than MTA_RETENTION_HOURS (default 48 h);
  2. **rows**  — never more than MTA_MAX_ROWS (default 1.2 M);
  3. **bytes** — never more than MTA_MAX_DB_BYTES (default 400 MB), measured
     as the real size of the .db + -wal + -shm files on disk, not as a row
     estimate.

Rule 3 is the one that actually saves you, and it is the one everybody gets
wrong: a plain DELETE in SQLite frees *pages*, not disk. The file does not
shrink. So the database is created with `auto_vacuum=INCREMENTAL` and every
cleanup ends with `PRAGMA incremental_vacuum` plus a truncating WAL
checkpoint, which does hand the pages back to the filesystem.

Both halves of that have a trap, and both traps are silent — see the comments
on `_prepare` (pragma ordering) and `reclaim` (executescript, not execute).
The first version of this file deleted 480 044 rows and shrank by zero bytes.

`scripts/retention_soak.py` proves it end to end: fill past the cap, run the
cleanup, watch the file get smaller. Do not trust this docstring; run it.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS observations (
    id                    INTEGER PRIMARY KEY,
    observed_ts           INTEGER NOT NULL,
    event_ts              INTEGER,
    route_id              TEXT    NOT NULL,
    stop_id               TEXT    NOT NULL,
    headway_sec           REAL    NOT NULL,
    predicted_headway_sec REAL,
    residual              REAL,
    anomaly_score         REAL    NOT NULL DEFAULT 0,
    reasons               TEXT
);
CREATE INDEX IF NOT EXISTS ix_obs_ts        ON observations(observed_ts);
CREATE INDEX IF NOT EXISTS ix_obs_score_ts  ON observations(anomaly_score DESC, observed_ts DESC);
CREATE INDEX IF NOT EXISTS ix_obs_stop_ts   ON observations(stop_id, observed_ts DESC);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Store:
    """Single-file store. One writer (the collector), many readers (the API).

    THREADING. The collector runs in a worker thread and the API answers on the
    event loop, so writes and reads genuinely overlap. Python's sqlite3 is
    serialized (threadsafety 3), so *sharing* one connection is safe — but
    serialized means exactly that: an API read would queue behind whatever the
    writer is doing. A retention pass that deletes two million aged-out rows
    takes ~21 s, and for those 21 s the page would hang.

    So the writer gets its own connection and every reading thread gets its
    own, which is the configuration WAL is designed for: readers never block on
    a writer and see a consistent snapshot throughout.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._connect()          # the single writer
        self._readers = threading.local()     # one read connection per thread
        self._prepare()

    # -- plumbing ---------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.path),
            timeout=10.0,
            check_same_thread=False,
            isolation_level=None,  # explicit transactions only
        )
        conn.row_factory = sqlite3.Row
        return conn

    @property
    def _read(self) -> sqlite3.Connection:
        """A per-thread read connection. Never used for writes."""
        conn = getattr(self._readers, "conn", None)
        if conn is None:
            conn = self._connect()
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute("PRAGMA query_only = ON")
            self._readers.conn = conn
        return conn

    def _prepare(self) -> None:
        conn = self._conn
        conn.execute("PRAGMA busy_timeout = 10000")

        # ORDER MATTERS, AND IT FAILS SILENTLY IF YOU GET IT WRONG.
        # `auto_vacuum` can only be changed while the database has no tables —
        # and enabling WAL first already writes a header, after which SQLite
        # accepts `PRAGMA auto_vacuum = INCREMENTAL` without complaint and
        # leaves the mode at NONE. The result is a store that deletes rows for
        # months and never returns a single byte to the filesystem: exactly the
        # failure this whole module exists to prevent. So set it first, then
        # read it back, and fall back to a full VACUUM (which rebuilds the file
        # in the new mode) if it did not stick.
        if self._auto_vacuum_mode() != 2:  # 2 == INCREMENTAL
            conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
            if self._auto_vacuum_mode() != 2:
                conn.execute("VACUUM")

        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        # Cap how large the WAL is allowed to grow between checkpoints.
        conn.execute("PRAGMA journal_size_limit = 16777216")

        conn.executescript(_DDL)
        self.set_meta("schema_version", SCHEMA_VERSION)
        self.set_meta("auto_vacuum_mode", self._auto_vacuum_mode())

    def _auto_vacuum_mode(self) -> int:
        return int(self._conn.execute("PRAGMA auto_vacuum").fetchone()[0])

    def freelist_pages(self) -> int:
        return int(self._conn.execute("PRAGMA freelist_count").fetchone()[0])

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            self._conn.close()

    # -- meta -------------------------------------------------------------
    def set_meta(self, key: str, value: Any) -> None:
        payload = json.dumps(value)
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, payload),
            )

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self._read.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return default

    # -- writes -----------------------------------------------------------
    def insert_observations(self, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        payload = [
            (
                int(r["observed_ts"]),
                int(r["event_ts"]) if r.get("event_ts") is not None else None,
                str(r["route_id"]),
                str(r["stop_id"]),
                float(r["headway_sec"]),
                None if r.get("predicted_headway_sec") is None else float(r["predicted_headway_sec"]),
                None if r.get("residual") is None else float(r["residual"]),
                float(r.get("anomaly_score") or 0.0),
                json.dumps(r.get("reasons") or []),
            )
            for r in rows
        ]
        with self._write() as conn:
            conn.executemany(
                "INSERT INTO observations("
                " observed_ts, event_ts, route_id, stop_id, headway_sec,"
                " predicted_headway_sec, residual, anomaly_score, reasons)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                payload,
            )
        return len(payload)

    # -- size accounting --------------------------------------------------
    def file_bytes(self) -> int:
        """Real bytes on disk: main file plus its WAL and shared-memory files."""
        total = 0
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(self.path) + suffix)
            try:
                total += candidate.stat().st_size
            except OSError:
                pass
        return total

    def count(self) -> int:
        row = self._read.execute("SELECT count(*) AS n FROM observations").fetchone()
        return int(row["n"]) if row else 0

    def time_span(self) -> tuple[int | None, int | None]:
        row = self._read.execute(
            "SELECT min(observed_ts) AS lo, max(observed_ts) AS hi FROM observations"
        ).fetchone()
        if not row or row["hi"] is None:
            return None, None
        return int(row["lo"]), int(row["hi"])

    # -- THE RETENTION MECHANISM -----------------------------------------
    def reclaim(self) -> int:
        """Hand freed pages back to the filesystem. Without this, DELETE is a lie.

        `PRAGMA incremental_vacuum` MUST go through `executescript`, not
        `execute`. Python's sqlite3 steps a pragma statement exactly once, and
        this particular pragma frees one page per step — so `execute` on a
        200 000-page freelist returns cleanly having recovered 4 KB. Measured:
        `execute` took a 396.8 MB file to 396.8 MB; `executescript` took the
        same file to 198.7 MB in 0.23 s.

        Returns the number of bytes actually handed back.
        """
        before = self.file_bytes()
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.executescript("PRAGMA incremental_vacuum;")
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
        return max(0, before - self.file_bytes())

    def vacuum_full(self) -> int:
        """Backstop: rebuild the file. Used only if incremental reclaim stalls.

        Costs an exclusive lock (measured ~0.5 s at the 400 MB cap) and needs
        transient free space, so it is never the first move — but it is the one
        thing that always works, including when auto_vacuum is somehow off.
        """
        before = self.file_bytes()
        with self._lock:
            try:
                self._conn.execute("VACUUM")
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
        return max(0, before - self.file_bytes())

    def _delete_oldest(self, limit: int) -> int:
        if limit <= 0:
            return 0
        with self._write() as conn:
            cursor = conn.execute(
                "DELETE FROM observations WHERE id IN ("
                "  SELECT id FROM observations ORDER BY observed_ts ASC, id ASC LIMIT ?"
                ")",
                (int(limit),),
            )
            return int(cursor.rowcount or 0)

    def enforce_limits(
        self,
        *,
        retention_sec: int,
        max_rows: int,
        max_bytes: int,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Apply all three caps. Returns exactly what it did, for the health endpoint."""
        started = time.monotonic()
        now_epoch = int(now if now is not None else time.time())
        bytes_before = self.file_bytes()
        rows_before = self.count()

        # Age cap, in chunks. In steady state a pass removes a few hundred rows
        # and this loop runs once. The chunking is for the abnormal case — a
        # service stopped for a fortnight that comes back with 2.1 M rows to
        # shed. As a single statement that is one ~21 s write transaction; in
        # 50 000-row bites the whole pass takes longer in total (~36 s
        # measured) but no individual lock is held for more than a moment,
        # which is what actually matters to anyone looking at the page.
        cutoff = now_epoch - int(retention_sec)
        deleted_by_age = 0
        while True:
            with self._write() as conn:
                cursor = conn.execute(
                    "DELETE FROM observations WHERE id IN ("
                    "  SELECT id FROM observations WHERE observed_ts < ? LIMIT 50000"
                    ")",
                    (cutoff,),
                )
                removed = int(cursor.rowcount or 0)
            deleted_by_age += removed
            if removed < 50000:
                break

        deleted_by_rows = 0
        rows_now = self.count()
        if max_rows > 0 and rows_now > max_rows:
            deleted_by_rows = self._delete_oldest(rows_now - max_rows)

        self.reclaim()

        # Size cap last: it is the backstop for anything the other two missed
        # (unexpectedly wide rows, index bloat, a stuck WAL).
        deleted_by_bytes = 0
        passes = 0
        full_vacuums = 0
        while max_bytes > 0 and self.file_bytes() > max_bytes and passes < 20:
            remaining = self.count()
            if remaining <= 1000:
                break
            # Drop the oldest tenth and try again. Converges fast and never
            # empties the table in one go, so the demo keeps something to show.
            deleted_by_bytes += self._delete_oldest(max(1000, remaining // 10))
            if self.reclaim() == 0:
                # Deleting rows freed no disk: incremental reclaim is not
                # working on this file. Rebuild it rather than spin.
                self.vacuum_full()
                full_vacuums += 1
            passes += 1

        bytes_after = self.file_bytes()
        result = {
            "ran_at_utc": now_epoch,
            "rows_before": rows_before,
            "rows_after": self.count(),
            "deleted_by_age": deleted_by_age,
            "deleted_by_row_cap": deleted_by_rows,
            "deleted_by_size_cap": deleted_by_bytes,
            "size_cap_passes": passes,
            "full_vacuums": full_vacuums,
            "auto_vacuum_mode": self._auto_vacuum_mode(),
            "freelist_pages": self.freelist_pages(),
            "bytes_before": bytes_before,
            "bytes_after": bytes_after,
            "bytes_reclaimed": max(0, bytes_before - bytes_after),
            "limits": {
                "retention_hours": round(retention_sec / 3600.0, 2),
                "max_rows": max_rows,
                "max_bytes": max_bytes,
            },
            "duration_ms": round((time.monotonic() - started) * 1000.0, 1),
            "within_limits": bytes_after <= max_bytes and self.count() <= max_rows,
        }
        self.set_meta("last_cleanup", result)
        return result

    # -- reads ------------------------------------------------------------
    def recent(
        self,
        *,
        since_epoch: int,
        route_id: str | None = None,
        min_score: float = 0.0,
        limit: int = 300,
        order: str = "score",
    ) -> list[dict[str, Any]]:
        sql = [
            "SELECT observed_ts, event_ts, route_id, stop_id, headway_sec,",
            "       predicted_headway_sec, residual, anomaly_score, reasons",
            "  FROM observations",
            " WHERE observed_ts >= ?",
        ]
        params: list[Any] = [int(since_epoch)]
        if route_id and route_id.lower() != "all":
            sql.append(" AND route_id = ?")
            params.append(route_id)
        if min_score > 0:
            sql.append(" AND anomaly_score >= ?")
            params.append(float(min_score))
        if order == "time":
            sql.append(" ORDER BY observed_ts DESC, anomaly_score DESC")
        else:
            sql.append(" ORDER BY anomaly_score DESC, observed_ts DESC")
        sql.append(" LIMIT ?")
        params.append(int(limit))

        rows = self._read.execute("".join(sql), params).fetchall()
        return [_row_to_dict(row) for row in rows]

    def peak_per_stop(self, *, since_epoch: int, route_id: str | None = None, limit: int = 1200) -> list[dict[str, Any]]:
        """Highest-scoring observation per stop in the window — the map layer."""
        sql = [
            "SELECT stop_id, route_id, observed_ts, event_ts, headway_sec,",
            "       predicted_headway_sec, residual, anomaly_score, reasons FROM (",
            "  SELECT *, row_number() OVER (",
            "      PARTITION BY stop_id ORDER BY anomaly_score DESC, observed_ts DESC",
            "  ) AS rn",
            "    FROM observations",
            "   WHERE observed_ts >= ?",
        ]
        params: list[Any] = [int(since_epoch)]
        if route_id and route_id.lower() != "all":
            sql.append("     AND route_id = ?")
            params.append(route_id)
        sql.append(") WHERE rn = 1 ORDER BY anomaly_score DESC LIMIT ?")
        params.append(int(limit))
        rows = self._read.execute("".join(sql), params).fetchall()
        return [_row_to_dict(row) for row in rows]

    def window_stats(self, *, since_epoch: int) -> dict[str, Any]:
        row = self._read.execute(
            "SELECT count(*) AS scored_rows,"
            "       count(DISTINCT stop_id) AS stations,"
            "       count(DISTINCT route_id || ':' || stop_id) AS route_stops,"
            "       sum(CASE WHEN anomaly_score >= 0.6  THEN 1 ELSE 0 END) AS anomalies,"
            "       sum(CASE WHEN anomaly_score >= 0.85 THEN 1 ELSE 0 END) AS anomalies_high,"
            "       avg(headway_sec) AS mean_headway_sec,"
            "       max(observed_ts) AS last_observed_ts"
            "  FROM observations WHERE observed_ts >= ?",
            (int(since_epoch),),
        ).fetchone()
        scored = int(row["scored_rows"] or 0)
        anomalies = int(row["anomalies"] or 0)
        return {
            "scored_rows": scored,
            "stations": int(row["stations"] or 0),
            "route_stops": int(row["route_stops"] or 0),
            "anomalies": anomalies,
            "anomalies_high": int(row["anomalies_high"] or 0),
            "anomaly_rate_pct": round(100.0 * anomalies / scored, 2) if scored else 0.0,
            "mean_headway_sec": round(float(row["mean_headway_sec"]), 1) if row["mean_headway_sec"] else None,
            "last_observed_ts": int(row["last_observed_ts"]) if row["last_observed_ts"] else None,
        }

    def routes_seen(self, *, since_epoch: int) -> list[str]:
        rows = self._read.execute(
            "SELECT DISTINCT route_id FROM observations WHERE observed_ts >= ? ORDER BY route_id",
            (int(since_epoch),),
        ).fetchall()
        return [str(row["route_id"]) for row in rows if row["route_id"]]

    def score_histogram(self, *, since_epoch: int, buckets: int = 10) -> list[int]:
        counts = [0] * buckets
        rows = self._read.execute(
            "SELECT anomaly_score FROM observations WHERE observed_ts >= ?", (int(since_epoch),)
        ).fetchall()
        for row in rows:
            score = float(row["anomaly_score"] or 0.0)
            index = min(buckets - 1, max(0, int(score * buckets)))
            counts[index] += 1
        return counts

    def series_per_minute(self, *, since_epoch: int, bucket_sec: int = 300) -> list[dict[str, Any]]:
        rows = self._read.execute(
            "SELECT (observed_ts / ?) * ? AS bucket,"
            "       count(*) AS rows_n,"
            "       max(anomaly_score) AS peak_score,"
            "       avg(anomaly_score) AS mean_score,"
            "       sum(CASE WHEN anomaly_score >= 0.6 THEN 1 ELSE 0 END) AS anomalies"
            "  FROM observations WHERE observed_ts >= ?"
            " GROUP BY bucket ORDER BY bucket ASC",
            (int(bucket_sec), int(bucket_sec), int(since_epoch)),
        ).fetchall()
        return [
            {
                "bucket_ts": int(row["bucket"]),
                "rows": int(row["rows_n"]),
                "peak_score": round(float(row["peak_score"] or 0.0), 4),
                "mean_score": round(float(row["mean_score"] or 0.0), 4),
                "anomalies": int(row["anomalies"] or 0),
            }
            for row in rows
        ]

    # -- test / soak support ---------------------------------------------
    def bulk_insert_synthetic(self, rows: Iterable[tuple]) -> int:
        """Fast path used by scripts/retention_soak.py to fill the file."""
        with self._write() as conn:
            cursor = conn.executemany(
                "INSERT INTO observations("
                " observed_ts, event_ts, route_id, stop_id, headway_sec,"
                " predicted_headway_sec, residual, anomaly_score, reasons)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                rows,
            )
            return int(cursor.rowcount or 0)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    raw = out.pop("reasons", None)
    if raw:
        try:
            out["reasons"] = json.loads(raw)
        except (TypeError, ValueError):
            out["reasons"] = []
    else:
        out["reasons"] = []
    return out
