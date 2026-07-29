# 博客问答接口——详细部署计划（第三阶段）

> 目标：在 tommywu-lab（Astro 6 + Cloudflare Pages）上加一个「iOS 知识问答」页面，
> 访客提问 → 检索你的知识库 → DeepSeek 生成带出处的回答。
> 本计划详细到每一步点什么；执行时可以让任何 AI 陪跑，也可以自己照做。
> **前置条件：本地知识库已建完（第二阶段），且你有 Cloudflare 账号（部署博客用的那个）。**

## 架构（与本地版的对应关系）

| 本地版 | 博客版 | 说明 |
|---|---|---|
| bge-m3（本机模型） | Workers AI `@cf/baai/bge-m3` | 同款模型，向量空间一致 |
| SQLite vec_chunks | Cloudflare Vectorize 索引 `ios-kb` | 由 export-vectorize 导出上传 |
| SQLite FTS5 | （无） | 博客版只走向量检索，够用 |
| ioskb web / cli | Pages Function `/api/ask` | 代码已写好：`functions/api/ask.ts` |
| .env 里的 key | Cloudflare Secret | key 只存在服务端 |

## Step 0：准备数据（本项目目录，约 5 分钟）

```bash
cd ~/Desktop/iOS知识agentt
uv run ioskb stats                 # 确认索引是最新的
uv run ioskb export-vectorize      # 生成 data/export/vectorize.ndjson
wc -l data/export/vectorize.ndjson # 记住条数，Step 3 要核对
```

## Step 1：创建 Vectorize 索引（tommywu-lab 目录，一次性）

```bash
cd ~/tommywu-lab
pnpm wrangler login                # 浏览器弹出授权（用部署博客的 Cloudflare 账号）
pnpm wrangler vectorize create ios-kb --dimensions=1024 --metric=cosine
```

## Step 2：上传向量

```bash
pnpm wrangler vectorize insert ios-kb --file="$HOME/Desktop/iOS知识agentt/data/export/vectorize.ndjson" --batch-size 1000
```
- 若报单条过大：说明某条 metadata 超 10KiB，回本项目把 `export_vectorize.py` 的 text 截断改小（2000→1500）再导出。
- 核对：`pnpm wrangler vectorize get ios-kb` 看 vectorCount 是否与 Step 0 的行数一致。

## Step 3：创建限流用 KV

```bash
pnpm wrangler kv namespace create ios-kb-rate
```
记下输出里的 namespace id。

## Step 4：放接口代码

把本项目 `website-templates/functions/api/ask.ts` 复制到 `tommywu-lab/functions/api/ask.ts`。
需要装类型（TS 编译不报错）：`pnpm add -D @cloudflare/workers-types`，并确认 tsconfig include 了 functions/。

## Step 5：配置绑定（Cloudflare Dashboard，点鼠标）

Dashboard → Workers & Pages → 项目 `tommywu-lab` → Settings → Bindings，添加三个：
1. **Workers AI**：变量名 `AI`
2. **Vectorize database**：变量名 `VECTORIZE`，选索引 `ios-kb`
3. **KV namespace**：变量名 `RATE_KV`，选 `ios-kb-rate`

然后设置 secret（终端）：
```bash
pnpm wrangler pages secret put DEEPSEEK_API_KEY --project-name=tommywu-lab
# 提示时粘贴你的 DeepSeek key
```

## Step 6：加前端页面（Astro）

新建 `src/pages/ios-ask.astro`（建议参考本地网页版 `src/ioskb/web_static/index.html` 的交互，
但要融入博客自己的布局组件与 DESIGN.md 的风格）。要点：
- POST `/api/ask`，请求体 `{question: "..."}`；响应 `{answer, sources[], remaining}`（非流式，简单可靠）；
- 回答用 marked 渲染 Markdown；来源列表渲染成编号引用条目：
  - `type=note/card` 的可链接到你博客已发布的对应文章（没有对应文章就只展示路径文字）；
  - `wwdc/doc/blog` 的展示路径与标题即可；
- 展示剩余次数 `remaining`，用完提示明日再来；
- 页面挂到导航或工具页，随你。

## Step 7：部署与验证

```bash
pnpm build && pnpm run deploy        # 你现有的部署命令
curl -s -X POST https://你的域名/api/ask -H 'content-type: application/json' \
  -d '{"question":"RunLoop 有哪些 mode"}'
```
验证清单：
- [ ] 正常返回 answer + sources；
- [ ] 同一 IP 第 11 次返回 429；
- [ ] 无 sources 时回答明确说"没有足够材料"（问一个知识库外的问题试试，如"Android 的 Handler"）；
- [ ] 页面在手机上排版正常。

## Step 8：日后同步更新

本地资料更新后：`uv run ioskb index` → `uv run ioskb export-vectorize` → 重跑 Step 2 的 insert
（相同 id 自动覆盖；若删除过大量笔记，先 `pnpm wrangler vectorize delete ios-kb` 重建再插）。

## 费用与风险

- Workers AI / Vectorize / KV / Pages Functions：个人博客流量下都在免费额度内；
- DeepSeek：唯一真实开销，约 ¥0.01-0.05/次，已有 10 次/IP/天限流兜底；
- 风险点：接口是公开的，若被刷可在 Dashboard 一键 Disable Function 或删掉 secret 止血。

## 回滚

出问题时删除 `functions/api/ask.ts` 重新部署即可，博客其他部分零影响。
