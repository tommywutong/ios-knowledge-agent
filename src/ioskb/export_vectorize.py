import json
import hashlib
import struct

from .metadata import export_metadata


def stable_vector_id(source, path, ordinal):
    key = f"{source}\0{path}\0{ordinal}".encode("utf-8")
    return "v1-" + hashlib.sha256(key).hexdigest()[:48]


def export(cfg, con, out_path):
    dim = cfg["embedding"]["dim"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = con.execute(
        "SELECT c.id, c.source, c.type, c.file_path, c.title_path, c.start_line, c.end_line, "
        "c.text, v.embedding, ROW_NUMBER() OVER (PARTITION BY c.file_path "
        "ORDER BY c.start_line, c.end_line, c.id) AS chunk_ordinal "
        "FROM chunks c JOIN vec_chunks v ON v.rowid = c.id "
        "WHERE c.vectorized = 1 AND c.type <> 'card' ORDER BY c.id"
    )
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for cid, source, ctype, path, title_path, start, end, text, blob, ordinal in rows:
            values = list(struct.unpack(f"{dim}f", blob))
            vector_id = stable_vector_id(source, path, ordinal)
            rec = {
                "id": vector_id,
                "values": values,
                "metadata": {
                    "source": source,
                    "type": ctype,
                    "path": path,
                    "title_path": title_path,
                    "lines": f"{start}-{end}",
                    "text": text[:2000],
                    **export_metadata(
                        path, title_path, text, source=source, ctype=ctype
                    ),
                },
            }
            # Cloudflare's NDJSON parser treats literal Unicode line separators as
            # record boundaries even though they are valid JSON string characters.
            line = json.dumps(rec, ensure_ascii=False)
            f.write(line.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") + "\n")
            count += 1
    return count
