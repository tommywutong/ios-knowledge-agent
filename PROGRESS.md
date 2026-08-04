# 进度报告

> 本文件随工作实时更新。最后更新：2026-08-04（问候语、引用兼容、跨仓库同步和生产部署已核对）

## 总体状态：✅ 原始资料建库、证据链改造及细粒度知识卡片完成

| # | 事项 | 状态 | 说明 |
|---|------|------|------|
| 1 | 项目脚手架与文档 | ✅ 完成 | pyproject/config.yaml/SPEC.md/README/网站接口模板 |
| 2 | Clone 两个 GitHub 资料仓库 | ✅ 完成 | 浅 clone 到 data/repos/（当前约 2.8G + 1.7G） |
| 3 | 采集清洗与切块（chunker/ingest/config） | ✅ 完成 | 超长单行与多空行边界已修复；Markdown 块最大 1600 字符；已增加 Swift/汇编采集和相应回归测试 |
| 4 | 索引与检索（db/embedder/retrieve） | ✅ 完成 | 真库实测通过：中文 FTS 命中、增量 hash 跳过/替换、向量存取、级联删除 |
| 5 | 问答核心与 CLI（llm/qa/cli） | ✅ 完成 | 问答与默认检索强制排除 card；最终引用只来自原始资料 |
| 6 | 知识卡片脚本（cards） | ✅ 完成 | 95 张/11 组已生成；程序化原始来源索引、失败重试、usage 统计和 audit-cards 已完成 |
| 7 | Vectorize 导出脚本 + 网站接口模板 | ✅ 完成 | website-templates/ 含 Pages Function 完整代码与部署说明 |
| 8 | 依赖安装 + bge-m3 模型下载 | ✅ 完成 | SQLite 3.51；bge-m3 已下载并验证（dim=1024，MPS 可用、日常加载强制离线） |
| 9 | 全链路建库实测 | ✅ 完成 | 141,734 文件 / 1,069,089 块；46,154 块向量化；大镜像 1,022,935 块全部进 FTS |
| 10 | 交接文档定稿 | ✅ 完成 | README / PROGRESS / HANDOFF 已同步最终状态、验证证据与后续操作 |
| 11 | 本地网页版（ioskb web） | ✅ 完成 | 模型常驻+流式回答+可点击引用+多轮追问；桌面双击启动 `iOS知识库.command`；接口实测通过 |
| 12 | 博客问答接口详细部署计划 | ✅ 完成 | `website-templates/DEPLOY_PLAN.md`，步骤级，含验证清单与回滚 |
| 13 | 26 暑期资料增量同步 | ✅ 完成 | summer2026 281 文件 / 8,249 块；summer-labs 4 / 11；objc4-source 380 / 1,680；17 篇纯 AI 文章继续排除 |
| 14 | 两个 GitHub 文档仓库更新 | ✅ 完成 | 两个浅克隆已快进到远端 main；核心 2,491 文件 / 33,284 块全部向量化；bulk 98,164 / 505,374、archive 40,262 / 517,561 全部进入 FTS |
| 15 | 原始证据边界 | ✅ 完成 | ask/web/search 默认及 Vectorize 导出排除 card；实测回答来源全为原始资料 |
| 16 | 细粒度知识卡片 | ✅ 完成 | 95 文件 / 1,192 块 / 1,192 向量；全量结构、路径、编号和行号审计通过 |
| 17 | 网站版 Agent 审查与生产同步 | ✅ 完成 | API 检索阈值、权威等级、引用校验、断流状态和额度保护已修复；Vectorize 44,962 条、D1 FTS 44,962 条按稳定 ID 同步 |
| 18 | 通用对话与 V4 Flash | ✅ 完成 | 问候及无可靠 iOS 证据的问题走 `general` 模式；检索故障自动降级；默认模型 `deepseek-v4-flash`；已部署生产 |
| 19 | 固定问候语与引用兼容 | ✅ 完成 | `hi`/你好由后端直接返回指定助手介绍，不调模型不占每日额度；组合及中文引用规范为 `[n]`；安全校验保留；网站 `0e8f05d` 已上线 |

