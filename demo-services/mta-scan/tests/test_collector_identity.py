"""Offline GTFS fixtures: ETA revisions are not observed train passages."""
import sys
import tempfile
import unittest
import httpx
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google.transit import gtfs_realtime_pb2 as gtfs
from mtascan.collector import Collector, parse_arrivals
from mtascan.config import Settings
from mtascan.scoring import new_bundle
from mtascan.store import Store

NOW = 1_800_000_000


def payload(trips, *, timestamp=NOW):
    feed = gtfs.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = timestamp
    for i, (trip_id, eta, direction) in enumerate(trips):
        entity = feed.entity.add(id=str(i))
        trip = entity.trip_update.trip
        trip.route_id = "A"
        trip.trip_id = trip_id
        trip.start_date = "20270115"
        trip.direction_id = direction
        update = entity.trip_update.stop_time_update.add(stop_id="A01N")
        update.arrival.time = eta
    return feed.SerializeToString()


class CollectorIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "mta.db")
        self.collector = Collector(settings=Settings(state_dir=Path(self.tmp.name)), store=self.store, bundle=new_bundle())
        self.scorer = patch("mtascan.collector.score_feature_row", return_value={
            "predicted_headway_sec": 200, "anomaly_score": 0.1, "reasons": []
        })
        self.scorer.start()

    def tearDown(self):
        self.scorer.stop()
        self.store.close()
        self.tmp.cleanup()

    def rows(self, trips, now=NOW):
        return self.collector._extract_and_score(list(parse_arrivals(payload(trips))), now)

    def test_same_trip_eta_revision_never_becomes_headway(self):
        self.assertEqual(self.rows([("one", NOW + 120, 0)]), [])
        self.assertEqual(self.rows([("one", NOW + 360, 0)], NOW + 30), [])

    def test_two_distinct_trips_produce_one_prediction_gap(self):
        rows = self.rows([("one", NOW + 120, 0), ("two", NOW + 420, 0)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["headway_sec"], 300)
        self.assertEqual(self.rows([("one", NOW + 180, 0), ("two", NOW + 540, 0)], NOW + 30), [])

    def test_directions_and_missing_trip_identity_cannot_form_pair(self):
        self.assertEqual(self.rows([("one", NOW + 120, 0), ("two", NOW + 420, 1)]), [])
        self.assertEqual(self.rows([("", NOW + 120, 0), ("", NOW + 420, 0)]), [])

    def test_duplicate_entity_is_not_second_train(self):
        self.assertEqual(self.rows([("one", NOW + 120, 0), ("one", NOW + 420, 0)]), [])

    def test_vehicle_position_timestamp_is_not_arrival(self):
        feed = gtfs.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        vehicle = feed.entity.add(id="vehicle").vehicle
        vehicle.trip.route_id = "A"
        vehicle.trip.trip_id = "one"
        vehicle.stop_id = "A01N"
        vehicle.timestamp = NOW
        self.assertEqual(list(parse_arrivals(feed.SerializeToString())), [])

    def test_stale_or_future_feed_is_not_reported_as_success(self):
        for timestamp in (NOW - 301, NOW + 61, 0):
            data = payload([("one", NOW + 120, 0), ("two", NOW + 420, 0)], timestamp=timestamp)
            with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=data))) as client:
                sink = []
                with patch("mtascan.collector.time.time", return_value=NOW):
                    status = self.collector._fetch_feed(client, "A", "https://example.test/feed", sink)
                self.assertFalse(status.ok)
                self.assertEqual(sink, [])

    def test_fresh_feed_exposes_source_age(self):
        data = payload([("one", NOW + 120, 0)], timestamp=NOW - 30)
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=data))) as client:
            with patch("mtascan.collector.time.time", return_value=NOW):
                status = self.collector._fetch_feed(client, "A", "https://example.test/feed", [])
        self.assertTrue(status.ok)
        self.assertEqual(status.source_age_sec, 30)

    def test_cancelled_skipped_and_unknown_updates_are_excluded(self):
        for relationship in (3, 7):
            feed = gtfs.FeedMessage.FromString(payload([("one", NOW + 120, 0)]))
            feed.entity[0].trip_update.trip.schedule_relationship = relationship
            self.assertEqual(list(parse_arrivals(feed.SerializeToString())), [])
        for relationship in (1, 2):
            feed = gtfs.FeedMessage.FromString(payload([("one", NOW + 120, 0)]))
            feed.entity[0].trip_update.stop_time_update[0].schedule_relationship = relationship
            self.assertEqual(list(parse_arrivals(feed.SerializeToString())), [])

    def test_reversed_pair_is_not_relearned_after_eta_reordering(self):
        self.assertEqual(len(self.rows([("one", NOW + 120, 0), ("two", NOW + 420, 0)])), 1)
        self.assertEqual(self.rows([("two", NOW + 180, 0), ("one", NOW + 540, 0)]), [])

    def test_previous_measurements_and_checkpoint_have_separate_namespace(self):
        settings = self.collector.settings
        self.assertEqual(settings.db_path.name, "mta-arrival-gaps-v2.db")
        self.assertEqual(settings.model_path.name, "model-arrival-gaps-v2.pkl")


if __name__ == "__main__":
    unittest.main()
