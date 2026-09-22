"""Offline replay evaluation — the thing a recruiter sees in the first second.

The live map is honest but slow theatre: real anomalies on the real network
happen when they happen, and a visitor who lands on an ordinary Tuesday sees a
calm city. So the demo also ships a **frozen, labelled replay** of three
scenarios and replays the *same* model code over it, producing measured
numbers against three baselines.

HONESTY, EXPLICITLY
-------------------
This dataset is 216 rows, 16 positive rows, 3 routes, 6 stops, 3 incidents.
It is a representative sanity evaluation, not a benchmark, and it is not
official MTA incident annotation. Every number this module produces carries
that sample size next to it in `summary.json` → `dataset`, and the API refuses
to serve the metrics without it.

Run it with `python -m mtascan.replay` (or scripts/run_replay_eval.py). The
artifacts under data/replay/ are committed so the demo works before the first
collector cycle finishes.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .baselines import add_baseline_scores
from .features import FEATURE_DESCRIPTIONS, FeatureEngine, _to_epoch
from .metrics import evaluate_methods
from .scoring import new_bundle, score_feature_row


METHOD_COLUMNS = {
    "online_model": "online_model_score",
    "zscore_baseline": "baseline_zscore",
    "ewma_baseline": "baseline_ewma",
    "threshold_baseline": "baseline_threshold",
}

DETECTION_THRESHOLD = 0.6

NUMERIC_INPUT_COLUMNS = (
    "label",
    "precipitation_mm",
    "weather_severity",
    "service_alert_active",
    "service_alert_severity",
)

TEXT_INPUT_COLUMNS = ("stop_name", "incident_id", "incident_title", "incident_note")


def _iso(value: Any) -> str | None:
    epoch = _to_epoch(value)
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def load_replay_dataset(path: str | Path) -> list[dict[str, Any]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Replay dataset not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))

    required = {"observed_ts", "route_id", "stop_id", "headway_sec"}
    if raw_rows:
        missing = sorted(required - set(raw_rows[0].keys()))
        if missing:
            raise ValueError(f"Replay dataset missing required columns: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        observed = _to_epoch(raw.get("observed_ts"))
        try:
            headway = float(raw.get("headway_sec") or "")
        except ValueError:
            continue
        if observed is None or headway <= 0:
            continue
        row: dict[str, Any] = {
            "observed_ts": observed,
            "event_ts": _to_epoch(raw.get("event_ts")),
            "route_id": str(raw.get("route_id") or ""),
            "stop_id": str(raw.get("stop_id") or ""),
            "headway_sec": headway,
        }
        for column in TEXT_INPUT_COLUMNS:
            row[column] = str(raw.get(column) or "")
        for column in NUMERIC_INPUT_COLUMNS:
            try:
                row[column] = float(raw.get(column) or 0.0)
            except ValueError:
                row[column] = 0.0
        rows.append(row)

    # Same ordering the pandas implementation used before grouping.
    rows.sort(key=lambda r: (r["observed_ts"], r["route_id"], r["stop_id"]))
    return rows


def replay_online_model(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replay the live scoring path over the dataset, sequentially, learning as it goes."""
    engine = FeatureEngine()
    bundle = new_bundle()
    out: list[dict[str, Any]] = []

    for row in rows:
        features = engine.compute(
            route_id=row["route_id"],
            stop_id=row["stop_id"],
            observed_ts=row["observed_ts"],
            headway_sec=row["headway_sec"],
            event_ts=row.get("event_ts"),
            precipitation_mm=row.get("precipitation_mm", 0.0),
            weather_severity=row.get("weather_severity", 0.0),
            service_alert_active=row.get("service_alert_active", 0.0),
            service_alert_severity=row.get("service_alert_severity", 0.0),
        )
        merged = dict(row)
        merged.update(features)
        result = score_feature_row(bundle, merged, learn=True)
        merged.update(
            {
                "predicted_headway_sec": result["predicted_headway_sec"],
                "residual": result["residual"],
                "online_model_score": result["anomaly_score"],
                "ssl_score": result["ssl_score"],
                "hst_score": result["hst_score"],
                "relative_error_score": result["relative_error_score"],
                "context_score": result["context_score"],
                "reason_details": result["reasons"],
                "reason_labels": [str(reason["label"]) for reason in result["reasons"]],
            }
        )
        out.append(merged)
    return out


# --------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------

def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "incident"


