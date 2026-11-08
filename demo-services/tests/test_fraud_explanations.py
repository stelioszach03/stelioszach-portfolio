"""Regression for explanations that overstated ordinary graph features."""
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "fraud-graph/vendor/app/services/explain.py"
spec = importlib.util.spec_from_file_location("fraud_explain", source)
explain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(explain)


class FraudExplanationTests(unittest.TestCase):
    def test_small_ach_payment_does_not_claim_high_risk_or_above_baseline(self):
        # Reproduced with a $1 synthetic ACH payment. Normalization makes this
        # amount feature positive despite a negative underlying z-score.
        features = {"is_new_pair": 1.0, "channel_risk": .35, "amount_z": .0974}
        weighted = [("is_new_pair", .5), ("channel_risk", .1925), ("amount_z", .08766)]
        reasons = explain.reasons_from_contributions(weighted, features)
        self.assertEqual(reasons[0], "First-time relationship between sender and receiver")
        self.assertIn("Channel heuristic prior: 0.350", reasons)
        self.assertIn("Normalized amount-deviation feature: 0.097", reasons)
        self.assertNotIn("far above", " ".join(reasons))
        self.assertNotIn("High-risk", " ".join(reasons))

    def test_empty_or_nonpositive_features_do_not_invent_an_explanation(self):
        reasons = explain.reasons_from_contributions(
            [("amount_z", 0), ("is_new_pair", 0), ("channel_risk", -.2)],
            {"amount_z": 0, "is_new_pair": 0, "channel_risk": .35},
        )
        self.assertEqual(reasons, ["No positive named heuristic features in this snapshot"])

    def test_graph_structure_does_not_assert_fraud_or_actual_account_age(self):
        reasons = explain.reasons_from_contributions(
            [("has_reverse_edge", .7), ("sender_new_account", .3)],
            {"has_reverse_edge": 1, "sender_new_account": 1},
        )
        self.assertIn("A reverse payment edge exists in the observed graph", reasons)
        self.assertIn("Sender has less than one hour of observed graph history", reasons)
        self.assertNotIn("circular", " ".join(reasons))


if __name__ == "__main__":
    unittest.main()
