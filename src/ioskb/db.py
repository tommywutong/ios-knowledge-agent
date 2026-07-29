"""SQLite 存储层：chunks 主表 + FTS5 关键词索引 + sqlite-vec 向量索引。"""
import re
import sqlite3

_CJK = re.compile(r"[一-鿿]")


def open_db(cfg):
    if tuple(int(x) for x in sqlite3.sqlite_version.split(".")[:2]) < (3, 43):
        raise SystemExit(
            f"SQLite 版本过低（{sqlite3.sqlite_version}），FTS5 contentless_delete 需要 ≥3.43。"
            "请改用较新的 Python（uv 安装的 3.11+ 均满足）。"
        )
    from .config import resolve_path

    path = resolve_path(cfg["db_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.enable_load_extension(True)
    import sqlite_vec

    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.execute("PRAGMA journal_mode=WAL")
    dim = cfg["embedding"]["dim"]
    con.execute(
        "CREATE TABLE IF NOT EXISTS files("
        "path TEXT PRIMARY KEY, source TEXT, hash TEXT, mtime REAL, nchunks INT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT, source TEXT, type TEXT,"
        "title_path TEXT, start_line INT, end_line INT, text TEXT, vectorized INT DEFAULT 0)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_path)")
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5("
        "tok, content='', contentless_delete=1)"
    )
    con.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{dim}])"
    )
    con.commit()
    return con


def tokenize_for_fts(text):
    if _CJK.search(text):
        import jieba

        return " ".join(jieba.cut_for_search(text))
    return text.lower()


def _delete_chunk_rows(con, ids):
    if not ids:
        return
    ph = ",".join("?" * len(ids))
    con.execute(f"DELETE FROM chunks_fts WHERE rowid IN ({ph})", ids)
    con.execute(f"DELETE FROM vec_chunks WHERE rowid IN ({ph})", ids)
    con.execute(f"DELETE FROM chunks WHERE id IN ({ph})", ids)


def upsert_file(con, source_name, file_key, content_hash, mtime, chunks):
    row = con.execute("SELECT hash FROM files WHERE path=?", (file_key,)).fetchone()
    if row and row[0] == content_hash:
        return "skipped"
    try:
        old = [r[0] for r in con.execute("SELECT id FROM chunks WHERE file_path=?", (file_key,))]
        _delete_chunk_rows(con, old)
        for c in chunks:
            cur = con.execute(
                "INSERT INTO chunks(file_path,source,type,title_path,start_line,end_line,text,vectorized)"
                " VALUES(?,?,?,?,?,?,?,0)",
                (
                    c["file_path"],
                    c["source"],
                    c["type"],
                    c.get("title_path", ""),
                    c["start_line"],
                    c["end_line"],
                    c["text"],
                ),
            )
            con.execute(
                "INSERT INTO chunks_fts(rowid, tok) VALUES(?,?)",
                (cur.lastrowid, tokenize_for_fts(c["text"])),
            )
        con.execute(
            "INSERT OR REPLACE INTO files(path,source,hash,mtime,nchunks) VALUES(?,?,?,?,?)",
            (file_key, source_name, content_hash, mtime, len(chunks)),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    return "indexed"


def delete_missing_files(con, source_name, existing_keys):
    gone = [
        r[0]
        for r in con.execute("SELECT path FROM files WHERE source=?", (source_name,))
        if r[0] not in existing_keys
    ]
    try:
        for path in gone:
            ids = [r[0] for r in con.execute("SELECT id FROM chunks WHERE file_path=?", (path,))]
            _delete_chunk_rows(con, ids)
            con.execute("DELETE FROM files WHERE path=?", (path,))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return len(gone)


def pending_vector_chunks(con, source_names):
    if not source_names:
        return []
    ph = ",".join("?" * len(source_names))
    return list(
        con.execute(
            f"SELECT id, text FROM chunks WHERE vectorized=0 AND source IN ({ph}) ORDER BY id",
            source_names,
        )
    )


def _to_blob(vec):
    import sqlite_vec

    if hasattr(vec, "tolist"):
        vec = vec.tolist()
    return sqlite_vec.serialize_float32(vec)


def store_vectors(con, ids, vectors):
    try:
        for cid, vec in zip(ids, vectors):
            con.execute(
                "INSERT OR REPLACE INTO vec_chunks(rowid, embedding) VALUES(?,?)",
                (cid, _to_blob(vec)),
            )
            con.execute("UPDATE chunks SET vectorized=1 WHERE id=?", (cid,))
        con.commit()
    except Exception:
        con.rollback()
        raise


def _query_tokens(query):
    toks, seen = [], set()
    for t in tokenize_for_fts(query).split():
        t = t.replace('"', "").strip()
        if not t or t in seen:
            continue
        if len(t) == 1 and ord(t) < 128:
            continue
        if not any(ch.isalnum() or _CJK.match(ch) for ch in t):
            continue
        seen.add(t)
        toks.append(t)
        if len(toks) >= 12:
            break
    return toks


def fts_search(con, query, top):
    toks = _query_tokens(query)
    if not toks:
        return []
    match = " OR ".join(f'"{t}"' for t in toks)
    try:
        rows = con.execute(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, top),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [(r[0], i) for i, r in enumerate(rows)]


def vec_search(con, qvec, top):
    rows = con.execute(
        "SELECT rowid FROM vec_chunks WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (_to_blob(qvec), top),
    ).fetchall()
    return [(r[0], i) for i, r in enumerate(rows)]


def get_chunks(con, ids):
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    cur = con.execute(f"SELECT * FROM chunks WHERE id IN ({ph})", list(ids))
    cols = [d[0] for d in cur.description]
    return {row[0]: dict(zip(cols, row)) for row in cur.fetchall()}
