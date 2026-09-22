"""Minimal stand-in for the upstream app.core.config.

The upstream module pulls in Postgres/Redis/Celery settings that this demo has no
use for. Only `max_text_size` is read by app/deid/engine.py, so this shim provides
exactly that and nothing else — which is also why the demo needs no database.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    max_text_size: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(max_text_size=int(os.getenv("DEID_MAX_TEXT_SIZE", "6000")))
