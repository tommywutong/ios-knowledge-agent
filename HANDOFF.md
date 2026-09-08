# HANDOFF —— 交接文档（给任何接手的 AI 或人）

> 新会话先读 `AGENTS.md`，再读本文件 + `SPEC.md` + `PROGRESS.md`。
> 最后更新：2026-09-08（P0 门禁锚点/夹具已补齐；网站残余修复待发布）

## 1. 这个项目是什么

**最新生产状态（2026-09-07）**：网站仓库 `tommywu-lab` 的 `main` 已合并到 `9ce55d7`，GitHub Actions `34125568913` 全部通过，Cloudflare Pages production 为 `https://280999a7.tommywu-lab.pages.dev`，自定义域名 `https://www.tommywutong.cn` 指向同一生产配置。两处首页/API 均 HTTP 200，公开 GET `configured: true`。原网站工作区仍在 `fix/chat-input-initial-height`，用户未提交首页和素材保持原样；所有网站改动均在隔离副本完成。

**本地评测门禁（2026-09-08）**：`scripts/run_production_eval.py` 支持显式 `--gate`。预检门禁要求知识题的预期锚点存在于当前本地索引、所有追问有已审核的前置夹具，且不遗留标记为人工复核的用例；`--live --gate` 还要求每个已运行用例均为 `passed`，失败或跳过都会返回非零。普通运行仍只报告诊断。8 条 P0 objc4 锚点已迁移至 `objc4-951.7`，2 条追问夹具已补齐；当前门禁仅阻断 10 条人工复核用例：`pem-000018` 至 `pem-000023` 需要审核追问语境，`pem-000028` 至 `pem-000031` 需要审核平台/实验局限。55 项知识库测试和两批候选校验器通过；未触碰生产数据或原始资料。

本次网站修复包含 `81ac3ce`（Apple 专有 API 路由、证据覆盖阈值、跨平台双侧证据）和 `9ce55d7`（v1 兼容检索路径复用命名 Apple API 证据闸门）。部署后关键 P0 复测为 3/5 通过：ARKit、Core ML、Android Handler vs iOS RunLoop 正确 `422 no_evidence`；WidgetKit 一次返回无 `done` 的异常流，Kotlin vs GCD 仍误进 `knowledge`。后续修复位于隔离分支 `codex/fix-ios-stream-and-cross-platform` 的 `3dd5617`：终结事件由幂等 `finish` 统一发送/关闭，跨平台比较要求双方证据；25 项检索测试、15 项 API 测试、TypeScript、完整构建通过。该补丁尚未推送或部署，因此生产结论不变。详见 `data/evaluation-results/production-eval-key-cases-20260907.json`，报告不含回答正文。

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
| summer2026 | /Users/tommywu/Desktop/26暑期内容 | iOS 基础/进阶文章、Tips、实验说明及 docx 笔记 | docx 经 pandoc 转 md，全量向量+FTS；排除 `articles/ai/` 下 17 篇纯 AI 文章及整个 `ios-source-learning/**` 工作区 |
| summer-labs | /Users/tommywu/Desktop/26暑期内容 | MemoryMapLab 等活跃实验源码 | Objective-C/C/C++/Swift/汇编按源码切块并向量+FTS；明确排除 `iOS底层源码探索/**` 和 `ios-source-learning/**` |
| objc4-source | /Users/tommywu/Desktop/26暑期内容/ios-source-learning/new objc4 | objc4-951.7（Apple 公开源码） | 向量+FTS；替代旧探索目录的 objc4-951.1，避免跨版本 Runtime 证据混用 |
| ios-source-maps | 同上 /maps | 28 份手写源码地图（版本、符号、文件、行号导航） | 向量+FTS 仅供本地 `search` 导航；排除问答上下文和云端导出 |
| apple-cf-source / apple-libdispatch-source | 同上 /CF-1153.18-apple、/libdispatch-apple | CF-1153.18 与 Apple libdispatch drop | FTS-only 的 Apple 公开源码；精确符号检索优先源码块 |
| swift-*-reference | 同上 /swift-corelibs-foundation、/swift-foundation、/libdispatch | Swift 开源/跨平台实现 | FTS-only 参照实现；不可表述为 iOS 私有实现 |
| gnustep-reference | 同上 /gnustep-base | GNUstep base 1.31.1 | FTS-only、明确非 Apple；仅作未开源 Foundation ObjC 细节的参照 |
| *-source（四个第三方库） | 同上 /third-party | AFNetworking 4.0.1、JSONModel 1.8.0、YYModel 1.0.4、SDWebImage 5.21.7 | FTS-only；只说明对应固定版本的库实现 |
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

