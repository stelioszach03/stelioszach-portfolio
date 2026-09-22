"""Ranking and incident-timing metrics for the replay evaluation.

Ported from the upstream `evaluation/metrics.py`, with one correction that
changes some published numbers and is worth stating plainly.

THE TIE PROBLEM
---------------
The original ranked rows with pandas' `sort_values`, an *unstable* quicksort,
then read off precision@k / recall@k / MRR. On this dataset that is not a
detail: the online model puts 7 rows at exactly 1.0 (6 positive, 1 negative)
and the fixed-threshold baseline puts 208 rows at exactly 0.0 (8 of them
positive). Whenever k cuts through a tied block, the metric is decided by
which equal-scoring row the sort happened to emit first — so p@5 could be
1.0 or 0.8 for the same model on the same data.

So every ranking metric here is computed as its **expected value over random
orderings within each tied block**, which has a closed form:

    E[hits@k] = (positives strictly above the block)
              + (slots taken from the block) x (block positive rate)

    E[1/rank] for a positive in a block spanning ranks a..b
              = mean(1/a, 1/a+1, ..., 1/b)

That is deterministic, independent of input order, and cannot be inflated by a
lucky sort. Metrics that never depended on the ordering — false-alarm rate,
incident detection rate, lead time, time-to-detect — are unchanged.

Effect on the published numbers, stated so nobody has to diff it themselves.
Of 64 metric values, 55 are bit-identical to the upstream artifacts and 9 move,
all of them at a k that cuts through a tie:

    online_model        p@5   1.0    -> 0.857    r@5   0.3125 -> 0.268
                        MRR   0.1992 -> 0.1865
    threshold_baseline  p@10  0.8    -> 0.808    r@10  0.5    -> 0.505
                        p@20  0.5    -> 0.423    r@20  0.625  -> 0.529
                        MRR   0.1836 -> 0.1776
    zscore_baseline     MRR   0.1278 -> 0.1577

The threshold baseline moves most because 208 of its 216 rows score exactly
0.0 — its r@20 was never a measurement, only a coin toss.

The headline comparison is untouched: recall@20 **1.00** for the online model
against **0.625** for both the z-score and EWMA baselines, at a false-alarm
rate of **0.030**, catching **3 of 3** incidents where the fixed-threshold
baseline catches 1 of 3 — on **216 rows, 16 positive, 3 incidents**.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence


DEFAULT_K_VALUES = (5, 10, 20)


def _score(row: dict[str, Any], score_col: str) -> float:
    return float(row.get(score_col, 0.0) or 0.0)


def _label(row: dict[str, Any], label_col: str) -> float:
    return float(row.get(label_col, 0.0) or 0.0)


def _tie_blocks(
    rows: Sequence[dict[str, Any]], score_col: str, label_col: str
) -> list[tuple[int, int]]:
    """Descending score blocks as (block_size, positives_in_block)."""
    pairs = sorted(
        ((_score(row, score_col), _label(row, label_col) > 0) for row in rows),
        key=lambda item: item[0],
        reverse=True,
    )
    blocks: list[tuple[int, int]] = []
    index = 0
    while index < len(pairs):
        score = pairs[index][0]
        end = index
        while end < len(pairs) and pairs[end][0] == score:
            end += 1
        size = end - index
        positives = sum(1 for _, is_positive in pairs[index:end] if is_positive)
        blocks.append((size, positives))
        index = end
    return blocks


def expected_hits_at_k(
    rows: Sequence[dict[str, Any]], score_col: str, label_col: str, k: int
) -> tuple[float, int]:
    """Expected positives in the top k, and the actual number of slots used."""
    if not rows:
        return 0.0, 0
    k = min(int(k), len(rows))
    hits = 0.0
    remaining = k
    for size, positives in _tie_blocks(rows, score_col, label_col):
        if remaining <= 0:
            break
        if remaining >= size:
            hits += positives
            remaining -= size
        else:
            # k cuts through this block: take the block's positive rate.
            hits += remaining * (positives / size)
            remaining = 0
    return hits, k


def precision_at_k(rows: Sequence[dict[str, Any]], score_col: str, label_col: str, k: int) -> float:
    hits, used = expected_hits_at_k(rows, score_col, label_col, k)
    return hits / float(used) if used else 0.0


def recall_at_k(rows: Sequence[dict[str, Any]], score_col: str, label_col: str, k: int) -> float:
    positives = sum(1 for row in rows if _label(row, label_col) > 0)
    if positives <= 0:
        return 0.0
    hits, _ = expected_hits_at_k(rows, score_col, label_col, k)
    return hits / float(positives)


def mean_reciprocal_rank(rows: Sequence[dict[str, Any]], score_col: str, label_col: str) -> float:
    """Mean expected reciprocal rank over the positives, tie blocks averaged."""
    reciprocals: list[float] = []
    rank = 1
    for size, positives in _tie_blocks(rows, score_col, label_col):
        if positives:
            block_mean = sum(1.0 / float(r) for r in range(rank, rank + size)) / float(size)
            reciprocals.extend([block_mean] * positives)
        rank += size
    if not reciprocals:
        return 0.0
    return sum(reciprocals) / float(len(reciprocals))


def false_alarm_rate(
    rows: Sequence[dict[str, Any]], score_col: str, label_col: str, threshold: float
) -> float:
    """Threshold-based, so ties do not affect it."""
    negatives = [row for row in rows if _label(row, label_col) <= 0]
    if not negatives:
        return 0.0
    flagged = [row for row in negatives if _score(row, score_col) >= threshold]
    return float(len(flagged)) / float(len(negatives))


def tie_report(rows: Sequence[dict[str, Any]], score_col: str, label_col: str) -> dict[str, Any]:
    """How much of the ranking is actually decided by ties. Shown in the API."""
    blocks = _tie_blocks(rows, score_col, label_col)
    tied = [(size, positives) for size, positives in blocks if size > 1]
    return {
        "distinct_scores": len(blocks),
        "tied_blocks": len(tied),
        "rows_in_ties": sum(size for size, _ in tied),
        "largest_tie": max((size for size, _ in tied), default=0),
    }


def _epoch(value: Any) -> float:
    from .features import _to_epoch  # local import keeps this module dependency-light

    parsed = _to_epoch(value)
    return 0.0 if parsed is None else parsed


def incident_timing_metrics(
    rows: Sequence[dict[str, Any]],
    score_col: str,
    label_col: str = "label",
    incident_col: str = "incident_id",
    threshold: float = 0.6,
) -> dict[str, Any]:
    """How reliably, and how early, each labelled incident is caught."""
    incident_ids: list[str] = []
    for row in rows:
        incident_id = str(row.get(incident_col) or "").strip()
        if incident_id and incident_id not in incident_ids:
            incident_ids.append(incident_id)

    if not incident_ids:
        return {
            "incident_detection_rate": 0.0,
            "detected_incidents": 0,
            "total_incidents": 0,
            "average_lead_time_min": 0.0,
            "average_time_to_detect_min": 0.0,
        }

    detected = 0
    lead_times: list[float] = []
    detection_delays: list[float] = []

    for incident_id in incident_ids:
        incident_rows = [
            row for row in rows if str(row.get(incident_col) or "").strip() == incident_id
        ]
        if not incident_rows:
            continue
        labelled = [row for row in incident_rows if _label(row, label_col) > 0]
        onset = min(_epoch(row.get("observed_ts")) for row in (labelled or incident_rows))
        detections = [row for row in incident_rows if _score(row, score_col) >= threshold]
        if not detections:
            continue
        detected += 1
        first_detection = min(_epoch(row.get("observed_ts")) for row in detections)
        delta_min = (first_detection - onset) / 60.0
        if delta_min <= 0:
            lead_times.append(abs(delta_min))
        else:
            detection_delays.append(delta_min)

    return {
        "incident_detection_rate": float(detected) / float(len(incident_ids)),
        "detected_incidents": int(detected),
        "total_incidents": int(len(incident_ids)),
        "average_lead_time_min": (sum(lead_times) / len(lead_times)) if lead_times else 0.0,
        "average_time_to_detect_min": (
            sum(detection_delays) / len(detection_delays) if detection_delays else 0.0
        ),
    }


def evaluate_method(
    rows: Sequence[dict[str, Any]],
    score_col: str,
    label_col: str = "label",
    threshold: float = 0.6,
    k_values: Iterable[int] = DEFAULT_K_VALUES,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "threshold": float(threshold),
        "rows": int(len(rows)),
        "positives": int(sum(1 for row in rows if _label(row, label_col) > 0)),
        "false_alarm_rate": false_alarm_rate(rows, score_col, label_col, threshold),
        "mean_reciprocal_rank": mean_reciprocal_rank(rows, score_col, label_col),
    }
    metrics["precision_at_k"] = {
        f"p@{k}": precision_at_k(rows, score_col, label_col, int(k)) for k in k_values
    }
    metrics["recall_at_k"] = {
        f"r@{k}": recall_at_k(rows, score_col, label_col, int(k)) for k in k_values
    }
    metrics["ties"] = tie_report(rows, score_col, label_col)
    metrics.update(incident_timing_metrics(rows, score_col, label_col=label_col, threshold=threshold))
    return metrics


def evaluate_methods(
    rows: Sequence[dict[str, Any]],
    method_cols: dict[str, str],
    label_col: str = "label",
    threshold: float = 0.6,
    k_values: Iterable[int] = DEFAULT_K_VALUES,
) -> dict[str, dict[str, Any]]:
    return {
        name: evaluate_method(rows, score_col, label_col=label_col, threshold=threshold, k_values=k_values)
        for name, score_col in method_cols.items()
    }
