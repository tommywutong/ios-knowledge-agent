import argparse
import copy
import hashlib
import json
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
    vectorized_sources = {
        source["name"] for source in cfg["sources"] if source.get("vectorize")
    }
    total_c = total_v = 0
    for source, nchunks, nvec in rows:
        nvec = nvec or 0
        total_c += nchunks
        total_v += nvec
        suffix = (
            f" / {nchunks - nvec} 待向量化"
            if source in vectorized_sources and nchunks > nvec
            else ""
        )
        print(
            f"  {source}: {fcounts.get(source, 0)} 文件 / {nchunks} 块 / "
            f"{nvec} 已向量化{suffix}"
        )
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
    excluded = set() if args.include_cards else {"card"}
    results = search(con, cfg, args.query, embedder, exclude_types=excluded)
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
    generate_cards(
        cfg,
        con,
        embedder,
        topics=args.topic,
        provider=args.provider,
        overwrite=args.force,
    )


def cmd_audit_cards(args):
    from .card_audit import audit_cards

    cfg = load_config()
    checked, errors = audit_cards(cfg)
    print(f"已审计 {checked} 张知识卡片。")
    if errors:
        print(f"发现 {len(errors)} 个问题：")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)
    print("结构、引用编号、原始路径和行号边界全部通过。")


def cmd_export_vectorize(args):
    from .export_vectorize import export

    cfg = load_config()
    con = open_db(cfg)
    out = resolve_path(args.output) if args.output else resolve_path("data/export/vectorize.ndjson")
    n = export(cfg, con, out)
    print(f"已导出 {n} 条向量到 {out}")


def cmd_export_fts(args):
    from .export_fts import export

    cfg = load_config()
    con = open_db(cfg)
    out = resolve_path(args.output) if args.output else resolve_path("data/export/fts-v2.ndjson")
    manifest = export(
        cfg,
        con,
        out,
        tier1_limit=args.tier1_limit,
        per_file_limit=args.per_file_limit,
        tier1_per_source_limit=args.tier1_per_source_limit,
        total_limit=args.total_limit,
    )
    counts = manifest["counts"]
    print(
        f"已导出 {counts['exported']} 条 FTS v2 记录到 {out} "
        f"（Tier 0: {counts['tier0']}，Tier 1: {counts['tier1']}）"
    )


def cmd_stats(args):
    cfg = load_config()
    con = open_db(cfg)
    _print_stats(con, cfg)


def _selected_source_names(cfg, requested):
    if not requested:
        return None
    names = {source["name"] for source in cfg["sources"]}
    unknown = sorted(set(requested) - names)
    if unknown:
        raise SystemExit(f"config.yaml 中没有名为 {', '.join(unknown)} 的 source")
    return set(requested)


def _print_freshness(report):
    labels = {
        "added": "新增",
        "modified": "修改",
        "deleted": "删除",
        "unavailable": "无法检查",
    }
    print("—— 资料新鲜度 ——")
    print(
        f"新增 {report.added}，修改 {report.modified}，删除 {report.deleted}，"
        f"无法检查 {report.unavailable}"
    )
    for change in report.changes:
        print(f"  [{change.source}] {labels[change.status]}: {change.path}")
    if not report.changes:
        print("  本地资料与索引一致。")
    if report.upstreams:
        print("—— Git 上游镜像 ——")
    upstream_labels = {
        "up_to_date": "已是最新",
        "update_available": "远端有新提交",
        "unavailable": "无法检查",
    }
    for upstream in report.upstreams:
        suffix = f"：{upstream.detail}" if upstream.detail else ""
        print(f"  {upstream.path}: {upstream_labels[upstream.status]}{suffix}")


def cmd_freshness(args):
    from .freshness import inspect_freshness, open_readonly_db

    cfg = load_config()
    source_names = _selected_source_names(cfg, args.source)
    con = open_readonly_db(cfg)
    try:
        report = inspect_freshness(
            cfg,
            con,
            source_names=source_names,
            check_upstreams=not args.skip_upstreams,
        )
    finally:
        con.close()
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        _print_freshness(report)
    if args.check and not report.clean:
        raise SystemExit(1)


