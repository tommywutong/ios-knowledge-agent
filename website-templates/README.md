# 网站问答接口模板（第三阶段）

这里是给 tommywu-lab（Astro + Cloudflare Pages）加"iOS 知识问答"接口的现成代码。
**部署前提：第二阶段建库完成**（本地索引已建好）。

## 部署步骤（在 tommywu-lab 仓库里操作）

1. **上传向量数据到 Cloudflare Vectorize**（本项目目录下执行）：
   ```bash
   uv run ioskb export-vectorize        # 生成 data/export/vectorize.ndjson
   cd ~/tommywu-lab
   pnpm wrangler vectorize create ios-kb --dimensions=1024 --metric=cosine
   pnpm wrangler vectorize insert ios-kb --file=~/Desktop/iOS知识agentt/data/export/vectorize.ndjson
   ```
   注意：Vectorize 单条 metadata 上限 10KiB，导出脚本已把 text 截断到 2000 字符。

2. **复制接口代码**：把 `functions/api/ask.ts` 复制到 `tommywu-lab/functions/api/ask.ts`。

3. **配置绑定**（Cloudflare Dashboard → Pages 项目 tommywu-lab → Settings → Functions）：
   - Workers AI 绑定，变量名 `AI`
   - Vectorize 绑定，变量名 `VECTORIZE`，索引 `ios-kb`
   - KV namespace 绑定，变量名 `RATE_KV`（先建一个 KV namespace，如 `ios-kb-rate`）
   - Secret：`pnpm wrangler pages secret put DEEPSEEK_API_KEY --project-name=tommywu-lab`

4. **前端页面**：在 Astro 里加一个页面（如 `src/pages/ask.astro`），POST `/api/ask`，
   请求体 `{"question": "..."}`，响应：
   ```json
   { "answer": "Markdown 回答", "sources": [{"n":1,"type":"个人笔记","path":"...","title_path":"...","lines":"12-48"}], "remaining": 9 }
   ```
   页面风格建议跟随站内 DESIGN.md；来源列表渲染成可折叠的引用块。

5. **限流**：默认每 IP 每天 10 次（`ask.ts` 顶部 `DAILY_LIMIT` 可调），KV 记数、48h 过期。

## 费用

- Workers AI bge-m3 与 Vectorize：免费额度内绰绰有余（个人博客流量）。
- DeepSeek：每次问答约 ¥0.01–0.05，有限流兜底。

## 与本地库的同步

资料更新重建索引后，重新 `export-vectorize` 并 `wrangler vectorize insert`（相同 id 会覆盖）。
若有大量删除，最干净的方式是 delete 索引重建再插入。
