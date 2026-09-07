# seed-evidence-boundary-and-eval-manifest-20260906 —— README / schema

## 任务

两阶段：① 对 85 条薄弱主题种子做**证据边界红队审计**（重点区分 Apple_source / iOS_public_api /
macOS_observation / personal_experiment / mixed_evidence / unclear）；② 汇同 r3 强集生成
**生产验证候选清单**（仅清单，不发起任何生产请求）。

## 输出

| 文件 | 说明 |
|---|---|
| `seed-boundary-audit.jsonl` | 85 条种子边界审计（keep 82 / rewrite 3 / remove 0；must_state 16） |
| `production-eval-manifest-candidates.jsonl` | **130 条**生产验证候选（P0 31 / P1 67 / P2 32；r3 65 + 种子 65） |
| `README.md` / `schema.md` / `coverage.md` / `FINAL_REPORT.md` | 说明与结论 |
| `tools/audit_seeds.py`、`build_manifest.py`、`validate_output.py` | 可复跑脚本与校验器 |

## schema 要点

### seed-boundary-audit.jsonl
`id`(sba-%06d)、`source_seed_id`、`decision`(keep/rewrite/remove)、`natural_query_test`、
`evidence_scope`（六类枚举）、`platform_scope`、`source_sufficiency`、`must_state_limitations`(bool)、
`required_answer_constraints`（如"必须说明结论仅来自 macOS 实验，不可直接外推 iOS"）、
`normalized_subject`、`answer_boundary`、`reason`、`rewrite_question`(仅 rewrite)、
`duplicate_of`(null=无重复)、`confidence`、`risk_notes`。

### production-eval-manifest-candidates.jsonl
`id`(pem-%06d)、`origin`(r3_gold/undercovered_seed)、`origin_id`、`question`、`topic`、`category`、
`expected_mode`、来源四字段（knowledge 必填）、`evidence_scope`、`answer_constraints`、
`evaluation_assertions`、`diagnostic_layer`（七层枚举）、`priority`(P0/P1/P2)、`selection_reason`、
`no_evidence_audit_ref`（no_evidence 必填，指向 r3 批次审查记录）、`risk_notes`。

## 判定依据（阶段一实际核对）

- dyld 环境变量段：来源为 `strings /usr/lib/dyld`（**macOS 观察**）→ 原题"在 iOS 上能用"改写为平台中性问法；
- NSUserDefaults 段：读 `~/Library/Preferences`（**macOS 路径**）→ 全部 must_state；
- 镜像个数计价/启动盲区：**探针实测（macOS）**→ 改写并强制区分实测与外推；
- SQLite 900 倍 / WAL / YYModel 基准：**个人实验** → 数字与机制结论分离陈述；
- URLSession/序列化/Codable 等：Apple 文档/源码级 → Apple_source，无平台外推风险。

## 复核方式

`python3 tools/validate_output.py` —— 含 5 项 P0 覆盖断言（actor reentrancy / 精确符号 / no-evidence /
追问 / 跨平台 / SQLite-WAL / dyld 平台边界）、must_state 与 constraints 联动、no_evidence 审查引用回溯、
题面结构残留、题意去重。校验器不使用词汇重叠率作判定依据。
