"""Offline source checks, not model training or full service integration."""
import ast
import hashlib
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("deid", "fraud-graph", "mta-scan", "smt-verify")


class HeadMetadata(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.icons = []
        self.meta = {}
        self.feed(html.split("</head>", 1)[0])

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "link" and "icon" in attrs.get("rel", "").split():
            self.icons.append(attrs.get("href"))
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.meta[key] = attrs.get("content", "")


class SourceChecks(unittest.TestCase):
    def test_demo_favicons_resolve_to_the_published_portfolio_asset(self):
        self.assertTrue((ROOT.parent / "public/assets/favicon.svg").is_file())
        for service in SERVICES:
            with self.subTest(service=service):
                head = HeadMetadata((ROOT / service / "static/index.html").read_text())
                self.assertEqual(head.icons, ["/assets/favicon.svg"])

    def test_local_social_images_exist_and_mta_uses_a_text_summary_card(self):
        for service in SERVICES:
            head = HeadMetadata((ROOT / service / "static/index.html").read_text())
            for key in ("og:image", "twitter:image"):
                if key not in head.meta:
                    continue
                url = urlsplit(head.meta[key])
                if url.netloc in ("", "stelioszach.com"):
                    with self.subTest(service=service, metadata=key):
                        self.assertTrue((ROOT.parent / "public" / url.path.lstrip("/")).is_file())
        mta = HeadMetadata((ROOT / "mta-scan/static/index.html").read_text()).meta
        self.assertEqual(mta.get("twitter:card"), "summary")
        for key in ("og:image", "og:image:width", "og:image:height", "twitter:image"):
            self.assertNotIn(key, mta)

    def test_runtime_python_parses(self):
        count = 0
        for service in (*SERVICES, "service-tests"):
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
