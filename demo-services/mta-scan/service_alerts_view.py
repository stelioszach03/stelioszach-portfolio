"""Allowlisted read-only official MTA context; no upstream requests on HTTP paths."""
import json
import os
from pathlib import Path
import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA = "mta-official-service-alerts-v1"
SOURCE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"
Count = Annotated[int, Field(ge=0)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Safe(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)


class Period(Safe):
    start: Count | None = None
    end: Count | None = None


class Alert(Safe):
    id: Annotated[str, Field(min_length=1, max_length=160)]
    kind: Literal["planned_work", "service_alert", "other"]
    routes: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,16}$")]] = Field(max_length=64)
    header: Annotated[str, Field(max_length=400)]
    description: Annotated[str, Field(max_length=1200)]
    description_truncated: bool
    active_period: Period
    revision_sha256: Digest


class Archive(Safe):
    retained_polls: Count
    first_receipt_ts: Count | None
    last_receipt_ts: Count | None
    retained_revisions: Count
    database_bytes: Count
    max_database_bytes: Count


class Summary(Safe):
    schema_version: Literal["mta-official-service-alerts-v1"] = Field(alias="schema")
    status: Literal["ok", "stale", "unavailable"]
    generated_ts: Count
    source_ts: Count | None
    valid_until_ts: Count | None
    source_url: Literal[SOURCE]
    snapshot_sha256: Digest | None = None
    total_feed_alerts: Annotated[int, Field(ge=0, le=2000)] | None
    active_alert_count: Annotated[int, Field(ge=0, le=2000)] | None
    display_truncated: bool
    alerts: list[Alert] = Field(max_length=100)
    archive: Archive
    is_model_prediction: Literal[False]
    is_incident_ground_truth: Literal[False]
    note: Annotated[str, Field(max_length=600)]


def unavailable():
    return {"schema": SCHEMA, "status": "unavailable", "alerts": [],
            "is_model_prediction": False, "is_incident_ground_truth": False,
            "note": "Official service-alert context is unavailable. Live feed observations remain separate."}


def read_service_alerts(path=None, *, now=None):
    now = int(time.time()) if now is None else now
    location = Path(path or os.environ.get("MTASCAN_SERVICE_ALERTS", "/run/mta-alerts-public/summary.json"))
    try:
        with location.open("rb") as stream:
            payload = stream.read(256 * 1024 + 1)
        if len(payload) > 256 * 1024:
            return unavailable()
        value = Summary.model_validate(json.loads(payload))
        if not 0 <= now - value.generated_ts <= 180:
            return unavailable()
        if (value.status != "ok" or value.source_ts is None or not -30 <= now - value.source_ts <= 600
                or value.valid_until_ts is None or not now < value.valid_until_ts <= value.generated_ts + 600):
            value.alerts = []
            if value.status == "ok":
                value.status = "stale"
        else:
            identities = [a.id for a in value.alerts]
            if len(identities) != len(set(identities)):
                return unavailable()
            if value.active_alert_count is None or value.active_alert_count < len(value.alerts):
                return unavailable()
            value.alerts = [a for a in value.alerts
                            if (a.active_period.start is None or a.active_period.start <= now)
                            and (a.active_period.end is None or now < a.active_period.end)
                            and not (a.active_period.start is not None and a.active_period.end is not None
                                     and a.active_period.end <= a.active_period.start)]
        return value.model_dump(by_alias=True)
    except (OSError, ValueError, ValidationError, TypeError, RecursionError):
        return unavailable()
