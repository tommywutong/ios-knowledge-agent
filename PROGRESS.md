# 进度报告

> 本文件随工作实时更新。最后更新：2026-09-05（资料源边界清理与本地同步状态）

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
| 9 | 全链路建库实测（历史基线） | ✅ 完成 | 2026-08-04 基线：141,735 文件 / 1,069,124 块；46,189 块向量化；大镜像 1,022,935 块全部进 FTS。当前数字见 2026-09-05 快照 |
| 10 | 交接文档定稿 | ✅ 完成 | README / PROGRESS / HANDOFF 已同步最终状态、验证证据与后续操作 |
| 11 | 本地网页版（ioskb web） | ✅ 完成 | 模型常驻+流式回答+可点击引用+多轮追问；桌面双击启动 `iOS知识库.command`；接口实测通过 |
| 12 | 博客问答接口详细部署计划 | ✅ 完成 | `website-templates/DEPLOY_PLAN.md`，步骤级，含验证清单与回滚 |
| 13 | 26 暑期资料增量同步 | ✅ 完成 | summer2026 281 文件 / 8,249 块；summer-labs 4 / 11；objc4-source 380 / 1,680；17 篇纯 AI 文章继续排除 |
| 14 | 两个 GitHub 文档仓库更新 | ✅ 完成 | 两个浅克隆已快进到远端 main；核心 2,491 文件 / 33,284 块全部向量化；bulk 98,164 / 505,374、archive 40,262 / 517,561 全部进入 FTS |
| 15 | 原始证据边界 | ✅ 完成 | ask/web/search 默认及 Vectorize 导出排除 card；实测回答来源全为原始资料 |
| 16 | 细粒度知识卡片 | ✅ 完成 | 95 文件 / 1,192 块 / 1,192 向量；全量结构、路径、编号和行号审计通过 |
| 17 | 网站版 Agent 审查与生产同步 | ✅ 完成 | API 检索阈值、权威等级、引用校验、断流状态和额度保护已修复；Vectorize 44,962 条、D1 FTS 44,962 条按稳定 ID 同步 |
| 18 | 通用对话与 V4 Flash | ✅ 完成 | 普通问题走 `general` 模式；默认模型 `deepseek-v4-flash`；已部署生产。后续 `0818ba0` 将可能为 iOS 的检索故障改为 503 退款，避免无依据降级 |
| 19 | 固定问候语与引用兼容 | ✅ 完成 | `hi`/你好由后端直接返回指定助手介绍，不调模型不占每日额度；组合及中文引用规范为 `[n]`；安全校验保留；网站 `0e8f05d` 已上线 |
| 20 | 新会话清空聊天记录 | ✅ 完成 | 前端移除 `sessionStorage` 聊天记录保存/恢复；聊天窗口每次重新打开为空，同一次打开仍支持多轮追问；网站 `27cff9f` 已上线 |
| 21 | 恢复复杂问题详细回答 | ✅ 完成 | 放宽知识/通用回答提示词，复杂问题展开机制、条件、示例和常见误区；`max_tokens` 从 1600 调为 2400；网站 `36eb071` 已上线 |
| 22 | Retrieval v2 分层 FTS 导出 | ✅ 完成 | 保留 44,962 条 Tier 0 原始证据；从两个 FTS-only 来源按主题/平台/符号/路径评分，最终 SQL 为 86,307 行，含邻接索引和 230 MiB 硬上限 |
| 23 | Retrieval v2 网站链路 | ✅ 完成 | 最多 4 路查询规划、Vectorize/D1 双路召回、RRF、Workers AI reranker、邻块扩展、段落引用校验、`no_evidence`/503 退款保护和 v1 回滚开关 |
| 24 | 生产 D1 FTS v2 导入 | ✅ 完成 | 初版曾在 `tommywu-lab-db` 使用两张 86,307 行 v2 表、约 338 MB；该阶段状态后续已由第 34/36 项的水平分库和业务库清理取代 |
| 25 | Retrieval v2 GitHub/Pages 发布 | ✅ 完成 | 知识库 `ccbeabf`/`024f4aa`、网站 `59975bc`/`33c6d9a` 已推送 `main`；三条 GitHub Actions 全部成功；初始 Pages 部署已验证，后续热修复为 `77f4779` |
| 26 | D1 容量故障修复 | ✅ 完成 | 确认 `Exceeded maximum DB size` 导致请求失败；移除重复旧 FTS，诊断表改为非阻断初始化；网站 `77f4779` 与 Pages `ed2b8461` 已上线 |
| 27 | 引用格式容错 | ✅ 完成 | `ae14f97` 曾对格式漂移做自动修正；该策略已被第 31 项收紧：保留格式兼容，但不再伪造或自动补第一个来源 |
| 28 | DeepSeek 空流重试与生产自测 | ✅ 完成 | 空正文流自动重试一次，两次为空退款并返回 `empty_answer`；网站 `3ebf6f0`、Pages `dfe8f355` 已上线；greeting、weak、ARC、general、no-evidence 五组生产自测全部通过 |
| 29 | 感谢语上下文误判修复 | ✅ 完成 | `9fc6fad` 让纯感谢/夸赞退出 iOS 检索，`7893c7d` 改为后端确定性回复且不调 DeepSeek、不占每日额度；当时的 Pages `ee8cef76` 与自定义域名定向复核均通过 |
| 30 | 混合对话路由重构 | ✅ 完成 | `0818ba0` 改为按当前轮次判断的新问题/追问状态机，只有显式追问继承相关历史；普通新话题隔离旧 iOS 上下文，边界技术问题先做证据探测；前端回传真实回答模式 |
| 31 | 来源、引用与上游可靠性加固 | ✅ 完成 | 落实暑期资料/官方/源码并列第一的排序；禁止自动伪造 `[1]`；`101cf86` 让空流和无正文断流安全重试且每次尝试使用独立超时；生产自测扩到 10 个混合场景并支持定向用例 |
| 32 | 资料新鲜度与安全同步 | ✅ 完成 | `ioskb freshness` 只读列出新增/修改/删除和 Git 镜像远端差异；`ioskb sync` 支持零写入预演、显式 fast-forward 拉取及仅本地云端发布包；最新对象模型笔记已增量入库，本地 freshness 已清零 |
| 33 | API/隐私/可观测性加固 | ✅ 完成 | DeepSeek 流与配额指标拆模块；精确错误原因、独立重试超时、后台留存清理、管理员 300 字来源预览；普通用户不接收个人笔记正文或绝对路径；当前 14 项 API 测试通过 |
| 34 | 完整 FTS 水平分库 | ✅ 完成 | Vectorize 44,997 条；主 D1 两张表各 84,997 行/约 332 MB，扩展 D1 各 40,000 行/约 114 MB，合计 124,997 条；双库 FTS/邻接 smoke test 通过 |
| 35 | 单一 CI 与依赖升级 | ✅ 完成 | 三条重复 workflow 合为一次完整门禁/构建/部署；Cloudflare Git 空部署关闭；Actions 锁定官方 SHA；TypeScript 6 及相关依赖升级，生产审计无已知漏洞 |
| 36 | DeepSeek V4 生成预算与生产收尾 | ✅ 完成 | 显式关闭默认隐藏思考，避免 ARC 等复杂题只消耗 reasoning 不输出正文；`a59622e` 上线后连续生产自测 10/10；业务 D1 旧 FTS 安全移除后约 0.35 MB，关键场景复测 4/4 |
| 37 | 聊天交互与内存管理回归 | ✅ 完成 | `0f9cff5` 增加输入历史、草稿恢复、4 条 FIFO 队列、动态拓展问题和分组图标操作区；生产原始问题返回 knowledge、6 来源、27 引用；Pages `97710bd9` 已上线 |
| 38 | 关闭聊天会话清理 | ✅ 完成 | `0571bb0` 关闭弹窗或 Astro 页面切换时清空未发送 FIFO 队列、中止当前请求，并在收尾后强制重置会话；停止按钮仍只停当前回答。Pages `00e20626` 已上线 |
| 39 | 聊天流式稳定与输入体验 | ✅ 完成 | `0571bb0` 流式期间不再每 48ms 重建 Markdown DOM，改为 80ms 纯文本更新+最终单次 Markdown 渲染，合并自动滚动帧；优化长文、列表和引用块排版；Enter 只换行，发送时统一清空输入框。Pages `00e20626` 已上线 |
| 40 | 资料源边界清理与生产同步 | 🟡 数据已上线，自测待额度恢复 | 两个 Git 镜像已更新；`summer-labs` 排除 `ios-source-learning/**` 并清理误收录的 3,469 文件。本地 1,080,698 块 / 56,827 向量；生产 Vectorize 55,635 条，新主 D1 84,818 行、归档 D1 40,000 行，Pages 部署 `2ed9ad9f` 已切换绑定。认证问答自测因 Cloudflare 免费套餐当日 D1 写入额度耗尽暂缓；2026-09-05 04:31（Asia/Shanghai）重试仍为 11/11 HTTP 500。 |

