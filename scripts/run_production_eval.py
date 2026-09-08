#!/usr/bin/env python3
"""Run the reviewed GLM evaluation manifest against the iOS production API.

Without --live this command performs a deterministic preflight only. Live mode
uses the existing production self-test token from the environment or macOS
Keychain and writes a local, ignored report without storing model answers.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_DIR = (
    ROOT / "data/glm/seed-evidence-boundary-and-eval-manifest-20260906"
)
DEFAULT_LEDGER_DIR = ROOT / "data/glm/evidence-ledger-and-grading-spec-20260906"
DEFAULT_BASE_URL = "https://www.tommywutong.cn"
KEYCHAIN_SERVICE = "tommywu-lab-ios-self-test"
USER_AGENT = "ioskb-production-evaluator/1.0"
SOURCE_MARKERS = (
    ("/Desktop/26暑期内容/", "26暑期内容/"),
    ("/Obsidian/iOS/", "Obsidian/iOS/"),
    ("/data/repos/apple-docs-vault/", "apple-docs-vault/"),
    (
        "/data/repos/apple-developer-archive-vault/",
        "apple-developer-archive-vault/",
    ),
)
# A reviewed production source may be a faithful translation of an anchor in
# the offline ledger. Keep this narrow and explicit instead of fuzzy matching.
EQUIVALENT_ANCHORS: dict[str, tuple[dict[str, Any], ...]] = {
    "pem-000001": (
        {
            "expected_source_path": (
                ROOT
                / "data/repos/apple-docs-vault/wwdc/zh/wwdc2021/"
                "10133-protect-mutable-state-with-swift-actors.md"
            ).as_posix(),
            "expected_start_line": 149,
            "expected_end_line": 153,
            "label": "same WWDC 2021/10133 Chinese translation",
        },
    ),
}


@dataclass(frozen=True)
class BatchPaths:
    manifest: Path
    ledger: Path
    contracts: Path
    boundaries: Path
    pairs: Path


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"Missing required input: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{path}:{line_number}: blank JSONL line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON ({exc.msg})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
        rows.append(row)
    return rows


def parse_lines(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str) or not value:
        return None
    pieces = value.split("-", 1)
    try:
        start = int(pieces[0])
        end = int(pieces[-1])
    except ValueError:
        return None
    return (start, end) if start > 0 and end >= start else None


def ranges_overlap(left: tuple[int, int] | None, right: tuple[int, int]) -> bool:
    return left is not None and left[0] <= right[1] and right[0] <= left[1]


def public_path(path: str) -> str:
    for marker, prefix in SOURCE_MARKERS:
        index = path.find(marker)
        if index >= 0:
            return f"{prefix}{path[index + len(marker):]}"
    return path


def source_matches_anchor(source: dict[str, Any], item: dict[str, Any]) -> bool:
    expected_path = item.get("expected_source_path")
    expected_start = item.get("expected_start_line")
    expected_end = item.get("expected_end_line")
    if not isinstance(expected_path, str):
        return False
    if not isinstance(expected_start, int) or not isinstance(expected_end, int):
        return False
    source_path = source.get("path")
    return (
        isinstance(source_path, str)
        and source_path == public_path(expected_path)
        and ranges_overlap(parse_lines(source.get("lines")), (expected_start, expected_end))
    )


def anchor_match_kind(source: dict[str, Any], item: dict[str, Any]) -> str | None:
    if source_matches_anchor(source, item):
        return "primary"
    for alternate in EQUIVALENT_ANCHORS.get(str(item.get("id")), ()):
        if source_matches_anchor(source, alternate):
            return str(alternate["label"])
    return None


def citation_numbers(answer: str) -> list[int]:
    import re

    return [int(match.group(1)) for match in re.finditer(r"\[(\d+)\]", answer)]


def parse_ndjson(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(body.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"NDJSON line {line_number}: invalid JSON ({exc.msg})") from exc
        if not isinstance(event, dict):
            raise ValueError(f"NDJSON line {line_number}: event must be an object")
        events.append(event)
    return events


def read_self_test_token() -> str:
    configured = os.environ.get("IOS_SELF_TEST_TOKEN", "").strip()
    if configured:
        return configured
    if sys.platform == "darwin":
        try:
            return subprocess.check_output(
                [
                    "security",
                    "find-generic-password",
                    "-a",
                    os.environ.get("USER", "tommywu"),
                    "-s",
                    KEYCHAIN_SERVICE,
                    "-w",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    raise RuntimeError(
        "Missing IOS_SELF_TEST_TOKEN. Set the environment variable or configure "
        f"the macOS Keychain service {KEYCHAIN_SERVICE}."
    )


def request_json(
    base_url: str,
    token: str,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> tuple[int, str, str]:
    payload = json.dumps(
        {"question": question, "history": history or []}, ensure_ascii=False
    ).encode("utf-8")
    request = Request(
        f"{base_url}/api/ios-ask",
        data=payload,
        method="POST",
        headers={
            "accept": "application/x-ndjson, application/json",
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "origin": base_url,
            "user-agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=90) as response:
            return (
                response.status,
                response.headers.get("content-type", ""),
                response.read().decode("utf-8", errors="replace"),
            )
    except HTTPError as exc:
        return (
            exc.code,
            exc.headers.get("content-type", ""),
            exc.read().decode("utf-8", errors="replace"),
        )
    except URLError as exc:
        raise RuntimeError(f"Production request failed: {exc.reason}") from exc


def request_status(base_url: str, token: str) -> tuple[int, str]:
    request = Request(
        f"{base_url}/api/ios-ask",
        method="GET",
        headers={
            "accept": "application/json",
            "authorization": f"Bearer {token}",
            "origin": base_url,
            "user-agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"Production status check failed: {exc.reason}") from exc


def verify_live_status(status: int, body: str) -> None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Production status returned invalid JSON (HTTP {status})") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Production status returned an invalid payload (HTTP {status})")
    required = ("configured", "authenticated", "unlimited")
    if status < 200 or status >= 300 or not all(payload.get(key) is True for key in required):
        raise RuntimeError(
            "Production self-test authorization is not ready "
            f"(HTTP {status}; configured={payload.get('configured')!r}, "
            f"authenticated={payload.get('authenticated')!r}, "
            f"unlimited={payload.get('unlimited')!r})."
        )


def source_is_indexed_locally(path: object) -> bool | None:
    if not isinstance(path, str):
        return None
    import sqlite3

    db_path = ROOT / "db/ios_kb.sqlite"
    if not db_path.is_file():
        return None
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT 1 FROM files WHERE path = ?", (path,)).fetchone()
    return row is not None


def validate_inputs(paths: BatchPaths) -> dict[str, dict[str, Any]]:
    manifest_rows = load_jsonl(paths.manifest)
    ledger_rows = load_jsonl(paths.ledger)
    contract_rows = load_jsonl(paths.contracts)
    boundary_rows = load_jsonl(paths.boundaries)
    pair_rows = load_jsonl(paths.pairs)

    manifest = {row.get("id"): row for row in manifest_rows}
    if len(manifest) != len(manifest_rows) or None in manifest:
        raise ValueError("Manifest ids must be unique non-empty strings")
    ledger = {row.get("manifest_id"): row for row in ledger_rows}
    contracts = {row.get("manifest_id"): row for row in contract_rows}
    boundaries = {row.get("manifest_id"): row for row in boundary_rows}
    if set(ledger) != set(manifest):
        raise ValueError("Evidence ledger does not cover the manifest exactly")
    if any(key not in manifest for key in contracts) or any(key not in manifest for key in boundaries):
        raise ValueError("Contract or platform-boundary entry references an unknown manifest id")

    follow_up_seeds: dict[str, str] = {}
    for pair in pair_rows:
        if pair.get("pair_type") != "follow_up_context":
            continue
        base = pair.get("base_manifest_id")
        if not isinstance(base, str) or base not in manifest:
            raise ValueError("Follow-up pair references an unknown manifest id")
        if manifest[base].get("category") != "follow_up":
            raise ValueError(f"Follow-up pair {pair.get('id')} does not target a follow-up item")
        seed = pair.get("question_a")
        if not isinstance(seed, str) or not seed.strip():
            raise ValueError(f"Follow-up pair {pair.get('id')} lacks question_a")
        if base in follow_up_seeds:
            raise ValueError(f"Multiple follow-up fixtures for {base}")
        follow_up_seeds[base] = seed

    return {
        "manifest": manifest,
        "ledger": ledger,
        "contracts": contracts,
        "boundaries": boundaries,
        "follow_up_seeds": follow_up_seeds,
    }


def select_items(
    manifest: dict[str, dict[str, Any]], priority: str, requested_ids: set[str]
) -> list[dict[str, Any]]:
    unknown = requested_ids - set(manifest)
    if unknown:
        raise ValueError(f"Unknown manifest ids: {', '.join(sorted(unknown))}")
    selected = [
        item
        for item in manifest.values()
        if (priority == "all" or item.get("priority") == priority)
        and (not requested_ids or item["id"] in requested_ids)
    ]
    return sorted(selected, key=lambda item: item["id"])


def preflight_item(item: dict[str, Any], follow_up_seeds: dict[str, str]) -> dict[str, Any]:
    expected_path = item.get("expected_source_path")
    follow_up = item.get("category") == "follow_up"
    missing_fixture = follow_up and item["id"] not in follow_up_seeds
    return {
        "id": item["id"],
        "priority": item.get("priority"),
        "expected_mode": item.get("expected_mode"),
        "category": item.get("category"),
        "anchor_exists": None if expected_path is None else Path(expected_path).is_file(),
        "anchor_indexed_locally": source_is_indexed_locally(expected_path),
        "follow_up_fixture": follow_up_seeds.get(item["id"]),
        "runnable": not missing_fixture,
        "skip_reason": "missing reviewed follow-up fixture" if missing_fixture else "",
    }


def gate_blockers(
    selected: list[dict[str, Any]],
    reviewed: dict[str, dict[str, Any]],
    results: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Return deterministic reasons a release evaluation cannot pass.

    A normal preflight is informational because its manifest may intentionally
    contain anchors for an older production snapshot. ``--gate`` is the
    explicit post-index-release check, so it requires current local anchors and
    complete follow-up fixtures, and no outstanding manual review before a live
    result can be trusted.
    """

    blockers: list[dict[str, str]] = []
    preflight_by_id = {
        row["id"]: row
        for row in (
            preflight_item(item, reviewed["follow_up_seeds"]) for item in selected
        )
    }
    for item in selected:
        item_id = str(item["id"])
        preflight = preflight_by_id[item_id]
        if not preflight["runnable"]:
            blockers.append(
                {"id": item_id, "reason": preflight["skip_reason"]}
            )
        if (
            item.get("expected_mode") == "knowledge"
            and item.get("expected_source_path")
            and preflight["anchor_indexed_locally"] is not True
        ):
            blockers.append(
                {
                    "id": item_id,
                    "reason": (
                        "expected knowledge anchor is not present in the current "
                        "local index; refresh the manifest for this source version"
                    ),
                }
            )
        contract = reviewed.get("contracts", {}).get(item_id, {})
        if contract.get("manual_review_required"):
            blockers.append(
                {
                    "id": item_id,
                    "reason": (
                        "manual review remains required: "
                        f"{contract.get('manual_review_reason', 'no approval recorded')}"
                    ),
                }
            )

    if results is not None:
        for result in results:
            if result.get("outcome") != "passed":
                blockers.append(
                    {
                        "id": str(result.get("id", "unknown")),
                        "reason": str(
                            result.get("reason")
                            or result.get("grade", {}).get("reason")
                            or "evaluation did not pass"
                        ),
                    }
                )
    return blockers