## 已定决策（讨论阶段结论）

1. Embedding 用本地 bge-m3（不依赖任何 API）；
2. apple-developer-archive-vault（600MB 英文归档）只进关键词索引，不做向量；
3. objc4 源码入库但以 `source_code` 类型降权；
4. 界面：本地 CLI + Cloudflare Pages Functions + Vectorize + Workers AI 网站版；
5. 建库解耦：代码与当前资料已实测并完成增量建库；后续资料变化时可再次运行 `ioskb index`；
6. 知识卡片脚本支持 DeepSeek / Claude 双后端（Anthropic OpenAI 兼容端点），不被 Claude 会员绑死；
7. 原始资料是唯一事实证据；知识卡片只用于复习和辅助浏览，不进入问答上下文；
8. DeepSeek 默认模型使用 `deepseek-v4-flash`，每张卡片保存实际 token 用量到生成报告。

## 留给用户的事

- [x] `.env` 已创建并配置 DEEPSEEK_API_KEY；问答链路此前已实测通过
- [x] 当前“26暑期内容”按约定范围完成增量灌库
- [x] 95 张细粒度卡片已生成、审计并回灌；本轮实际 443,950 输入 + 206,680 输出 = 650,630 tokens
- [x] 网站版问答已接入博客；资料更新按 `HANDOFF.md` 的稳定 ID 同步流程执行

## 遇到的问题记录

1. **apple-docs-vault 比预估大一个数量级**（10 万个 md、251MB 文本，含 405MB apple-docs 镜像与 435MB oss 目录），
   全量向量化需 20+ 小时。已按既定原则拆分：`apple-docs-core`（wwdc+blogs，向量+FTS）与
   `apple-docs-bulk`（apple-docs/oss/meta，只进 FTS）。config.yaml 已同步修改。
2. **少数导入文档把整段 transcript 压成一个超长物理行**，旧切块器会产生最大约 29,000 字符的块。
   已增加超长单行、多空行和窗口边界兜底，定向重建 361 个已入库文件，并全语料验证无超限块。
3. **sentence-transformers 会探测 Hugging Face adapter 元数据**，网络异常时可能让已下载模型也加载失败。
   `Embedder` 现同时使用 `local_files_only=True` 与 `HF_HUB_OFFLINE=1`，断网验证通过。

## 最终验证快照

- SQLite `PRAGMA quick_check = ok`；
- orphan chunks / files.nchunks 不一致 / vector 标记不一致 / 空块 / Markdown 超限块均为 0；
- 混合检索命中个人笔记、暑期提纲与 RunLoop 博客；
- FTS-only 检索命中 CloudKit 当前官方文档与 TN2232 / HTTPS Server Trust 历史归档；
- 26 暑期目录三路来源与磁盘现状一致：modified/new/stale 均为 0；17 篇纯 AI 文章未入库；
- Swift、Objective-C、C/C++ 与汇编检索已用具体源码符号验证命中；
- 新增 WWDC、App Store Server Notifications、App Sandbox 文档均已验证检索命中并返回文件与行号；
- 95 张卡片全量审计通过：固定结构、正文编号、原始路径、行号边界、无 card 自引用；
- RunLoop Source0/Source1 真实问答通过，8 条来源全部为原始资料；
- 本地网页 `/api/status`：141,734 文件、1,069,089 块、46,154 已向量化，模型离线预热完成；
- 2026-08-04 重新运行 16 项单元测试，全部通过；
- 本仓库最后核对的功能代码基线为 `2f6e9b0`（交接文档提交位于其后），网站仓库 `main`/`origin/main` = `0e8f05d`；
- 生产 Vectorize 与 D1 均为 44,962 条，`GET /api/ios-ask` 返回 `configured: true`；
- 网站提交 `0e8f05d` 的 Code quality、Build and Check 和 Cloudflare Pages 部署全部成功；
- 最新 Pages 部署为 `https://5263a04a.tommywu-lab.pages.dev`，生产 API 返回 `configured: true`；
- 登录态 9 题运行时评估待有管理员 `IOS_EVAL_COOKIE` 时重跑，不在仓库保存该 Cookie。
