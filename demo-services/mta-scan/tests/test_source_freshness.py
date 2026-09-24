"""Offline API contracts: fresh feed data need not contain a new train pair."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import Response
import service
from mtascan.collector import Collector, CycleResult, FeedStatus
from mtascan.config import Settings
from mtascan.scoring import new_bundle
from mtascan.store import Store


NOW = 1_800_000_000


class SourceFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(state_dir=Path(self.tmp.name), collector_enabled=True)
        self.store = Store(Path(self.tmp.name) / "mta.db")
        self.collector = Collector(settings=self.settings, store=self.store, bundle=new_bundle())
        self.patches = [patch.object(service, "SETTINGS", self.settings), patch.object(service, "_collector", self.collector),
                        patch.object(service, "_store", self.store), patch.object(service, "_now", return_value=NOW),
                        patch.object(service, "load_stops", return_value=({}, None)), patch.object(service, "load_routes", return_value={})]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.store.close()
        self.tmp.cleanup()

    def observation(self, age):
        self.store.insert_observations([{
            "observed_ts": NOW - age, "event_ts": NOW + 120, "route_id": "A", "stop_id": "A01N",
            "headway_sec": 300, "predicted_headway_sec": 300, "residual": 0, "anomaly_score": 0.1, "reasons": [],
        }])

    def cycle(self, source_age, *, ok=True, cycle_age=5):
        self.collector.cycles = 5
        self.collector.last_cycle = CycleResult(started_epoch=NOW - cycle_age, duration_ms=1, feeds=[
            FeedStatus("ACE", ok=ok, source_epoch=NOW - source_age, source_age_sec=source_age,
                       last_success_epoch=NOW - cycle_age if ok else NOW - 600),
        ])

    def states(self):
        return service.state(Response(), window="30m", route_id="All", top=25), service.summary(Response(), window="30m")

    def test_fresh_unchanged_pair_is_live_with_old_observation_age(self):
        self.observation(600)
        self.cycle(30)
        state, summary = self.states()
        self.assertEqual(state["live"]["state"], "live")
        self.assertEqual(summary["live_state"], "live")
        self.assertEqual(state["live"]["last_observed_age_sec"], 600)
        self.assertEqual(state["live"]["observation_state"], "older")
        self.assertIn("no new", state["live"]["note"].lower())

    def test_recent_stored_row_does_not_make_old_source_live(self):
        self.observation(10)
        self.cycle(301)
        state, summary = self.states()
        self.assertEqual(state["live"]["state"], "stale")
        self.assertEqual(summary["live_state"], "stale")
        self.assertEqual(state["live"]["feeds_ok"], 0)
        self.assertEqual(state["live"]["last_observed_age_sec"], 10)

    def test_failed_current_poll_does_not_reuse_previous_success(self):
        self.observation(10)
        self.cycle(30, ok=False)
        state, _ = self.states()
        self.assertEqual(state["live"]["state"], "stale")

    def test_stopped_collector_ages_out_even_with_once_successful_feed(self):
        self.observation(10)
        self.cycle(30, cycle_age=301)
        state, _ = self.states()
        self.assertEqual(state["live"]["state"], "stale")

    def test_fresh_sources_without_new_pair_remain_live(self):
        self.cycle(30)
        state, summary = self.states()
        self.assertEqual(state["live"]["state"], "live")
        self.assertEqual(state["live"]["observation_state"], "none")
        self.assertEqual(summary["live_state"], "live")
        self.assertIn("two distinct", state["live"]["note"])

    def test_no_first_cycle_is_warming_up(self):
        state, _ = self.states()
        self.assertEqual(state["live"]["state"], "warming_up")

    def test_deep_health_uses_current_source_age(self):
        self.cycle(301)
        result = service.health_deep()
        self.assertFalse(result["checks"]["feeds"]["ok"])
        self.assertEqual(result["checks"]["feeds"]["state"], "stale")
        self.assertEqual(result["checks"]["feeds"]["feeds_ok"], 0)

    def test_partial_fresh_feeds_keep_state_live_but_explain_coverage(self):
        self.cycle(30)
        self.collector.last_cycle.feeds.append(FeedStatus("G", ok=False))
        state, _ = self.states()
        self.assertEqual(state["live"]["state"], "live")
        self.assertEqual(state["live"]["feeds_ok"], 1)
        self.assertEqual(state["live"]["feeds_total"], 2)
        self.assertIn("1/2", state["live"]["note"])

    def test_future_source_is_excluded_even_if_poll_previously_succeeded(self):
        self.cycle(-61)
        state, _ = self.states()
        self.assertEqual(state["live"]["state"], "stale")

    def test_paused_collection_never_claims_live(self):
        self.cycle(30)
        with patch.object(service, "SETTINGS", Settings(state_dir=Path(self.tmp.name), collector_enabled=False)):
            state, _ = self.states()
        self.assertEqual(state["live"]["state"], "paused")


if __name__ == "__main__":
    unittest.main()
