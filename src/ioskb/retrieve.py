"""混合检索：FTS + 向量召回，RRF 融合，类型加权，按文件限流。"""
import re
import unicodedata

from . import db
from .metadata import evidence_metadata

RRF_K = 60
_QUERY_STOP_WORDS = {
    "什么", "怎么", "怎么样", "如何", "为什么", "一下", "介绍", "解释",
    "区别", "问题", "方法", "使用", "实现", "相关", "关于", "可以", "是否",
    "请问", "帮我", "保证", "做", "会", "和", "的", "了", "吗", "呢", "讲", "说",
    "the", "and", "with", "from", "what", "why", "how",
}
_COMPETING_PLATFORM = re.compile(r"\bandroid\b|\bkotlin\b|\bjetpack\b|\bjava\b", re.I)
_APPLE_PLATFORM = re.compile(
    r"\bios\b|\bipados\b|\bmacos\b|\bwatchos\b|\btvos\b|\bvisionos\b|"
    r"\bswift\b|objective-c|\bobjc\b|\buikit\b|\bappkit\b|\bxcode\b",
    re.I,
)
_AUTHORITY_WEIGHTS = {
    "official": 1.08,
    "primary_source": 1.04,
    "reviewed_note": 0.98,
    "community": 0.9,
    "unverified_note": 0.78,
}


def _normalized(value):
    return unicodedata.normalize("NFKC", value).lower()


def _keyword_coverage(query, row):
    tokens = [
        token.lower()
        for token in db.query_tokens(query)
        if token.lower() not in _QUERY_STOP_WORDS
    ]
    if not tokens:
        return 0.0
    searchable = _normalized(
        f"{row.get('title_path', '')}\n{row.get('file_path', '')}\n{row.get('text', '')}"
    )
    return sum(token in searchable for token in tokens) / len(tokens)


def _explicitly_out_of_domain(query):
    return bool(_COMPETING_PLATFORM.search(query) and not _APPLE_PLATFORM.search(query))


def search(con, cfg, query, embedder=None, *, exclude_types=None):
    """检索相关块。

    ``exclude_types`` 用于证据边界：问答和卡片生成必须排除二次生成的
    ``card``，从而保证最终证据始终回到原始资料。
    """
    r = cfg["retrieval"]
    if _explicitly_out_of_domain(query):
        return []
    excluded = set(exclude_types or ())
    # 过滤发生在取回元数据之后；多召回一些候选，避免被排除类型占满候选池。
    candidate_multiplier = 4 if excluded else 1
    signals = {}
    for cid, rank, bm25 in db.fts_search(
        con, query, r["fts_top"] * candidate_multiplier
    ):
        signals.setdefault(cid, {})["fts"] = (rank, bm25)
    if embedder is not None:
        qvec = embedder.encode([query])[0]
        for cid, rank, distance in db.vec_search(
            con, qvec, r["vector_top"] * candidate_multiplier
        ):
            signals.setdefault(cid, {})["vector"] = (rank, distance)
    rows = db.get_chunks(con, list(signals))
    weights = r.get("type_weights", {})
    max_vector_distance = r.get("max_vector_distance", 0.8)
    min_keyword_coverage = r.get("min_keyword_coverage", 0.55)
    scored = []
    for cid, signal in signals.items():
        row = rows.get(cid)
        if not row or row["type"] in excluded:
            continue
        coverage = _keyword_coverage(query, row)
        vector = signal.get("vector")
        fts = signal.get("fts")
        valid_vector = bool(vector and vector[1] <= max_vector_distance)
        valid_fts = bool(fts and coverage >= min_keyword_coverage)
        if not valid_vector and not valid_fts:
            continue
        score = 0.0
        if valid_vector:
            score += 1.0 / (RRF_K + vector[0])
        if valid_fts:
            score += 1.0 / (RRF_K + fts[0])
        row = dict(row)
        provenance = evidence_metadata(
            row.get("source", ""), row.get("type", ""),
            row.get("file_path", ""), row.get("text", ""),
        )
        row.update(provenance)
        row["semantic_distance"] = vector[1] if vector else None
        row["keyword_coverage"] = coverage
        row["score"] = (
            score
            * weights.get(row["type"], 1.0)
            * _AUTHORITY_WEIGHTS.get(row["authority"], 0.85)
        )
        scored.append(row)
    scored.sort(key=lambda x: -x["score"])

    max_per_file = r.get("max_per_file", 2)
    final_top = r.get("final_top", 8)
    out, per_file, seen_text = [], {}, set()
    for row in scored:
        fp = row["file_path"]
        if per_file.get(fp, 0) >= max_per_file:
            continue
        # 同一内容存在于多个位置时（如同一笔记在两个目录各有一份）只保留得分最高的一条
        fingerprint = "".join(row["text"].split())
        if fingerprint in seen_text:
            continue
        seen_text.add(fingerprint)
        per_file[fp] = per_file.get(fp, 0) + 1
        out.append(row)
        if len(out) >= final_top:
            break
    return out