def stream_observations(
    status: int, content_type: str, body: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, list[dict[str, Any]], str]:
    if status < 200 or status >= 300 or "application/x-ndjson" not in content_type:
        return None, None, "", [], f"expected NDJSON stream, got HTTP {status}"
    try:
        events = parse_ndjson(body)
    except ValueError as exc:
        return None, None, "", [], str(exc)
    done = next((event for event in reversed(events) if event.get("type") == "done"), None)
    error = next((event for event in events if event.get("type") == "error"), None)
    if not isinstance(done, dict):
        return None, error if isinstance(error, dict) else None, "", [], "stream has no done event"
    answer = str(done.get("answer", "")).strip()
    sources = done.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    return done, error if isinstance(error, dict) else None, answer, sources, ""


def public_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "n": source.get("n"),
            "source_type": source.get("sourceType"),
            "path": source.get("path"),
            "lines": source.get("lines"),
        }
        for source in sources
    ]


def evaluate_response(
    item: dict[str, Any], status: int, content_type: str, body: str
) -> dict[str, Any]:
    expected_mode = item["expected_mode"]
    if expected_mode == "no_evidence":
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        passed = status == 422 and payload.get("reason") == "no_evidence"
        done, error, answer, sources, stream_error = stream_observations(
            status, content_type, body
        )
        citations = citation_numbers(answer)
        actual_mode = done.get("mode") if isinstance(done, dict) else None
        if passed:
            reason = ""
        elif actual_mode:
            reason = f"expected 422 no_evidence, got {actual_mode} stream"
        elif stream_error:
            reason = f"expected 422 no_evidence, got HTTP {status}: {stream_error}"
        elif error:
            reason = f"expected 422 no_evidence, got stream error {error.get('reason', 'unknown')}"
        else:
            reason = f"expected 422 no_evidence, got HTTP {status}"
        return {
            "automated_pass": passed,
            "reason": reason,
            "response_status": status,
            "mode": actual_mode,
            "answer_chars": len(answer),
            "citations": citations,
            "sources": public_sources(sources),
            "anchor_citation_pass": None,
        }

    done, error, answer, sources, stream_error = stream_observations(status, content_type, body)
    if stream_error:
        return {
            "automated_pass": False,
            "reason": stream_error,
            "response_status": status,
            "mode": None,
            "answer_chars": 0,
            "citations": [],
            "sources": [],
            "anchor_citation_pass": False,
        }
    citations = citation_numbers(answer)
    valid_citations = [number for number in citations if 1 <= number <= len(sources)]
    matching_kinds = [
        anchor_match_kind(sources[number - 1], item)
        for number in valid_citations
        if isinstance(sources[number - 1], dict)
    ]
    matching_kinds = [kind for kind in matching_kinds if kind is not None]
    mode_matches = isinstance(done, dict) and done.get("mode") == expected_mode
    anchor_pass = bool(matching_kinds)
    passed = bool(done and not error and answer and mode_matches and anchor_pass)
    return {
        "automated_pass": passed,
        "reason": "" if passed else "mode, citation, or expected anchor check failed",
        "response_status": status,
        "mode": done.get("mode") if isinstance(done, dict) else None,
        "answer_chars": len(answer),
        "citations": citations,
        "sources": public_sources(sources),
        "anchor_citation_pass": anchor_pass,
        "anchor_citation_match": matching_kinds[0] if matching_kinds else None,
    }


