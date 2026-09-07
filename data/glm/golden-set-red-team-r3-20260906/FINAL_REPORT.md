# FINAL_REPORT —— golden-set-red-team-r3-20260906

执行日期：2026-09-06。任务：对 r2 黄金集 160 条做红队审查（假设用户从未看过任何笔记标题），
并全量重审 20 条 no_evidence 题。

## 0. 校验记录

```
命令：python3 tools/validate_output.py
结果：r3-audit: 160 | no-evidence-audit-r3: 20 | r3 gold: 131
      ALL CHECKS PASSED（0 错误）
```

校验器内置：5 条已知反例黑名单（gold-r2-000036/067/068/069/071 及其题面碎片，绝不进入 r3）、
题面结构残留正则、comparison 必须 comparison_validity=valid、keep/rewrite 必须携带
normalized_subject / answer_boundary / source_support_summary、no_evidence 必须关联 r3 无证据审查、
keep 题面不得改动、rewrite 题面必须等于审查记录改写。**不使用词汇重叠率作为保留依据。**

## 1. 核心数字

| 项目 | 数量 |
|---|---|
| r2 的 160 条 → keep | **112** |
| r2 的 160 条 → rewrite（全部二次核对来源） | **19** |
| r2 的 160 条 → remove | **29** |
| r3 强集最终数量 | **131**（少于 160，质量优先，如实说明） |
| 20 条 no_evidence | retain 20 / promote 0 / remove 0 |

## 2. 全部 20 条 no_evidence 结论

20 条全部 `retain_no_evidence`。判定方式：每条按"具体主张"检索 wwdc zh+en 全部 284 个文件名
（本轮首次含 en）+ 全库关键词 grep。要点：

- WidgetKit/App Intents/StoreKit 2/Metal/Core ML/ARKit/Vision/Xcode Cloud/visionOS/Apple
  Intelligence/Swift Charts/iOS 26：文件名与关键词零命中；
- 唯一相关命中为 `10114-ipad-and-iphone-apps-on-apple-silicon-macs.md` 正文顺带提到 StoreKit 框架名
  ——不构成"订阅状态同步机制"的资料，不提升；
- 4 条跨平台题（Flutter/Android Handler/RN Fabric/Kotlin 协程 JVM/微信小程序）均为非 iOS 侧主张，语料零覆盖。

## 3. 红队新发现的最常见坏题模式（按出现频次）

1. **lookup/trouble 孪生题**（约 16 对）：同一笔记标题生成"X 到底是什么"+"我在面试里被问到 X"两条。
   标题为纯名词短语的保留一条或两条；含冒号叙事的改写一条、移除孪生（同义重复不留两条）。
2. **伪对比题**（12 条 comparison 中 8 条 remove / 2 条改写降级）：对比对象实为
   "标题 vs 正文"、"概述 vs 具体主题"、"同一概念两个标题"、"两个断言碎片"——只有
   isa_t vs ISA_BITFIELD、主线程 vs 其他线程 dispatch_sync 两对真正成立。
3. **叙事性小标题直接出题**："坐标系：frame 是算出来的…""那些桩在优化后大部分会消失""PAGE_MIN_SIZE
   不等于系统页大小"——已改写为自然问法（如"为什么 malloc 之后要等到首次写入才真正占用物理内存？"），
   每条都重新打开来源核对。
4. **文档元数据残留**：时间戳标题（2026-05-14 23:33 …）混入 5 条——均 remove（1 条救回改写）。
5. **栏目名当概念**："Runtime 简介""前言""卡顿-检测"等出现在题面——均 remove。

## 4. 仍须 Codex 人工抽检

1. 19 条 rewrite 题的语义自然度与回答深度（每条已核对来源片段，但属规则辅助下的人工判断）；
2. symbol 类 24 条中"函数用途由命名推断"的条目（源码定义真实，作用描述需对照源码确认）；
3. follow_up 16 条的上一轮助手内容部分为合成占位，衔接自然度需通读对话链确认；
4. r3 强集 131 条投入生产评测前的最终定版；
5. 20 条 no_evidence 的生产实际判定（本批结论仅为语料层证据核查）。

## 5. 明确没有做的事情

- 未修改任何此前 GLM 批次文件（r3 全部产物只在本目录）。
- 未修改原始资料、`db/`、索引、配置、代码、网站、Cloudflare、Git 历史。
- 未运行 `ioskb index/sync/ask/cards`、Wrangler、部署或任何 Git 写操作。
- 未读取或输出任何凭据；未触碰 `mermaid-diagram.svg`。
- 未为凑满 160 条保留低质量题（r3 = 131 条，缺口 29 条为移除的坏题，已在 r3-audit 逐条留痕）。
- 未宣称任何生产检索结论；未生成最终问答正文。
