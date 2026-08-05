# HANDOFF —— 交接文档（给任何接手的 AI 或人）

> 新会话先读 `AGENTS.md`，再读本文件 + `SPEC.md` + `PROGRESS.md`。
> 最后更新：2026-08-05（网站 `101cf86` 已推送并完成 Pages 部署，混合路由及独立重试超时已完成线上复核）

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
| obsidian-ios | /Users/tommywu/Obsidian/iOS | 当前 57 篇高质量中文专题笔记（核心资产，会继续变化） | 全量向量+FTS |
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
问答:  问题 → 规划（最多 4 条查询）→ Vectorize top48 + D1 FTS v2 双路 top60
        → RRF 去重 → reranker 前30 → top8 anchor → 邻块扩展 → DeepSeek → 流式回答 + 引用列表
```

- **SQLite 单文件**（db/ios_kb.sqlite）：不引入任何数据库服务，好备份好迁移。
- **bge-m3**：中英混合检索质量好，本地跑（MPS），与 Cloudflare Workers AI 同款（第三阶段云端查询向量兼容）。
  首次安装单独下载模型；日常 `Embedder` 强制从本地缓存加载，不访问 Hugging Face。
- **jieba**：FTS5 默认分词不支持中文，入库和查询都先 jieba 分词再进 FTS。英文文本走 fast path 不过 jieba。
- **双路召回**：语义问题靠向量，`objc_msgSend` 这类精确符号靠 FTS，RRF 融合；v2
  额外保留 `file_key + chunk_ordinal` 邻接索引，避免扩展上下文时扫描整张 FTS。
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

**第一阶段及 2026-08-04 增量同步（已完成）**：全部代码 + 用当前资料实测全链路。当前快照：

| source | 文件 | 块 | 向量 |
|---|---:|---:|---:|
| obsidian-ios | 57 | 1,738 | 1,738 |
| summer2026 | 281 | 8,249 | 8,249 |
| summer-labs | 4 | 11 | 11 |
| objc4-source | 380 | 1,680 | 1,680 |
| apple-docs-core | 2,491 | 33,284 | 33,284 |
| apple-docs-bulk | 98,164 | 505,374 | 0（按设计仅 FTS） |
| apple-archive | 40,262 | 517,561 | 0（按设计仅 FTS） |
| knowledge-cards | 95 | 1,192 | 1,192 |
| **合计** | **141,734** | **1,069,089** | **46,154** |

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

**第三阶段（网站问答接口，Retrieval v2 已完成代码、数据和生产发布）**：用户网站是 `/Users/tommywu/tommywu-lab`
（Astro 7 静态博客，Cloudflare Pages 部署）。当前生产版已完成：
1. `uv run ioskb export-vectorize` 导出 44,962 条稳定 `v1-*` ID（本地 bge-m3 向量 + 出处 metadata）；
2. Cloudflare Vectorize `ios-kb` 已用 `upsert` 同步，远端旧数字 ID 已清理；
3. D1 Retrieval v2 已按 `data/export/ios_fts_v2/000.sql`–`115.sql` 导入并用
   `999-finalize.sql` 原子切换：`ios_ask_fts_v2` 和 `ios_ask_fts_v2_neighbors` 各 `86,307` 行。
   v2 导入后数据库达到 `513 MB` 并触发最大大小限制，已移除重复的旧 `ios_ask_fts`，当前约 `338 MB`；
   旧表可由本地 `data/export/ios_fts/` 或 D1 Time Travel 恢复；
4. Pages Function 使用 Workers AI `@cf/baai/bge-m3` → Vectorize + D1 FTS v2，最多 4 路
   查询规划、RRF 合并、`@cf/baai/bge-reranker-base` 重排和邻块扩展，返回段落级引用；
5. API 有用户/管理员限流、知识回答引用校验、反馈审计和断流状态；前端不保存未完成回答到后续上下文，并随历史回传上一轮真实的 `knowledge`/`general` 模式；
6. iOS 问题有可靠证据时走 `knowledge` 模式；没有可靠证据时返回 `422 no_evidence` 并退款，
   不调用 DeepSeek；检索故障返回 `503` 并退款。`hi`、你好等纯问候跳过检索，由后端直接
   返回用户指定的固定助手介绍；`谢谢`、`你真棒` 等纯感谢/夸赞以及 `收到`、`明白了` 等确认语也由后端确定性回复，即使上一轮
   是 iOS 问题也不会继承检索意图；这些回复均不调用模型且不占每日额度。非 iOS 问题走 `general` 模式；
   前端不再用 `sessionStorage` 保存或恢复聊天记录，聊天窗口每次从关闭状态重新打开时为空；同一次打开期间仍保留多轮追问上下文，“新建对话”仍可手动清空当前会话；
7. DeepSeek 默认模型是 `deepseek-v4-flash`，生产没有 `DEEPSEEK_MODEL` 覆盖项；知识模式和通用模式均按问题复杂度组织回答，复杂问题展开机制、条件、示例和常见误区，API `max_tokens` 为 `2400`；
8. 生产 Vectorize `ios-kb` 为 44,962 条；D1 v2 两张表各 86,307 行，旧 v1 表因空间限制已移除；
9. 当前轮次先分为问候、感谢、确认、新问题、追问，再决定领域与是否继承历史。明确 iOS 必须检索，明确普通问题不检索，边界技术问题先证据探测；只有明确指代的追问继承相关上下文，新话题隔离旧历史；
10. 检索排序在网站层落实 `26暑期内容`/官方文档/源码并列第一、个人笔记第二、技术博客第三。引用解析兼容组合及中文格式并统一为 `[n]`；越界引用会移除，但不再伪造来源或自动补 `[1]`，最终无有效引用则退款报错；
11. DeepSeek 首次空流或在输出正文前断流时重试一次；每次尝试重新创建中止控制器并获得独立 50 秒超时。生产自测脚本支持 `IOS_SELF_TEST_CASES` 按用例定向运行；
12. 网站功能代码与文档已按 clean-commit 拆分提交，混合对话重构为 `0818ba0`，独立重试超时修复为 `101cf86`，均已快进推送到网站 `main`/`origin/main`；
13. GitHub Actions 的 Code quality、Build and Check、Deploy to Cloudflare Pages 全部成功；
    最新 Pages production deployment 为 `https://3504e14d.tommywu-lab.pages.dev`（source `101cf86`），自定义域名
    `https://www.tommywutong.cn/api/ios-ask` 与预览地址均返回 HTTP 200、`configured: true`。
