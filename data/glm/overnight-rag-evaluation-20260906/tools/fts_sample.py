#!/usr/bin/env python3
"""只读 FTS 抽样：对 knowledge 评测候选分主题抽样，运行
`uv run ioskb search <q> --no-vector -k 8` 并记录真实返回。"""
import json, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/tommywu/Desktop/iOS知识agentt")
OUT = HERE.parent / "retrieval-samples/fts-sample-results.jsonl"

rows = []
for fp in sorted((HERE.parent / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if r["expected_mode"] == "knowledge" and r["expected_source_path"]:
            rows.append(r)

# 按主题分桶，确定性等距抽样
from collections import defaultdict
buckets = defaultdict(list)
for r in rows:
    buckets[r["topic"]].append(r)
PER = 36
sample = []
buckets = {t: b for t, b in sorted(buckets.items())}
# 主题轮转均衡抽样：每轮从各主题取一条，直到达到目标数量
CURSOR = {t: 0 for t in buckets}
STEP = {t: max(1, len(b) // PER) for t, b in buckets.items()}
while len(sample) < 252:
    progressed = False
    for t in buckets:
        if len(sample) >= 252:
            break
        b = buckets[t]
        i = CURSOR[t]
        if i < len(b):
            sample.append(b[i])
            CURSOR[t] = i + STEP[t] if i + STEP[t] < len(b) else i + 1
            progressed = True
    if not progressed:
        break
print(f"sampled {len(sample)} of {len(rows)}", flush=True)

CITE = re.compile(r"\[(\d+)\]【([^】]*)】(.+?) › .*（第(\d+)-(\d+)行）")

def run_query(q):
    try:
        t0 = time.time()
        proc = subprocess.run(
            ["uv", "run", "ioskb", "search", q, "--no-vector", "-k", "8"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=90)
        dt = time.time() - t0
        return proc.stdout, proc.stderr, dt
    except subprocess.TimeoutExpired:
        return None, "timeout", 90.0

def classify(row, status):
    if status != "miss":
        return "none"
    try:
        text = Path(row["expected_source_path"]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "path_mismatch"
    # 粗判：问题关键词是否存在于预期文件
    toks = [t for t in re.split(r"[\s，。？！、「」（）()：:，,.]+", row["question"])
            if len(t) >= 2]
    hit = any(t in text for t in toks[:12])
    if row["category"] in {"alias"}:
        return "alias" if hit else "lexical_recall"
    return "lexical_recall" if hit else "source_coverage"

results = []
for i, r in enumerate(sample, 1):
    out, err, dt = run_query(r["question"])
    rec = {
        "eval_id": r["id"],
        "query": r["question"],
        "expected_source_path": r["expected_source_path"],
        "observed_top_paths": [],
        "expected_source_found": False,
        "best_rank": None,
        "status": "not_run",
        "suspected_failure_class": "other",
        "notes": "",
    }
    if out is None:
        rec["notes"] = f"命令超时: {err}"
        results.append(rec)
        print(f"[{i}/{len(sample)}] {r['id']} TIMEOUT", flush=True)
        continue
    paths = []
    for ln in out.split("\n"):
        m = CITE.search(ln)
        if m:
            paths.append((int(m.group(1)), m.group(3)))
    paths = [p for _, p in paths][:8]
    rec["observed_top_paths"] = paths
    if not paths:
        rec["status"] = "miss"
        rec["notes"] = "无返回结果"
    else:
        rank = None
        for j, p in enumerate(paths, 1):
            if p == r["expected_source_path"]:
                rank = j
                break
        rec["expected_source_found"] = rank is not None
        rec["best_rank"] = rank
        if rank and rank <= 3:
            rec["status"] = "pass"
        elif rank:
            rec["status"] = "partial"
        else:
            rec["status"] = "miss"
            rec["notes"] = f"预期来源未进入 top8（共返回 {len(paths)} 条）"
    rec["suspected_failure_class"] = classify(r, rec["status"])
    rec["notes"] = rec["notes"] or f"耗时 {dt:.1f}s"
    results.append(rec)
    print(f"[{i}/{len(sample)}] {r['id']} {rec['status']}", flush=True)

with OUT.open("w", encoding="utf-8") as f:
    for rec in results:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
from collections import Counter
print("status:", dict(Counter(r["status"] for r in results)))
print("class:", dict(Counter(r["suspected_failure_class"] for r in results)))
