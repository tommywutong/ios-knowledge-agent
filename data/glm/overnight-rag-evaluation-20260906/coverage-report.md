# coverage-report —— overnight-rag-evaluation-20260906

生成时间：2026-09-06（过夜离线批次）。所有数字由脚本从批次内 JSONL 实时统计。

## 1. 评测候选（eval-candidates/，8 个批次）

**总计 1,866 条**（全部唯一 id，knowledge 题路径/行号校验 0 错误）。

### 按 category

| category | 数量 |
|---|---|
| answerable | 1,097 |
| comparison | 284 |
| symbol | 154 |
| alias | 148 |
| follow_up | 81 |
| no_evidence | 57 |
| general | 25 |
| cross_platform | 20 |

### 按 topic

| topic | 数量 |
|---|---|
| foundation | 348 |
| runloop-gcd | 258 |
| memory | 255 |
| runtime | 201 |
| uikit | 149 |
| network | 103 |
| persistence | 120 |
| source-symbol | 119 |
| kvc-kvo-notify | 95 |
| block | 78 |
| routing | 77 |
| swift-interop | 19 |
| build-startup | 19 |
| general | 25（含在 routing/general 计数外另列） |

（注：swift-interop/build-startup 数量较少，tips 中相关文件未全部纳入。）

### 按 difficulty

easy 495 / medium 891 / hard 480。

### 按 expected_mode

- knowledge：**1,775**（100% 有真实来源路径与行号，其中 1,381 条标注"模板生成待人工复核"）
- no_evidence：**66**
- general：**25**

### 建议覆盖量达成情况

| 建议项 | 要求 | 实际 |
|---|---|---|
| Runtime / ARC / 内存管理 | ≥250 | 456（runtime 201 + memory 255） |
| RunLoop / GCD / 多线程 | ≥180 | 258 |
| UIKit / 事件 / 视图 / Auto Layout | ≥160 | 149（uikit 单独）+ 相关 foundation/kvc 条目；uikit 主题略低，建议人工复核时关注 |
| 网络 / KVC / KVO / 通知 / Block | ≥160 | 276（network 103 + kvc-kvo-notify 95 + block 78） |
| 源码符号与精确 API | ≥150 | 154 |
| 中英文别名 / 错别字 / 改写 | ≥120 | 148 |
| no_evidence / general / 跨平台 / 路由边界 | ≥100 | 148（no_evidence 66 + general 25 + cross_platform 20 + routing 37） |
| 明确追问与新话题隔离 | ≥80 | 81 |

## 2. 术语与别名库（terminology-aliases.jsonl）

- 总数：**436**（唯一 canonical term）。
- 已定位真实证据行：**342**；证据为 null（标注"术语候选，未作为事实证据验证"）：**94**。
- 歧义标注：high 3（copy、atomic、Category 与 Extension）／medium 210／low 223。
- 类别分布：runtime 96、memory 79、runloop-gcd 72、uikit 69、foundation 25、build-startup 25、network 23、persistence 16、block 13、kvc-kvo-notify 9、swift-interop 9。

## 3. FTS 抽样（retrieval-samples/fts-sample-results.jsonl）

只读命令 `uv run ioskb search "<q>" --no-vector -k 8`，共 **252** 条（主题轮转均衡抽样，覆盖全部 13 个主题桶），全部为真实命令输出。

- **pass（1-3 名命中预期来源）：66**
- **partial（4-8 名命中）：46**
- **miss（top8 未命中）：140**
- **not_run：0**

另：observed_top_paths 中有 31 条路径在磁盘上已不存在（本地索引含陈旧 display path，见第 4 节补充发现）。

### 分主题薄弱度（miss 率从高到低）

| 主题 | 抽样 | pass | partial | miss | miss 率 |
|---|---|---|---|---|---|
| source-symbol | 20 | 0 | 0 | 20 | **100%** |
| swift-interop | 19 | 0 | 0 | 19 | **100%** |
| build-startup | 19 | 0 | 3 | 16 | **84%** |
| routing（跨平台 knowledge 侧） | 11 | 0 | 2 | 9 | 82% |
| foundation | 21 | 4 | 3 | 14 | 67% |
| memory | 20 | 5 | 4 | 11 | 55% |
| runtime | 20 | 5 | 4 | 11 | 55% |
| persistence | 20 | 6 | 4 | 10 | 50% |
| block | 21 | 4 | 8 | 9 | 43% |
| network | 20 | 9 | 5 | 6 | 30% |
| runloop-gcd | 20 | 12 | 3 | 5 | 25% |
| uikit | 20 | 8 | 7 | 5 | 25% |
| kvc-kvo-notify | 21 | 13 | 3 | 5 | 24% |

### 分 category（关键词层）

- symbol 类：**0/20 pass，20 miss** —— 精确符号查询在 FTS 路径全军覆没，top8 常被 `apple-docs-vault/oss` 的周报/博客镜像占据。
- alias 类：0/12 pass —— 口语改写主要依赖语义路径（本抽样为 FTS-only，不构成对生产向量链路的判断）。

**边界声明**：这只是本地 FTS-only 抽样，不能据此宣称生产 Vectorize + RRF + reranker 的完整效果；miss 率是"检索薄弱候选信号"，不是生产结论。

## 4. 资料质量发现（quality-findings.jsonl）

共 **332 条**：

- duplicate 168（WWDC zh/en 双语逐字稿 105、博客双语 60、已排除 objc4 目录 2、Obsidian/桌面双路径 1）
- low_ios_relevance 34（tips 中算法/设计模式/通用工程篇）
- directory_page 23
- bad_conversion 22（超长单行/转换残留）
- ambiguous_version 14（oss 镜像的来源等级风险）
- normal_sample 59（抽样确认正常）
- terminology_gap 10
- conflict 1

