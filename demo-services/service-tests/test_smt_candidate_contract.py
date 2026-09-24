"""Actual local SMT ASGI contract; synthetic cases, no provider or live calls.

Run in a separate service environment so another CEGVR checkout cannot satisfy
the imports and hide a stale vendored verifier.
"""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


BASE = Path(__file__).resolve().parents[1]
ADAPTER = BASE / "smt-verify"
VENDOR = (ADAPTER / "vendor").resolve()
for name, module in list(sys.modules.items()):
    if name == "cegvr" or name.startswith("cegvr."):
        source = getattr(module, "__file__", None)
        if source and VENDOR not in Path(source).resolve().parents:
            raise RuntimeError("Run SMT adapter contracts in an isolated process")
sys.path.insert(0, str(ADAPTER))
spec = importlib.util.spec_from_file_location("smt_contract_adapter", ADAPTER / "service.py")
service = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = service
spec.loader.exec_module(service)

from cegvr.candidate import types as candidate_types  # noqa: E402
from cegvr.candidate import verifier as candidate_verifier  # noqa: E402


def integer_problem():
    return {
        "variables": [
            {"name": "x", "domain": "int", "bounds": {"lower": 0, "upper": 3}},
            {"name": "y", "domain": "int", "bounds": {"lower": 0, "upper": 3}},
        ],
        "constraints": [{"constraint_id": "c1", "kind": "linear_ineq",
            "terms": [{"variable": "x", "coefficient": 1}, {"variable": "y", "coefficient": 1}],
            "relation": "=", "rhs": 2, "offset": 0}],
    }


def boolean_problem(value=True):
    return {"variables": [{"name": "flag", "domain": "bool"}],
        "constraints": [{"constraint_id": "c1", "kind": "bool_atom", "variable": "flag", "value": value}]}


class SMTCandidateContractTests(unittest.TestCase):
    def setUp(self):
        self.context = TestClient(service.app)
        self.client = self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def verify(self, problem, assignment):
        return self.client.post("/api/verify", json={**problem, "candidate": {"status": "sat", "assignment": assignment}})

    def test_actual_adapter_imports_only_its_vendor(self):
        for module in (candidate_types, candidate_verifier):
            self.assertIn(VENDOR, Path(module.__file__).resolve().parents)

    def test_missing_referenced_variable_returns_domain_rejection_without_solver(self):
        with patch.object(candidate_verifier, "_build_problem_solver", side_effect=AssertionError("solver must not run")):
            response = self.verify(integer_problem(), {"x": 1})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["verified_outcome"], "REJECTED_DOMAIN")
        self.assertEqual(payload["verifier_result"], "precheck")
        self.assertEqual(payload["solver_time_ms"], 0)
        self.assertIn("missing variable 'y'", payload["diagnostics"]["precheck_errors"])

    def test_string_and_float_assignments_are_not_silently_coerced(self):
        for value in ("1", 1.0, 1.5, "true"):
            with self.subTest(value=value):
                response = self.verify(integer_problem(), {"x": value, "y": 1})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("malformed candidate", response.json()["detail"])

    def test_boolean_strings_are_not_silently_coerced(self):
        for value in ("true", "false", "1", "0"):
            with self.subTest(value=value):
                response = self.verify(boolean_problem(), {"flag": value})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("malformed candidate", response.json()["detail"])

    def test_boolean_is_not_an_integer_domain_assignment(self):
        for value in (True, False):
            with self.subTest(value=value), patch.object(candidate_verifier, "_build_problem_solver", side_effect=AssertionError("solver must not run")):
                response = self.verify(integer_problem(), {"x": value, "y": 1})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["verified_outcome"], "REJECTED_DOMAIN")

    def test_integer_is_not_a_boolean_domain_assignment(self):
        for value in (0, 1):
            with self.subTest(value=value), patch.object(candidate_verifier, "_build_problem_solver", side_effect=AssertionError("solver must not run")):
                response = self.verify(boolean_problem(), {"flag": value})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["verified_outcome"], "REJECTED_DOMAIN")

    def test_native_boolean_assignments_remain_supported(self):
        for value in (True, False):
            with self.subTest(value=value):
                response = self.verify(boolean_problem(value), {"flag": value})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["verified_outcome"], "CERTIFIED_SAT")
                self.assertIs(response.json()["certified_assignment"]["flag"], value)

    def test_extra_variables_and_bounds_reject_before_solver(self):
        for assignment in ({"x": 1, "y": 1, "extra": 0}, {"x": 99, "y": 1}):
            with self.subTest(assignment=assignment), patch.object(candidate_verifier, "_build_problem_solver", side_effect=AssertionError("solver must not run")):
                response = self.verify(integer_problem(), assignment)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["verified_outcome"], "REJECTED_DOMAIN")

    def test_all_published_examples_keep_actual_sat_unsat_outcomes(self):
        for example in service.EXAMPLES:
            with self.subTest(example=example["id"]):
                body = copy.deepcopy(example["problem"])
                body["candidate"] = example["candidate"]
                response = self.client.post("/api/verify", json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["verified_outcome"], example["expect"])


if __name__ == "__main__":
    unittest.main()
