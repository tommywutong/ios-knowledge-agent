# iOS 知识问答生产部署与同步

> 当前生产实现位于 `/Users/tommywu/tommywu-lab`：Astro 7 + Cloudflare Pages Functions，
> 问答入口为 `POST /api/ios-ask`，前端组件为 `src/components/global/IosKnowledgeChat.astro`。
> 本文描述当前架构，不适用于早期的 `/api/ask` 模板。

## 架构

| 本地能力 | 生产能力 | 用途 |
|---|---|---|
| bge-m3 | Workers AI `@cf/baai/bge-m3` | 查询向量 |
| sqlite-vec | Vectorize `ios-kb` | 语义候选召回 |
| SQLite FTS5 | D1 `ios_ask_fts_v2` | 分层关键词候选召回 |
| DeepSeek | `DEEPSEEK_API_KEY` | 知识库或通用流式答案 |
| SQLite 用户/反馈表 | 同一 D1 绑定 `DB` | 登录、额度、限流、反馈、审计 |

函数最多规划 4 条查询；每条从 Vectorize top48 和 D1 FTS v2 top60 召回，经 RRF、正文去重、
Workers AI `@cf/baai/bge-reranker-base`（1.5 秒超时，失败自动回退）后保留 anchor，并通过
`ios_ask_fts_v2_neighbors` 扩展相邻块。有可靠证据时走 `knowledge` 模式并校验段落级引用；
iOS 问题无可靠证据时返回 `422 no_evidence` 并退款，不调用 DeepSeek；检索故障返回 `503` 并退款。
`hi`、你好等问候跳过检索并返回固定文本；其他问题走 `general` 模式。非管理员账户每日有 2 次提问额度。

## 首次配置

在 Cloudflare Pages 项目的 Production 环境配置：

- D1：`DB`，数据库 `tommywu-lab-db`
- Workers AI：`AI`
- Vectorize：`VECTORIZE`，索引 `ios-kb`
- Secret：`DEEPSEEK_API_KEY`
- 可选变量：`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`ADMIN_EMAILS`；未配置模型覆盖时默认
  `deepseek-v4-flash`

不要配置旧的 `RATE_KV`，限流和反馈已迁移到 D1。

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

随后在 `tommywu-lab` 仓库按文件名顺序导入 D1 的 `ios_fts_v2` 批次。先执行 `000.sql`，
再执行 `001.sql`–`115.sql`；中途网络失败时先查询 `MAX(rowid)`，确认批次是否已经落库后再重试：

```bash
for sql_file in /Users/tommywu/Desktop/iOS知识agentt/data/export/ios_fts_v2/{000..115}.sql; do
  pnpm exec wrangler d1 execute tommywu-lab-db --remote --file "$sql_file" || exit 1
done
pnpm exec wrangler d1 execute tommywu-lab-db --remote --command \
  "SELECT COUNT(*) AS rows FROM ios_ask_fts_v2_next; SELECT COUNT(*) AS neighbors FROM ios_ask_fts_v2_neighbors_next;"
```

两张 `*_next` 表都应为 `86,307` 行后，再执行 `999-finalize.sql` 原子切换。切换后核对：
`ios_ask_fts_v2=86,307`、`ios_ask_fts_v2_neighbors=86,307`、旧 `ios_ask_fts=44,962`，
并测试 `MATCH 'uikit'` 和按 `file_key + chunk_ordinal` 的邻接查询。旧表至少保留 7 天。

## 发布与验证

在网站仓库执行：

```bash
pnpm exec tsc --noEmit
pnpm check
pnpm build
pnpm audit --prod
git push origin main
```

部署完成后，无登录请求 `GET https://www.tommywutong.cn/api/ios-ask` 应返回未登录状态，不应暴露
密钥或知识库内容。完整的 9 题运行时评估需要管理员会话 cookie：

```bash
IOS_EVAL_COOKIE='tw_auth_session=...' pnpm exec node scripts/run-ios-agent-evaluation.mjs
```

评估应覆盖有证据回答、`hi`、Android/菜谱/天气/写诗等通用回答、引用编号和来源类型。
生产 cookie 不写入仓库或日志。

## 回滚

网站代码问题通过回滚 `tommywu-lab` 的提交并重新部署处理。数据问题优先将 Pages 变量
`IOS_RETRIEVAL_VERSION` 设为 `v1`，使用保留的 `ios_ask_fts`（44,962 行）和现有 Vectorize；
不要删除当前生产索引或旧表。确认 v2 稳定运行至少 7 天后，才可另行安排旧表清理。
