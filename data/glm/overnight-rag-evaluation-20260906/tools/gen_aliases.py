#!/usr/bin/env python3
"""只读生成 terminology-aliases.jsonl：在真实原始资料中定位术语，填充证据行。"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from alias_data import TERMS

ROOT = Path("/Users/tommywu/Desktop/iOS知识agentt")
OUT = HERE.parent / "terminology-aliases.jsonl"
COV = HERE.parent / "source-coverage.jsonl"

# 证据检索优先级：个人笔记 > tips > 源码 > 官方/博客
def priority(source_id, kind):
    return {"obsidian-ios": 0, "summer2026": 1, "summer-labs": 3, "objc4-source": 2,
            "apple-docs-core": 4, "apple-archive": 5}.get(source_id, 9)

# 预加载覆盖清单中的文件（全部只读）
docs = []
for line in COV.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    p = Path(r["source_path"])
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    docs.append((priority(r["source_id"], r["content_kind"]), r["source_path"], text, text.split("\n")))
docs.sort(key=lambda d: d[0])
print(f"loaded {len(docs)} files")

def find(term):
    """返回 (path, line_1indexed) 或 None。符号区分大小写，中文不区分。"""
    ascii_term = term.isascii()
    for _, path, text, lines in docs:
        if ascii_term:
            if term in text:
                for i, ln in enumerate(lines, 1):
                    if term in ln:
                        return path, i
        else:
            if term in text:
                for i, ln in enumerate(lines, 1):
                    if term in ln:
                        return path, i
    return None

records = []
unverified = 0
for idx, (canon, lang, aliases, cat, plat, amb, hint) in enumerate(TERMS, 1):
    hit = None
    for cand in [canon] + list(aliases):
        hit = find(cand)
        if hit:
            break
    risk = []
    if hit:
        path, ln = hit
        ev_path, s, e = path, ln, ln
    else:
        ev_path, s, e = None, None, None
        unverified += 1
        risk = ["术语候选，未作为事实证据验证"]
    records.append({
        "id": f"alias-{idx:06d}",
        "canonical_term": canon,
        "language": lang,
        "aliases": list(aliases),
        "category": cat,
        "platform_scope": list(plat),
        "ambiguity": amb,
        "disambiguation_hint": hint or "",
        "evidence_path": ev_path,
        "evidence_start_line": s,
        "evidence_end_line": e,
        "risk_notes": risk,
    })

with OUT.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"written {len(records)}; unverified(evidence=null): {unverified}")
from collections import Counter
print("by category:", dict(Counter(r["category"] for r in records)))
print("by ambiguity:", dict(Counter(r["ambiguity"] for r in records)))
