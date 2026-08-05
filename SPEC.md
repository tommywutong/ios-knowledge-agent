# ioskb 模块接口规格（冻结版 v1）

所有实现必须严格遵守本文件的函数签名与行为约定。包目录 `src/ioskb/`，Python ≥3.11。
配置见 `config.yaml`；`chunk` 在模块间以 dict 传递，字段：
`{source, type, file_path, title_path, start_line, end_line, text}`（行号 1-indexed，含首尾）。

## config.py
- `ROOT: Path` — 项目根（`config.py` 的上两级，即含 config.yaml 的目录）。
- `load_config() -> dict` — 读 `ROOT/config.yaml`，并 `load_dotenv(ROOT/'.env')`。
- `resolve_path(p) -> Path` — expanduser；相对路径按 `ROOT` 解析。

## chunker.py（纯函数，无第三方依赖）
- `markdown_chunks(text: str, max_chars: int) -> list[dict]`
  返回 `{title_path, start_line, end_line, text}`。按 ATX 标题（#..######）切分并维护标题栈，
  `title_path` 形如 `"H1 › H2 › H3"`（无标题时为 ""）。代码围栏 ``` 内的 # 不算标题。
  单节超过 max_chars 时按空行段落组进一步切分。text 包含所属标题行。跳过纯空 chunk。
- `code_chunks(text: str, max_lines: int, min_lines: int) -> list[dict]`
  按行扫描：遇到 ObjC 方法定义 `^[-+]\s*\(` 或 C 风格函数起始 `^[A-Za-z_].*\)\s*\{?\s*$`
  且当前块 ≥ min_lines 时开新块；任何块到 max_lines 强制切。title_path = 块内第一个匹配到的
  签名行（strip 后截断 80 字符），没有则 ""。

## ingest.py
- `iter_source_files(source_cfg: dict) -> list[Path]`
  按 include/exclude（glob，相对 source path）收集文件，排序返回。跳过路径中任何以 `.` 开头的目录。
- `file_chunks(source_cfg: dict, path: Path, chunking_cfg: dict) -> tuple[str, list[dict]]`
  返回 `(display_path, chunks)`，chunks 为完整 chunk dict（补齐 source/type/file_path）。
  - type：`source_cfg['type']`；若有 `type_overrides`，按文件相对路径前缀覆盖。
  - `.md`：直接读（errors='replace'）→ markdown_chunks。
  - `.docx`：pandoc 转 `ROOT/data/converted/<source_name>/<stem>.md`（目标不存在或 mtime 旧于
    docx 时重转：`pandoc -f docx -t gfm --wrap=none`），display_path 用转换后文件的绝对路径，
    再走 markdown_chunks。pandoc 失败则返回空 chunks 并 print 警告。
  - 源码后缀（.h/.m/.mm/.c/.cpp/.swift/.s，大小写归一）→ code_chunks。
  - display_path：md/源码用原文件绝对路径。

## db.py
- `open_db(cfg) -> sqlite3.Connection` — 打开 `cfg['db_path']`（resolve_path，建父目录），
  `enable_load_extension` 后加载 `sqlite_vec`，建表（IF NOT EXISTS）：
  - `files(path TEXT PRIMARY KEY, source TEXT, hash TEXT, mtime REAL, nchunks INT)`
  - `chunks(id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT, source TEXT, type TEXT,
     title_path TEXT, start_line INT, end_line INT, text TEXT, vectorized INT DEFAULT 0)`
    及 `idx_chunks_file ON chunks(file_path)`
  - `CREATE VIRTUAL TABLE chunks_fts USING fts5(tok, content='', contentless_delete=1)`（rowid=chunk id）
  - `CREATE VIRTUAL TABLE vec_chunks USING vec0(embedding float[<dim>])`（rowid=chunk id，dim 取配置）
- `tokenize_for_fts(text: str) -> str` — 含 CJK 字符时 `' '.join(jieba.cut_for_search(text))`，否则 `text.lower()`。
- `upsert_file(con, source_name, file_key: str, content_hash: str, mtime: float, chunks: list[dict]) -> str`
  返回 'skipped'（hash 未变）或 'indexed'。变更时：删除该 file_key 旧 chunks 及对应 fts/vec 行，
  插入新 chunks（含 fts），vectorized=0。file_key 用 display_path。整个操作单事务。
- `delete_missing_files(con, source_name, existing_keys: set[str]) -> int` — 清理已删除文件的记录。
- `pending_vector_chunks(con, source_names: list[str]) -> list[tuple[int, str]]` — vectorized=0 且 source 在列表中。
- `store_vectors(con, ids: list[int], vectors) -> None` — `sqlite_vec.serialize_float32` 写入，置 vectorized=1。
- `fts_search(con, query: str, top: int) -> list[tuple[int, int]]` — 对 query 做 tokenize_for_fts 后取词
  （去重、去掉长度为 1 的 ASCII 词与标点、最多 12 个、内嵌引号去掉），每词加双引号用 ` OR ` 连接，
  bm25 排序取 top，返回 (chunk_id, 名次从0起)。查询词为空或 FTS 语法错误时返回 []。
- `vec_search(con, qvec, top: int) -> list[tuple[int, int]]` — `embedding MATCH ? AND k = ?` 距离升序。
- `get_chunks(con, ids: list[int]) -> dict[int, dict]` — id → chunk 行 dict。

## embedder.py
- `class Embedder:` `__init__(self, cfg)` 懒加载；`encode(self, texts: list[str]) -> np.ndarray`
  float32、L2 归一化（`normalize_embeddings=True`），device 优先 mps，batch_size 取配置，
  encode 时 `show_progress_bar=len(texts)>32`。模型名取配置。

## retrieve.py
- `search(con, cfg, query: str, embedder=None, *, exclude_types=None) -> list[dict]`
  FTS 召回 fts_top 条；embedder 非 None 时向量召回 vector_top 条。RRF 融合：`score=Σ 1/(60+rank)`，
  再乘 `type_weights.get(type,1.0)`。按 score 排序，同一 file_path 最多 `max_per_file` 条，
  取前 `final_top` 条。exclude_types 非空时候选池放大 4 倍并过滤相应类型。返回 chunk dict 附加 `score` 字段。

## llm.py
- `get_client(cfg, provider: str|None) -> tuple[OpenAI, str]` — provider 默认取 `cfg['llm']['provider']`，
  从 `cfg['llm'][provider]` 读 base_url/model/api_key_env；key 缺失时 `raise SystemExit`（中文提示怎么配 .env）。
- `chat_stream(client, model, messages) -> Iterator[str]` — stream=True，yield 文本增量。
- `chat_with_usage(client, model, messages) -> tuple[str, dict]` — 非流式返回正文及 prompt/completion/total/cache token。

## qa.py
- `SYSTEM_PROMPT: str` — 中文。角色：iOS 知识问答助手。规则：只依据提供的材料回答；每个论点标注 [n]；
  材料不足以回答时明确说"知识库中没有足够材料"并说明缺什么；不编造；回答用中文、Markdown、
  可有代码示例；末尾不用重复来源列表（由程序打印）。
- `build_context(chunks: list[dict]) -> str` — 每块格式：
  `[n] 【<类型中文名>】<file_path> › <title_path>（第<start>-<end>行）\n<text>\n`
  类型中文名映射：note=个人笔记, doc=官方文档, wwdc=WWDC, blog=博客, source_code=源码, card=知识卡片。
- `format_citation(i: int, c: dict) -> str` — 打印用单行引用。
- `ask(cfg, con, embedder, question, provider=None, k=None) -> tuple[list[dict], Iterator[str]]`
  检索时强制 exclude_types={"card"}（k 覆盖 final_top）→ 组 messages → 返回 (chunks, 流式文本迭代器)。

## cards.py
- `load_card_topics(cfg) -> list[dict]` — 优先读取 `cards.topics_file`，兼容内联 topics。
- `generate_cards(cfg, con, embedder, topics=None, provider=None, overwrite=False) -> None`
  遍历 `card_topics.yaml`（topics 给定时过滤按 name）。每主题：对每个 query 排除 card 后检索
  （final_top 临时放大到 chunks_per_topic//len(queries)+4），合并去重（按 chunk id），
  截断到 chunks_per_topic。prompt 要求生成结构：`# <主题>`、`## 一句话总结`、`## 核心原理`、
  `## 关键细节与易错点`、`## 高频追问`。程序校验章节、引用编号和推断标记，并自动追加
  `## 原始资料索引`（文件/标题/行号）；失败自动重试一次。写
  `knowledge_cards/<group>/<name>.md`，并更新 `_generation_report.json` 的实际 token。

## card_audit.py
- `audit_cards(cfg) -> tuple[int, list[str]]` — 检查所有卡片的固定章节、正文编号、来源索引、
  原始路径存在性、禁止 card 自引用和行号边界。

## export_vectorize.py
- `export(cfg, con, out_path: Path) -> int` — 导出 vectorized=1 且 type != card 的原始 chunk 为 NDJSON，每行
  `{"id": stable_vector_id(source,path,ordinal), "values": [...], "metadata": {source,type,path,title_path,lines,text}}`
  （text 截 2000 字符；values 从 vec_chunks 读回并转 list）。返回条数。

## scripts/build_fts_v2_import.py
- `build(input_path, output_dir, *, batch_size=750, max_bytes=230MiB, start_row=0, max_rows=None)` —
  把 FTS v2 NDJSON 转为可原子切换的 D1 SQL 批次；先写 `*_next`，最后由
  `999-finalize.sql` 切换正式表。`start_row`/`max_rows` 允许把一个稳定排序导出切为互不重叠的
  D1 主库和扩展库，非法负数或零长度分片必须拒绝。

## freshness.py
- `open_readonly_db(cfg) -> sqlite3.Connection` — 以 SQLite `mode=ro` + `query_only=ON` 打开已有索引；
  不加载 sqlite-vec、不建表、不创建新数据库，索引不存在时明确报错。
- `indexed_path_for(source_cfg: dict, source_path: Path) -> str` — 不转换 DOCX 即计算稳定数据库键；
  Markdown/源码为原文件绝对路径，DOCX 为 `data/converted/<source>/<relative>.md`。
- `inspect_sources(cfg, con, source_names=None) -> tuple[FileChange, ...]` — 只读对比原文件 SHA-256
  与 `files.hash`，列出 `added`/`modified`/`deleted`；来源根路径或文件无法读取时报
  `unavailable`，不把卸载盘误判为全量删除或误报干净。不调用切块或 Embedder。
- `inspect_upstream(repo: Path) -> UpstreamStatus` — 用 `git ls-remote origin HEAD` 只读对比远端，
  不 fetch/pull、不修改本地 ref。
- `inspect_freshness(...) -> FreshnessReport` — 合并语料变化和去重后的 Git 镜像状态。
- `pull_upstream(repo: Path) -> None` — 仅对工作区干净的镜像执行 `git pull --ff-only`；
  有本地修改或无法快进时必须拒绝。

## cli.py
- `main()` — argparse 子命令：
  - `index [--no-embed] [--full] [--source NAME]`：遍历 sources（--source 过滤；--full 忽略 hash 全量重建，
    实现方式为先 DELETE 该 source 数据）；对每文件 sha256 内容 hash → upsert_file；结束后
    delete_missing_files；非 --no-embed 时对 vectorize=true 的 source 跑 pending → Embedder → store_vectors，
    分批（每批 256 条）提交并打印进度；最后打印各 source 统计。
  - `freshness [--source NAME]... [--skip-upstreams] [--json] [--check]`：只读列出语料新增/修改/
    删除和镜像远端 HEAD 差异；默认不加载 embedding；`--check` 在有差异或远端无法
    确认最新时返回状态码 1。
  - `sync [--dry-run] [--source NAME] [--no-embed] [--pull-upstreams] [--skip-upstreams]
    [--prepare-cloud]`：默认只执行本地增量索引；`--dry-run` 零写入；上游拉取必须
    显式指定且只允许 fast-forward；`--prepare-cloud` 只生成本地发布包，永不上传/导入
    Cloudflare。`--prepare-cloud` 与 `--no-embed` 互斥且必须在打开数据库前拒绝。
  - `search QUERY [-k N] [--no-vector] [--include-cards]`：默认排除 card；打印每条序号、score、引用行和预览。
  - `ask QUESTION [-k N] [--provider P] [--show-chunks]`：先打印"—— 来源 ——"引用列表，再流式打印回答。
    （--show-chunks 额外打印每块全文。）
  - `cards [--topic NAME]... [--provider P] [--force]`
  - `audit-cards`
  - `export-vectorize [-o PATH]`（默认 data/export/vectorize.ndjson）
  - `stats`：db 大小、files/chunks 计数按 source、vectorized 计数。
  - embedder 仅在需要时构造；`index --no-embed`、`search --no-vector`、FTS-only 场景不得加载模型。
