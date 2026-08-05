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
- 网站仓库：`/Users/tommywu/tommywu-lab`，本地 `main`、`feat/retrieval-v2`、`origin/main` 和 `origin/feat/retrieval-v2` 已统一到 `7893c7d`；该提交让纯感谢/夸赞由后端确定性回复，不再误继承上一轮 iOS 检索上下文。
- 通用对话实现提交：`e06c445 Route general chat to DeepSeek V4 Flash`。
- 对应文档提交：`c080b0b Document general DeepSeek answer routing`。
- 问候语与引用兼容修复：`2188b85 Fix chat greetings and citation formats`。
- 确定性问候回复：`0e8f05d Return fixed greetings without model calls`。
- 新会话清空聊天记录：`27cff9f Reset chat when opening a new session`。
- 恢复复杂问题详细回答：`36eb071 fix: restore detailed chat answers`。
- 感谢语退出 iOS 检索：`9fc6fad fix: keep acknowledgements out of iOS retrieval`。
- 感谢语确定性回复：`7893c7d fix: answer casual acknowledgements directly`。
- 线上地址：`https://www.tommywutong.cn`；本轮最新 production Pages 部署为
  `https://ee8cef76.tommywu-lab.pages.dev`（source `7893c7d`）。
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
- 前端不再用 `sessionStorage` 保存或恢复聊天记录；聊天窗口每次从关闭状态重新打开时都是空白，只有同一次打开期间保留多轮追问上下文；“新建对话”仍可手动清空当前会话。
  没有可靠 iOS 证据的非 iOS 问题走 DeepSeek 通用回答，不附知识库来源；检索异常也降级到通用模式。
- 引用校验已兼容 `[1, 2]`、`【1、2】`、`【资料 1】`、`[来源：2]` 等 DeepSeek 输出，
  并统一为前端可点击的 `[1][2]`；模型编号越界或个别段落漏标时自动修正为本次证据编号，
  不再丢弃整条回答。没有检索证据的问题仍不会进入知识回答。
- DeepSeek 流偶发 HTTP 200 但无正文时，Pages Function 会在同一请求额度内自动重试一次；
  两次都为空时退款并返回 `empty_answer`，不再误报为引用错误。
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
  Deploy to Cloudflare Pages 全部成功；`9fc6fad` 部署的生产自测六组用例（greeting、weak、ARC、general、
  acknowledgement-after-ios、no-evidence）全部通过。`7893c7d` 最新生产版已对“weak 上下文后说你真棒”
  做登录态定向复核：自定义域名与 Pages 地址均返回 HTTP 200、`general`、0 来源和固定感谢回复。

终端可从 macOS 钥匙串读取生产自测 Bearer token，但仓库不保存 token/Cookie。不要把上述定向复核
误写成 `7893c7d` 上重新跑过完整六组生产评测，也不要把它冒充为浏览器 Cookie 登录流程验证。

## Maintenance Rules

- 原始资料目录只读，不要为修复程序而改写用户笔记或镜像语料。
- 不要把 `.env`、API Key、Cookie、Cloudflare/GitHub token 写入文档、日志或提交。
- 工作区可能有用户并行修改；只处理任务相关文件，不回退未知变更。
- 更新索引或线上数据时遵循 `HANDOFF.md` 和 `website-templates/DEPLOY_PLAN.md` 的稳定 ID 流程。
- 每次完成会改变上述状态的工作后，同时更新本文件的 Current Checkpoint、`HANDOFF.md`
  和 `PROGRESS.md`，让下一次会话可以直接续接。
