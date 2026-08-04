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

最后核对时间：2026-08-04（Asia/Shanghai）。

- 本知识库仓库最后核对的功能代码基线为 `2f6e9b0`；本交接文档提交位于其后，
  实际 `main`/`origin/main` 以开场核对命令为准。
- 网站仓库：`/Users/tommywu/tommywu-lab`，`main` = `origin/main` = `06d2bb7`。
- 通用对话实现提交：`e06c445 Route general chat to DeepSeek V4 Flash`。
- 对应文档提交：`c080b0b Document general DeepSeek answer routing`。
- 线上地址：`https://www.tommywutong.cn`；最新核对的 Pages 部署为
  `https://51b79fad.tommywu-lab.pages.dev`。
- 线上 API `GET /api/ios-ask` 返回 `configured: true`。
- 当前默认回答模型为 `deepseek-v4-flash`；生产环境没有 `DEEPSEEK_MODEL` 覆盖项。
- iOS 问题优先走 Workers AI embedding + Vectorize/D1 混合检索，答案要求引用。
- `hi`、你好等问候跳过检索；没有可靠 iOS 证据的非 iOS 问题走 DeepSeek 通用回答，
  不附知识库来源。检索服务异常时也降级到通用模式。
- Cloudflare Vectorize `ios-kb` 与 D1 `ios_ask_fts` 均为 `44,962` 条。
- 本地索引：`141,734` 文件、`1,069,089` 块、`46,154` 已向量化。
- 本地测试：16 项全部通过。网站的 Prettier、Astro Check、完整构建、链接检查、
  体积检查与最新 GitHub Actions/Cloudflare 部署均通过。

尚未自动执行登录后的线上 `hi` 端到端对话，因为终端没有管理员
`tw_auth_session`/`IOS_EVAL_COOKIE`。不要把公开健康检查误写成已完成登录态运行时评估。

## Maintenance Rules

- 原始资料目录只读，不要为修复程序而改写用户笔记或镜像语料。
- 不要把 `.env`、API Key、Cookie、Cloudflare/GitHub token 写入文档、日志或提交。
- 工作区可能有用户并行修改；只处理任务相关文件，不回退未知变更。
- 更新索引或线上数据时遵循 `HANDOFF.md` 和 `website-templates/DEPLOY_PLAN.md` 的稳定 ID 流程。
- 每次完成会改变上述状态的工作后，同时更新本文件的 Current Checkpoint、`HANDOFF.md`
  和 `PROGRESS.md`，让下一次会话可以直接续接。
