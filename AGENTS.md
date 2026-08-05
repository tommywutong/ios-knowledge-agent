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

最后核对时间：2026-08-05（Asia/Shanghai）。

- 本知识库仓库正在推进 Retrieval v2 功能分支；实际 `main`/`origin/main` 和功能分支提交以开场核对命令为准。
- 网站仓库：`/Users/tommywu/tommywu-lab`，本地 `main`、`feat/retrieval-v2`、`origin/main` 和 `origin/feat/retrieval-v2` 已统一到 `101cf86`；`0818ba0` 完成混合对话路由重构，`101cf86` 修复 DeepSeek 重试复用旧超时的问题。
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
- 线上地址：`https://www.tommywutong.cn`；本轮最新 production Pages 部署为
  `https://3504e14d.tommywu-lab.pages.dev`（source `101cf86`）。
- 线上 API `GET /api/ios-ask` 在 Pages 预览地址和自定义域名均返回 HTTP 200、`configured: true`；
  未登录状态按设计不执行问答。
- 当前默认回答模型为 `deepseek-v4-flash`；生产环境没有 `DEEPSEEK_MODEL` 覆盖项。
- 当前知识/通用回答均按问题复杂度组织：简单问题直接回答，复杂问题展开机制、条件、示例和常见误区；DeepSeek `max_tokens` 为 `2400`，不再强制一律简洁。
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
- 引用校验已兼容 `[1, 2]`、`【1、2】`、`【资料 1】`、`[来源：2]` 等 DeepSeek 输出，
  并统一为前端可点击的 `[1][2]`；越界编号会被移除，但不会再伪造 `[1]` 或把无引用段落强行归给第一个来源。知识回答若最终没有任何有效引用则退款并返回 `invalid_citations`。
- DeepSeek 流首次无正文或在产生正文前异常时会自动重试一次；每次尝试有独立的 50 秒超时，第二次不再复用第一次已到期的中止信号。两次都为空时退款并返回 `empty_answer`。
- 生产检索排序落实用户指定优先级：`26暑期内容`、官方文档、源码并列第一，个人笔记第二，技术博客第三；该权重在网站层按来源 metadata 生效，无需重建索引。
- Cloudflare Vectorize `ios-kb` 保持 `44,962` 条稳定 `v1-*` 向量；生产 D1 已切换到
  `ios_ask_fts_v2` 与 `ios_ask_fts_v2_neighbors`，各 `86,307` 行，数据库大小已降至约 `338 MB`。
  因 D1 最大数据库大小限制，旧 `ios_ask_fts` 已移除；v1 回滚需先从本地 SQL 或 D1 Time Travel 恢复。
- Retrieval v2 的链路为查询规划（最多 4 路）→ Vectorize/D1 FTS 召回 → RRF 去重 →
  Workers AI `@cf/baai/bge-reranker-base`（失败自动回退）→ 邻块扩展 → 段落级引用校验。
  iOS 问题无可靠证据时返回 `422 no_evidence`，不调用 DeepSeek；检索故障返回 `503` 并退款。
- 本地索引：`141,734` 文件、`1,069,089` 块、`46,154` 已向量化。
- 本地测试：Retrieval v2 导出与知识库测试全部通过；网站的 Retrieval 逻辑测试、TypeScript、
  Astro Check、runtime 评测集覆盖检查、完整构建、链接检查和体积检查已通过。生产 D1
  已完成真实导入和全文/邻接 smoke test；GitHub Actions 的 Code quality、Build and Check、
  Deploy to Cloudflare Pages 在 `101cf86` 全部成功。网站 Retrieval 测试现为 18 项；生产自测扩为 10 项，
  覆盖 greeting、weak、ARC、general、感谢、确认、iOS 后切普通话题、iOS 短追问、iOS 新话题和 no-evidence。
  `101cf86` 在自定义域名的首轮全套运行有 4 项遇到本机网络中断或引用门拦截，随后仅定向复测这 4 项全部通过；
  因而 10 项均已在该生产版逐项通过，但不要写成一次连续运行 10/10。Pages 地址和自定义域名公开健康检查均为 HTTP 200、`configured: true`。

终端可从 macOS 钥匙串读取生产自测 Bearer token，但仓库不保存 token/Cookie。不要把上述定向复核
误写成一次连续运行 10/10，也不要把 API 级登录态自测冒充为浏览器 Cookie 登录流程验证。

## Maintenance Rules

- 原始资料目录只读，不要为修复程序而改写用户笔记或镜像语料。
- 不要把 `.env`、API Key、Cookie、Cloudflare/GitHub token 写入文档、日志或提交。
- 工作区可能有用户并行修改；只处理任务相关文件，不回退未知变更。
- 更新索引或线上数据时遵循 `HANDOFF.md` 和 `website-templates/DEPLOY_PLAN.md` 的稳定 ID 流程。
- 每次完成会改变上述状态的工作后，同时更新本文件的 Current Checkpoint、`HANDOFF.md`
  和 `PROGRESS.md`，让下一次会话可以直接续接。
