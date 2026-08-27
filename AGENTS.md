# Repository Agent Notes

## Session Bootstrap

每次从本目录开始新会话时，先完整阅读：

1. `HANDOFF.md`：架构、生产状态、跨仓库同步点和维护流程；
2. `PROGRESS.md`：完成项与最后验证快照；
3. `SPEC.md`：模块接口与不可破坏的行为约束。

不要只依赖下面的提交号。开始工作前用只读命令核对实际状态：

```bash
git status --short --branch
git fetch origin
git rev-list --left-right --count HEAD...origin/main
git -C /Users/tommywu/tommywu-lab status --short --branch
git -C /Users/tommywu/tommywu-lab fetch origin
git -C /Users/tommywu/tommywu-lab rev-list --left-right --count HEAD...origin/main
```

## Current Checkpoint

最后核对时间：2026-08-27（Asia/Shanghai）。

- 本知识库仓库的 `main`、`origin/main` 与 `feat/retrieval-v2` 已同步包含 Retrieval v2、资料新鲜度/安全同步和 FTS 分区导出；实际提交仍以开场核对命令为准。
- 网站仓库：`/Users/tommywu/tommywu-lab`，本地 `main`、`origin/main` 和 `fix/chat-ui-stability` 已统一到 `0571bb0`；`feat/retrieval-v2` 仍停在 `0f9cff5`。`ea0a2c3` 新增资源文章目录，`0571bb0` 完成聊天流式稳定与输入体验修复。
- 自动回复仓库：`/Users/tommywu/wechat-auto-reply` 的 `main`、`origin/main` 已同步到 `0c087b3`。PR #2（默认启动跳过停机期间历史消息）、PR #3（显式追补模式覆盖首次发现会话）、PR #4（Android/macOS README 与 macOS 自安装说明）、PR #5（统一 macOS 双服务生命周期）、PR #6（模块级 Agent 记忆和开发者地图）、PR #7（macOS 接收/发送链路性能优化）及 PR #8（按联系人个性化回复与机械拖延修复）均已合并，功能分支已删除；本轮新增按联系人历史样本检索风格、过滤机械拖延回复并修正本机“忙不忙”规则；Python 205 项、Swift 11 项测试通过；Android 本机测试因缺少 SDK 未运行。
- 自动回复默认启动只建立当前历史游标，不追补停机期间消息；控制 App 的“启动时追补停机消息”或 CLI `--replay-offline` 才会显式启用追补。批次交给模型前立即持久化 `seen_ids`，降低重启重复回复风险。
- 自动回复控制 App 现将规则服务与轮询器聚合为“运行中 / 部分运行 / 已停止 / 未安装”，启动只补齐未运行项，停止会卸载两项，重启按依赖顺序完整停启，并在返回成功前轮询确认最终状态。macOS Bash 3.2 的空追补参数数组崩溃已修复；本机 App 已真实验证停止、启动、重启后两项服务均达到目标状态，当前恢复为运行中。
- 自动回复仓库已增加根 `AGENTS.md`、`MEMORY.md` 以及各模块 `MEMORY.md`/`README.md`，按模块渐进加载上下文；PR #6 为文档-only 变更，未修改回复、发送或配置逻辑。
- 自动回复 README 现已说明 Android 与 macOS 的消息入口、前台要求、消息完整度、媒体能力和数据流向差异，并给出从环境准备、Keychain、构建控制 App、权限、安全试跑到停止服务的完整 macOS 安装流程；`安装到Mac.command` 的更新源已指向 `tommywutong/wechat-auto-reply`。
- `0571bb0` 关闭弹窗或 Astro 页面切换时会清空未发送 FIFO 队列、中止当前请求，并在请求收尾后强制重置会话；流式回答改为 80ms 节流纯文本刷新，完成时只渲染一次 Markdown，并合并自动滚动帧；回答排版增强了列表、引用块和长文行高；输入框 Enter 只换行，发送只由按钮触发，真正发送时统一清空输入框。修复已提交、推送 `main` 并部署生产。
- 通用对话实现提交：`e06c445 Route general chat to DeepSeek V4 Flash`。
- 对应文档提交：`c080b0b Document general DeepSeek answer routing`。
- 问候语与引用兼容修复：`2188b85 Fix chat greetings and citation formats`。
- 确定性问候回复：`0e8f05d Return fixed greetings without model calls`。
- 新会话清空聊天记录：`27cff9f Reset chat when opening a new session`。
- 恢复复杂问题详细回答：`36eb071 fix: restore detailed chat answers`。
- 感谢语退出 iOS 检索：`9fc6fad fix: keep acknowledgements out of iOS retrieval`。
- 感谢语确定性回复：`7893c7d fix: answer casual acknowledgements directly`。
- 混合对话状态机：`0818ba0 fix: make mixed chat routing turn-aware`。
- DeepSeek 独立重试超时：`101cf86 fix: isolate DeepSeek retry timeouts`。
- CI 全新环境 Astro 类型同步：`9fe2708 fix: generate Astro types before CI checks`。
- DeepSeek 隐藏思考耗尽正文预算修复：`a59622e fix: reserve DeepSeek budget for visible answers`。
- 聊天输入历史、顺序队列、动态追问与操作区升级：`0f9cff5 feat: improve knowledge chat interactions`。
- 聊天流式稳定、Markdown 排版与 Enter 行为修复：`0571bb0 fix: stabilize chat streaming and input`。
- 线上地址：`https://www.tommywutong.cn`；本轮最新 production Pages 部署为
  `https://00e20626.tommywu-lab.pages.dev`（source `0571bb0`）。