14. 网站内置生产自测入口 `pnpm ios-self-test:production`，现含 10 个混合场景并支持 `IOS_SELF_TEST_CASES` 定向运行。
    `101cf86` 在自定义域名的首轮全套运行中，6 项直接通过，4 项因本机网络中断或模型引用门被拦；随后定向复测
    weak、ARC、general、new-ios-topic-after-ios 四项全部通过。10 项均已在同一生产版逐项通过，但不是一次连续 10/10。

当前跨仓库同步点：

- 本仓库 `/Users/tommywu/Desktop/iOS知识agentt`：Retrieval v2 功能与导出脚本已提交为 `ccbeabf`、
  `024f4aa` 并快进推送到 `main`/`origin/main`；
- 网站仓库 `/Users/tommywu/tommywu-lab`：Retrieval v2 及后续修复已提交至 `101cf86`，并快进推送到
    `main`/`origin/main`；
- 生产站点：`https://www.tommywutong.cn`；本轮 Pages production 部署为 `https://3504e14d.tommywu-lab.pages.dev`（source `101cf86`）；
- 两个地址的公开 API 健康检查均显示 HTTP 200、`configured: true`；macOS 钥匙串中的生产自测 token
  可用于自定义域名的受控登录态自测且不会写入仓库。最新版 10 个场景均逐项通过；首轮全套有 4 项失败后定向复测通过，
  不要记成一次连续运行 10/10。

问候语固定回复全文：`Hi`、`hi`、你好等纯问候只回复
`我是TommyWu的ai学习助手，有什么可以帮你吗？无论是iOS、日常聊天还是其他问题，都可以告诉我`。
该回复不调用 DeepSeek、不消耗每日 2 次额度，但仍记录请求指标并受每小时防刷限制。
纯感谢/夸赞固定回复全文：`谢谢`、`你真棒` 等独立表达只回复
`谢谢你的认可！有问题继续问我就好。`；同样不调用 DeepSeek、不消耗每日额度，且不会继承上一轮 iOS 检索意图。
确认语固定回复全文：`收到`、`明白了` 等只回复 `好的，有问题继续问我就好。`；同样不调模型、不消耗每日额度。
聊天记录不写入 `sessionStorage`；每次重新打开聊天窗口都会从空白会话开始，不能因上一次会话输入过 `hi` 而自动显示固定问候；同一次打开期间的多轮上下文只存在当前页面内。
回答风格：简单问题直接回答；复杂 iOS 问题必须完整展开机制、条件、实践影响、示例和常见误区，避免只给几句概括；DeepSeek 输出上限为 `2400` tokens。
终端没有浏览器 Cookie；生产自测使用 macOS 钥匙串中的专用 Bearer token。不要把 API 级登录态
定向复核冒充为浏览器 Cookie 登录流程，也不要把“首轮 6 项 + 定向 4 项”写成一次连续 10/10。

资料更新时：重新导出并 `wrangler vectorize upsert ios-kb --file=...`，先列出远端 ID 做备份，
再删除本次导出不存在的 stale ID；运行 `uv run ioskb export-fts` 生成 `data/export/ios_fts_v2/`，
依次导入 `000.sql`–`115.sql`，核对 `*_next` 各 86,307 行后执行 `999-finalize.sql`。若接近 D1 大小上限，
不要创建可选诊断表阻断问答；v1 回滚需先恢复旧表再设置 `IOS_RETRIEVAL_VERSION=v1`。

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