**2026-09-07 源码学习工作区本地融合（未发布生产）**：`ios-source-learning` 根仓库已同步到 `215ba1a`，
`bootstrap.sh --check` 确认 eleven source trees 与地图链接均就位。知识库以受控来源接入 2,031 个文件 / 17,586 块：
`objc4-951.7`（975 块）和 28 份地图（173 块）为向量+FTS，其余 16,438 块源码为 FTS-only；源码地图、卡片均被程序排除出最终问答和 Cloudflare 导出。精确符号会给实际源码块加分，`CFRunLoopRunSpecific` 已实测首命中 `CFRunLoop.c`。同时从 `summer2026` 清理曾误入库的 154 个工作区 Markdown 文件。当前本地 `1,092,820` 块 / `52,511` 向量，`PRAGMA quick_check=ok`、受控来源 freshness clean、55 项测试通过。生产 Vectorize/D1/Pages **未变**；需先按稳定 ID 流程重新导出、审计容量、更新网站的类型展示和生产评测，不能把本地结果视为已上线。`check-updates.sh` 仍报告 Swift Foundation 有远端更新且 CF/corelibs 远端探测失败，本轮以已核对的本地 commit 为准。

**2026-09-06 维护状态（生产数据已发布，本地清理待下次生产发布）**：两个 Git 镜像已更新，本地文件/FTS 增量索引已完成；
`summer-labs` 曾误扫入 `ios-source-learning` 的依赖与源码树，现已通过配置排除并清理
3,469 个文件。随后离线评测发现 `summer2026` 的 `ios-basics/` 有 32 个已删除文件仍留在本地索引；
已用 `uv run ioskb sync --source summer2026 --no-embed` 清理 1,521 个块。当前本地数据库为
1,079,177 块、55,306 块已向量化，待向量化为 0；`freshness --source summer2026 --skip-upstreams --check`
clean。生产 Vectorize 仍是清理前的 55,635 条，
新主 D1 正式 FTS/邻接表各 84,818 行，归档 D1 各 40,000 行，并已将 Pages `IOS_DB` 切换到
`tommywu-ios-kb-primary-20260905`。首页与公开 GET 均为 HTTP 200、`configured: true`；
认证 POST 在 2026-09-05 曾因导入触发 Cloudflare 免费套餐当日 D1 写入额度耗尽而返回 HTTP 500；
额度恢复后于 2026-09-06 00:13（Asia/Shanghai）重跑，11/11 场景全部通过。

**GLM 离线评测批次（2026-09-06）**：`data/glm/overnight-rag-evaluation-20260906/` 保存 3,143 行
候选资产（评测题、术语别名、资料质量发现、FTS-only 样本和失败归因），用
`uv run python scripts/validate_glm_batch.py data/glm/overnight-rag-evaluation-20260906` 复核。
它不是生产回归集：1,381 条标题模板题必须先人工确认题面与锚定小节相符，且本地 FTS-only 结果不能
推断生产 Vectorize/RRF/reranker 效果。`CODEX_REVIEW.md` 记录了这些边界和本地清理结果。