- 线上 API `GET /api/ios-ask` 在 Pages 预览地址和自定义域名均返回 HTTP 200、`configured: true`；
  未登录状态按设计不执行问答。
- 当前默认回答模型为 `deepseek-v4-flash`；生产环境没有 `DEEPSEEK_MODEL` 覆盖项。问答显式关闭
  DeepSeek V4 默认隐藏思考，避免隐藏 reasoning 与正文共用 `max_tokens` 后挤掉最终答案。
- 当前知识/通用回答均按问题复杂度组织：普通 iOS 查阅题用 6 条证据、12,000 字上下文和 1,800 tokens；原理、对比、代码、排障等复杂题保留 8 条证据、20,000 字上下文和 2,400 tokens。
- iOS 问题优先走 Workers AI embedding + Vectorize/D1 混合检索，答案要求引用。
- `hi`、你好等纯问候跳过检索，并只回复固定文本：
  `我是TommyWu的ai学习助手，有什么可以帮你吗？无论是iOS、日常聊天还是其他问题，都可以告诉我`。
  该分支由后端直接按 NDJSON 协议返回，不调用 DeepSeek、不占每日 2 次提问额度，但仍受每小时防刷限制。
- `谢谢`、`你真棒` 等纯感谢/夸赞同样跳过检索和 DeepSeek，固定回复
  `谢谢你的认可！有问题继续问我就好。`，不占每日 2 次额度；即使前一轮讨论 `weak`，也不会误进 iOS 检索或返回 `no_evidence`。
- `收到`、`明白了` 等确认语也由后端固定回复 `好的，有问题继续问我就好。`，不调用模型、不占每日额度。
- 路由先判断当前轮次，再决定是否继承历史：只有“为什么？”等明确指代上一轮的追问会携带相关历史；新话题不会被旧 iOS 上下文污染。前端把上一轮真实的 `knowledge`/`general` 模式随历史回传，短追问不再靠关键词猜测。
- 明确 iOS 问题必须检索；明确普通问题直接走通用回答；边界不清的技术问题先做证据探测，只有强证据才进入知识模式。可能是 iOS 的问题遇到检索故障时返回 `503` 并退款，不用无依据的通用回答冒充。
- 前端不再用 `sessionStorage` 保存或恢复聊天记录；聊天窗口每次从关闭状态重新打开时都是空白，只有同一次打开期间保留多轮追问上下文；“新建对话”仍可手动清空当前会话。
  普通问题走 DeepSeek 通用回答，不附知识库来源；只有真实追问才把相关历史送入提示词，新话题的提示词与检索词都不混入旧上下文。
- 输入框支持上/下箭头浏览本次会话的提问历史并恢复未发送草稿；回答生成期间仍可输入，提交后进入最多 4 条的前端 FIFO 队列，停止当前回答使用独立按钮。已问过或本会话已展示过的拓展问题会被排除，服务端按主题提供最多 5 个候选用于轮换；回答操作区改为带图标的两组 32px 控件。
- 本地关闭清理修复保留“停止回答”只停当前请求、随后继续队列的语义；只有关闭弹窗或页面切换才会丢弃整个会话和队列。
- 本地版不再于每个流式 delta 重建整棵 Markdown DOM；流式期间以纯文本稳定增长，结束/停止/中断时再生成最终 Markdown 和引用按钮。输入框 Enter 保留为换行，不再发送。
- 引用校验已兼容 `[1, 2]`、`【1、2】`、`【资料 1】`、`[来源：2]` 等 DeepSeek 输出，
  并统一为前端可点击的 `[1][2]`；越界编号会被移除，但不会再伪造 `[1]` 或把无引用段落强行归给第一个来源。知识回答若最终没有任何有效引用则退款并返回 `invalid_citations`。
- DeepSeek 流首次无正文或在产生正文前异常时会自动重试一次；每次尝试有独立的 50 秒超时，第二次不再复用第一次已到期的中止信号。两次都为空时退款并返回 `empty_answer`。
- 生产检索排序落实用户指定优先级：`26暑期内容`、官方文档、源码并列第一，个人笔记第二，技术博客第三；该权重在网站层按来源 metadata 生效，无需重建索引。
- Cloudflare Vectorize `ios-kb` 为 `44,997` 条稳定 `v1-*` 向量。生产检索已拆到
  `tommywu-ios-kb-primary`（两张 v2 表各 `84,997` 行，约 `332 MB`）和
  `tommywu-ios-kb-archive`（各 `40,000` 行，约 `114 MB`）；Pages 绑定为 `IOS_DB`、
  `IOS_ARCHIVE_DB`。登录/额度/指标仍在 `DB`，任一扩展库查询失败会降级使用其余检索库。
  旧 v2 FTS 已在记录 D1 Time Travel 恢复点后从业务库移除，业务 D1 现约 `0.35 MB`。
