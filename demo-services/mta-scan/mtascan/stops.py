"""Station geometry, loaded once from a vendored slice of the MTA static GTFS.

The realtime feeds carry stop *ids* only, so latitude/longitude has to come
from the static schedule. Rather than download a 5 MB zip on every boot (and
break when the MTA is unreachable), `scripts/build_stops.py` extracts the two
files we need into data/stops.csv + data/routes.csv and those are shipped with
the demo. Source and extraction date are recorded in data/SOURCES.md.
"""
from __future__ import annotations

import csv
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=4)
def load_stops(path: str) -> tuple[dict[str, dict[str, Any]], str]:
    """Return {stop_id: {...}} plus a weak ETag for HTTP caching."""
    stops: dict[str, dict[str, Any]] = {}
    file_path = Path(path)
    if not file_path.exists():
        return stops, 'W/"stops-0"'

    with file_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            stop_id = (row.get("stop_id") or "").strip()
            if not stop_id:
                continue
            try:
                lat = float(row.get("lat") or row.get("stop_lat") or "")
                lon = float(row.get("lon") or row.get("stop_lon") or "")
            except ValueError:
                continue
            stops[stop_id] = {
                "stop_id": stop_id,
                "stop_name": (row.get("stop_name") or "").strip(),
                "lat": lat,
                "lon": lon,
                "borough": (row.get("borough") or "").strip() or None,
            }

    digest = hashlib.sha1(",".join(sorted(stops)).encode("utf-8")).hexdigest()[:16]
    return stops, f'W/"stops-{len(stops)}-{digest}"'


@lru_cache(maxsize=4)
def load_routes(path: str) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    file_path = Path(path)
    if not file_path.exists():
        return routes
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            route_id = (row.get("route_id") or "").strip()
            if not route_id:
                continue
            colour = (row.get("route_color") or "").strip()
            routes[route_id] = {
                "route_id": route_id,
                "name": (row.get("route_long_name") or route_id).strip(),
                "color": f"#{colour}" if colour else "#4b5563",
                "text_color": f"#{(row.get('route_text_color') or 'FFFFFF').strip()}",
            }
    return routes
