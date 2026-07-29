import argparse
import copy
import hashlib
import os
import sys

from .config import load_config, resolve_path
from .db import delete_missing_files, open_db, pending_vector_chunks, store_vectors, upsert_file
from .ingest import file_chunks, iter_source_files
from .qa import format_citation


def _delete_source(con, source_name):
    ids = [r[0] for r in con.execute("SELECT id FROM chunks WHERE source = ?", (source_name,))]
    for i in range(0, len(ids), 500):
        batch = ids[i : i + 500]
        marks = ",".join("?" * len(batch))
        con.execute(f"DELETE FROM vec_chunks WHERE rowid IN ({marks})", batch)
        con.execute(f"DELETE FROM chunks_fts WHERE rowid IN ({marks})", batch)
    con.execute("DELETE FROM chunks WHERE source = ?", (source_name,))
    con.execute("DELETE FROM files WHERE source = ?", (source_name,))
    con.commit()


def cmd_index(args):
    cfg = load_config()
    con = open_db(cfg)
    chunking_cfg = cfg.get("chunking", {})
    sources = cfg["sources"]
    if args.source:
        sources = [s for s in sources if s["name"] == args.source]
        if not sources:
            raise SystemExit(f"config.yaml 中没有名为 {args.source} 的 source")

    for s in sources:
        base = resolve_path(s["path"])
        if not base.exists():
            print(f"[{s['name']}] 路径不存在，跳过：{base}")
            continue
        if args.full:
            _delete_source(con, s["name"])
        files = iter_source_files(s)
        print(f"[{s['name']}] 共 {len(files)} 个文件")
        indexed = skipped = 0
        existing_keys = set()
        for i, f in enumerate(files, 1):
            try:
                data = f.read_bytes()
            except OSError as e:
                print(f"  读取失败，跳过 {f}：{e}")
                continue
            h = hashlib.sha256(data).hexdigest()
            # 非 docx 的 display_path 就是原文件绝对路径，可先查 hash 免去切块开销
            if f.suffix.lower() != ".docx":
                key = str(f.resolve())
                row = con.execute("SELECT hash FROM files WHERE path = ?", (key,)).fetchone()
                if row and row[0] == h:
                    existing_keys.add(key)
                    skipped += 1
                    if i % 200 == 0:
                        print(f"  ... {i}/{len(files)}")
                    continue
            display, chunks = file_chunks(s, f, chunking_cfg)
            existing_keys.add(display)
            status = upsert_file(con, s["name"], display, h, f.stat().st_mtime, chunks)
            if status == "indexed":
                indexed += 1
            else:
                skipped += 1
            if i % 200 == 0:
                print(f"  ... {i}/{len(files)}")
        removed = delete_missing_files(con, s["name"], existing_keys)
        print(f"[{s['name']}] 新建/更新 {indexed}，未变 {skipped}，清理失效 {removed}")

    if not args.no_embed:
        vec_sources = [s["name"] for s in cfg["sources"] if s.get("vectorize")]
        if args.source:
            vec_sources = [n for n in vec_sources if n == args.source]
        pending = pending_vector_chunks(con, vec_sources)
        if pending:
            from .embedder import Embedder

            emb = Embedder(cfg)
            total = len(pending)
            print(f"待向量化 {total} 块（bge-m3，首次运行会较慢）")
            for i in range(0, total, 256):
                batch = pending[i : i + 256]
                vecs = emb.encode([t for _, t in batch])
                store_vectors(con, [cid for cid, _ in batch], vecs)
                print(f"  向量化 {min(i + 256, total)}/{total}")
        else:
            print("没有待向量化的块。")
    _print_stats(con, cfg)


def _print_stats(con, cfg):
    print("\n—— 索引统计 ——")
    rows = con.execute(
        "SELECT source, COUNT(*), SUM(vectorized) FROM chunks GROUP BY source ORDER BY source"
    ).fetchall()
    fcounts = dict(con.execute("SELECT source, COUNT(*) FROM files GROUP BY source").fetchall())
    total_c = total_v = 0
    for source, nchunks, nvec in rows:
        nvec = nvec or 0
        total_c += nchunks
        total_v += nvec
        print(f"  {source}: {fcounts.get(source, 0)} 文件 / {nchunks} 块 / {nvec} 已向量化")
    db_path = resolve_path(cfg["db_path"])
    if db_path.exists():
        size_mb = os.path.getsize(db_path) / 1048576
        print(f"  合计 {total_c} 块（{total_v} 已向量化），DB 大小 {size_mb:.1f} MB")


