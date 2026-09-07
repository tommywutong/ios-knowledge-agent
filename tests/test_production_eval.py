from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_production_eval.py"
SPEC = importlib.util.spec_from_file_location("production_eval", SCRIPT)
assert SPEC and SPEC.loader
production_eval = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = production_eval
SPEC.loader.exec_module(production_eval)


class ProductionEvalTests(unittest.TestCase):
    def test_public_path_matches_the_production_source_format(self):
        self.assertEqual(
            production_eval.public_path(
                "/Users/tommywu/Desktop/26暑期内容/ios-source-learning/new objc4/runtime/objc-os.mm"
            ),
            "26暑期内容/ios-source-learning/new objc4/runtime/objc-os.mm",
        )

    def test_source_match_requires_path_and_overlapping_lines(self):
        item = {
            "expected_source_path": "/Users/tommywu/Obsidian/iOS/topic.md",
            "expected_start_line": 40,
            "expected_end_line": 60,
        }
        self.assertTrue(
            production_eval.source_matches_anchor(
                {"path": "Obsidian/iOS/topic.md", "lines": "55-75"}, item
            )
        )
        self.assertFalse(
            production_eval.source_matches_anchor(
                {"path": "Obsidian/iOS/topic.md", "lines": "61-75"}, item
            )
        )

    def test_reviewed_translation_anchor_is_accepted_only_for_its_manifest_case(self):
        source = {
            "path": "apple-docs-vault/wwdc/zh/wwdc2021/10133-protect-mutable-state-with-swift-actors.md",
            "lines": "149-153",
        }
        item = {
            "id": "pem-000001",
            "expected_source_path": "/not-the-translation.md",
            "expected_start_line": 1,
            "expected_end_line": 2,
        }
        self.assertEqual(
            production_eval.anchor_match_kind(source, item),
            "same WWDC 2021/10133 Chinese translation",
        )
        item["id"] = "pem-unknown"
        self.assertIsNone(production_eval.anchor_match_kind(source, item))

    def test_ndjson_and_citation_parser_ignore_blank_lines(self):
        events = production_eval.parse_ndjson('{"type":"delta"}\n\n{"type":"done"}\n')
        self.assertEqual([event["type"] for event in events], ["delta", "done"])
        self.assertEqual(production_eval.citation_numbers("A[1] B[12]"), [1, 12])

    def test_production_client_identifies_itself(self):
        self.assertEqual(production_eval.USER_AGENT, "ioskb-production-evaluator/1.0")

    def test_no_evidence_stream_keeps_diagnostics_without_answer_text(self):
        item = {"expected_mode": "no_evidence"}
        body = (
            '{"type":"done","mode":"knowledge","answer":"正文 [1]",'
            '"sources":[{"n":1,"sourceType":"note","path":"Obsidian/iOS/topic.md",'
            '"lines":"10-20"}]}\n'
        )
        grade = production_eval.evaluate_response(
            item, 200, "application/x-ndjson", body
        )
        self.assertFalse(grade["automated_pass"])
        self.assertEqual(grade["mode"], "knowledge")
        self.assertEqual(grade["citations"], [1])
        self.assertEqual(grade["sources"][0]["path"], "Obsidian/iOS/topic.md")
        self.assertNotIn("answer", grade)

    def test_live_status_requires_configured_authenticated_unlimited(self):
        production_eval.verify_live_status(
            200, '{"configured":true,"authenticated":true,"unlimited":true}'
        )
        with self.assertRaisesRegex(RuntimeError, "unlimited=False"):
            production_eval.verify_live_status(
                200, '{"configured":true,"authenticated":true,"unlimited":false}'
            )