**2026-09-07 生产评测基线（仅评测，未改生产）**：`scripts/run_production_eval.py` 将经审核的
130 条 manifest、证据账本、判分契约及 45 对反例输入做一致性预检；`--live` 模式才读取现有生产自测
Bearer token，先验证 `/api/ios-ask` 的 `configured/authenticated/unlimited`，并将不含回答正文的报告写入
Git 忽略的 `data/evaluation-results/`。P0 首测报告 `production-eval-20260907-123525.json` 为 6 passed /
23 failed / 2 skipped：8 个精确 objc4 符号题大多仍锚定旧生产的 objc4 快照；4 个有夹具的追问未命中
指定专题锚点；`pem-000001` 实际命中同一 WWDC 2021/10133 的中文译文（149-153 行），而账本锚定英文
281-295 行。工具现以显式、人工核实的同场次中英映射接受该等价锚点，不使用模糊相似度。

针对 10 条 P0 `no_evidence` 的后续定向复测报告 `production-eval-20260907-125200.json`：只有
`pem-000013`（Metal 光线步进）正确返回 `422 no_evidence`；`pem-000010/012/014/015/017` 错误进入
`knowledge`（泛主题或不相干资料仍被当作强证据），`pem-000011/016/026/027` 错误进入 `general`。因此下一
阶段应先修复网站的领域路由与证据阈值、确保明确 iOS 但无可靠资料的问题退款返回 422，然后在**新版
源码语料已发布后**重跑该 manifest；不能把当前失败归因给尚未上线的 `ios-source-learning`。

**2026-09-07 网站路由与证据阈值修复（历史记录，现已合并部署）**：为避免污染用户正在调整首页的工作区，
修复在隔离副本的 GitHub 分支 `codex/fix-ios-evidence-routing-live` 中完成，提交 `81ac3ce`
`fix(retrieval): require grounded iOS evidence`。它将 WidgetKit、App Intents、Siri、Vision 等 Apple 专有
框架识别为必检索的 iOS 问题；对 iOS 证据，reranker 高分不能再单独越过关键词/API 覆盖阈值；对跨平台
比较，若资料没有覆盖问题所要求的另一平台，则不允许用单侧 iOS 资料拼接结论，返回 `422 no_evidence`
并退款。用户明确要求“只从 iOS 侧”时保留单侧解释入口，且回答提示词要求声明边界。回归覆盖 Apple API
路由、泛资料泄漏、跨平台范围、`422` 不调用 DeepSeek；本地 `23` 项 Retrieval、`14` 项 API、TypeScript
和完整网站构建通过。该提交已由 `9ce55d7` 补强 v1 路径并快进到远端 `main`；CI `34125568913` 与 Pages `280999a7` 已成功。生产 P0 定向复测仍有 WidgetKit 异常流和 Kotlin/GCD 误进 knowledge 两个残余问题，不能写成全部 no-evidence 已修复。

**2026-09-07 补充 GLM 离线资产（已归档，未接入生产）**：6 个结构化批次已放入 `data/glm/`：语义审查与
黄金集、r2/r3 红队、薄弱主题种子、种子边界/130 条生产清单、证据账本/判分规范。共 3,479 条 JSONL
记录；逐批校验器均通过。它们是可复跑、可审阅的评测和学习资产，不是原始事实证据，不修改资料、索引或云端。

**历史基线（2026-08-04 增量同步）**：全部代码 + 当时资料实测全链路。以下数字仅用于追溯，当前实时统计以
2026-09-05 维护状态和 `uv run ioskb stats` 为准：

| source | 文件 | 块 | 向量 |
|---|---:|---:|---:|
| obsidian-ios | 58 | 1,773 | 1,773 |
| summer2026 | 281 | 8,249 | 8,249 |
| summer-labs | 4 | 11 | 11 |
| objc4-source | 380 | 1,680 | 1,680 |
| apple-docs-core | 2,491 | 33,284 | 33,284 |
| apple-docs-bulk | 98,164 | 505,374 | 0（按设计仅 FTS） |
| apple-archive | 40,262 | 517,561 | 0（按设计仅 FTS） |
| knowledge-cards | 95 | 1,192 | 1,192 |
| **历史合计** | **141,735** | **1,069,124** | **46,189** |

