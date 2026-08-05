# iOS 知识问答生产部署与同步

> 当前生产实现位于 `/Users/tommywu/tommywu-lab`：Astro 7 + Cloudflare Pages Functions，
> 问答入口为 `POST /api/ios-ask`，前端组件为 `src/components/global/IosKnowledgeChat.astro`。
> 本文描述当前架构，不适用于早期的 `/api/ask` 模板。

## 架构

| 本地能力 | 生产能力 | 用途 |
|---|---|---|
| bge-m3 | Workers AI `@cf/baai/bge-m3` | 查询向量 |
| sqlite-vec | Vectorize `ios-kb` | 语义候选召回 |
| SQLite FTS5 | D1 `IOS_DB` + `IOS_ARCHIVE_DB` | 分层关键词候选召回 |
| DeepSeek | `DEEPSEEK_API_KEY` | 知识库或通用流式答案 |
| SQLite 用户/反馈表 | 同一 D1 绑定 `DB` | 登录、额度、限流、反馈、审计 |

函数最多规划 4 条查询；每条从 Vectorize top48 和两个 D1 FTS v2 各 top60 召回，经 RRF、正文去重、
Workers AI `@cf/baai/bge-reranker-base`（1.5 秒超时，失败自动回退）后保留 anchor，并通过
`ios_ask_fts_v2_neighbors` 扩展相邻块。有可靠证据时走 `knowledge` 模式并校验段落级引用；
iOS 问题无可靠证据时返回 `422 no_evidence` 并退款，不调用 DeepSeek；检索故障返回 `503` 并退款。
`hi`、你好等问候跳过检索并返回固定文本；其他问题走 `general` 模式。非管理员账户每日有 2 次提问额度。
DeepSeek V4 的默认隐藏思考已显式关闭，避免 reasoning 与最终答案共用 `max_tokens` 后耗尽正文预算。

## 首次配置

在 Cloudflare Pages 项目的 Production 环境配置：

- D1：`DB`，数据库 `tommywu-lab-db`
- D1：`IOS_DB`，数据库 `tommywu-ios-kb-primary`
- D1：`IOS_ARCHIVE_DB`，数据库 `tommywu-ios-kb-archive`
- Workers AI：`AI`
- Vectorize：`VECTORIZE`，索引 `ios-kb`
- Secret：`DEEPSEEK_API_KEY`
- 可选变量：`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`ADMIN_EMAILS`；未配置模型覆盖时默认
  `deepseek-v4-flash`

不要配置旧的 `RATE_KV`，限流和反馈已迁移到 D1。
业务 `DB` 不保存 FTS；截至 2026-08-06 旧 v2 表已在记录 Time Travel 恢复点后移除，检索只读
`IOS_DB` 与 `IOS_ARCHIVE_DB`。

## 资料同步

在 iOS 知识库仓库更新并导出：

```bash
uv run ioskb index
uv run ioskb export-vectorize
uv run ioskb export-fts
```

`vectorize.ndjson` 的 ID 必须是稳定的 `v1-*`。上传时按最多 1,000 条分批使用
`wrangler vectorize upsert ios-kb --file <batch>`。完整 upsert 后，先备份远端 ID，只删除
本次导出中不再存在的 stale ID；绝不能删除整个 `ios-kb` 索引。

先生成两个互不重叠的 SQL 分区；主库保留全部 Tier 0 和前 40,000 条 Tier 1，扩展库保存
剩余 40,000 条 Tier 1：

```bash
uv run python scripts/build_fts_v2_import.py data/export/fts-v2.ndjson \
  data/export/ios_fts_v2_primary --max-rows 84997 --batch-size 5000
uv run python scripts/build_fts_v2_import.py data/export/fts-v2.ndjson \
  data/export/ios_fts_v2_archive --start-row 84997 --batch-size 5000
```

随后分别按文件名顺序导入。中途网络失败时先查询 `MAX(rowid)`，确认批次是否已经落库后再重试：

```bash
for sql_file in /Users/tommywu/Desktop/iOS知识agentt/data/export/ios_fts_v2_primary/[0-9][0-9][0-9].sql; do
  pnpm exec wrangler d1 execute tommywu-ios-kb-primary --remote --file "$sql_file" || exit 1
done
pnpm exec wrangler d1 execute tommywu-ios-kb-primary --remote \
  --file /Users/tommywu/Desktop/iOS知识agentt/data/export/ios_fts_v2_primary/999-finalize.sql
for sql_file in /Users/tommywu/Desktop/iOS知识agentt/data/export/ios_fts_v2_archive/[0-9][0-9][0-9].sql; do
  pnpm exec wrangler d1 execute tommywu-ios-kb-archive --remote --file "$sql_file" || exit 1
done
pnpm exec wrangler d1 execute tommywu-ios-kb-archive --remote \
  --file /Users/tommywu/Desktop/iOS知识agentt/data/export/ios_fts_v2_archive/999-finalize.sql
```

扩展库同样导入 `ios_fts_v2_archive/` 后执行其 `999-finalize.sql`。最终主库两张表都应为
84,997 行，扩展库两张表都应为 40,000 行；两库都测试 `MATCH 'uikit'` 和按
`file_key + chunk_ordinal` 的邻接查询。旧 v1 表需恢复到 `IOS_DB` 后才能作为 v1 回滚源。

## 发布与验证

在网站仓库执行：

```bash
pnpm astro sync
pnpm exec tsc --noEmit
pnpm check
pnpm build
pnpm audit --prod
git push origin main
```

部署完成后，无登录请求 `GET https://www.tommywutong.cn/api/ios-ask` 应返回未登录状态，不应暴露
密钥或知识库内容。完整的 10 场景生产自测从 macOS 钥匙串读取专用管理员 Bearer token：

```bash
pnpm ios-self-test:production
# 也可定向：IOS_SELF_TEST_CASES=weak,arc,general,no-evidence pnpm ios-self-test:production
```

评估覆盖问候、weak、ARC、普通问题、感谢/确认、混合多轮、iOS 新话题和无证据拒答；必须验证
知识回答的引用编号与来源类型。生产 token/Cookie 不写入仓库或日志。

## 回滚

网站代码问题通过回滚 `tommywu-lab` 的提交并重新部署处理。数据问题先从本地
`data/export/ios_fts/` 恢复旧 v1 表到 `IOS_DB`，再将 Pages 变量 `IOS_RETRIEVAL_VERSION`
设为 `v1`；未恢复旧表前保持 `v2`，不要把不存在的旧表配置为回滚源。
