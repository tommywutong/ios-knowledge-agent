# HANDOFF —— 交接文档（给任何接手的 AI 或人）

> 读完本文件 + `SPEC.md` + `PROGRESS.md`，你就拥有继续这个项目所需的全部上下文。
> 最后更新：2026-08-02（本地索引、网站接口和生产同步完成）

## 1. 这个项目是什么

TommyWu（iOS 学习者，大二）要把自己的 iOS 资料建成带引用溯源的 RAG 问答系统：
问"给我讲讲 RunLoop"，得到基于**他自己的资料**的回答，并标注每个结论出自哪个文件哪一段（精确到行号）。

设计约束（重要，不要违背）：
- **日常运行不依赖 Claude**：Claude 会员可能断。重活（写代码、总结卡片）现在做完；
  日常问答只用 DeepSeek API（便宜）+ 本地 embedding 模型（免费）。
- 知识卡片生成脚本必须同时支持 DeepSeek 和 Claude 后端。
- 不修改用户的原始资料（笔记目录只读）。

## 2. 语料来源

| source 名 | 位置 | 内容 | 处理方式 |
|---|---|---|---|
| obsidian-ios | /Users/tommywu/Obsidian/iOS | 当前 56 篇高质量中文专题笔记（核心资产，会继续变化） | 全量向量+FTS |
| summer2026 | /Users/tommywu/Desktop/26暑期内容 | iOS 基础/进阶文章、Tips、实验说明及 docx 笔记 | docx 经 pandoc 转 md，全量向量+FTS；排除 `articles/ai/` 下 17 篇纯 AI 文章 |
| summer-labs | /Users/tommywu/Desktop/26暑期内容 | MemoryMapLab 等活跃实验源码 | Objective-C/C/C++/Swift/汇编按源码切块并向量+FTS |
| objc4-source | 同上 /iOS底层源码探索 | objc4 源码（含 Swift/汇编；排除两个旧版重复目录） | 按函数切块，type=source_code 降权 |
| apple-docs-core | data/repos/apple-docs-vault 的 wwdc/+blogs/ | WWDC 逐字稿+博客（含中文翻译） | 向量+FTS，子目录映射类型 |
| apple-docs-bulk | 同仓库 apple-docs/+oss/+meta/ | 大体量文档与源码镜像 | **只进 FTS**（全量向量耗时和体积不划算） |
| apple-archive | data/repos/apple-developer-archive-vault | 英文 Apple 历史官方文档归档 | **只进 FTS 关键词索引**（量太大，向量不划算） |
| knowledge-cards | knowledge_cards/ | 95 张细粒度专题卡片（回灌） | 向量+FTS；只用于复习/浏览，问答证据强制排除 |

两个 repo 是浅 clone（--depth 1），更新用 `git -C data/repos/<name> pull`。

## 3. 架构与技术选型（以及为什么）

```
建库:  资料 → ingest(清洗/pandoc/切块+元数据) → SQLite 单文件
                                        ├─ chunks 表（正文+出处元数据）
                                        ├─ chunks_fts（FTS5 关键词，jieba 分词）
                                        └─ vec_chunks（sqlite-vec 向量，bge-m3 1024维）
问答:  问题 → bge-m3 向量召回 + FTS 召回 → 排除 type=card → RRF 融合(k=60) × 类型权重 → top8
        → 拼 prompt（材料带 [n] 编号+出处）→ DeepSeek → 流式回答 + 引用列表
```

- **SQLite 单文件**（db/ios_kb.sqlite）：不引入任何数据库服务，好备份好迁移。
- **bge-m3**：中英混合检索质量好，本地跑（MPS），与 Cloudflare Workers AI 同款（第三阶段云端查询向量兼容）。
  首次安装单独下载模型；日常 `Embedder` 强制从本地缓存加载，不访问 Hugging Face。
- **jieba**：FTS5 默认分词不支持中文，入库和查询都先 jieba 分词再进 FTS。英文文本走 fast path 不过 jieba。
- **双路召回**：语义问题靠向量，`objc_msgSend` 这类精确符号靠 FTS，RRF 融合。
- **增量索引**：files 表存内容 sha256，没变就跳过；删除的文件会被清理。

模块接口的唯一权威定义在 `SPEC.md`。目录结构：

```
config.yaml          # 语料来源/检索参数/LLM后端/卡片参数
card_topics.yaml     # 95 个细粒度卡片主题及检索查询
.env                 # DEEPSEEK_API_KEY（用户自填，gitignored）
src/ioskb/           # config/chunker/ingest/db/embedder/retrieve/llm/qa/cards/export_vectorize/cli
db/ios_kb.sqlite     # 索引库（gitignored，可随时重建）
data/repos/          # 两个 clone 的资料仓库（gitignored）
data/converted/      # docx→md 转换缓存；docx 的引用行号指向这里的文件
knowledge_cards/     # 生成的专题卡片
```

常用命令见 `README.md`。

另有本地网页版：`ioskb web`（src/ioskb/webapp.py + web_static/index.html），FastAPI，
模型常驻内存、NDJSON 流式回答、多轮追问、来源点击经 `/api/open` 跳 Obsidian/访达；
桌面 `iOS知识库.command` 双击启动，端口 8787。博客版部署计划：`website-templates/DEPLOY_PLAN.md`。