当时 `db/ios_kb.sqlite` 约 1.9GB（历史基线；当前约 2.0GB）。95 张卡片已生成并通过
`ioskb audit-cards` 全量审计；生成报告记录实际 650,630 tokens。
2026-07-29 同步到的仓库提交：apple-docs-vault `fcbf992d`，
apple-developer-archive-vault `c0fc987f`。

**第二阶段（资料以后再次更新或维护卡片时，零 Claude 依赖）**：
```bash
uv run ioskb freshness        # 只读检查本地资料和 Git 镜像远端 HEAD
uv run ioskb sync --dry-run   # 零写入预演
uv run ioskb sync             # 只更新本地索引/向量，默认不拉镜像、不发布云端
uv run ioskb sync --pull-upstreams  # 干净镜像 fast-forward 后再增量入库
uv run ioskb cards                              # 只生成缺少的卡片
uv run ioskb cards --topic <主题> --force        # 覆盖重生成单卡
uv run ioskb audit-cards                        # 审计原始来源与行号
uv run ioskb index --source knowledge-cards     # 卡片回灌
```

`sync --prepare-cloud` 只生成本地 Vectorize/FTS 发布包，不上传、不导入、
不读取 Cloudflare 密钥。真正的远端发布仍必须按第三阶段的备份、稳定 ID、
计数核对和原子切换流程独立执行。

**第三阶段（网站问答接口，Retrieval v2 已完成代码、数据和生产发布）**：用户网站是 `/Users/tommywu/tommywu-lab`
（Astro 7 静态博客，Cloudflare Pages 部署）。当前生产版已完成：
1. `uv run ioskb export-vectorize` 导出 55,635 条稳定 `v1-*` ID（本地 bge-m3 向量 + 出处 metadata）；
2. Cloudflare Vectorize `ios-kb` 已用 `upsert` 同步，远端旧数字 ID 已清理；
3. D1 Retrieval v2 已水平拆分并原子导入：`IOS_DB` 对应 `tommywu-ios-kb-primary-20260905`，两张 v2 表
   各 84,818 行、约 338 MB；`IOS_ARCHIVE_DB` 对应 `tommywu-ios-kb-archive`，各 40,000 行、
   约 114 MB。业务 `DB` 只保留登录、额度、反馈和指标；旧 v2 FTS 在记录 Time Travel 恢复点后
   已移除，业务库现约 0.35 MB；
4. Pages Function 使用 Workers AI `@cf/baai/bge-m3` → Vectorize + 两个 D1 FTS v2，最多 4 路
   查询规划、RRF 合并、`@cf/baai/bge-reranker-base` 重排和邻块扩展，返回段落级引用；
5. API 有用户/管理员限流、知识回答引用校验、反馈审计和断流状态；前端不保存未完成回答到后续上下文，并随历史回传上一轮真实的 `knowledge`/`general` 模式；
6. iOS 问题有可靠证据时走 `knowledge` 模式；没有可靠证据时返回 `422 no_evidence` 并退款，
   不调用 DeepSeek；检索故障返回 `503` 并退款。`hi`、你好等纯问候跳过检索，由后端直接
   返回用户指定的固定助手介绍；`谢谢`、`你真棒` 等纯感谢/夸赞以及 `收到`、`明白了` 等确认语也由后端确定性回复，即使上一轮
   是 iOS 问题也不会继承检索意图；这些回复均不调用模型且不占每日额度。非 iOS 问题走 `general` 模式；
   前端不再用 `sessionStorage` 保存或恢复聊天记录，聊天窗口每次从关闭状态重新打开时为空；同一次打开期间仍保留多轮追问上下文，“新建对话”仍可手动清空当前会话；
