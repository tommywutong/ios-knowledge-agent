# 进度报告

> 本文件随工作实时更新。最后更新：2026-07-29（26 暑期资料增量同步完成）

## 总体状态：✅ 第一阶段及最新资料增量同步完成

| # | 事项 | 状态 | 说明 |
|---|------|------|------|
| 1 | 项目脚手架与文档 | ✅ 完成 | pyproject/config.yaml/SPEC.md/README/网站接口模板 |
| 2 | Clone 两个 GitHub 资料仓库 | ✅ 完成 | 浅 clone 到 data/repos/（当前约 2.8G + 1.7G） |
| 3 | 采集清洗与切块（chunker/ingest/config） | ✅ 完成 | 超长单行与多空行边界已修复；Markdown 块最大 1600 字符；已增加 Swift/汇编采集和相应回归测试 |
| 4 | 索引与检索（db/embedder/retrieve） | ✅ 完成 | 真库实测通过：中文 FTS 命中、增量 hash 跳过/替换、向量存取、级联删除 |
| 5 | 问答核心与 CLI（llm/qa/cli） | ✅ 完成 | 七个子命令齐全；无 key 时报错提示已验证 |
| 6 | 知识卡片脚本（cards） | ✅ 完成 | 代码就绪；按约定等资料定稿后再真实生成 |
| 7 | Vectorize 导出脚本 + 网站接口模板 | ✅ 完成 | website-templates/ 含 Pages Function 完整代码与部署说明 |
| 8 | 依赖安装 + bge-m3 模型下载 | ✅ 完成 | SQLite 3.51；bge-m3 已下载并验证（dim=1024，MPS 可用、日常加载强制离线） |
| 9 | 全链路建库实测 | ✅ 完成 | 142,563 文件 / 1,078,759 块；核心 55,824 块全部向量化；大镜像 1,022,935 块全部进 FTS |
| 10 | 交接文档定稿 | ✅ 完成 | README / PROGRESS / HANDOFF 已同步最终状态、验证证据与后续操作 |
| 11 | 本地网页版（ioskb web） | ✅ 完成 | 模型常驻+流式回答+可点击引用+多轮追问；桌面双击启动 `iOS知识库.command`；接口实测通过 |
| 12 | 博客问答接口详细部署计划 | ✅ 完成 | `website-templates/DEPLOY_PLAN.md`，步骤级，含验证清单与回滚 |
| 13 | 26 暑期资料增量同步 | ✅ 完成 | summer2026 282 文件 / 8,351 块；summer-labs 4 / 11；objc4-source 380 / 1,680；17 篇纯 AI 文章继续排除 |
| 14 | 两个 GitHub 文档仓库更新 | ✅ 完成 | 两个浅克隆已快进到远端 main；核心 3,411 文件 / 43,816 块全部向量化；bulk 98,164 / 505,374、archive 40,262 / 517,561 全部进入 FTS |

## 已定决策（讨论阶段结论）

1. Embedding 用本地 bge-m3（不依赖任何 API）；
2. apple-developer-archive-vault（600MB 英文归档）只进关键词索引，不做向量；
3. objc4 源码入库但以 `source_code` 类型降权；
4. 界面：本地 CLI + 网站接口（第三阶段，Cloudflare Pages Functions + Vectorize + Workers AI）；
5. 建库解耦：代码与当前资料已实测并完成增量建库；后续资料变化时可再次运行 `ioskb index`；
6. 知识卡片脚本支持 DeepSeek / Claude 双后端（Anthropic OpenAI 兼容端点），不被 Claude 会员绑死。

## 留给用户的事

- [x] `.env` 已创建并配置 DEEPSEEK_API_KEY；问答链路此前已实测通过
- [x] 当前“26暑期内容”按约定范围完成增量灌库
- [ ] 如果以后确认资料定稿并需要专题卡片：`uv run ioskb cards` → `uv run ioskb index`
- [ ] 如果以后决定把问答公开到博客：按 `website-templates/DEPLOY_PLAN.md` 执行第三阶段

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
- 本地网页 `/api/status`：142,563 文件、1,078,759 块、55,824 已向量化，模型离线预热完成；
- 26 暑期目录三路来源与磁盘现状一致：modified/new/stale 均为 0；17 篇纯 AI 文章未入库；
- Swift、Objective-C、C/C++ 与汇编检索已用具体源码符号验证命中；
- 新增 WWDC、App Store Server Notifications、App Sandbox 文档均已验证检索命中并返回文件与行号；
- 本轮收尾没有调用 DeepSeek API，不产生 API token 费用。
