import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service_alerts_view import read_service_alerts, SCHEMA, SOURCE

NOW = 1_900_000_000


def fixture():
    return {"schema": SCHEMA, "status": "ok", "generated_ts": NOW - 2, "source_ts": NOW - 10,
            "valid_until_ts": NOW + 290, "source_url": SOURCE, "total_feed_alerts": 1,
            "active_alert_count": 1, "display_truncated": False,
            "alerts": [{"id": "lmm:alert:42", "kind": "service_alert", "routes": ["A"],
                        "header": "Service update", "description": "Synthetic fixture",
                        "description_truncated": False, "active_period": {"start": NOW - 30, "end": NOW + 30},
                        "revision_sha256": "a" * 64}],
            "archive": {"retained_polls": 1, "first_receipt_ts": NOW - 2, "last_receipt_ts": NOW - 2,
                        "retained_revisions": 1, "database_bytes": 40960, "max_database_bytes": 268435456},
            "is_model_prediction": False, "is_incident_ground_truth": False, "note": "Official context only"}


class AlertViewTests(unittest.TestCase):
    def read(self, value, now=NOW):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "summary.json"; path.write_text(json.dumps(value))
            return read_service_alerts(path, now=now)

    def test_fresh_summary_is_preserved_and_private_fields_removed(self):
        value = fixture(); value["raw_path"] = "/private"; value["alerts"][0]["member_ids"] = ["secret"]
        result = self.read(value)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertNotIn("raw_path", json.dumps(result)); self.assertNotIn("member_ids", json.dumps(result))

    def test_source_and_worker_expiry_independently_clear_alerts(self):
        for key, v in [("source_ts", NOW - 601), ("source_ts", NOW + 31),
                       ("generated_ts", NOW - 181), ("generated_ts", NOW + 1),
                       ("valid_until_ts", NOW), ("valid_until_ts", NOW + 1000), ("status", "unavailable")]:
            value = fixture(); value[key] = v
            self.assertEqual(self.read(value)["alerts"], [], key)

    def test_period_expiry_and_future_start_are_filtered(self):
        value = fixture()
        self.assertEqual(self.read(value, NOW + 30)["alerts"], [])
        value["alerts"][0]["active_period"]["start"] = NOW + 1
        self.assertEqual(self.read(value)["alerts"], [])

    def test_duplicate_identity_bad_route_and_false_ground_truth_fail_closed(self):
        value = fixture(); value["alerts"] *= 2; value["active_alert_count"] = 2
        self.assertEqual(self.read(value)["alerts"], [])
        value = fixture(); value["alerts"][0]["routes"] = ["../../secret"]
        self.assertEqual(self.read(value)["alerts"], [])
        value = fixture(); value["is_incident_ground_truth"] = True
        self.assertEqual(self.read(value)["alerts"], [])


if __name__ == "__main__": unittest.main()
