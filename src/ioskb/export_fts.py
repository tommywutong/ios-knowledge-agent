"""Export a bounded, evidence-only full-text corpus for the website."""

from __future__ import annotations

import hashlib
import heapq
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone

from .export_vectorize import stable_vector_id
from .metadata import export_metadata


DEFAULT_TIER1_LIMIT = 80_000
DEFAULT_PER_FILE_LIMIT = 24
EXCERPT_LIMIT = 2_000

_PLATFORM = re.compile(
    r"\b(?:ios|ipados|iphone|ipad|macos|watchos|tvos|visionos|swift|swiftui|"
    r"objective-c|objc|uikit|appkit|xcode|cocoa(?:\s+touch)?|darwin)\b",
    re.I,
)
_SYMBOL = re.compile(
    r"\b(?:[A-Z]{2,}[A-Za-z0-9_]{2,}|[a-z_][A-Za-z0-9_]{2,}\([^)]*\)|"
    r"k[A-Z][A-Za-z0-9_]{3,}|NS[A-Z][A-Za-z0-9_]{2,}|UI[A-Z][A-Za-z0-9_]{2,})\b"
)
_ERROR_CODE = re.compile(r"\b(?:NS|k?CF|OSStatus|errno|error)\s*[-_:]?[A-Z0-9_-]{2,}\b", re.I)
_TOPICS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"memory|retain|release|weak|autorelease|arc|内存|引用计数",
        r"runtime|objc_msgsend|message forwarding|method swizz|isa|运行时|消息转发",
        r"runloop|cfRunLoop|source0|source1|运行循环",
        r"concurr|thread|dispatch|gcd|actor|async|await|lock|并发|线程|锁",
        r"uikit|view controller|autolayout|calayer|animation|渲染|布局",
        r"swiftui|viewbuilder|stateobject|observable|environment",
        r"urlsession|network|http|tls|socket|bonjour|网络",
        r"core data|swiftdata|sqlite|filemanager|userdefaults|存储|数据库",
        r"security|keychain|crypt|certificate|sandbox|entitlement|安全|证书",
        r"avfoundation|audio|video|camera|photo|media|音频|视频|相机",
        r"core location|mapkit|location|geocod|定位|地图",
        r"notification|pushkit|usernotifications|推送|通知",
        r"accessibility|voiceover|dynamic type|辅助功能",
        r"xctest|testing|testflight|ui test|单元测试|测试",
        r"compiler|linker|mach-o|dyld|build|xcode|编译|链接|启动",
        r"app store|distribution|provision|signing|receipt|storekit|分发|签名",
        r"performance|instrument|metric|hang|crash|energy|性能|卡顿|崩溃",
        r"architecture|mvc|mvvm|vip|coordinator|dependency inject|架构",
        r"foundation|core foundation|cf[A-Z]|nsobject|kvc|kvo",
        r"webkit|webview|javascriptcore|网页",
        r"cloudkit|icloud|sync|同步",
        r"metal|core image|core graphics|spritekit|图形",
        r"arkit|realitykit|vision|machine learning|core ml|机器学习",
    )
)
_TOPIC_UNION = re.compile(
    "|".join(f"(?:{pattern.pattern})" for pattern in _TOPICS), re.I
)
_EXCLUDED_COMPONENT = re.compile(
    r"(?:^|/)(?:license|licenses|changelog|changes|contributing|code_of_conduct|"
    r"authors|contributors|package-lock|repositories|readme)(?:[._/-]|$)",
    re.I,
)
_LOW_VALUE_TITLE = re.compile(
    r"^(?:see also|topics|relationships|revision history|document revision history|copyright)$",
    re.I,
)


def _digest(value: str, length: int = 48) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def stable_file_key(source: str, path: str) -> str:
    return "k1-" + _digest(f"{source}\0{path}", 32)


def stable_fts_id(source: str, path: str, ordinal: int, vectorized: bool = False) -> str:
    if vectorized:
        return stable_vector_id(source, path, ordinal)
    return "f1-" + _digest(f"{source}\0{path}\0{ordinal}")


def normalized_content_hash(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).lower().split())
    return _digest(normalized, 40)


def safe_json_line(record: dict) -> str:
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    return line.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def tier1_score(path: str, title_path: str, text: str) -> tuple[int, str]:
    """Return a deterministic relevance score and rejection reason."""
    clean_text = " ".join(text.split())
    lower_path = unicodedata.normalize("NFKC", path).lower()
    title = unicodedata.normalize("NFKC", title_path).strip()
    if _EXCLUDED_COMPONENT.search(lower_path):
        return 0, "metadata_path"
    if len(clean_text) < 60:
        return 0, "too_short"
    if _LOW_VALUE_TITLE.fullmatch(title.split("›")[-1].strip() if title else ""):
        return 0, "low_value_section"
    if clean_text.count("http") >= 8 and len(re.findall(r"[.!?。！？]", clean_text)) < 2:
        return 0, "link_list"

    heading = f"{lower_path}\n{title}"
    sample = text[:4_000]
    platform_heading = len(_PLATFORM.findall(heading))
    platform_body = len(_PLATFORM.findall(sample))
    topic_heading = bool(_TOPIC_UNION.search(heading))
    topic_body = bool(_TOPIC_UNION.search(sample))
    symbol = bool(_SYMBOL.search(f"{title}\n{sample}"))
    error_code = bool(_ERROR_CODE.search(sample))
    reference_path = any(
        part in lower_path
        for part in ("/documentation/", "/apple-docs/", "/releasenotes/", "/swift-evolution/")
    )
    score = (
        min(platform_heading, 3) * 12
        + min(platform_body, 3) * 5
        + (12 if topic_heading else 0)
        + (8 if topic_body else 0)
        + (8 if symbol else 0)
        + (4 if error_code else 0)
        + (5 if reference_path else 0)
    )
    if score < 13:
        return score, "weak_ios_signal"
    return score, "selected"


