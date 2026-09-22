"""Offline source checks, not model training or full service integration."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("deid", "fraud-graph", "mta-scan", "smt-verify")


class SourceChecks(unittest.TestCase):
    def test_runtime_python_parses(self):
        count = 0
        for service in SERVICES:
            for path in (ROOT / service).rglob("*.py"):
                if any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(ROOT).parts):
                    continue
                with self.subTest(file=str(path.relative_to(ROOT))):
                    ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
                    count += 1
        self.assertGreater(count, 20)

    def test_published_json_is_parseable(self):
        count = 0
        for service in SERVICES:
            for folder in [ROOT / service / "data", ROOT / service / "static" / "data"]:
                if not folder.exists():
                    continue
                for path in folder.rglob("*.json"):
                    with self.subTest(file=str(path.relative_to(ROOT))):
                        json.loads(path.read_text(encoding="utf-8"))
                        count += 1
        self.assertGreater(count, 5)

    def test_bundled_synthetic_checkpoint_matches_reviewed_bytes(self):
        model = (ROOT / "fraud-graph/artifacts/models/edge_model.pt").read_bytes()
        self.assertEqual(len(model), 8806)
        self.assertEqual(hashlib.sha256(model).hexdigest(), "3ba36ca9c297d3756bc5f03277e473260c475b2572705e7b59c3f2eef473ae89")


if __name__ == "__main__":
    unittest.main()