| 41 | 自动回复重启消息策略 | ✅ 完成 | `/Users/tommywu/wechat-auto-reply` 的 PR #2、#3 已合并至 `main`（`a1de282`）。默认启动只建立历史游标并跳过停机期间消息；控制 App 开关或 `--replay-offline` 才追补，批次认领状态在模型调用前持久化。Python 193 项、Swift 7 项测试通过 |
| 42 | Android/macOS 安装与差异文档 | ✅ 完成 | 自动回复仓库 PR #4 已合并至 `main`（`cef5812`），README 增加两端能力对比、macOS 13+ 依赖、Keychain 配置、控制 App 构建、权限、安全试跑和服务停止步骤；同时修正 `安装到Mac.command` 的自更新源。Python 193 项、Swift 7 项通过；Android 本机因缺少 SDK 未运行 |
| 43 | macOS 双服务生命周期统一 | ✅ 完成 | 自动回复仓库 PR #5 已合并至 `main`（`cdf5c43`）。控制 App 聚合规则服务与自动回复轮询器状态，启动只补齐未运行项，停止会卸载两项，重启按依赖顺序完整停启并轮询确认最终状态；修复 macOS Bash 3.2 空追补参数数组导致轮询器启动即退出。Python 194 项、Swift 11 项、release App 构建通过，本机真实停止/启动/重启均验证并恢复双服务运行 |
| 44 | 自动回复模块记忆与开发者地图 | ✅ 完成 | 自动回复仓库 PR #6 已合并至 `main`（`3951ea6`），新增根级 `AGENTS.md`/`MEMORY.md` 和各模块 `MEMORY.md`/`README.md`，提供渐进式上下文路由与开发约束；仅文档变更，未修改运行逻辑，Python 194 项回归测试通过 |
| 45 | 自动回复消息链路性能优化 | ✅ 完成 | 自动回复仓库 PR #7 已合并至 `main`（`f127a88`）。TraceMemo 白名单会话并行读取但按原顺序决策/认领/发送；TraceMemo、引擎和媒体下载复用 HTTP 连接；轮询按固定节拍运行，草稿模式统一读取 `var/poll-interval`；微信已有可用窗口时跳过重复启动等待。新增并行读取、失败隔离和脚本间隔回归测试；Python 197 项、macOS 测试 40 项、shell 语法与编译检查通过；本地 App 已重新构建并打开，未擅自启动原先停止的真实自动回复服务 |
| 46 | 按联系人个性化回复与机械拖延修复 | ✅ 完成 | 自动回复仓库 PR #8 已合并至 `main`（`0c087b3`）。每会话独立风格画像保留近30天最多48组“来信→本人回复”样本，按当前消息选最多3组相关示例；过滤历史“忙完再说/等会儿再说/晚点回”，低风险闲聊候选触发一次自然重写；本机“在不在、忙不忙”规则改为直接接话。Python 205 项、Swift 11 项、编译/脚本语法与差异检查通过，功能分支已删除 |
| 47 | 控制 App 自动更新与 Dock 窗口恢复 | ✅ 完成 | 自动回复仓库 PR #9 已合并至 `main`（`b1da74b`）。App 启动或 Dock 重新打开时，在工作区干净且 `main` 可 fast-forward 时自动拉取并重建控制 App；记录 bundle 对应提交号，关闭窗口后点击 Dock 恢复主窗口；本地有修改、分叉或网络失败时跳过，不强制重启后台服务。Python 205 项、Swift 11 项、编译/脚本语法与差异检查通过 |

