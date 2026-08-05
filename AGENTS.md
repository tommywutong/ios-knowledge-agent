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

最后核对时间：2026-08-06（Asia/Shanghai）。

- 本知识库仓库的 `main`、`origin/main` 与 `feat/retrieval-v2` 已同步包含 Retrieval v2、资料新鲜度/安全同步和 FTS 分区导出；实际提交仍以开场核对命令为准。
- 网站仓库：`/Users/tommywu/tommywu-lab`，本地与远端 `main`、`feat/retrieval-v2` 已统一到 `0f9cff5`；本轮完成 API 拆分、分库检索、指标/留存、管理员来源预览、依赖升级、单一 CI 部署门禁、DeepSeek 可见回答预算修复和聊天交互升级。
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
- 线上地址：`https://www.tommywutong.cn`；本轮最新 production Pages 部署为
  `https://97710bd9.tommywu-lab.pages.dev`（source `0f9cff5`）。
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
  全新 checkout 会先运行 `astro sync` 再做独立 TypeScript 检查。Actions run `31034429859` 全部成功。
- 本地测试：Retrieval v2 导出与知识库测试全部通过；网站的 Retrieval 逻辑测试、TypeScript、
  Astro Check、runtime 评测集覆盖检查、完整构建、链接检查和体积检查已通过。生产 D1
  已完成两库真实导入和全文/邻接 smoke test；网站本地 14 项 API 测试、20 项 Retrieval 测试、
  TypeScript、Astro Check、完整构建、链接/体积检查和生产依赖审计全部通过。网站生产自测为 11 项，
  新增用户原始问题 `给我讲讲iOS内存管理`；该题线上返回 knowledge、6 个来源和 27 处引用。其余 10 项
  也通过；完整批次中 general 曾遇到一次终端网络 `fetch failed`，随即定向重跑成功。Pages 地址和
  自定义域名公开健康检查均为 HTTP 200、`configured: true`，线上静态资源已确认包含新版交互代码。

终端可从 macOS 钥匙串读取生产自测 Bearer token，但仓库不保存 token/Cookie。不要把上述定向复核
或连续自测冒充为浏览器 Cookie 登录流程验证。

## Maintenance Rules

- 原始资料目录只读，不要为修复程序而改写用户笔记或镜像语料。
- 不要把 `.env`、API Key、Cookie、Cloudflare/GitHub token 写入文档、日志或提交。
- 工作区可能有用户并行修改；只处理任务相关文件，不回退未知变更。
- 更新索引或线上数据时遵循 `HANDOFF.md` 和 `website-templates/DEPLOY_PLAN.md` 的稳定 ID 流程。
- 每次完成会改变上述状态的工作后，同时更新本文件的 Current Checkpoint、`HANDOFF.md`
  和 `PROGRESS.md`，让下一次会话可以直接续接。