严重级别：medium 119 / low 105 / info 108。全部仅为发现报告，未执行任何修复或语料排除。

**补充发现（第 331-332 条）**：本地索引含磁盘上已不存在的陈旧文件路径（`awesome-ios-interview-main/articles/ios-basics/` 约 32 条，FTS 仍返回它们）；同一 awesome-ios-interview 语料在 Desktop 与 Obsidian 两处路径均有入库。只报告，未清理。

## 5. 失败归因（failure-triage.jsonl）

共 **120 条** = 定义类 18（10 个允许类别全覆盖 + 症状变体）+ 案例类 102（来自 FTS 抽样的 miss/partial，每主题每类别最多 4 条）。案例类别分布：lexical_recall 52（含 alias 映射）、rerank 38、missing_source 12（原 source_coverage 映射）。

## 6. 不能从当前资料可靠回答的领域（no_evidence 评测依据）

SwiftUI / Swift Concurrency / Combine / SwiftData / WidgetKit / App Intents / StoreKit 2 / Metal / Core ML / ARKit / Vision / Xcode Cloud / visionOS / Apple Intelligence 等新框架主题；Android/Flutter/RN/后端等非 iOS 平台细节；App Store 审核条款与合规材料；以及语料中完全缺失的通用计算机科学主题。

## 7. 最值得人工优先复核的前 30 项

1. **source-symbol 100% miss**：抽查 `fts-sample-results.jsonl` 中 symbol 案例，确认 objc4 源码块是否真的进入生产/本地 FTS top 候选（疑被 oss 镜像挤出）。
2. **oss 镜像压顶效应**（quality `ambiguous_version` 14 条）：`apple-docs-vault/oss` 周报类内容 type=doc 权重 1.12，与"官方文档第一"的意图偏差，需人工确认。
3. **WWDC zh/en 双语重复 105 对**：是否应只保留单一语言或做去重，属资料治理决策。
4. **build-startup 84% miss**：启动/链接/Mach-O 中文笔记标题与常见问法差异大，抽查别名缺口。
5. **swift-interop 100% miss**：样本仅 19，建议扩充该主题评测题再复核。
6. **alias 类 0/12**：确认生产向量路径能否兜住口语改写（本批次无法验证）。
7. **runtime/memory 55% miss**：抽查 lexical_recall 案例，确认是别名缺失还是关键词覆盖阈值（min_keyword_coverage=0.55）过滤。
8. **术语库 94 条无证据条目**：逐条确认术语表述是否正确，防止以讹传讹。
9. **1,381 条"模板生成待复核"评测题**：抽查 compare/boundary 模板题是否与锚定小节真正对应（每批次抽 10 条）。
10. **11 条跨平台 knowledge 题的 iOS 侧锚点**：确认锚定小节能否支撑 iOS 侧对比。
11. **follow_up 合成上一轮内容**（41 条）：确认语义衔接自然后再用于追问评测。
12. **no_evidence 66 条**：个别主题可能在 archive/bulk 有零星 FTS 命中，需生产复核判定阈值。
13. **归档/AI 融合稿冲突记录**（conflict 1 条）：确认 config 排除路径是否覆盖全部旧稿。
14. **目录页 23 条**：确认是否应进索引（config 未排除 `_Index`/README 类文件时会被收录）。
15. **超长单行 22 条**（bad_conversion）：docx/网页转换残留，影响切块质量，建议人工确认分块边界。
16. **objc4 已排除旧目录仍在磁盘**：生成引用时须确认路径指向在索引中的 `objc4/runtime`。
17. **low_ios_relevance 34 条**：是否对算法/设计模式 tips 降权属资料策略决策。
18. **术语映射缺口 10 条**：确认别名表能否 bridging 中英查询差距。
19. **博客双语 60 对**：同 WWDC 双语决策。
20. **normal_sample 59 条**：抽查 5 条确认"正常"判定无误。
21. **kvc-kvo-notify/runloop/uikit 主题表现最好**（miss 24-25%）：复核这些主题的别名与排序策略是否可复制到弱主题。
22. **foundation 67% miss**：类簇/集合类笔记标题与问法差异，抽查案例。
23. **routing 9 miss**：跨平台题在 FTS 路径几乎必然 miss，确认生产是否有意图探测兜底。
24. **lexical_recall 案例 52 条**：逐条核对查询分词与预期来源全文，输出缺失别名清单。
25. **rerank 案例 38 条**（4-8 名命中）：确认预期来源是否值得进入 top3（含 max_per_file 限制的影响）。
26. **比较类题 284 条**：预期"两小节对比"通常不在同一块内，复核预期行号范围是否需要跨节。
27. **tips 精选 45 文件之外的内容**未纳入评测题，是否扩充由人工决定。
28. **WWDC 精选仅 9 文件**：apple-docs-core 有 286 个 WWDC 文件，评测覆盖面极小，建议扩量。
29. **apple-archive 未出评测题**：FTS-only 历史归档的兜底能力未测，需专门设计关键词查询评测。
30. **dispatch 类/锁类笔记**（GCD.md 与专题笔记并存）：同主题多文件时预期来源选择是否合理，需人工裁定。

## 8. 资料覆盖

- source-coverage.jsonl 共 **137** 条实际检查过的文件：obsidian-ios 52 / summer2026 52 / objc4-source 15 / apple-docs-core 14 / summer-labs 4。
- 已知未覆盖：apple-archive（未出题）、apple-docs-bulk（未出题）、tips 其余 ~84 文件、WWDC 其余 ~277 文件、iOS-Weekly 等未抽样的 oss 内容。