def cmd_sync(args):
    from .freshness import (
        discover_upstream_repositories,
        inspect_freshness,
        open_readonly_db,
        pull_upstream,
    )

    cfg = load_config()
    source_names = _selected_source_names(cfg, args.source)
    if args.prepare_cloud and args.no_embed:
        raise SystemExit("--prepare-cloud 不能与 --no-embed 同时使用，先补齐本地向量。")
    con = open_readonly_db(cfg)
    try:
        before = inspect_freshness(
            cfg,
            con,
            source_names=source_names,
            check_upstreams=not args.skip_upstreams,
        )
    finally:
        con.close()
    _print_freshness(before)
    if args.dry_run:
        print("\n预演完成：未拉取上游、未写入索引、未生成或发布云端数据。")
        return

    if args.pull_upstreams:
        for repo in discover_upstream_repositories(cfg, source_names):
            print(f"\n快进更新上游镜像：{repo}")
            pull_upstream(repo)

    index_args = argparse.Namespace(
        source=args.source[0] if args.source else None,
        full=False,
        no_embed=args.no_embed,
    )
    cmd_index(index_args)

    con = open_readonly_db(cfg)

    try:
        if args.prepare_cloud:
            from .export_fts import export as export_fts
            from .export_vectorize import export as export_vectorize

            vector_out = resolve_path("data/export/vectorize.ndjson")
            fts_out = resolve_path("data/export/fts-v2.ndjson")
            vectors = export_vectorize(cfg, con, vector_out)
            manifest = export_fts(cfg, con, fts_out)
            print(
                f"\n已生成本地发布包：{vectors} 条向量，"
                f"{manifest['counts']['exported']} 条 FTS。"
            )
            print("未连接 Cloudflare，未修改任何远端数据。")

        after = inspect_freshness(
            cfg,
            con,
            source_names=source_names,
            check_upstreams=False,
        )
    finally:
        con.close()
    if after.changes:
        print("\n同步后仍有本地差异：")
        _print_freshness(after)
        raise SystemExit(1)
    print("\n本地增量同步完成；云端数据未发布。")


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
    ps.add_argument(
        "--include-cards",
        action="store_true",
        help="同时检索模型生成的卡片（默认只显示可作为证据的原始资料）",
    )
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
    pc.add_argument("--force", action="store_true", help="覆盖并重新生成已存在的卡片")
    pc.set_defaults(func=cmd_cards)

    pac = sub.add_parser("audit-cards", help="审计知识卡片的结构与原始资料引用")
    pac.set_defaults(func=cmd_audit_cards)

    pe = sub.add_parser("export-vectorize", help="导出 NDJSON 供 Cloudflare Vectorize 上传")
    pe.add_argument("-o", "--output", help="输出路径（默认 data/export/vectorize.ndjson）")
    pe.set_defaults(func=cmd_export_vectorize)

    pf = sub.add_parser("export-fts", help="导出网站 FTS v2 精选文本索引")
    pf.add_argument("-o", "--output", help="输出路径（默认 data/export/fts-v2.ndjson）")
    pf.add_argument("--tier1-limit", type=int, default=80_000, help="FTS-only 精选上限")
    pf.add_argument("--per-file-limit", type=int, default=24, help="单文件 Tier 1 上限")
    pf.add_argument(
        "--tier1-per-source-limit",
        type=int,
        default=60_000,
        help="单 source 的 Tier 1 上限，避免大型归档挤占全部候选",
    )
    pf.add_argument(
        "--total-limit",
        type=int,
        default=124_997,
        help="生产 D1 两库总容量上限；Tier 0 增长时自动压缩 Tier 1",
    )
    pf.set_defaults(func=cmd_export_fts)

    pst = sub.add_parser("stats", help="查看索引统计")
    pst.set_defaults(func=cmd_stats)

    pfr = sub.add_parser("freshness", help="只读检查资料和上游镜像是否有更新")
    pfr.add_argument("--source", action="append", help="只检查指定 source（可多次）")
    pfr.add_argument("--skip-upstreams", action="store_true", help="不访问 Git 远端")
    pfr.add_argument("--json", action="store_true", help="输出 JSON 报告")
    pfr.add_argument("--check", action="store_true", help="有任何差异时以状态码 1 退出")
    pfr.set_defaults(func=cmd_freshness)

    psy = sub.add_parser("sync", help="安全编排本地增量同步（默认不发布云端）")
    psy.add_argument("--dry-run", action="store_true", help="只显示将发生的变化")
    psy.add_argument("--source", action="append", help="只同步指定 source（当前最多一个）")
    psy.add_argument("--no-embed", action="store_true", help="只更新文本/FTS，不加载 embedding")
    psy.add_argument("--pull-upstreams", action="store_true", help="显式快进拉取 Git 资料镜像")
    psy.add_argument("--skip-upstreams", action="store_true", help="不访问 Git 远端")
    psy.add_argument(
        "--prepare-cloud",
        action="store_true",
        help="只生成本地云端发布包，不上传、不导入",
    )
    psy.set_defaults(func=cmd_sync)

    pw = sub.add_parser("web", help="启动本地网页版（模型常驻，浏览器聊天界面）")
    pw.add_argument("--port", type=int, default=8787)
    pw.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    pw.set_defaults(func=cmd_web)

    args = p.parse_args()
    if args.cmd == "sync" and args.source and len(args.source) > 1:
        p.error("sync --source 当前最多指定一次")
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
