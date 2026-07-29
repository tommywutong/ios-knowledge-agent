"""混合检索：FTS + 向量召回，RRF 融合，类型加权，按文件限流。"""
from . import db

RRF_K = 60


def search(con, cfg, query, embedder=None):
    r = cfg["retrieval"]
    scores = {}
    for cid, rank in db.fts_search(con, query, r["fts_top"]):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    if embedder is not None:
        qvec = embedder.encode([query])[0]
        for cid, rank in db.vec_search(con, qvec, r["vector_top"]):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    rows = db.get_chunks(con, list(scores))
    weights = r.get("type_weights", {})
    scored = []
    for cid, s in scores.items():
        row = rows.get(cid)
        if not row:
            continue
        row = dict(row)
        row["score"] = s * weights.get(row["type"], 1.0)
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
        fingerprint = hash("".join(row["text"].split()))
        if fingerprint in seen_text:
            continue
        seen_text.add(fingerprint)
        per_file[fp] = per_file.get(fp, 0) + 1
        out.append(row)
        if len(out) >= final_top:
            break
    return out
