# coverage —— 边界审计与生产验证清单覆盖

## 1. 阶段一：85 条种子的证据边界

| 证据性质 | 数量 | must_state |
|---|---|---|
| mixed_evidence（Apple 机制 + 个人/macOS 实验） | 40 | 多数 |
| Apple_source（Apple 文档/源码级） | 29 | 0 |
| iOS_public_api（公开 API/公共协议知识） | 13 | 0 |
| personal_experiment（个人基准） | 3 | 3 |
| macOS_observation / unclear | 0 | — |
| **合计 must_state_limitations=true** | | **16** |

决策：keep 82 / rewrite 3 / remove 0（rewrite：dyld 环境变量 iOS 化误设、『400 微秒的洞』自造比喻、
『计价单位』自造措辞）。duplicate_of 全部为 null（上一轮每小节 ≤2 题约束下未发现重复题意）。

## 2. 阶段二：130 条生产验证候选

| 维度 | 分布 |
|---|---|
| priority | P0 31 / P1 67 / P2 32 |
| origin | r3_gold 65 / undercovered_seed 65 |
| expected_mode | knowledge 110 / no_evidence 20 |
| diagnostic_layer | semantic_recall 66 / query_planning 24 / routing 22 / follow_up_context 16 / rerank_diversity 2 |

P0 覆盖（7 项任务要求全部达成）：actor reentrancy 1、精确符号 7、no-evidence 8、追问 3、
跨平台干扰 4（含 knowledge/no_evidence 两态）、SQLite/WAL 2、dyld 平台边界 2。

## 3. 未进入清单的部分（如实说明）

- r3 强集的 8 条 general 闲聊题未纳入（生产自测已有独立路由场景，且本清单聚焦检索与无证据判定）；
- r3 强集与种子池中共约 30 条 easy/P2 尾部题因 130 容量上限未进入，完整池仍在原批次可随时替换；
- 种子池 3 条 rewrite 中 1 条（dyld 环境变量）以改写题进入 P0，另 2 条以改写题进入 P1/P2。

## 4. 生产评测执行注意（写给未来执行者）

1. 清单只是候选：执行前须按当时的生产版本核对 expected_source_path 的行号仍与索引一致；
2. 带 answer_constraints 的 16+ 条，评测判分必须检查回答是否包含局限说明，否则判不通过；
3. no_evidence 20 条的判分依据是"退款 + 不调用模型 + 不用同主题泛资料冒充"，不是"检索不到"；
4. follow_up 条目需要按 dialogue_context 构造多轮会话后发送，不能单轮直发。
