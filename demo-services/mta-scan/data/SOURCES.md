# Vendored data

| File | Source | Retrieved |
|---|---|---|
| `stops.csv`, `routes.csv` | MTA static GTFS, `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip` | 2026-08-07 |
| `sample_subway_headways.csv` | Hand-labelled replay scenarios from the NYC-Subway-Anomaly-Detection repo (216 rows, 3 incidents) | committed with the repo |
| `../static/data/basemap.json` | MTA static GTFS `stops.txt` + `shapes.txt` + `routes.txt`, `http://web.mta.info/developers/data/nyct/subway/google_transit.zip` — 475 station dots and one simplified polyline per route, so the map is not empty before the first API response | 2026-08-07 |
| `../static/data/replay.json` | Baked from `replay/` + `stops.csv` by `build/build_replay.py`; identical numbers to `GET /api/replay` | build artifact |

MTA open data is published under the MTA's open-data terms; no account or API key is required for either the static schedule or the realtime feeds.

Base map tiles are fetched by the browser from OpenStreetMap and are not vendored;
attribution is rendered on the map and in the page footer, per the
[OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

Regenerate the first two with `python scripts/build_stops.py`, the frontend data
files with `python build/build_basemap.py <google_transit.zip>` and
`python build/build_replay.py`.
