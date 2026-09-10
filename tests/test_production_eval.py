from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
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

    def test_gate_blocks_stale_anchor_and_missing_follow_up_fixture(self):
        selected = [
            {
                "id": "pem-stale",
                "expected_mode": "knowledge",
                "expected_source_path": "/does/not/exist.m",
                "category": "answerable",
            },
            {
                "id": "pem-follow-up",
                "expected_mode": "knowledge",
                "expected_source_path": None,
                "category": "follow_up",
            },
        ]
        reviewed = {"follow_up_seeds": {}}
        blockers = production_eval.gate_blockers(selected, reviewed, None)
        self.assertEqual(
            {blocker["id"] for blocker in blockers},
            {"pem-stale", "pem-follow-up"},
        )
        self.assertTrue(any("local index" in blocker["reason"] for blocker in blockers))

    def test_gate_blocks_any_live_case_that_did_not_pass(self):
        selected = [{"id": "pem-ok", "expected_mode": "no_evidence"}]
        reviewed = {"follow_up_seeds": {}}
        blockers = production_eval.gate_blockers(
            selected,
            reviewed,
            [{"id": "pem-ok", "outcome": "failed", "reason": "wrong mode"}],
        )
        self.assertEqual(blockers, [{"id": "pem-ok", "reason": "wrong mode"}])

    def test_gate_blocks_cases_that_still_require_manual_review(self):
        selected = [{"id": "pem-manual", "expected_mode": "no_evidence"}]
        reviewed = {
            "follow_up_seeds": {},
            "contracts": {
                "pem-manual": {
                    "manual_review_required": True,
                    "manual_review_reason": "platform boundary requires review",
                }
            },
        }
        blockers = production_eval.gate_blockers(selected, reviewed, None)
        self.assertEqual(
            blockers,
            [
                {
                    "id": "pem-manual",
                    "reason": "manual review remains required: platform boundary requires review",
                }
            ],
        )

    def test_report_exposes_gate_status_without_answer_text(self):
        selected = [{"id": "pem-ok"}]
        reviewed = {"follow_up_seeds": {}}
        report = production_eval.make_report(
            selected,
            reviewed,
            "https://example.test",
            False,
            gate_enabled=True,
            gate_blockers_list=[],
        )
        self.assertEqual(report["gate"], {"enabled": True, "passed": True, "blockers": []})

    def test_aggregate_metrics_reports_no_evidence_and_citation_rates(self):
        selected = [
            {"id": "pem-ne", "expected_mode": "no_evidence"},
            {"id": "pem-knowledge", "expected_mode": "knowledge"},
            {"id": "pem-general", "expected_mode": "general"},
        ]
        results = [
            {
                "id": "pem-ne",
                "outcome": "passed",
                "grade": {
                    "response_status": 422,
                    "mode": None,
                    "response_classification": "no_evidence",
                    "valid_citation_count": 0,
                    "anchor_citation_pass": None,
                },
            },
            {
                "id": "pem-knowledge",
                "outcome": "passed",
                "grade": {
                    "response_status": 200,
                    "mode": "knowledge",
                    "valid_citation_count": 2,
                    "anchor_citation_pass": False,
                },
            },
            {
                "id": "pem-general",
                "outcome": "failed",
                "grade": {
                    "response_status": 422,
                    "mode": None,
                    "response_classification": "no_evidence",
                    "valid_citation_count": 0,
                    "anchor_citation_pass": None,
                },
            },
        ]
        metrics = production_eval.aggregate_metrics(selected, results)
        self.assertEqual(metrics["evaluated_count"], 3)
        self.assertEqual(
            metrics["no_evidence"],
            {
                "true_positive": 1,
                "false_positive": 1,
                "true_negative": 1,
                "false_negative": 0,
                "precision": 0.5,
                "recall": 1.0,
                "accuracy": 0.6667,
            },
        )
        self.assertEqual(metrics["valid_citation_coverage"], 1.0)
        self.assertEqual(metrics["expected_anchor_coverage"], 0.0)
        self.assertEqual(
            metrics["failure_causes"], {"general_expected_but_no_evidence": 1}
        )

    def test_evaluation_grade_records_valid_and_invalid_citations(self):
        item = {
            "expected_mode": "knowledge",
            "expected_source_path": "/Users/tommywu/Obsidian/iOS/topic.md",
            "expected_start_line": 10,
            "expected_end_line": 20,
        }
        body = (
            '{"type":"done","mode":"knowledge","answer":"A [1] [9]",'
            '"sources":[{"n":1,"sourceType":"note",'
            '"path":"Obsidian/iOS/topic.md","lines":"10-20"}]}'
        )
        grade = production_eval.evaluate_response(
            item, 200, "application/x-ndjson", body
        )
        self.assertEqual(grade["valid_citation_count"], 1)
        self.assertEqual(grade["invalid_citation_count"], 1)
        self.assertEqual(grade["response_classification"], "knowledge")

    def test_historical_report_citation_counts_are_recomputed_from_redacted_fields(self):
        self.assertEqual(
            production_eval.valid_citation_count(
                {"citations": [1, 3, 9], "sources": [{}, {}, {}]}
            ),
            2,
        )

    def test_offline_summary_rejects_release_gate(self):
        argv = [
            "run_production_eval.py",
            "--gate",
            "--summarize-report",
            "data/evaluation-results/production-eval-key-cases-20260907.json",
        ]
        with patch.object(sys, "argv", argv):
            self.assertEqual(production_eval.main(), 1)

    def test_live_gate_skips_network_when_preflight_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            argv = [
                "run_production_eval.py",
                "--live",
                "--gate",
                "--case",
                "pem-000028",
                "--report",
                str(report_path),
            ]
            with patch.object(sys, "argv", argv), patch.object(
                production_eval,
                "read_self_test_token",
                side_effect=AssertionError("network must not be reached"),
            ):
                self.assertEqual(production_eval.main(), 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["live_attempted"])
            self.assertFalse(report["gate"]["passed"])
