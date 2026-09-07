# FINAL_REPORT —— golden-set-audit-r2-20260906

执行日期：2026-09-06。任务：旧黄金集 190 条逐题人工语义复核 + 7 条 no_evidence 候选按具体主张重审。

## 0. 校验记录

```
命令：python3 tools/validate_output.py
结果：gold-audit: 190 | no-evidence-audit: 7 | r2 gold: 160
      ALL CHECKS PASSED（0 错误）
```

校验覆盖：JSONL 合法/UTF-8/唯一 ID；r2 每条回溯到 A 的 keep/rewrite（keep 题面不得改动、
rewrite 题面必须等于审查记录改写）；knowledge 来源路径与行号真实（含文件行数上界）；
题面禁用结构残留正则（`目录|这篇在系列中的位置|本篇|本节|Part N|第N部分/篇/章|draft:|日期时间戳`）；
no_evidence 条目与 B 阶段结论一致；promote 条目附真实证据路径与行号。

## 1. 已由人工逐题确认的结论

1. **Codex 指出的 6 条结构标题全部处置**：gold-000023/024（「目录」）、gold-000027/028（「这篇在系列中的位置」）
   → remove；gold-000025/026（「第一部分 · 快速路径」「第三部分 · 消息转发」）→ 改写为自然概念题，
   且改写题逐条打开来源核对（Part 2 笔记第 23-45 行的大纲清单确实逐步列出缓存命中机制；第 46-75 行列出转发三部曲）。
2. **复核工具自身发现的额外 25 条问题并全部处置**：时间戳笔记标题（gold-000085/086/087/088/019）、
   笔记标题复述（gold-000011/045/053/056/014）、行文碎片（gold-000039/047/050/051/057/054/063）、
   编号规则语境（gold-000078/079）、论断式小标题（gold-000070/073）、无意义对比（gold-000067/068/091/094/095/097/098/099/101/102）。
3. **eval-001701 可提升为 knowledge 候选**：`wwdc/en/wwdc2021/10133-protect-mutable-state-with-swift-actors.md`
   第 281-295 行直接、完整地解释 actor reentrancy（跨 await 的状态假设风险、防死锁与前进保证、
   同步代码内变更状态/await 前恢复一致性的设计对策），第 561 行再次强调。已进入 r2（gold-r2，
   证据类型 wwdc）。
4. **6 条 no_evidence 经按主张核对后维持**：UIScreenKit 全库零命中（疑造词）；Combine 仅入门/实操场次；
   SwiftData 仅使用层文档；TestFlight 仅崩溃诊断场次；加密合规报告与分发合规零覆盖；
   SwiftUI 跑 Android 无任何资料。每条的证据路径与检索说明都写在 no-evidence-audit.jsonl。
5. **最终数字**：旧黄金集 keep 150 / rewrite 9 / remove 31；r2 = 160 条。

## 2. 仍只是候选（需人工/后续确认）

- r2 中 96 条 evidence_fit=partial 的条目：规则化重叠率核验通过，但"来源能否完整回答"未经人工逐字阅读。
- 9 条 rewrite 题：改写已二次核对来源片段，但语义自然度与回答深度仍属候选判断。
- 20 条 no_evidence 题：本批只验证了"语料无可答证据"（且仅对 7 条做了按主张深查），
  生产路由行为（会不会误判、会不会对部分主题返回知识）未验证。
- eval-001700 题面含疑造词 UIScreenKit，已建议人工改写或淘汰，r2 中仍以原题保留并加风险标注。

## 3. 只能在生产 Retrieval v2 中验证的结论

- r2 黄金集是否能在生产链路上命中预期证据、引用能否定位到标注行号；
- no_evidence 题在生产证据探测下的真实判定（尤其 SwiftUI/Combine 类"主题存在但具体主张不可答"的边界）；
- 追问条目的上下文继承与路由行为；
- 提升条目（actor reentrancy）的中文问题→英文逐字稿的跨语言召回效果。

## 4. 明确没有做的事情

- 未修改此前两个 GLM 批次的任何文件（所有纠错只落在本批次输出中）。
- 未修改原始资料、`db/`、索引、配置、应用代码、测试、网站仓库、Cloudflare、Git 历史。
- 未运行 `ioskb index/sync/ask/cards`、Wrangler、部署、任何 Git 写操作。
- 未读取或输出任何 `.env`、token、Cookie、密钥；未触碰 `mermaid-diagram.svg`。
- 未把 remove 条目改头换面塞回黄金集凑数；未依据"语料存在宽泛主题"推翻具体 no_evidence 问题。
- 未宣称任何生产检索结论。

## 5. 仍需 Codex 接手的事项

1. 抽查 r2 中 96 条 evidence_fit=partial（建议每主题抽 3 条），确认"来源可答"判定；
2. 对 eval-001700 做处置决定（改写为"SwiftUI 布局系统的工作方式"类可答题，或直接淘汰）；
3. 用生产 Retrieval v2 跑 r2 的 160 条，重点观察 actor reentrancy 提升条目与 20 条 no_evidence 的实际判定；
4. network/persistence/build-startup/swift-interop 主题的真实缺口需按资料人工补题（资料存在，题不在）；
5. `GCD.md`、`RunLoop 与 AutoReleasePool.md` 等时间戳博客摘录型笔记的结构质量问题
   （本批 5 条 remove 均源于此），建议纳入下一轮资料治理评估。