def seed_follow_up(
    base_url: str, token: str, seed_question: str
) -> tuple[list[dict[str, str]] | None, str]:
    status, content_type, body = request_json(base_url, token, seed_question)
    if status < 200 or status >= 300 or "application/x-ndjson" not in content_type:
        return None, f"follow-up seed returned HTTP {status}"
    try:
        events = parse_ndjson(body)
    except ValueError as exc:
        return None, str(exc)
    done = next((event for event in reversed(events) if event.get("type") == "done"), None)
    if not isinstance(done, dict):
        return None, "follow-up seed did not produce a done event"
    answer = str(done.get("answer", "")).strip()
    mode = done.get("mode")
    if not answer or mode not in {"knowledge", "general"}:
        return None, "follow-up seed did not produce a usable answer"
    return [
        {"role": "user", "content": seed_question},
        {"role": "assistant", "content": answer, "mode": mode},
    ], ""


def run_live(
    selected: list[dict[str, Any]],
    reviewed: dict[str, dict[str, Any]],
    base_url: str,
    token: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in selected:
        preflight = preflight_item(item, reviewed["follow_up_seeds"])
        result: dict[str, Any] = {"preflight": preflight, "id": item["id"]}
        if not preflight["runnable"]:
            result.update({"outcome": "skipped", "reason": preflight["skip_reason"]})
            results.append(result)
            continue
        history: list[dict[str, str]] = []
        seed_question = reviewed["follow_up_seeds"].get(item["id"])
        if seed_question:
            history, seed_error = seed_follow_up(base_url, token, seed_question)
            if history is None:
                result.update({"outcome": "skipped", "reason": seed_error})
                results.append(result)
                continue
            result["follow_up_seed"] = {"question": seed_question, "status": "ok"}
        try:
            response_status, content_type, body = request_json(
                base_url, token, item["question"], history
            )
            grade = evaluate_response(item, response_status, content_type, body)
        except RuntimeError as exc:
            grade = {
                "automated_pass": False,
                "reason": str(exc),
                "response_status": None,
                "mode": None,
                "answer_chars": 0,
                "citations": [],
                "sources": [],
                "anchor_citation_pass": False,
            }
        contract = reviewed["contracts"].get(item["id"], {})
        ledger = reviewed["ledger"][item["id"]]
        boundary = reviewed["boundaries"].get(item["id"])
        manual = bool(contract.get("manual_review_required")) or ledger.get(
            "evidence_status"
        ) in {"partial", "mixed", "needs_human"}
        result.update(
            {
                "outcome": "passed" if grade["automated_pass"] else "failed",
                "grade": grade,
                "manual_review_required": manual,
                "manual_review_reason": contract.get("manual_review_reason", ""),
                "platform_boundary_rule": boundary.get("required_citation_rule", "")
                if isinstance(boundary, dict)
                else "",
                "answer_boundary": ledger.get("answer_boundary", ""),
            }
        )
        results.append(result)
        print(f"{result['outcome'].upper()} {item['id']}: {grade['reason'] or grade['mode']}")
    return results


def make_report(
    selected: list[dict[str, Any]],
    reviewed: dict[str, dict[str, Any]],
    base_url: str,
    live: bool,
    results: list[dict[str, Any]] | None = None,
    *,
    gate_enabled: bool = False,
    gate_blockers_list: list[dict[str, str]] | None = None,
    live_attempted: bool = False,
) -> dict[str, Any]:
    preflight = [preflight_item(item, reviewed["follow_up_seeds"]) for item in selected]
    output = results if results is not None else [{"id": row["id"], "preflight": row} for row in preflight]
    counts = Counter(row.get("outcome", "preflight") for row in output)
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "preflight",
        "live_attempted": live_attempted,
        "base_url": base_url,
        "selected_count": len(selected),
        "selected_ids": [item["id"] for item in selected],
        "summary": dict(sorted(counts.items())),
        "gate": {
            "enabled": gate_enabled,
            "passed": not gate_blockers_list if gate_enabled else None,
            "blockers": gate_blockers_list or [],
        },
        "anchor_version_warning": (
            "An anchor absent from the current local index may still be valid for the "
            "2026-09-06 production snapshot. It must be refreshed before evaluating a "
            "post-ios-source-learning release."
        ),
        "results": output,
    }