## 已定决策（讨论阶段结论）

1. Embedding 用本地 bge-m3（不依赖任何 API）；
2. apple-developer-archive-vault（600MB 英文归档）只进关键词索引，不做向量；
3. objc4 源码入库；生产网站按当前约定将源码与暑期资料、官方文档并列第一；
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
- [x] Retrieval v2 本地导出、SQL 分批导入、生产 D1 原子切换与全文/邻接 smoke test 完成
- [x] Retrieval v2 网站代码推送 `main`、Pages 自动部署及公开 API 线上验证

## 遇到的问题记录

1. **apple-docs-vault 比预估大一个数量级**（10 万个 md、251MB 文本，含 405MB apple-docs 镜像与 435MB oss 目录），
   全量向量化需 20+ 小时。已按既定原则拆分：`apple-docs-core`（wwdc+blogs，向量+FTS）与
   `apple-docs-bulk`（apple-docs/oss/meta，只进 FTS）。config.yaml 已同步修改。
2. **少数导入文档把整段 transcript 压成一个超长物理行**，旧切块器会产生最大约 29,000 字符的块。
   已增加超长单行、多空行和窗口边界兜底，定向重建 361 个已入库文件，并全语料验证无超限块。
3. **sentence-transformers 会探测 Hugging Face adapter 元数据**，网络异常时可能让已下载模型也加载失败。
   `Embedder` 现同时使用 `local_files_only=True` 与 `HF_HUB_OFFLINE=1`，断网验证通过。

