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

- 本知识库仓库最后核对的功能代码基线为 `2f6e9b0`；本交接文档提交位于其后，
  实际 `main`/`origin/main` 以开场核对命令为准。
- 网站仓库：`/Users/tommywu/tommywu-lab`，`main` = `origin/main` = `36eb071`。
- 通用对话实现提交：`e06c445 Route general chat to DeepSeek V4 Flash`。
- 对应文档提交：`c080b0b Document general DeepSeek answer routing`。
- 问候语与引用兼容修复：`2188b85 Fix chat greetings and citation formats`。
- 确定性问候回复：`0e8f05d Return fixed greetings without model calls`。
- 新会话清空聊天记录：`27cff9f Reset chat when opening a new session`。
- 恢复复杂问题详细回答：`36eb071 fix: restore detailed chat answers`。
- 线上地址：`https://www.tommywutong.cn`；最新核对的 Pages 部署为
  `https://bd136cf3.tommywu-lab.pages.dev`。
- 线上 API `GET /api/ios-ask` 返回 `configured: true`。
- 当前默认回答模型为 `deepseek-v4-flash`；生产环境没有 `DEEPSEEK_MODEL` 覆盖项。
- 当前知识/通用回答均按问题复杂度组织：简单问题直接回答，复杂问题展开机制、条件、示例和常见误区；DeepSeek `max_tokens` 为 `2400`，不再强制一律简洁。
- iOS 问题优先走 Workers AI embedding + Vectorize/D1 混合检索，答案要求引用。
- `hi`、你好等纯问候跳过检索，并只回复固定文本：
  `我是TommyWu的ai学习助手，有什么可以帮你吗？无论是iOS、日常聊天还是其他问题，都可以告诉我`。
  该分支由后端直接按 NDJSON 协议返回，不调用 DeepSeek、不占每日 2 次提问额度，但仍受每小时防刷限制。
- 前端不再用 `sessionStorage` 保存或恢复聊天记录；聊天窗口每次从关闭状态重新打开时都是空白，只有同一次打开期间保留多轮追问上下文；“新建对话”仍可手动清空当前会话。
  没有可靠 iOS 证据的非 iOS 问题走 DeepSeek 通用回答，不附知识库来源；检索异常也降级到通用模式。
- 引用校验已兼容 `[1, 2]`、`【1、2】`、`【资料 1】`、`[来源：2]` 等 DeepSeek 输出，
  并统一为前端可点击的 `[1][2]`；完全无引用或编号越界仍会被拒绝。
- Cloudflare Vectorize `ios-kb` 与 D1 `ios_ask_fts` 均为 `44,962` 条。
- 本地索引：`141,734` 文件、`1,069,089` 块、`46,154` 已向量化。
- 本地测试：16 项全部通过。网站的 Prettier、Astro Check、iOS 评测、完整构建、
  链接检查、体积检查与提交 `36eb071` 的三条 GitHub Actions/Cloudflare 部署均通过。

尚未自动执行登录后的线上 `hi` 端到端对话，因为终端没有管理员
`tw_auth_session`/`IOS_EVAL_COOKIE`。不要把公开健康检查误写成已完成登录态运行时评估。

## Maintenance Rules

- 原始资料目录只读，不要为修复程序而改写用户笔记或镜像语料。
- 不要把 `.env`、API Key、Cookie、Cloudflare/GitHub token 写入文档、日志或提交。
- 工作区可能有用户并行修改；只处理任务相关文件，不回退未知变更。
- 更新索引或线上数据时遵循 `HANDOFF.md` 和 `website-templates/DEPLOY_PLAN.md` 的稳定 ID 流程。
- 每次完成会改变上述状态的工作后，同时更新本文件的 Current Checkpoint、`HANDOFF.md`
  和 `PROGRESS.md`，让下一次会话可以直接续接。
