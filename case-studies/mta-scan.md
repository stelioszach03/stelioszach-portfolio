# MTA-Scan — streaming data, model evaluation and service context

[Live workspace](https://stelioszach.com/demos/mta-scan/) · [Deployed API and interface](../demo-services/mta-scan) · [Collection and evaluation workers](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection)

## Problem and delivery

A useful live transit ML interface must distinguish fresh source data, model outputs, official service messages and missing information. It must also keep collecting and serving within a fixed CPU and disk budget.

I built the GTFS-Realtime ingestion workers, FastAPI service, native Mapbox workspace, snapshot export, bounded historical archive and autonomous temporal evaluation. An independent collector now preserves official subway service alerts and their revisions; the UI filters the currently active messages by route. The website does not turn a request into a training job or an upstream data fetch.

## Engineering decisions

| Decision | Why it matters |
| --- | --- |
| Record response-availability timestamps and source timestamps separately | A response that finishes after a forecast decision cannot leak into that earlier feature window. |
| Preserve raw snapshots, hashes, failed polls and immutable completed-day exports | Later analysis can inspect provenance and actual coverage, including missing or stale data. |
| Choose fixed platform cohorts on training data and use chronological splits with a 30-minute purge | Comparisons use consistent targets and separate fitting, selection and held-out evaluation. |
| Compare persistence, seasonal and incremental linear models; select on validation only | Additional model complexity must earn promotion, and the held-out set does not choose the model. |
| Run offline workers independently of the public API | The live interface stays responsive while collection and evaluation follow resource limits. |
| Publish only bounded, allowlisted summaries through read-only mounts | The web process cannot access raw archives or initiate model computation. |
| Restore baseline windows from bounded retained observations at startup | Restarts recover up to 100,000 recent rows / 8,192 keys, with 24 values per key, without retraining or rewriting stored scores. |
| Enforce freshness and expiry in the worker, API and browser | A fresh status wrapper cannot revive a model evaluation older than six hours. |
| Archive official service messages independently | Official alerts provide context and prospective weak-label material without being confused with anomaly scores or invented ground truth. |

## Measured evidence

The [November 7 coverage audit](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection/blob/main/docs/COLLECTION_COVERAGE.md) verified 44/44 daily exports against their hashes and row counts. The rolling evaluation covered 28 days, 8,060 five-minute windows and 45 stable route/direction groups, with 99.44% complete/fresh windows at that snapshot.

Held-out aggregate MAE was 146.33 seconds for persistence versus 198.18 seconds for the linear model at 15 minutes, and 166.04 versus 227.40 seconds at 30 minutes. The validation-selected pipeline stayed close to persistence. Keeping this negative comparison visible is part of the system's model-selection discipline.

The alert collector's first deployment received 213 official messages, of which 31 had active periods at that receipt. Those are a dated operational check, not a performance score. The [alert collection protocol](https://github.com/stelioszach03/NYC-Subway-Anomaly-Detection/blob/main/docs/SERVICE_ALERTS.md) records its retention, timing, validation and deployment contract.

## Validation and operation

Offline checks cover duplicate trip identities, source freshness, temporal leakage, fixed-cohort comparison, immutable exports, recovery, archive retention and API validation. New alert checks exercise raw snapshot recovery, revision deduplication, failed/malformed/oversized responses, future planned work, source and browser expiry, text escaping, route filtering and preserved expansion state. A second regression reproduced loss of station baselines after restart; bounded history recovery now seeds those windows without replaying model training. A regression first reproduced publication of forecasts from an evaluation older than six hours; the API and browser now reject that condition.

Deployment uses supervised Linux services, independent storage namespaces, constrained memory/CPU, atomic summary publication and a recoverable backup of changed demo files. API health and actual scheduled collection are checked after deployment.

## Scope

The forecast target is a future feed-predicted arrival-spacing proxy, not realized train headway or passenger wait time. Official service messages may be delayed, revised or spatially broad. Incident-level accuracy needs a frozen label/matching protocol and prospective held-out observations; the new alert archive does not invent prior history. The separate constructed replay remains explicitly labelled. This is a deployed engineering prototype, not an MTA-endorsed operational service or uptime guarantee.