## 最终验证快照

- 2026-09-05 当前同步结果：本地 `uv run ioskb stats` 为 1,080,698 块 / 56,827 向量，`freshness --skip-upstreams --check` clean；39 项知识库单元测试全部通过，SQLite `quick_check` 为 `ok`。代码与记录已提交为 `f468b22`、`74ac4d5` 并推送到 `feat/knowledge-sync-20260905`。
- 生产数据发布完成：Vectorize `ios-kb` 55,635 条；新主库 `tommywu-ios-kb-primary-20260905` 正式 FTS/邻接表各 84,818 行，归档库各 40,000 行；两库 `MATCH 'uikit'` 均有命中。
- Pages 生产部署 `https://2ed9ad9f.tommywu-lab.pages.dev`（source `d331ef3`）与 `https://www.tommywutong.cn` 均返回首页/API HTTP 200，未登录 GET 显示 `configured: true`；认证 POST 自测在 2026-09-05 04:31（Asia/Shanghai）仍因 Cloudflare 免费 D1 当日写入额度耗尽返回 HTTP 500，等待额度重置后重跑。

- SQLite `PRAGMA quick_check = ok`；
- orphan chunks / files.nchunks 不一致 / vector 标记不一致 / 空块 / Markdown 超限块均为 0；
- 混合检索命中个人笔记、暑期提纲与 RunLoop 博客；
- FTS-only 检索命中 CloudKit 当前官方文档与 TN2232 / HTTPS Server Trust 历史归档；
- 26 暑期目录三路来源与磁盘现状一致：modified/new/stale 均为 0；17 篇纯 AI 文章未入库；
- Swift、Objective-C、C/C++ 与汇编检索已用具体源码符号验证命中；
- 新增 WWDC、App Store Server Notifications、App Sandbox 文档均已验证检索命中并返回文件与行号；
- 95 张卡片全量审计通过：固定结构、正文编号、原始路径、行号边界、无 card 自引用；
- RunLoop Source0/Source1 真实问答通过，8 条来源全部为原始资料；
- 历史本地索引基线：141,735 文件、1,069,124 块、46,189 已向量化；Obsidian 修改笔记重建 85 块、随后新增验收笔记 28 块；当前统计见本节首条 2026-09-05 快照；
- `ioskb freshness` 全库本地差异为 0，两个 Git 资料镜像均已是远端最新；
- 2026-08-06 知识库全量单元测试为 35 项，全部通过；其中 freshness/sync 新增 11 项安全回归测试；
- 2026-08-04 重新运行 16 项单元测试，全部通过；
- 本仓库 Retrieval v2、freshness/sync 和 FTS 分区导出已推送，`feat/retrieval-v2` 与 `main` 同步；网站同名功能分支也与 `main` 同步；
- 生产 Vectorize `ios-kb` 为 55,635 条；新主 D1 `ios_ask_fts_v2` 与邻接表各 84,818 条，扩展 D1 各 40,000 条；旧主库保留作回退快照；
- 新增《2026 暑假第一周验收 - 对象模型与进程内存地图》28 块已同步生产；真实问答返回 knowledge 模式、6 个来源和 25 处引用，并引用该笔记 14-54 行；
- 主/扩展 D1 分别约 332 MB/114 MB，远程 `MATCH 'uikit'` 与邻接查询均成功；Pages production 已绑定 `IOS_DB`/`IOS_ARCHIVE_DB`；
- 2026-08-05 曾因 D1 返回 `Exceeded maximum DB size` 导致请求失败；已移除重复旧 FTS 并将诊断表初始化改为非阻断，热修复发布后需复测登录态问答；
- 网站本地 Retrieval v2 测试、TypeScript、Astro Check、runtime 评测集覆盖、完整构建、链接和体积检查均通过；
- 网站最终 commit 为 `0f9cff5`；本地 14 项 API + 20 项 Retrieval 测试、TypeScript、Astro Check、完整构建、链接/体积检查和浏览器交互验证通过；
- `0571bb0` 聊天前端修复（关闭清理、流式稳定、Markdown 排版与 Enter 行为）已通过 Prettier、TypeScript、Astro Check（156 个文件）、14 项 API + 20 项 Retrieval 测试、253 页完整构建、261 页链接检查和体积预算；本次无可用浏览器实例，未进行真实 `<dialog>` 自动化回归；
- GitHub Actions 单一 CI/部署 run `31095416698` 全部成功；全新 checkout 会先运行 Astro 类型同步再做 TypeScript 检查；
- 最新 Pages production deployment 为 `https://2ed9ad9f.tommywu-lab.pages.dev`（source `d331ef3`）；该地址和 `https://www.tommywutong.cn` 的首页与公开 API 均返回 HTTP 200、`configured: true`；认证问答自测因 Cloudflare 免费 D1 当日写入额度耗尽暂缓；
- 历史生产自测记录（此前数据批次）：`给我讲讲iOS内存管理` 曾返回 knowledge、6 来源、27 引用；完整批次中的 general 曾瞬时 `fetch failed`，立即定向重跑通过。当前数据批次的 11 项认证自测仍待额度恢复；
- 记录 D1 Time Travel 恢复点后，业务库旧 `ios_ask_fts_v2`/邻接表已移除，库大小由约 338 MB 降到约 0.35 MB；登录、额度、指标表保留，随后 weak、ARC、general、no-evidence 复测 4/4；
- 生产自测认证信息只从 macOS 钥匙串读取，不写入仓库；上述是 API 级登录态复核，不冒充浏览器 Cookie 登录流程。
