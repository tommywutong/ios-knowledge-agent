# iOS 知识库问答 Agent（ioskb）

把多份 iOS 资料（Obsidian 笔记、26暑期内容、apple-developer-archive-vault、apple-docs-vault）
建成本地知识库，日常用 DeepSeek API 问答，**每条回答都标注来源出处**（哪个文件、哪个标题、第几行）。

详细架构与决策见 `HANDOFF.md`，当前进度见 `PROGRESS.md`。

当前第一阶段及 2026-07-29 全部增量同步已完成：本地库包含 142,563 个文件、1,078,759 个文本块；55,824 个核心块有
bge-m3 语义向量，1,022,935 个大型官方镜像块使用 FTS5 关键词检索。

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

## 生成专题知识卡片（资料定稿后跑）

```bash
uv run ioskb cards                       # 按 config.yaml 里的 topics 全部生成
uv run ioskb cards --topic RunLoop       # 只生成某主题
uv run ioskb index                       # 卡片回灌入库
```

## 网站接口（第三阶段）

```bash
uv run ioskb export-vectorize            # 导出 NDJSON，供上传 Cloudflare Vectorize
```
后续步骤见 `HANDOFF.md` 的"第三阶段"一节。

## 配置

- 语料来源、检索参数、卡片主题：`config.yaml`
- API key：`.env`（不进 git）

## 验证

```bash
uv run python -m unittest discover -s tests -v
uv run ioskb search "RunLoop mach_msg_trap"   # 本地混合检索，不调用 API
uv run ioskb stats
```
