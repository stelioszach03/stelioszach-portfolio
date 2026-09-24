import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from temporal_view import read_summary

NOW = 2_000_000_000


def fixture():
    return {'schema': 'mta-temporal-evaluation-v1', 'generated_ts': NOW - 2,
            'target_name': 'future feed-predicted arrival-spacing proxy',
            'feature_cutoff_ts': NOW - 100, 'evaluation_cutoff_ts': NOW - 1000,
            'valid_until_ts': NOW + 500, 'readiness': {'status': 'ready', 'public_forecasts_ready': True, 'reasons': []},
            'coverage': {'first_window_ts': NOW - 15*86400, 'last_window_ts': NOW - 100, 'span_seconds': 15*86400,
                         'retained_windows': 4000, 'expected_window_slots': 4320, 'complete_fresh_window_fraction': .95, 'stable_groups_evaluated': 8},
            'forecasts': [{'route_id': 'A', 'direction': 'platform:N', 'horizon_seconds': 900, 'origin_ts': NOW - 100,
                           'target_ts': NOW + 800, 'predicted_proxy_seconds': 180.0, 'algorithm': 'persistence',
                           'cohort_sha256': 'a'*64, 'paired_platform_count': 3, 'cohort_coverage_fraction': 1.0,
                           'validation_mae_seconds': 20.0, 'heldout_test_mae_seconds': 30.0}]}


class TemporalViewTests(unittest.TestCase):
    def read(self, value, now=NOW):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'summary.json'
            path.write_text(json.dumps(value))
            return read_summary(path, now=now)

    def test_ready_summary_preserves_measured_prediction(self):
        result = self.read(fixture())
        self.assertTrue(result['readiness']['public_forecasts_ready'])
        self.assertEqual(result['forecasts'][0]['predicted_proxy_seconds'], 180)
        self.assertFalse(result['is_observed_train_headway'])

    def test_expired_snapshot_never_keeps_forecasts(self):
        result = self.read(fixture(), now=NOW+1000)
        self.assertEqual(result['forecasts'], [])
        self.assertFalse(result['readiness']['public_forecasts_ready'])

    def test_ready_flag_is_insufficient_without_coverage_and_expiration(self):
        for field, val in [('valid_until_ts', NOW-1), ('feature_cutoff_ts', NOW-800), ('coverage', None)]:
            sample = fixture(); sample[field] = val
            self.assertEqual(self.read(sample)['forecasts'], [], field)
        sample = fixture(); sample['coverage']['span_seconds'] = 86400
        self.assertEqual(self.read(sample)['forecasts'], [])

    def test_forecast_time_and_origin_contract(self):
        for field, value in [('origin_ts', NOW+10), ('target_ts', NOW-5), ('target_ts', NOW+700)]:
            sample = fixture(); sample['forecasts'][0][field] = value
            self.assertEqual(self.read(sample)['forecasts'], [])

    def test_future_generated_and_features_rejected(self):
        for field in ['generated_ts', 'feature_cutoff_ts', 'evaluation_cutoff_ts']:
            sample = fixture(); sample[field] = NOW+100
            self.assertEqual(self.read(sample)['forecasts'], [])

    def test_private_unknown_fields_stripped_recursively(self):
        sample = fixture(); sample['database_path'] = '/private'; sample['coverage']['private_ids'] = ['secret']
        sample['forecasts'][0]['raw_image'] = 'private'
        encoded = json.dumps(self.read(sample))
        for word in ['database_path', 'private_ids', 'raw_image']:
            self.assertNotIn(word, encoded)

    def test_invalid_schema_nonfinite_and_bad_artifact_fail_closed(self):
        for field, value in [('schema', 'v999'), ('artifact_id', '../../private'), ('generated_ts', float('nan'))]:
            sample = fixture(); sample[field] = value
            self.assertEqual(self.read(sample)['forecasts'], [])

    def test_collecting_status_cannot_publish_hidden_forecast(self):
        sample = fixture(); sample['readiness']['status'] = 'collecting'
        self.assertEqual(self.read(sample)['forecasts'], [])

    def test_error_summary_safe_and_paths_not_exposed(self):
        sample = {'schema':'mta-temporal-evaluation-v1','generated_ts':NOW,'target_name':'future feed-predicted arrival-spacing proxy',
                  'readiness':{'status':'error','public_forecasts_ready':False,'reasons':['Worker unavailable']}, 'error_category':'OSError', 'exception':'/private/database'}
        result = self.read(sample)
        self.assertEqual(result['readiness']['status'], 'error')
        self.assertNotIn('exception', result)
        self.assertEqual(result['metrics'], [])

    def test_missing_oversized_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'summary.json'
            self.assertEqual(read_summary(path)['forecasts'], [])
            for content in ['x'*(256*1024+1), '{bad']:
                path.write_text(content)
                self.assertEqual(read_summary(path)['forecasts'], [])


if __name__ == '__main__': unittest.main()