def default_report_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ROOT / "data/evaluation-results" / f"production-eval-{stamp}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="send requests to production")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="fail unless anchors, fixtures, manual reviews, and live cases pass",
    )
    parser.add_argument("--priority", choices=["P0", "P1", "P2", "all"], default="P0")
    parser.add_argument("--case", action="append", default=[], help="manifest id; repeat as needed")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--report", type=Path, help="local JSON report path")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_LEDGER_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = BatchPaths(
        manifest=args.manifest_dir / "production-eval-manifest-candidates.jsonl",
        ledger=args.ledger_dir / "evidence-ledger.jsonl",
        contracts=args.ledger_dir / "grading-contract-candidates.jsonl",
        boundaries=args.ledger_dir / "platform-boundary-review.jsonl",
        pairs=args.ledger_dir / "adversarial-pairs.jsonl",
    )
    try:
        reviewed = validate_inputs(paths)
        selected = select_items(reviewed["manifest"], args.priority, set(args.case))
        if not selected:
            raise ValueError("No evaluation cases selected")
        base_url = args.base_url.rstrip("/")
        results = None
        blockers = gate_blockers(selected, reviewed, None) if args.gate else []
        if args.live and not blockers:
            token = read_self_test_token()
            status, body = request_status(base_url, token)
            verify_live_status(status, body)
            results = run_live(selected, reviewed, base_url, token)
            if args.gate:
                blockers = gate_blockers(selected, reviewed, results)
        report = make_report(
            selected,
            reviewed,
            base_url,
            args.live,
            results,
            gate_enabled=args.gate,
            gate_blockers_list=blockers,
            live_attempted=results is not None,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report or args.live:
        report_path = args.report or default_report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(encoded, encoding="utf-8")
        print(f"Report: {report_path}")
    else:
        print(encoded, end="")
    if args.gate and blockers:
        print(
            f"GATE BLOCKED: {len(blockers)} blocker(s); see the report for details.",
            file=sys.stderr,
        )
        return 1
    if args.gate:
        if args.live:
            print("GATE PASSED: live evaluation is release-ready.")
        else:
            print(
                "PREFLIGHT GATE PASSED: anchors, fixtures, and manual reviews are ready."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
