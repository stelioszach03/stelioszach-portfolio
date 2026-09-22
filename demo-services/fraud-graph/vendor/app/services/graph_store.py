from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import networkx as nx


@dataclass(slots=True)
class TxEvent:
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: float
    currency: str
    channel: str
    country_from: str
    country_to: str
    timestamp_utc: datetime


class GraphStore:
    def __init__(self, max_events: int = 300_000, max_alerts: int = 10_000) -> None:
        self.graph = nx.DiGraph()
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.alerts: deque[dict[str, Any]] = deque(maxlen=max_alerts)

    def _init_node(self, node_id: str, ts: datetime) -> None:
        if node_id in self.graph:
            node = self.graph.nodes[node_id]
            node["last_seen"] = ts
            return
        self.graph.add_node(
            node_id,
            first_seen=ts,
            last_seen=ts,
            in_count=0,
            out_count=0,
            in_total=0.0,
            out_total=0.0,
        )

    def add_event(
        self,
        event: TxEvent,
        risk_score: float | None = None,
        risk_band: str | None = None,
        reasons: list[str] | None = None,
    ) -> None:
        ts = event.timestamp_utc.astimezone(timezone.utc)
        self._init_node(event.sender_id, ts)
        self._init_node(event.receiver_id, ts)

        sender = self.graph.nodes[event.sender_id]
        receiver = self.graph.nodes[event.receiver_id]
        sender["out_count"] += 1
        sender["out_total"] += float(event.amount)
        sender["last_seen"] = ts

        receiver["in_count"] += 1
        receiver["in_total"] += float(event.amount)
        receiver["last_seen"] = ts

        if self.graph.has_edge(event.sender_id, event.receiver_id):
            edge = self.graph[event.sender_id][event.receiver_id]
            edge["count"] += 1
            edge["total"] += float(event.amount)
            edge["last_ts"] = ts
        else:
            self.graph.add_edge(
                event.sender_id,
                event.receiver_id,
                count=1,
                total=float(event.amount),
                first_ts=ts,
                last_ts=ts,
            )

        item = {
            "tx_id": event.tx_id,
            "sender_id": event.sender_id,
            "receiver_id": event.receiver_id,
            "amount": float(event.amount),
            "currency": event.currency,
            "channel": event.channel,
            "country_from": event.country_from,
            "country_to": event.country_to,
            "timestamp_utc": ts,
            "risk_score": float(risk_score) if risk_score is not None else None,
            "risk_band": risk_band,
            "reasons": reasons or [],
        }
        self.events.append(item)

    def add_alert(self, item: dict[str, Any]) -> None:
        self.alerts.append(item)

    def out_degree(self, account_id: str) -> int:
        return int(self.graph.out_degree(account_id)) if account_id in self.graph else 0

    def in_degree(self, account_id: str) -> int:
        return int(self.graph.in_degree(account_id)) if account_id in self.graph else 0

    def has_seen_pair(self, sender_id: str, receiver_id: str) -> bool:
        return self.graph.has_edge(sender_id, receiver_id)

    def has_reverse_edge(self, sender_id: str, receiver_id: str) -> bool:
        return self.graph.has_edge(receiver_id, sender_id)

    def shared_counterparties(self, sender_id: str, receiver_id: str) -> int:
        if sender_id not in self.graph or receiver_id not in self.graph:
            return 0
        sender_neighbors = set(self.graph.successors(sender_id))
        receiver_neighbors = set(self.graph.predecessors(receiver_id))
        return len(sender_neighbors & receiver_neighbors)

    def sender_amount_stats(self, sender_id: str, lookback: int = 150) -> tuple[float, float]:
        vals: list[float] = []
        for row in reversed(self.events):
            if row["sender_id"] == sender_id:
                vals.append(float(row["amount"]))
                if len(vals) >= lookback:
                    break
        if not vals:
            return 0.0, 1.0
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        std = (var ** 0.5) if var > 1e-8 else 1.0
        return mean, std

    def sender_event_count(self, sender_id: str) -> int:
        if sender_id not in self.graph:
            return 0
        node = self.graph.nodes[sender_id]
        return int(node.get("out_count", 0))

    def global_amount_stats(
        self,
        lookback: int = 4000,
        prior_mean: float = 1200.0,
        prior_std: float = 2500.0,
    ) -> tuple[float, float]:
        vals: list[float] = []
        limit = max(50, int(lookback))
        for row in reversed(self.events):
            vals.append(float(row["amount"]))
            if len(vals) >= limit:
                break

        if len(vals) < 30:
            return float(prior_mean), float(max(1.0, prior_std))

        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        std = (var ** 0.5) if var > 1e-8 else 1.0
        return mean, std

    def recent_count(self, account_id: str, seconds: int, direction: str = "sender") -> int:
        if seconds <= 0:
            return 0
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=seconds)
        key = "sender_id" if direction == "sender" else "receiver_id"
        total = 0
        for row in reversed(self.events):
            ts = row["timestamp_utc"]
            # Arrival order can differ from event time; do not stop at a late event.
            if ts < cutoff or ts > now:
                continue
            if row[key] == account_id:
                total += 1
        return total

    def account_age_seconds(self, account_id: str) -> float:
        if account_id not in self.graph:
            return 0.0
        first_seen = self.graph.nodes[account_id].get("first_seen")
        if first_seen is None:
            return 0.0
        return max(0.0, (datetime.now(timezone.utc) - first_seen).total_seconds())

    def totals(self, account_id: str) -> tuple[float, float]:
        if account_id not in self.graph:
            return 0.0, 0.0
        node = self.graph.nodes[account_id]
        return float(node.get("out_total", 0.0)), float(node.get("in_total", 0.0))

    def summary(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        high_risk_last_hour = 0
        for row in reversed(self.events):
            if not cutoff <= row["timestamp_utc"] <= now:
                continue
            score = float(row["risk_score"] or 0.0)
            if score >= 0.85:
                high_risk_last_hour += 1

        return {
            "nodes_total": int(self.graph.number_of_nodes()),
            "edges_total": int(self.graph.number_of_edges()),
            "events_total": int(len(self.events)),
            "alerts_total": int(len(self.alerts)),
            "high_risk_last_hour": int(high_risk_last_hour),
        }

    def latest_alerts(self, min_score: float = 0.82, limit: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in reversed(self.alerts):
            if float(row.get("risk_score", 0.0)) < min_score:
                continue
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def clear(self) -> None:
        """Reset all in-memory state. Used for deterministic demos and tests."""
        self.graph.clear()
        self.events.clear()
        self.alerts.clear()

    def neighborhood(
        self,
        node_id: str,
        depth: int = 1,
        limit: int = 40,
    ) -> dict[str, Any] | None:
        """
        Return a BFS-expanded neighborhood around `node_id` as a serializable
        subgraph. Depth is capped at 2 to keep payload small; limit caps the
        total node count.
        """
        if node_id not in self.graph:
            return None

        depth = max(1, min(2, int(depth)))
        limit = max(1, int(limit))

        visited: set[str] = {node_id}
        frontier: set[str] = {node_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for nbr in self.graph.successors(nid):
                    if nbr not in visited:
                        next_frontier.add(nbr)
                for nbr in self.graph.predecessors(nid):
                    if nbr not in visited:
                        next_frontier.add(nbr)
                if len(visited) + len(next_frontier) >= limit:
                    break
            visited |= next_frontier
            if len(visited) >= limit:
                break
            frontier = next_frontier
            if not frontier:
                break

        # Truncate deterministically if we blew past the cap.
        node_list = list(visited)
        if len(node_list) > limit:
            # Keep the focus + closest seen first
            node_list = [node_id] + [n for n in node_list if n != node_id]
            node_list = node_list[:limit]
        kept = set(node_list)

        nodes: list[dict[str, Any]] = []
        for nid in node_list:
            node_data = self.graph.nodes[nid]
            nodes.append(
                {
                    "id": nid,
                    "in_count": int(node_data.get("in_count", 0)),
                    "out_count": int(node_data.get("out_count", 0)),
                    "in_total": float(node_data.get("in_total", 0.0)),
                    "out_total": float(node_data.get("out_total", 0.0)),
                    "is_focus": nid == node_id,
                    "first_seen_utc": _iso(node_data.get("first_seen")),
                    "last_seen_utc": _iso(node_data.get("last_seen")),
                }
            )

        edges: list[dict[str, Any]] = []
        for u, v, data in self.graph.edges(data=True):
            if u in kept and v in kept:
                edges.append(
                    {
                        "source": u,
                        "target": v,
                        "count": int(data.get("count", 0)),
                        "total": float(data.get("total", 0.0)),
                        "last_ts_utc": _iso(data.get("last_ts")),
                    }
                )

        return {
            "focus": node_id,
            "depth": depth,
            "nodes": nodes,
            "edges": edges,
        }


def _iso(value: Any) -> str | None:
    """Best-effort ISO-8601 serialization for datetimes."""
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except Exception:
        return None
    return None
