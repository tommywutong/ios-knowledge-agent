# Retrieval v2 发布前检查清单

本清单不授权任何发布、推送、合并或 Cloudflare 写入；每项均需在获得单独授权后执行。

## 本地基线

- [ ] 知识库工作区仅含预期改动；不处理 `mermaid-diagram.svg` 等用户未跟踪文件。
- [ ] 原始学习资料、Obsidian 和源码镜像保持只读。
- [ ] 运行 `uv run python -m unittest discover -s tests -v`。
- [ ] 运行 `uv run ioskb stats` 并记录实际块、向量和数据库大小。
- [ ] 运行 `uv run python scripts/run_production_eval.py --priority P0 --gate`。
- [ ] 门禁没有锚点失效、夹具缺失或 `manual_review_required` 阻断；不得通过删除人工复核标记绕过。

## 网站补丁整合

- [ ] 在隔离副本中从最新 `origin/main` 重新整合 `3dd5617`；绝不修改 `/Users/tommywu/tommywu-lab` 的用户工作区。
- [ ] 运行 `pnpm test:ios-retrieval`、`pnpm test:ios-api`、`pnpm format:check`、`pnpm check`、`pnpm build`。
- [ ] 定向检查 WidgetKit 成功/失败流都只有一个终结事件，Kotlin/GCD 等跨平台题需要双方证据。
- [ ] 评审合并差异和生产配置，确认无 token、Cookie、绝对本机路径或原始正文进入提交。

## 数据与生产验证

- [ ] 按 `HANDOFF.md` 的稳定 ID、备份、容量审计和 D1 原子切换流程准备发布包。
- [ ] 发布后先做公开健康检查，再在现有受控认证机制下执行小范围 P0 定向评测。
- [ ] 用 `--live --gate` 执行完整门禁，并保存无正文报告。
- [ ] 以 `--summarize-report` 产出 no-evidence、引用覆盖率和失败归因；人工审阅答案事实性与平台边界。
- [ ] 只有线上 P0 全部满足契约后，才能更新 `HANDOFF.md`、`PROGRESS.md` 和简历中的生产状态。