def cmd_search(args):
    from .retrieve import search

    cfg = load_config()
    con = open_db(cfg)
    if args.k:
        cfg = copy.deepcopy(cfg)
        cfg["retrieval"]["final_top"] = args.k
    embedder = None
    if not args.no_vector:
        from .embedder import Embedder

        embedder = Embedder(cfg)
    results = search(con, cfg, args.query, embedder)
    if not results:
        print("没有检索到结果。")
        return
    for i, c in enumerate(results, 1):
        print(f"\n#{i}  score={c['score']:.4f}")
        print(f"  {format_citation(i, c)}")
        preview = " ".join(c["text"].split())[:200]
        print(f"  {preview}")


def cmd_ask(args):
    from .embedder import Embedder
    from .qa import ask

    cfg = load_config()
    con = open_db(cfg)
    embedder = Embedder(cfg)
    chunks, stream = ask(
        cfg, con, embedder, args.question, provider=args.provider, k=args.k
    )
    if not chunks:
        print("知识库中没有检索到任何相关材料，请先运行 ioskb index 建立索引。")
        return
    print("—— 来源 ——")
    for i, c in enumerate(chunks, 1):
        print(format_citation(i, c))
    if args.show_chunks:
        print("\n—— 材料全文 ——")
        for i, c in enumerate(chunks, 1):
            print(f"\n[{i}] {c['text']}")
    print("\n—— 回答 ——")
    for piece in stream:
        print(piece, end="", flush=True)
    print()


def cmd_cards(args):
    from .cards import generate_cards
    from .embedder import Embedder

    cfg = load_config()
    con = open_db(cfg)
    embedder = Embedder(cfg)
    generate_cards(cfg, con, embedder, topics=args.topic, provider=args.provider)


def cmd_export_vectorize(args):
    from .export_vectorize import export

    cfg = load_config()
    con = open_db(cfg)
    out = resolve_path(args.output) if args.output else resolve_path("data/export/vectorize.ndjson")
    n = export(cfg, con, out)
    print(f"已导出 {n} 条向量到 {out}")


def cmd_stats(args):
    cfg = load_config()
    con = open_db(cfg)
    _print_stats(con, cfg)


def cmd_web(args):
    import threading
    import webbrowser

    import uvicorn

    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()
    print(f"iOS 知识库网页版：{url}（Ctrl+C 退出）")
    uvicorn.run("ioskb.webapp:app", host="127.0.0.1", port=args.port, log_level="warning")


def main():
    p = argparse.ArgumentParser(prog="ioskb", description="iOS 知识库：本地混合检索 + LLM 问答（回答带出处）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index", help="建立/增量更新索引")
    pi.add_argument("--no-embed", action="store_true", help="只建文本/关键词索引，跳过向量化")
    pi.add_argument("--full", action="store_true", help="忽略缓存，全量重建")
    pi.add_argument("--source", help="只处理指定 source")
    pi.set_defaults(func=cmd_index)

    ps = sub.add_parser("search", help="只检索不问答，查看召回质量")
    ps.add_argument("query")
    ps.add_argument("-k", type=int, help="返回条数")
    ps.add_argument("--no-vector", action="store_true", help="只用关键词检索（不加载模型）")
    ps.set_defaults(func=cmd_search)

    pa = sub.add_parser("ask", help="向知识库提问")
    pa.add_argument("question")
    pa.add_argument("-k", type=int, help="喂给 LLM 的材料条数")
    pa.add_argument("--provider", help="LLM 后端（deepseek / deepseek-reasoner / anthropic）")
    pa.add_argument("--show-chunks", action="store_true", help="打印检索到的材料全文")
    pa.set_defaults(func=cmd_ask)

    pc = sub.add_parser("cards", help="生成专题知识卡片")
    pc.add_argument("--topic", action="append", help="只生成指定主题（可多次）")
    pc.add_argument("--provider", help="LLM 后端")
    pc.set_defaults(func=cmd_cards)

    pe = sub.add_parser("export-vectorize", help="导出 NDJSON 供 Cloudflare Vectorize 上传")
    pe.add_argument("-o", "--output", help="输出路径（默认 data/export/vectorize.ndjson）")
    pe.set_defaults(func=cmd_export_vectorize)

    pst = sub.add_parser("stats", help="查看索引统计")
    pst.set_defaults(func=cmd_stats)

    pw = sub.add_parser("web", help="启动本地网页版（模型常驻，浏览器聊天界面）")
    pw.add_argument("--port", type=int, default=8787)
    pw.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    pw.set_defaults(func=cmd_web)

    args = p.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
