"""Read only the worker's bounded, allowlisted public summary; never train here."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SCHEMA = 'mta-temporal-evaluation-v1'
TARGET = 'future feed-predicted arrival-spacing proxy'
Number = Annotated[float, Field(ge=0)]
Fraction = Annotated[float, Field(ge=0, le=1)]
Count = Annotated[int, Field(ge=0)]
Text = Annotated[str, Field(max_length=600)]


class SafeModel(BaseModel):
    # Unknown keys (including private provenance/paths) never reach the API.
    model_config = ConfigDict(extra='ignore', strict=True, allow_inf_nan=False)


class Readiness(SafeModel):
    status: Literal['collecting', 'short_window_feasibility', 'ready', 'temporarily_unavailable', 'error']
    public_forecasts_ready: bool
    reasons: list[Text] = Field(default_factory=list, max_length=20)


class Coverage(SafeModel):
    first_window_ts: Count
    last_window_ts: Count
    span_seconds: Count
    retained_windows: Count
    expected_window_slots: Count
    complete_fresh_window_fraction: Fraction
    stable_groups_evaluated: Count


class Feed(SafeModel):
    feed: Annotated[str, Field(max_length=16)]
    latest_poll_status: Annotated[str, Field(max_length=32)] | None = None
    last_receipt_ts: Count | None = None
    receipt_age_seconds: float | None = None
    source_age_seconds: float | None = None


class Measurement(SafeModel):
    n: Count
    eligible_pairs: Count
    coverage_fraction: Fraction | None
    mae_seconds: Number | None
    rmse_seconds: Number | None
    bias_seconds: float | None

    @model_validator(mode='after')
    def measured(self):
        if self.n > self.eligible_pairs or (self.n == 0 and any(x is not None for x in (self.mae_seconds, self.rmse_seconds, self.bias_seconds))):
            raise ValueError('Invalid measurement count')
        return self


class Algorithms(SafeModel):
    persistence: Measurement
    seasonal_24h: Measurement
    online_linear: Measurement


class Metric(SafeModel):
    horizon_seconds: Literal[900, 1800]
    partition: Literal['validation', 'test']
    models: Algorithms
    selected_from_validation: Measurement


class Forecast(SafeModel):
    route_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,16}$')]
    direction: Annotated[str, Field(pattern=r'^(platform:[NS]|gtfs:[01]|unknown)$')]
    horizon_seconds: Literal[900, 1800]
    origin_ts: Count
    target_ts: Count
    predicted_proxy_seconds: Annotated[float, Field(ge=0, le=3600)]  # Reject invalid proxy range; never silently clip.
    algorithm: Literal['persistence', 'seasonal_24h', 'online_linear']
    cohort_sha256: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
    paired_platform_count: Annotated[int, Field(ge=1, le=3)]
    cohort_coverage_fraction: Literal[1.0]
    validation_mae_seconds: Number
    heldout_test_mae_seconds: Number


class Pipeline(SafeModel):
    pending_export_days: Count | None = None
    ingested_export_days: Count | None = None
    feature_bytes: Count | None = None


class Summary(SafeModel):
    schema_version: Literal['mta-temporal-evaluation-v1'] = Field(alias='schema')
    generated_ts: Count
    generated_at_utc: Annotated[str, Field(max_length=40)] | None = None
    valid_until_ts: Count | None = None
    feature_cutoff_ts: Count | None = None
    evaluation_cutoff_ts: Count | None = None
    target_name: Literal['future feed-predicted arrival-spacing proxy']
    target_definition: Text | None = None
    is_observed_train_headway: Literal[False] = False
    incident_evaluation_available: Literal[False] = False
    readiness: Readiness
    coverage: Coverage | None = None
    feeds: list[Feed] = Field(default_factory=list, max_length=8)
    metrics: list[Metric] = Field(default_factory=list, max_length=4)
    forecasts: list[Forecast] = Field(default_factory=list, max_length=128)
    pipeline: Pipeline | None = None
    artifact_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_.-]{1,160}$')] | None = None
    limitations: list[Text] = Field(default_factory=list, max_length=20)


def unavailable(reason):
    return {'schema': SCHEMA, 'target_name': TARGET, 'is_observed_train_headway': False,
            'incident_evaluation_available': False, 'readiness': {'status': 'temporarily_unavailable',
            'public_forecasts_ready': False, 'reasons': [reason]}, 'metrics': [], 'forecasts': [],
            'feeds': [], 'coverage': None, 'limitations': ['No forecast is available from this snapshot.']}


def read_summary(path=None, *, now=None):
    now = int(time.time()) if now is None else now
    location = Path(path or os.environ.get('MTASCAN_TEMPORAL_SUMMARY', '/run/mta-temporal-public/summary.json'))
    try:
        with location.open('rb') as stream:
            raw = stream.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError('Oversized summary')
        data = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        summary = Summary.model_validate(data)
        if summary.generated_ts > now + 30 or now - summary.generated_ts > 900:
            return unavailable('Temporal worker snapshot is stale or future-dated. Live map monitoring is separate.')
        if summary.feature_cutoff_ts is not None and summary.feature_cutoff_ts > now:
            raise ValueError('Future feature window')
        if (summary.evaluation_cutoff_ts is not None and summary.feature_cutoff_ts is not None
                and summary.evaluation_cutoff_ts > summary.feature_cutoff_ts):
            raise ValueError('Future evaluation cutoff')
        ready = summary.readiness
        valid = (summary.valid_until_ts is not None and now < summary.valid_until_ts <= summary.generated_ts + 900
                 and summary.feature_cutoff_ts is not None and 0 <= now - summary.feature_cutoff_ts <= 600
                 and summary.coverage is not None and summary.coverage.span_seconds >= 14 * 86400
                 and summary.coverage.complete_fresh_window_fraction >= .9)
        if not ready.public_forecasts_ready or ready.status != 'ready' or not valid:
            summary.forecasts = []
        else:
            summary.forecasts = [f for f in summary.forecasts if 0 <= now - f.origin_ts <= 600
                                 and f.target_ts == f.origin_ts + f.horizon_seconds and f.target_ts > now]
        if ready.public_forecasts_ready and not summary.forecasts:
            ready.status = 'temporarily_unavailable'
            ready.reasons.append('Forecasts withheld: readiness, coverage or timestamp checks did not pass.')
        ready.public_forecasts_ready = bool(summary.forecasts)
        return summary.model_dump(by_alias=True)
    except FileNotFoundError:
        return unavailable('Temporal collection summary is not available yet. Live map monitoring is separate.')
    except (OSError, ValueError, ValidationError, TypeError, RecursionError):
        return unavailable('Temporal summary could not be validated. No forecast is shown.')