def build_timeline(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ts: dict[float, list[dict[str, Any]]] = {}
    for row in rows:
        by_ts.setdefault(float(row["observed_ts"]), []).append(row)

    points: list[dict[str, Any]] = []
    for index, stamp in enumerate(sorted(by_ts)):
        group = by_ts[stamp]
        ranked = sorted(group, key=lambda r: float(r["online_model_score"]), reverse=True)

        peaks: dict[str, float] = {}
        for row in group:
            route_id = str(row["route_id"])
            peaks[route_id] = max(peaks.get(route_id, 0.0), float(row["online_model_score"]))
        top_routes = sorted(peaks.items(), key=lambda item: item[1], reverse=True)[:3]

        incident_rows = [row for row in group if str(row.get("incident_id") or "")]
        points.append(
            {
                "index": index,
                "observed_ts": _iso(stamp),
                "model_peak_score": max(float(r["online_model_score"]) for r in group),
                "baseline_zscore_peak": max(float(r["baseline_zscore"]) for r in group),
                "baseline_ewma_peak": max(float(r["baseline_ewma"]) for r in group),
                "baseline_threshold_peak": max(float(r["baseline_threshold"]) for r in group),
                "label": int(max(float(r.get("label", 0.0)) for r in group)),
                "incident_id": str(incident_rows[0].get("incident_id")) if incident_rows else "",
                "incident_title": str(incident_rows[0].get("incident_title")) if incident_rows else "",
                "top_routes": [
                    {"route_id": route_id, "peak_score": score} for route_id, score in top_routes
                ],
                "top_stops": [
                    {
                        "route_id": str(row["route_id"]),
                        "stop_id": str(row["stop_id"]),
                        "stop_name": str(row.get("stop_name") or row["stop_id"]),
                        "headway_sec": float(row["headway_sec"]),
                        "predicted_headway_sec": float(row["predicted_headway_sec"]),
                        "online_model_score": float(row["online_model_score"]),
                        "baseline_zscore": float(row["baseline_zscore"]),
                        "baseline_ewma": float(row["baseline_ewma"]),
                        "baseline_threshold": float(row["baseline_threshold"]),
                        "reasons": list(row.get("reason_labels") or []),
                    }
                    for row in ranked[:5]
                ],
            }
        )
    return points


def _line_svg(points: Sequence[dict[str, Any]], title: str, series: Sequence[tuple[str, str]]) -> str:
    width, height = 980, 340
    left, right, top, bottom = 52, 20, 28, 36
    inner_w, inner_h = width - left - right, height - top - bottom
    xs = [idx / max(len(points) - 1, 1) for idx in range(len(points))]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
        '<rect width="100%" height="100%" fill="#f8fafc" rx="18" />',
        f'<text x="{left}" y="18" font-size="16" font-weight="700" fill="#0f172a">{title}</text>',
    ]
    for tick in range(6):
        y = top + inner_h - (inner_h * tick / 5.0)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#dbe4ef" stroke-width="1" />'
        )
        parts.append(f'<text x="14" y="{y + 4:.1f}" font-size="11" fill="#64748b">{tick / 5.0:.1f}</text>')

    for name, color in series:
        coords = []
        for index, point in enumerate(points):
            x = left + xs[index] * inner_w
            score = max(0.0, min(1.0, float(point.get(name, 0.0) or 0.0)))
            coords.append(f"{x:.1f},{top + inner_h - score * inner_h:.1f}")
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{" ".join(coords)}" />'
        )

    for index, (name, color) in enumerate(series):
        lx = left + index * 170
        parts.append(f'<rect x="{lx}" y="{height - 22}" width="12" height="12" rx="3" fill="{color}" />')
        parts.append(f'<text x="{lx + 18}" y="{height - 12}" font-size="12" fill="#334155">{name}</text>')

    if points:
        parts.append(
            f'<text x="{left}" y="{height - 8}" font-size="11" fill="#64748b">{points[0].get("observed_ts", "")}</text>'
        )
        parts.append(
            f'<text x="{width - right - 190}" y="{height - 8}" font-size="11" fill="#64748b">{points[-1].get("observed_ts", "")}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


SERIES = (
    ("online_model_score", "#0f766e"),
    ("baseline_zscore", "#dc2626"),
    ("baseline_ewma", "#2563eb"),
    ("baseline_threshold", "#9333ea"),
)


def write_artifacts(
    *,
    rows: Sequence[dict[str, Any]],
    metrics: dict[str, Any],
    out_dir: str | Path,
    dataset_path: str,
) -> dict[str, Any]:
    out_path = Path(out_dir)
    (out_path / "incidents").mkdir(parents=True, exist_ok=True)
    (out_path / "plots").mkdir(parents=True, exist_ok=True)

    timeline = build_timeline(rows)
    (out_path / "timeline.json").write_text(json.dumps({"points": timeline}, indent=2), encoding="utf-8")

    (out_path / "plots" / "overall-scores.svg").write_text(
        _line_svg(
            [
                {
                    "observed_ts": point["observed_ts"],
                    "online_model_score": point["model_peak_score"],
                    "baseline_zscore": point["baseline_zscore_peak"],
                    "baseline_ewma": point["baseline_ewma_peak"],
                    "baseline_threshold": point["baseline_threshold_peak"],
                }
                for point in timeline
            ],
            title="Replay timeline: online model vs baselines",
            series=SERIES,
        ),
        encoding="utf-8",
    )

    incident_ids: list[str] = []
    for row in rows:
        incident_id = str(row.get("incident_id") or "").strip()
        if incident_id and incident_id not in incident_ids:
            incident_ids.append(incident_id)

    incidents: list[dict[str, Any]] = []
    for incident_id in incident_ids:
        incident_rows = sorted(
            (row for row in rows if str(row.get("incident_id") or "").strip() == incident_id),
            key=lambda r: float(r["observed_ts"]),
        )
        if not incident_rows:
            continue
        title = str(incident_rows[0].get("incident_title") or incident_id)
        slug = _slugify(incident_id)
        start_ts = min(float(r["observed_ts"]) for r in incident_rows)
        end_ts = max(float(r["observed_ts"]) for r in incident_rows)

        detections = [
            r for r in incident_rows if float(r["online_model_score"]) >= DETECTION_THRESHOLD
        ]
        labelled = [r for r in incident_rows if float(r.get("label", 0.0)) > 0]
        detection_delay_min = 0.0
        if detections and labelled:
            first_detection = min(float(r["observed_ts"]) for r in detections)
            labelled_start = min(float(r["observed_ts"]) for r in labelled)
            detection_delay_min = (first_detection - labelled_start) / 60.0

        points = [
            point
            for point in timeline
            if point.get("incident_id") == incident_id
            or (start_ts <= (_to_epoch(point["observed_ts"]) or 0.0) <= end_ts)
        ]
        (out_path / "plots" / f"{slug}.svg").write_text(
            _line_svg(
                [
                    {
                        "observed_ts": point["observed_ts"],
                        "online_model_score": point["model_peak_score"],
                        "baseline_zscore": point["baseline_zscore_peak"],
                        "baseline_ewma": point["baseline_ewma_peak"],
                        "baseline_threshold": point["baseline_threshold_peak"],
                    }
                    for point in points
                ],
                title=f"Incident replay: {title}",
                series=SERIES,
            ),
            encoding="utf-8",
        )

        reason_counts: dict[str, int] = {}
        for row in incident_rows:
            for label in row.get("reason_labels") or []:
                reason_counts[label] = reason_counts.get(label, 0) + 1
        top_reasons = [
            label for label, _ in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        ]

        route_peaks: dict[str, float] = {}
        for row in incident_rows:
            route_id = str(row["route_id"])
            route_peaks[route_id] = max(route_peaks.get(route_id, 0.0), float(row["online_model_score"]))
        top_routes = sorted(route_peaks.items(), key=lambda item: item[1], reverse=True)[:3]

        top_stops = [
            {
                "stop_id": str(row["stop_id"]),
                "stop_name": str(row.get("stop_name") or row["stop_id"]),
                "route_id": str(row["route_id"]),
                "online_model_score": float(row["online_model_score"]),
                "headway_sec": float(row["headway_sec"]),
                "predicted_headway_sec": float(row["predicted_headway_sec"]),
            }
            for row in sorted(
                incident_rows, key=lambda r: float(r["online_model_score"]), reverse=True
            )[:5]
        ]

        detail = {
            "incident_id": incident_id,
            "incident_title": title,
            "what_happened": str(incident_rows[0].get("incident_note") or "Representative replay scenario."),
            "window_start": _iso(start_ts),
            "window_end": _iso(end_ts),
            "peak_score": max(float(r["online_model_score"]) for r in incident_rows),
            "peak_label": int(max(float(r.get("label", 0.0)) for r in incident_rows)),
            "detection_delay_min": detection_delay_min,
            "top_reasons": top_reasons,
            "top_routes": [{"route_id": r, "peak_score": s} for r, s in top_routes],
            "top_stops": top_stops,
            "points": points,
            "plot_path": f"plots/{slug}.svg",
        }
        (out_path / "incidents" / f"{slug}.json").write_text(
            json.dumps(detail, indent=2), encoding="utf-8"
        )

        incidents.append(
            {
                "incident_id": incident_id,
                "incident_title": title,
                "window_start": _iso(start_ts),
                "window_end": _iso(end_ts),
                "peak_score": detail["peak_score"],
                "detection_delay_min": detection_delay_min,
                "top_reasons": top_reasons,
                "affected_routes": [route_id for route_id, _ in top_routes],
                "detail_path": f"incidents/{slug}.json",
                "plot_path": f"plots/{slug}.svg",
            }
        )

    (out_path / "incidents.json").write_text(json.dumps({"incidents": incidents}, indent=2), encoding="utf-8")
    (out_path / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    # Never bake an absolute build path into a published artifact.
    try:
        relative_dataset = str(Path(dataset_path).relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        relative_dataset = Path(dataset_path).name

    summary = {
        "dataset": {
            "path": relative_dataset,
            "rows": len(rows),
            "positive_rows": int(sum(float(r.get("label", 0.0)) for r in rows)),
            "routes": len({str(r["route_id"]) for r in rows}),
            "stops": len({str(r["stop_id"]) for r in rows}),
            "incidents": len(incidents),
        },
        "metrics": metrics,
        "feature_highlights": [
            {"feature": feature, "why_it_matters": description}
            for feature, description in FEATURE_DESCRIPTIONS.items()
        ],
        "artifacts": {
            "timeline_json": "timeline.json",
            "incidents_json": "incidents.json",
            "overall_plot": "plots/overall-scores.svg",
        },
        "notes": [
            "Representative labelled scenarios, not official MTA incident annotations.",
            "216 rows / 16 positive rows / 3 incidents: a sanity evaluation, not a benchmark.",
            "The online model is replayed sequentially through the same scoring code the live collector runs.",
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    (out_path / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Flat event export, handy for anyone who wants to check the numbers by hand.
    export_columns = [
        "observed_ts",
        "route_id",
        "stop_id",
        "stop_name",
        "headway_sec",
        "predicted_headway_sec",
        "residual",
        "online_model_score",
        "baseline_zscore",
        "baseline_ewma",
        "baseline_threshold",
        "label",
        "incident_id",
        "reason_labels",
    ]
    with (out_path / "events.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(export_columns)
        for row in rows:
            writer.writerow(
                [
                    _iso(row["observed_ts"]),
                    row["route_id"],
                    row["stop_id"],
                    row.get("stop_name", ""),
                    row["headway_sec"],
                    row["predicted_headway_sec"],
                    row["residual"],
                    row["online_model_score"],
                    row["baseline_zscore"],
                    row["baseline_ewma"],
                    row["baseline_threshold"],
                    int(row.get("label", 0)),
                    row.get("incident_id", ""),
                    json.dumps(row.get("reason_labels") or []),
                ]
            )

    return summary


def run_replay_evaluation(dataset_path: str | Path, out_dir: str | Path) -> dict[str, Any]:
    source = load_replay_dataset(dataset_path)
    scored = replay_online_model(source)
    rows = add_baseline_scores(scored)
    metrics = evaluate_methods(rows, METHOD_COLUMNS, label_col="label", threshold=DETECTION_THRESHOLD)
    summary = write_artifacts(
        rows=rows, metrics=metrics, out_dir=out_dir, dataset_path=str(dataset_path)
    )
    return {"summary": summary, "metrics": metrics, "rows": rows}


def main() -> None:
    import argparse

    from .config import get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the replay evaluation and rewrite its artifacts")
    parser.add_argument("--input", default=str(settings.data_dir / "sample_subway_headways.csv"))
    parser.add_argument("--out-dir", default=str(settings.replay_dir))
    args = parser.parse_args()

    payload = run_replay_evaluation(args.input, args.out_dir)
    print(json.dumps({"dataset": payload["summary"]["dataset"], "methods": payload["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