7. DeepSeek 默认模型是 `deepseek-v4-flash`，生产没有 `DEEPSEEK_MODEL` 覆盖项；普通 iOS 查阅题
   使用 6 条证据/12,000 字上下文/1,800 tokens，复杂题使用 8 条/20,000 字/2,400 tokens；
   V4 默认隐藏思考已显式关闭，使该预算全部用于最终可见答案和引用；
8. 生产 Vectorize `ios-kb` 为 55,635 条；D1 两库合计 124,818 条 FTS v2 证据；
9. 当前轮次先分为问候、感谢、确认、新问题、追问，再决定领域与是否继承历史。明确 iOS 必须检索，明确普通问题不检索，边界技术问题先证据探测；只有明确指代的追问继承相关上下文，新话题隔离旧历史；
10. 检索排序在网站层落实 `26暑期内容`/官方文档/源码并列第一、个人笔记第二、技术博客第三。引用解析兼容组合及中文格式并统一为 `[n]`；越界引用会移除，但不再伪造来源或自动补 `[1]`，最终无有效引用则退款报错；
11. DeepSeek 首次空流或在输出正文前断流时重试一次；每次尝试重新创建中止控制器并获得独立 50 秒超时。生产自测脚本支持 `IOS_SELF_TEST_CASES` 按用例定向运行；
12. 网站功能代码与后续修复已提交至 `0f9cff5` 并快进推送到网站 `main`/`origin/main` 和 `feat/retrieval-v2`；API 拆为
    流处理、运营数据和主编排模块，新增精确故障指标、后台留存清理、双库降级、管理员安全来源预览，
    并修复 DeepSeek 默认思考模式耗尽正文 token 的问题；
13. GitHub Actions 已合并为单一 CI/部署门禁，Cloudflare Git 自动部署已关闭；本轮 Pages 绑定更新部署
    为 `https://2ed9ad9f.tommywu-lab.pages.dev`（source `d331ef3`），自定义域名与该地址首页/API 均返回
    HTTP 200、`configured: true`。
14. 网站内置生产自测入口 `pnpm ios-self-test:production`，现含 11 个混合场景并支持 `IOS_SELF_TEST_CASES` 定向运行；
    早期认证 POST 曾因 Cloudflare 免费套餐当日 D1 写入额度耗尽统一返回 HTTP 500，错误位于 `reserveHourlyRequest`；
    额度恢复后于 2026-09-06 00:13（Asia/Shanghai）重跑，11/11 场景全部通过，确认不是新 FTS/Vectorize 数据错误。
15. 前端支持本会话输入历史、未发送草稿恢复、回答期间继续输入和最多 4 条 FIFO 排队；当前回答的停止按钮独立保留。
    已问/已展示拓展问题会过滤，服务端每个主题提供最多 5 个候选轮换；回答工具与反馈改为分组图标按钮。

网站提交 `0571bb0` 的聊天稳定修复仍为已验证代码基线；本轮未覆盖网站工作区用户修改，仅更新 Pages 绑定并发布 `d331ef3` 构建。生产数据发布后，`https://2ed9ad9f.tommywu-lab.pages.dev` 与自定义域名首页/API 均为 HTTP 200、`configured: true`；2026-09-06 00:13（Asia/Shanghai）认证问答 11/11 全部通过。当前会话没有可用浏览器实例，不得宣称已完成真实 `<dialog>` 自动化验证。

当前跨仓库同步点：

