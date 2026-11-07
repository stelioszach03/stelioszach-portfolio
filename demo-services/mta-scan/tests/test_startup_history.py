import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mtascan.collector import Collector
from mtascan.config import Settings
from mtascan.features import FeatureEngine
from mtascan.scoring import new_bundle
from mtascan.store import Store

NOW = 1_900_000_000


class StartupHistoryTests(unittest.TestCase):
    def test_restart_restores_baseline_without_retraining_or_rewriting_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'history.sqlite3')
            try:
                rows = [{'route_id': 'A', 'stop_id': 'A01N', 'observed_ts': NOW-30+i,
                         'headway_sec': gap} for i, gap in enumerate([100, 110, 90])]
                store.insert_observations(rows)
                bundle = new_bundle()
                with patch('mtascan.collector.time.time', return_value=NOW):
                    collector = Collector(settings=Settings(state_dir=Path(folder)), store=store, bundle=bundle)
                self.assertEqual(collector.features.history_stats()['ready'], 1)
                expected = FeatureEngine()
                for row in rows: expected.compute(**row)
                actual_features = collector.features.compute(route_id='A', stop_id='A01N', observed_ts=NOW,
                                                               headway_sec=120, learn=False)
                expected_features = expected.compute(route_id='A', stop_id='A01N', observed_ts=NOW,
                                                     headway_sec=120, learn=False)
                for key in ['lag_headway_1', 'rolling_mean_6', 'station_median_24', 'station_mad_24']:
                    self.assertEqual(actual_features[key], expected_features[key], key)
                self.assertEqual(bundle.telemetry.rows_seen, 0)
                self.assertEqual(store.count(), 3)
            finally:
                store.close()

    def test_history_read_excludes_future_and_old_rows_and_obeys_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'history.sqlite3')
            try:
                store.insert_observations([{'route_id': 'A', 'stop_id': 'A01N', 'observed_ts': t,
                                            'headway_sec': 120} for t in [NOW-1000, NOW-3, NOW-2, NOW-1, NOW+10]])
                rows = store.baseline_history(since_epoch=NOW-100, before_epoch=NOW, limit=2)
                self.assertEqual([r['observed_ts'] for r in rows], [NOW-1, NOW-2])
                self.assertEqual(store.count(), 5)
            finally:
                store.close()

    def test_recovery_is_bounded_and_never_introduces_future_or_invalid_values(self):
        engine = FeatureEngine()
        records = [{'route_id': 'A', 'stop_id': 'A01N', 'observed_ts': NOW-i, 'headway_sec': 100+i}
                   for i in range(40)]
        records.insert(0, {'route_id': 'A', 'stop_id': 'A01N', 'observed_ts': NOW+10, 'headway_sec': 999})
        records.append({'route_id': 'bad', 'stop_id': 'bad', 'observed_ts': NOW-200000, 'headway_sec': 100})
        result = engine.restore_history(records, now_epoch=NOW)
        self.assertEqual(result['retained_values'], 24)
        self.assertEqual(engine.active_keys(), 1)
        self.assertEqual(engine.compute(route_id='A', stop_id='A01N', observed_ts=NOW+1,
                                        headway_sec=100, learn=False)['lag_headway_1'], 100)
        with self.assertRaises(ValueError):
            engine.restore_history(records, now_epoch=NOW)

    def test_most_recent_keys_win_the_recovery_budget(self):
        engine = FeatureEngine()
        records = [{'route_id': 'A', 'stop_id': str(i), 'observed_ts': NOW-i, 'headway_sec': 100}
                   for i in range(9000)]
        result = engine.restore_history(records, now_epoch=NOW)
        self.assertEqual(result['keys'], 8192)
        self.assertEqual(engine.active_keys(), 8192)