def _record(
    row,
    ordinal: int,
    tier: int,
    selection_score: int,
    *,
    content_hash: str | None = None,
) -> dict:
    _, source, ctype, path, title_path, start, end, text, vectorized = row
    excerpt = text[:EXCERPT_LIMIT].replace("\x00", "")
    content_hash = content_hash or normalized_content_hash(excerpt)
    return {
        "id": stable_fts_id(source, path, ordinal, bool(vectorized)),
        "file_key": stable_file_key(source, path),
        "chunk_ordinal": ordinal,
        "content_hash": content_hash,
        "tier": tier,
        "selection_score": selection_score,
        "metadata": {
            "source": source,
            "type": ctype,
            "path": path,
            "title_path": title_path or "",
            "lines": f"{start}-{end}",
            "text": excerpt,
            **export_metadata(path, title_path or "", excerpt, source=source, ctype=ctype),
        },
    }


def export(cfg, con, out_path, *, tier1_limit=DEFAULT_TIER1_LIMIT, per_file_limit=DEFAULT_PER_FILE_LIMIT):
    """Export all vector evidence plus a bounded high-value FTS-only tier."""
    if tier1_limit < 0 or per_file_limit < 1:
        raise ValueError("tier limits must be positive")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = con.execute(
        "SELECT id, source, type, file_path, title_path, start_line, end_line, text, vectorized "
        "FROM chunks WHERE type <> 'card' "
        "ORDER BY file_path, start_line, end_line, id"
    )
    core_records = []
    tier1_heap = []
    file_candidates = []
    core_hashes = set()
    tier1_hashes = set()
    counters = Counter()
    selected_by_source = Counter()
    current_path = None
    ordinal = 0

    def keep_file_candidates():
        nonlocal file_candidates
        for item in heapq.nlargest(
            per_file_limit, file_candidates, key=lambda candidate: candidate[:2]
        ):
            if len(tier1_heap) < tier1_limit:
                heapq.heappush(tier1_heap, item)
            elif item[:2] > tier1_heap[0][:2]:
                heapq.heapreplace(tier1_heap, item)
        file_candidates = []

    for row in rows:
        path = row[3]
        if path != current_path:
            keep_file_candidates()
            current_path = path
            ordinal = 1
        else:
            ordinal += 1
        counters["scanned"] += 1
        if counters["scanned"] % 100_000 == 0:
            print(f"  已筛选 {counters['scanned']:,} 个文本块...", flush=True)
        if row[8]:
            record = _record(row, ordinal, 0, 100)
            core_records.append(record)
            core_hashes.add(record["content_hash"])
            selected_by_source[row[1]] += 1
            counters["tier0"] += 1
            continue

        score, reason = tier1_score(path, row[4] or "", row[7])
        counters[f"rejected_{reason}"] += reason != "selected"
        if reason != "selected":
            continue
        content_hash = normalized_content_hash(row[7][:EXCERPT_LIMIT])
        if content_hash in core_hashes or content_hash in tier1_hashes:
            counters["rejected_duplicate"] += 1
            continue
        tier1_hashes.add(content_hash)
        record_id = stable_fts_id(row[1], path, ordinal, False)
        file_candidates.append((score, record_id, row, ordinal, content_hash))
    keep_file_candidates()

    selected_tier1 = [
        _record(item[2], item[3], 1, item[0], content_hash=item[4])
        for item in sorted(tier1_heap, key=lambda candidate: (-candidate[0], candidate[1]))
    ]
    with out_path.open("w", encoding="utf-8") as output:
        for record in core_records:
            output.write(safe_json_line(record) + "\n")
        for record in selected_tier1:
            output.write(safe_json_line(record) + "\n")
            selected_by_source[record["metadata"]["source"]] += 1
    counters["tier1"] = len(selected_tier1)
    counters["exported"] = len(core_records) + len(selected_tier1)
    manifest = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output": str(out_path),
        "bytes": out_path.stat().st_size,
        "tier1_limit": tier1_limit,
        "per_file_limit": per_file_limit,
        "counts": dict(sorted(counters.items())),
        "selected_by_source": dict(sorted(selected_by_source.items())),
    }
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
