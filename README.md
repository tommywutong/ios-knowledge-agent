# iOS 知识库问答 Agent（ioskb）

把多份 iOS 资料（Obsidian 笔记、26暑期内容、apple-developer-archive-vault、apple-docs-vault）
建成本地知识库，日常用 DeepSeek API 问答，**每条知识库回答都标注来源出处**（哪个文件、哪个标题、第几行）。
生产网站还支持通用对话：非 iOS 或没有可靠资料的问题由 DeepSeek 直接回答，不伪造知识库引用。

详细架构与决策见 `HANDOFF.md`，当前进度见 `PROGRESS.md`。

截至 2026-08-04，本地库包含 141,734 个文件、1,069,089 个文本块；46,154 个块有
bge-m3 语义向量，另外 1,022,935 个大型官方镜像块使用 FTS5 关键词检索。

26 暑期目录当前已纳入 iOS 基础/进阶文档、Tips、MemoryMapLab 实验源码以及
Swift/Objective-C/C/C++/汇编源码；`articles/ai/` 下 17 篇纯 AI 文章、旧版重复 objc4 目录和构建/媒体产物按约定排除。
两个 GitHub 文档仓库也已更新到远端最新 `main` 并完成增量灌库。

## 首次安装（一次性）

```bash
cd ~/Desktop/iOS知识agentt
uv sync                                # 建虚拟环境、装依赖
cp .env.example .env                   # 然后编辑 .env，填入 DEEPSEEK_API_KEY
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
                                       # 下载 embedding 模型（~2.3GB，一次性）
```

模型下载完成后，`ioskb` 的日常索引和检索会强制使用本地缓存，断网也能运行。

## 建库 / 更新库

```bash
uv run ioskb index            # 增量：只处理新增/修改过的文件（资料更新后跑这个）
uv run ioskb index --full     # 全量重建
uv run ioskb stats            # 看库里有多少东西
```

索引和检索本身完全在本机执行，不调用 DeepSeek、不消耗 API token；只有 `ask`、网页版提问和
`cards` 会调用配置的模型 API。

## 日常问答

**推荐：网页版**（模型常驻内存，问答秒响应，支持多轮追问，来源可点击跳转）：
双击桌面的 `iOS知识库.command`，或运行 `uv run ioskb web`，浏览器会自动打开 http://127.0.0.1:8787 。

命令行版（备用）：
```bash
uv run ioskb ask "给我讲讲 RunLoop"
uv run ioskb ask "objc_msgSend 的查找流程" --provider deepseek-reasoner   # 深度推理模式
uv run ioskb search "AutoreleasePool 哨兵"   # 只检索不生成（免费，不调 API）
```

问答、网页版、默认 `search` 和 Vectorize 导出都只使用原始资料作为证据，模型生成的知识卡片
不会进入最终回答的引用。回答中的来源可定位到原文件、标题和行号。

## 细粒度专题知识卡片

```bash
uv run ioskb cards                              # 按 card_topics.yaml 生成缺少的卡片
uv run ioskb cards --topic weak引用实现          # 只生成某一张
uv run ioskb cards --topic weak引用实现 --force  # 覆盖重生成
uv run ioskb audit-cards                        # 检查结构、原始路径和行号
uv run ioskb index --source knowledge-cards     # 卡片回灌
```

当前已生成 95 张原子主题卡片，分为 11 组；共 1,192 个块并全部向量化。卡片正文使用 `[n]`
引用，末尾原始资料索引由程序自动写入，不能自行伪造位置。生成报告在
`knowledge_cards/_generation_report.json`。

## 网站接口

网站上的 iOS 问题优先使用 Vectorize + D1 混合检索并返回引用；`hi`、你好等问候和没有可靠
iOS 证据的问题走 `general` 模式。生产默认模型为 `deepseek-v4-flash`。

```bash
uv run ioskb export-vectorize            # 导出 NDJSON，供上传 Cloudflare Vectorize
```
导出使用稳定的 `v1-*` ID。网站同步时用 Vectorize `upsert`，并删除远端已不存在的旧 ID；
D1 的 `data/export/ios_fts/*.sql` 批次按顺序执行，最后执行 `999-finalize.sql`。
部署和线上验证记录见 `HANDOFF.md`。

## 配置

- 语料来源、检索参数：`config.yaml`
- 细粒度卡片主题：`card_topics.yaml`
- API key：`.env`（不进 git）

## 验证

```bash
uv run python -m unittest discover -s tests -v
uv run ioskb search "RunLoop mach_msg_trap"   # 本地混合检索，不调用 API
uv run ioskb stats
```