## 4. 三个阶段

**第一阶段及 2026-08-02 增量同步（已完成）**：全部代码 + 用当前资料实测全链路。当前快照：

| source | 文件 | 块 | 向量 |
|---|---:|---:|---:|
| obsidian-ios | 56 | 1,730 | 1,730 |
| summer2026 | 281 | 8,249 | 8,249 |
| summer-labs | 4 | 11 | 11 |
| objc4-source | 380 | 1,680 | 1,680 |
| apple-docs-core | 2,491 | 33,284 | 33,284 |
| apple-docs-bulk | 98,164 | 505,374 | 0（按设计仅 FTS） |
| apple-archive | 40,262 | 517,561 | 0（按设计仅 FTS） |
| knowledge-cards | 95 | 1,191 | 1,191 |
| **合计** | **141,733** | **1,069,080** | **46,145** |

当前 `db/ios_kb.sqlite` 约 1.9GB。95 张卡片已生成并通过
`ioskb audit-cards` 全量审计；生成报告记录实际 650,630 tokens。
2026-07-29 同步到的仓库提交：apple-docs-vault `fcbf992d`，
apple-developer-archive-vault `c0fc987f`。

**第二阶段（资料以后再次更新或维护卡片时，零 Claude 依赖）**：
```bash
git -C data/repos/apple-developer-archive-vault pull
git -C data/repos/apple-docs-vault pull
uv run ioskb index          # 资料变化后增量更新
uv run ioskb cards                              # 只生成缺少的卡片
uv run ioskb cards --topic <主题> --force        # 覆盖重生成单卡
uv run ioskb audit-cards                        # 审计原始来源与行号
uv run ioskb index --source knowledge-cards     # 卡片回灌
```

**第三阶段（网站问答接口，已完成）**：用户网站是 `/Users/tommywu/tommywu-lab`
（Astro 7 静态博客，Cloudflare Pages 部署）。当前生产版已完成：
1. `uv run ioskb export-vectorize` 导出 44,954 条稳定 `v1-*` ID（本地 bge-m3 向量 + 出处 metadata）；
2. Cloudflare Vectorize `ios-kb` 已用 `upsert` 同步，远端旧数字 ID 已清理；
3. D1 的 `ios_ask_fts` 已按 SQL 批次原子切换，最终行数与导出一致；
4. Pages Function 使用 Workers AI `@cf/baai/bge-m3` → Vectorize + D1 FTS → DeepSeek，
   按 authority、关键词覆盖率和语义阈值排序，并返回带行号、来源类型和置信度的引用；
5. API 有用户/管理员限流、无证据拒答、回答引用校验、反馈审计和断流状态；前端不保存未完成回答到后续上下文；
6. 部署前通过 `pnpm exec tsc --noEmit`、`pnpm check`、`pnpm build` 和 `pnpm audit --prod`。

资料更新时：重新导出并 `wrangler vectorize upsert ios-kb --file=...`，先列出远端 ID 做备份，
再删除本次导出不存在的 stale ID；D1 依次执行 `data/export/ios_fts/*.sql`，最后执行 `999-finalize.sql`。

## 5. 已知注意点 / 坑

- DeepSeek **没有 embedding API**，这就是为什么 embedding 必须本地（或第三阶段用 Workers AI）。
- bge-m3 首次下载后，日常加载使用 `local_files_only=True` + `HF_HUB_OFFLINE=1`；断网可索引、检索。
- FTS5 contentless_delete=1 需要 SQLite ≥3.43（Python 3.13 自带的满足）。
- docx 的引用行号对应 `data/converted/` 下转换后的 md，不是原 docx。
- apple-archive 没有向量：纯语义问题可能搜不到它，属预期取舍（它主要靠关键词兜底）。
- 原始资料是唯一事实证据：`ask`、网页、默认 `search` 和 Vectorize 导出都排除 type=card。
- 卡片的来源索引由程序从检索块写入，不接受模型自行生成；卡片不能递归引用其他卡片。
- `ioskb index` 首次全量跑 embedding 需要较久（objc4 + apple-docs-vault 块多），属一次性成本。
- 16GB Mac 上 bge-m3 的 `batch_size` 保持 8；提高到 16 会在大批量更新时造成明显交换空间压力。
- Markdown 切块必须保证 `max_chars` 硬上限；不要删除超长单行、多空行、窗口边界三个回归测试。
- 用户全局规则：始终中文回复、称呼 "TommyWu"、写码前先讨论方案、提交走 clean-commit skill。

## 6. 接手时核对

1. `uv run ioskb stats` 应能读出上面的快照（资料后续变化时数字允许增加）；
2. `uv run python -m unittest discover -s tests -v` 应全部通过；
3. `uv run ioskb index` 是安全的增量更新：未变文件跳过，新增/修改重建，删除文件清理；
4. `uv run ioskb search "RunLoop mach_msg_trap"` 可免费验证混合检索；
5. `uv run ioskb web` 后访问 `/api/status`，确认 `model_ready=true`；
6. 不要为了普通验证调用 `ask` 或 `cards`：这两个命令会使用 DeepSeek API token。