- 本仓库 `/Users/tommywu/Desktop/iOS知识agentt`：本轮资料边界、元数据权威等级、FTS source/总容量保护和生产导出已完成；本地已清理 32 个陈旧 `summer2026` 文件的 1,521 块，但生产仍保留清理前快照，后续发布必须按稳定 ID 流程同步；6 个 GLM 离线候选批次已归档并逐批校验，未自动接入检索。新增生产评测器只读入审核资产，`--live` 仅写 Git 忽略的无正文报告；`mermaid-diagram.svg` 仍为用户未跟踪文件；
- 网站仓库 `/Users/tommywu/tommywu-lab`：远端 `main` 为 `2dee16f`，生产 Pages 仍是此前部署 `2ed9ad9f`；用户工作区的首页改动和未跟踪内容未处理。路由/证据阈值修复 `81ac3ce` 已推送 `codex/fix-ios-evidence-routing-live`，未合并、未部署，后续需合并后以 P0 `no_evidence` 定向复测验证；
- 自动回复仓库 `/Users/tommywu/wechat-auto-reply`：PR #8 已合并至 `main`（`0c087b3`），PR #9 已合并至 `main`（`b1da74b`）。除按联系人独立画像、相关历史示例检索和机械拖延防护外，控制 App 现在启动或 Dock 重新打开时会在工作区干净且可快进的条件下自动拉取 `main` 并按提交号重建；关闭窗口后点击 Dock 会恢复主窗口。自动更新不会覆盖本地修改，也不会强制重启后台服务。TraceMemo 原始历史仍只在本机读取，画像写入 Git 忽略且 0600 的 `var/style-profiles.json`，不做整库微调或上传；本轮 Python 205 项、Swift 11 项测试通过，Android 本机因缺少 SDK 未运行；功能分支已删除。
- 生产站点：`https://www.tommywutong.cn`；本轮 Pages production 部署为 `https://2ed9ad9f.tommywu-lab.pages.dev`（source `d331ef3`）；
- 两个地址的公开 API 健康检查均显示 HTTP 200、`configured: true`；macOS 钥匙串中的生产自测 token 未写入仓库。
 认证问答于 2026-09-06 00:13（Asia/Shanghai）重跑，11/11 全部通过。

问候语固定回复全文：`Hi`、`hi`、你好等纯问候只回复
`我是TommyWu的ai学习助手，有什么可以帮你吗？无论是iOS、日常聊天还是其他问题，都可以告诉我`。
该回复不调用 DeepSeek、不消耗每日 2 次额度，但仍记录请求指标并受每小时防刷限制。
纯感谢/夸赞固定回复全文：`谢谢`、`你真棒` 等独立表达只回复
`谢谢你的认可！有问题继续问我就好。`；同样不调用 DeepSeek、不消耗每日额度，且不会继承上一轮 iOS 检索意图。
确认语固定回复全文：`收到`、`明白了` 等只回复 `好的，有问题继续问我就好。`；同样不调模型、不消耗每日额度。
聊天记录不写入 `sessionStorage`；每次重新打开聊天窗口都会从空白会话开始，不能因上一次会话输入过 `hi` 而自动显示固定问候；同一次打开期间的多轮上下文只存在当前页面内。
回答风格：简单问题直接回答；复杂 iOS 问题必须完整展开机制、条件、实践影响、示例和常见误区，避免只给几句概括；DeepSeek 输出上限为 `2400` tokens，并显式关闭默认隐藏思考，把预算留给可见正文。
终端没有浏览器 Cookie；生产自测使用 macOS 钥匙串中的专用 Bearer token。不要把 API 级登录态
复核冒充为浏览器 Cookie 登录流程。

资料更新时：重新导出并 `wrangler vectorize upsert ios-kb --file=...`，先列出远端 ID 做备份，
再删除本次导出不存在的 stale ID；运行 `uv run ioskb export-fts` 后用
`scripts/build_fts_v2_import.py` 按 84,997/剩余行分区，分别导入 primary/archive 并执行各自
`999-finalize.sql`。v1 回滚需先把旧表恢复到 `IOS_DB` 再设置 `IOS_RETRIEVAL_VERSION=v1`。

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