- Retrieval v2 的链路为查询规划（最多 4 路）→ Vectorize/D1 FTS 召回 → RRF 去重 →
  Workers AI `@cf/baai/bge-reranker-base`（失败自动回退）→ 邻块扩展 → 段落级引用校验。
  iOS 问题无可靠证据时返回 `422 no_evidence`，不调用 DeepSeek；检索故障返回 `503` 并退款。
- 本地索引：`141,735` 文件、`1,069,124` 块、`46,189` 已向量化。
- 资料新鲜度已有只读命令 `uv run ioskb freshness`：按原文件 SHA-256 精确列出
  新增/修改/删除，并只读对比 Git 镜像的远端 HEAD，不加载 embedding。
  `uv run ioskb sync` 默认只做本地增量索引；`--dry-run` 零写入，拉取镜像须显式
  `--pull-upstreams`，`--prepare-cloud` 也只生成本地发布包，不连接 Cloudflare。
- 2026-08-06 已将 Obsidian 《Part 1 - 对象与类的本质》的最新修改增量入库：
  随后新增的《2026 暑假第一周验收 - 对象模型与进程内存地图》也已增量入库；该来源现为
  `58` 文件 / `1,773` 块 / `1,773` 向量，全库 freshness 本地差异已清零。两篇变更的相关向量均已
  upsert；远端 Vectorize 现为 `44,997`，完整 FTS v2 也已同步到两个检索库。新增验收笔记的生产
  真实问答已返回 knowledge 模式、6 个来源、25 处引用，并命中该笔记 14-54 行。
- API 已拆分 DeepSeek 流处理与运营数据模块；空流/超时/HTTP/客户端中断有精确原因，配额退款、
  无证据、非法引用和双库扇出都有回归测试。指标只保存长度、模式、原因和时延，不保存问题正文；
  数据留存清理每 24 小时最多由一个认证请求在后台触发一次。管理员可看最多 300 字来源预览，
  普通用户看不到个人笔记正文或本机绝对路径。
- GitHub Actions 已合并为单一顺序门禁，复用一次完整构建后再部署；Cloudflare Git 自动部署已关闭，
  不再为同一提交额外生成 Idle/404 部署。Actions 均锁定到官方最新稳定 release 的精确 SHA；
  全新 checkout 会先运行 `astro sync` 再做独立 TypeScript 检查。最新 Actions run `31095416698` 全部成功。
- 本地测试：Retrieval v2 导出与知识库测试全部通过；网站的 Retrieval 逻辑测试、TypeScript、
  Astro Check、runtime 评测集覆盖检查、完整构建、链接检查和体积检查已通过。生产 D1
  已完成两库真实导入和全文/邻接 smoke test；网站本地 14 项 API 测试、20 项 Retrieval 测试、
  TypeScript、Astro Check、完整构建、链接/体积检查和生产依赖审计全部通过。网站生产自测为 11 项，
  新增用户原始问题 `给我讲讲iOS内存管理`；该题线上返回 knowledge、6 个来源和 27 处引用。其余 10 项
  也通过；完整批次中 general 曾遇到一次终端网络 `fetch failed`，随即定向重跑成功。Pages 地址和
  自定义域名公开健康检查均为 HTTP 200、`configured: true`，线上静态资源已确认包含新版交互代码。
- `0571bb0` 已通过 Prettier、TypeScript、Astro Check（156 个文件）、14 项 API 测试、20 项 Retrieval 测试、253 页完整构建、261 页链接检查和体积预算；Actions run `31095416698` 成功部署。Pages 地址和自定义域名首页及公开 API 均为 HTTP 200、`configured: true`，线上 HTML 已确认包含 `enterkeyhint="enter"`。当前会话无可用浏览器实例，因此不能将该项写成真实 `<dialog>` 浏览器自动化验证。

终端可从 macOS 钥匙串读取生产自测 Bearer token，但仓库不保存 token/Cookie。不要把上述定向复核
或连续自测冒充为浏览器 Cookie 登录流程验证。

## Maintenance Rules

- 原始资料目录只读，不要为修复程序而改写用户笔记或镜像语料。
- 不要把 `.env`、API Key、Cookie、Cloudflare/GitHub token 写入文档、日志或提交。
- 工作区可能有用户并行修改；只处理任务相关文件，不回退未知变更。
- 更新索引或线上数据时遵循 `HANDOFF.md` 和 `website-templates/DEPLOY_PLAN.md` 的稳定 ID 流程。
- 每次完成会改变上述状态的工作后，同时更新本文件的 Current Checkpoint、`HANDOFF.md`
  和 `PROGRESS.md`，让下一次会话可以直接续接。
