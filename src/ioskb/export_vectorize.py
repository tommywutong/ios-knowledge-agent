import json
import struct

from .metadata import export_metadata


def export(cfg, con, out_path):
    dim = cfg["embedding"]["dim"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = con.execute(
        "SELECT c.id, c.source, c.type, c.file_path, c.title_path, c.start_line, c.end_line, "
        "c.text, v.embedding FROM chunks c JOIN vec_chunks v ON v.rowid = c.id "
        "WHERE c.vectorized = 1 AND c.type <> 'card' ORDER BY c.id"
    )
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for cid, source, ctype, path, title_path, start, end, text, blob in rows:
            values = list(struct.unpack(f"{dim}f", blob))
            rec = {
                "id": str(cid),
                "values": values,
                "metadata": {
                    "source": source,
                    "type": ctype,
                    "path": path,
                    "title_path": title_path,
                    "lines": f"{start}-{end}",
                    "text": text[:2000],
                    **export_metadata(path, title_path, text),
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count
