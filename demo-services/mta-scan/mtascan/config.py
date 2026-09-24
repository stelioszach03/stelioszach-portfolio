"""Runtime configuration, entirely from environment variables.

No pydantic-settings, no .env files, no secrets. Every value has a default that
works on a laptop; systemd overrides the paths and limits in production.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
APP_ROOT = PACKAGE_ROOT.parent


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _state_dir() -> Path:
    """Where the rolling SQLite window and the model checkpoint live.

    systemd's ``StateDirectory=`` exports ``STATE_DIRECTORY``; under
    ``DynamicUser=yes`` that resolves to /var/lib/private/mta-scan and is the
    only writable path the unit has. Locally it falls back to ./var.
    """
    explicit = os.environ.get("MTA_STATE_DIR", "").strip()
    if explicit:
        return Path(explicit)
    systemd = os.environ.get("STATE_DIRECTORY", "").strip()
    if systemd:
        # systemd may hand over a colon-separated list.
        return Path(systemd.split(":")[0])
    return APP_ROOT / "var"


@dataclass(frozen=True)
class Settings:
    version: str = "2.1.1"

    # --- paths -----------------------------------------------------------
    state_dir: Path = _state_dir()
    data_dir: Path = Path(os.environ.get("MTA_DATA_DIR", str(APP_ROOT / "data")))
    static_dir: Path = Path(os.environ.get("MTA_STATIC_DIR", str(APP_ROOT / "static")))

    # --- collector -------------------------------------------------------
    collector_enabled: bool = _env_bool("MTA_COLLECTOR_ENABLED", True)
    poll_seconds: float = _env_float("MTA_POLL_SECONDS", 30.0)
    feed_timeout: float = _env_float("MTA_FEED_TIMEOUT", 12.0)
    user_agent: str = os.environ.get(
        "MTA_USER_AGENT",
        "mta-scan/2.0 (portfolio demo; +https://stelioszach.com/demos/mta-scan/)",
    )
    # A headway outside this band is a feed artefact, not a train.
    min_headway_sec: float = _env_float("MTA_MIN_HEADWAY_SEC", 60.0)
    max_headway_sec: float = _env_float("MTA_MAX_HEADWAY_SEC", 3600.0)

    # --- the limits that keep the disk from filling ----------------------
    retention_hours: float = _env_float("MTA_RETENTION_HOURS", 48.0)
    max_rows: int = _env_int("MTA_MAX_ROWS", 1_200_000)
    max_db_bytes: int = _env_int("MTA_MAX_DB_BYTES", 400 * 1024 * 1024)
    cleanup_every_cycles: int = _env_int("MTA_CLEANUP_EVERY_CYCLES", 10)

    # --- API -------------------------------------------------------------
    default_window_sec: int = _env_int("MTA_DEFAULT_WINDOW_SEC", 1800)
    # Rows older than this make the live view "stale" rather than "live".
    stale_after_sec: int = _env_int("MTA_STALE_AFTER_SEC", 300)

    @property
    def db_path(self) -> Path:
        explicit = os.environ.get("MTA_DB_PATH", "").strip()
        if explicit:
            return Path(explicit)
        # Keep the earlier ETA-transition data separate from trip-pair gaps.
        return self.state_dir / "mta-arrival-gaps-v2.db"

    @property
    def model_path(self) -> Path:
        return self.state_dir / "model-arrival-gaps-v2.pkl"

    @property
    def stops_path(self) -> Path:
        return self.data_dir / "stops.csv"

    @property
    def routes_path(self) -> Path:
        return self.data_dir / "routes.csv"

    @property
    def replay_dir(self) -> Path:
        return self.data_dir / "replay"

    @property
    def retention_sec(self) -> int:
        return int(self.retention_hours * 3600)


_settings: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    global _settings
    if _settings is None or refresh:
        _settings = Settings(
            state_dir=_state_dir(),
            data_dir=Path(os.environ.get("MTA_DATA_DIR", str(APP_ROOT / "data"))),
            static_dir=Path(os.environ.get("MTA_STATIC_DIR", str(APP_ROOT / "static"))),
            collector_enabled=_env_bool("MTA_COLLECTOR_ENABLED", True),
            poll_seconds=_env_float("MTA_POLL_SECONDS", 30.0),
            feed_timeout=_env_float("MTA_FEED_TIMEOUT", 12.0),
            min_headway_sec=_env_float("MTA_MIN_HEADWAY_SEC", 60.0),
            max_headway_sec=_env_float("MTA_MAX_HEADWAY_SEC", 3600.0),
            retention_hours=_env_float("MTA_RETENTION_HOURS", 48.0),
            max_rows=_env_int("MTA_MAX_ROWS", 1_200_000),
            max_db_bytes=_env_int("MTA_MAX_DB_BYTES", 400 * 1024 * 1024),
            cleanup_every_cycles=_env_int("MTA_CLEANUP_EVERY_CYCLES", 10),
            default_window_sec=_env_int("MTA_DEFAULT_WINDOW_SEC", 1800),
            stale_after_sec=_env_int("MTA_STALE_AFTER_SEC", 300),
        )
    return _settings
