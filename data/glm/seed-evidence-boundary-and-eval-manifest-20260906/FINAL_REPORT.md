# FINAL_REPORT —— seed-evidence-boundary-and-eval-manifest-20260906

执行日期：2026-09-06。前置确认：r3 批次与种子池批次均已存在、校验通过、本轮只读。

## 0. 校验记录

```
命令：python3 tools/validate_output.py
结果：seed-boundary-audit: 85 | manifest: 130 | P0: 31
      manifest priority: {P0: 31, P1: 67, P2: 32} | origin: {r3_gold: 65, undercovered_seed: 65}
      mode: {knowledge: 110, no_evidence: 20}
      ALL CHECKS PASSED（0 错误）
```

校验覆盖：JSONL 合法、唯一 ID、knowledge 来源路径与行号真实（含文件行数上界）、跨文件回溯
（r3 强集 / 种子池 / 边界审计三方一致，keep 题面不改、rewrite 题面一致）、题意去重、
must_state 与 answer_constraints 联动、no_evidence 必须引用 r3 批次审查记录且断言包含
"不得用同主题泛资料冒充"、P0 七项覆盖断言、题面结构残留禁用。

## 1. 核心数字

| 项目 | 数量 |
|---|---|
| 种子 keep / rewrite / remove | **82 / 3 / 0** |
| 平台边界风险数（must_state_limitations=true） | **16**（mixed_evidence 40、personal_experiment 3 中产生） |
| 生产验证清单数量 | **130**（P0 31 / P1 67 / P2 32） |
| 清单构成 | r3_gold 65 + undercovered_seed 65；knowledge 110 + no_evidence 20 |

## 2. 已证实（逐条打开来源核对）

1. **dyld 环境变量段是 macOS 观察**（`strings /usr/lib/dyld`），原题"在 iOS 上能用"已改写为平台中性
   问法并强制局限说明（seed-boundary-audit rewrite 记录）。
2. **NSUserDefaults 段是 macOS 路径观察**（`~/Library/Preferences`，作者本人还在文中纠正过一次
   "macOS 上是同步写的"误判）→ 该文件 5 条种子全部 must_state。
3. **镜像个数计价、启动测量盲区为 macOS 探针实验** → 2 条改写为自然问法并要求区分
   "macOS 实测数据"与"iOS 是否适用的推断"。
4. **SQLite 900 倍、WAL、YYModel 基准为个人实验** → 5 条种子 must_state（机制结论与具体数字分离陈述）。
5. 其余 69 条种子为 Apple_source / iOS_public_api 性质，无平台外推风险。

## 3. 仍只是候选

- 3 条 rewrite 的语义自然度、19+16 条带局限说明题的"局限说明是否足以防误用"需人工通读；
- manifest 130 条的 answer_boundary 与 evaluation_assertions 是判分设计意图，
  实际判分脚本尚未编写（不在本轮范围）；
- evidence_scope 分类中 mixed_evidence 占 40 条，个别条目 Apple 机制与个人实验的占比未逐条量化。

## 4. 只能在生产 Retrieval v2 中验证

- 130 条候选的实际路由、召回、重排、引用与 no_evidence 判定表现；
- 特别是 actor reentrancy 的中文→英文逐字稿跨语言召回，以及 20 条 no_evidence 的退款行为；
- 带 must_state 的题在生产回答中是否会自动附带平台/版本/实验条件局限（提示词层能力）。

## 5. 最需 Codex 人工复核的 20 条

pem-000001（actor reentrancy，跨语言召回）、pem-000028/000029（SQLite 900 倍/WAL，个人实验局限）、
pem-000030/000031（dyld 分界与平台边界）、pem-000002/000003/000004/000005/000006/000007/000008/000009
（8 条精确符号 → query_planning）、pem-000010/000011/000012（no_evidence 代表：WidgetKit/App Intents/StoreKit 2）、
pem-000018（追问上下文继承）、pem-000032/000034/000035（URLSession 重定向、NSUserDefaults 两条 macOS 局限题）。

## 6. 明确没有做的事情

- 未修改任何既有 GLM 批次、原始资料、索引、`db/`、配置、代码、测试、网站仓库或 Git 历史。
- 未运行 `ioskb index/sync/ask/cards`、Wrangler、部署或任何 Git 写操作。
- 未调用任何生产接口——清单只是候选，生产评测的执行与判分脚本不在本轮范围。
- 未读取或输出任何凭据；未触碰 `mermaid-diagram.svg`。
- 未把"检索到同主题资料"当作"能回答具体问题"（no_evidence 断言已显式写入校验器）。
