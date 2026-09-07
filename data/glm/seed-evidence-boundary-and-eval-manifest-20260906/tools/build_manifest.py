#!/usr/bin/env python3
"""第二阶段：生产验证候选清单（仅清单，不发起任何请求）。
来源：r3 强集 + 第一阶段通过（keep/rewrite）的种子。P0 强制覆盖指定主题。
"""
import json, re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
R3 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-red-team-r3-20260906")
SD = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/undercovered-topic-seeds-20260906")

r3 = [json.loads(l) for l in (R3 / "gold-eval-candidates-r3.jsonl").read_text(encoding="utf-8").splitlines()]
seeds = [json.loads(l) for l in (SD / "seed-eval-candidates.jsonl").read_text(encoding="utf-8").splitlines()]
sba = {r["source_seed_id"]: r for r in (json.loads(l) for l in (HERE.parent / "seed-boundary-audit.jsonl").read_text(encoding="utf-8").splitlines())}
r2gold = {r["id"]: r for r in (json.loads(l) for l in (R3 / "gold-eval-candidates-r3.jsonl").read_text(encoding="utf-8").splitlines())}
NEV3 = {r["source_r2_id"]: r["id"] for r in (json.loads(l) for l in (Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-red-team-r3-20260906") / "no-evidence-audit-r3.jsonl").read_text(encoding="utf-8").splitlines())}

ASSERT = {
    "knowledge": ["expected_mode=knowledge，证据充足时不得返回 no_evidence",
                  "预期来源出现在最终候选中（同文件即可），引用可回溯到标注区间",
                  "回答范围不超出 answer_boundary"],
    "no_evidence": ["expected_mode=no_evidence：应返回无证据并退款，不调用模型",
                    "不得用同主题泛资料拼凑出『看似有据』的回答",
                    "未检索到可靠证据时不得降级为 general 冒充"],
    "follow_up": ["追问必须继承上一轮模式与相关历史，检索不得混入无关旧话题",
                  "expected_mode=knowledge，回答锚定在追问所涉小节"],
    "general": ["路由为 general，不进入 iOS 检索，不伪造知识库引用"],
    "cross": ["按预期模式路由；iOS 侧证据可用时引用锚定区间，非 iOS 侧必须声明无资料"],
}
LAYER = {"symbol": "query_planning", "alias": "lexical_recall", "follow_up": "follow_up_context",
         "no_evidence": "routing", "general": "routing", "cross_platform": "routing",
         "comparison": "rerank_diversity", "answerable": "semantic_recall"}

rows = []
def add(origin, origin_id, g, priority, sel, extra_constraints=None, layer=None):
    cat = g["category"]
    mode = g["expected_mode"]
    if mode == "no_evidence":
        akey = "no_evidence"
    elif cat == "cross_platform":
        akey = "cross"
    elif cat in ASSERT:
        akey = cat
    else:
        akey = "knowledge"
    constraints = list(extra_constraints or [])
    rows.append({
        "id": "pem-%06d" % (len(rows) + 1),
        "origin": origin,
        "origin_id": g["id"],
        "question": g["question"],
        "topic": g["topic"],
        "category": cat,
        "expected_mode": mode,
        "expected_source_path": g["expected_source_path"],
        "expected_start_line": g["expected_start_line"],
        "expected_end_line": g["expected_end_line"],
        "expected_evidence_type": g["expected_evidence_type"],
        "evidence_scope": ("通用技术问题，公开可验证" if mode != "knowledge" else "见来源；平台/实验局限见 answer_constraints"),
        "answer_constraints": constraints,
        "evaluation_assertions": ASSERT[akey],
        "diagnostic_layer": layer or LAYER.get(cat, "semantic_recall"),
        "priority": priority,
        "selection_reason": sel,
        "no_evidence_audit_ref": (NEV3.get(g.get("source_r2_id")) if mode == "no_evidence" else None),
        "risk_notes": list(g.get("risk_notes") or []),
    })

used_q = set()
def dup(g):
    k = re.sub(r"\s", "", g["question"])[:50]
    if k in used_q:
        return True
    used_q.add(k)
    return False

# ---------- P0：强制覆盖 ----------
P0_DONE = Counter()
def take(g, sel, extra_constraints=None, layer=None, pri="P0"):
    if dup(g): return False
    origin = "r3_gold" if g["id"].startswith("gold-r3") else "undercovered_seed"
    add(origin, g["id"], g, pri, sel, extra_constraints, layer)
    return True

# actor reentrancy
for g in r3:
    if "重入" in g["question"]: take(g, "P0：actor reentrancy 是 r3 唯一从 no_evidence 提升的 knowledge 题，跨语言召回风险最高")
# 精确符号 8 条（覆盖 objc_msgSend/cache/weak/SideTable 等核心）
sym = [g for g in r3 if g["category"] == "symbol"]
core_kw = ["objc_msgSend", "objc_msgSendSuper", "objc_msgLookup", "lookUpImpOrForward", "cache_fill", "objc_sync_enter", "resolveMethod_locked", "_objc_init"]
for kw in core_kw:
    for g in sym:
        if kw.lower() in g["question"].lower():
            take(g, f"P0：精确符号（{kw}）→ query_planning 层验证（CODEX 已证裸符号可召回）"); break
# no-evidence 8 条
ne = [g for g in r3 if g["expected_mode"] == "no_evidence"]
for g in ne[:8]:
    take(g, "P0：no_evidence 判定（无证据退款、不调用模型、不用同主题泛资料冒充）")
# 追问 6 条
fu = [g for g in r3 if g["category"] == "follow_up"]
for g in fu[:6]:
    take(g, "P0：追问上下文继承与路由状态机")
# 跨平台干扰 4 条（2 knowledge + 2 no_evidence）
cp_k = [g for g in r3 if g["category"] == "cross_platform" and g["expected_mode"] == "knowledge"]
cp_n = [g for g in r3 if g["category"] == "cross_platform" and g["expected_mode"] == "no_evidence"]
for g in cp_k[:2] + cp_n[:2]:
    take(g, "P0：跨平台干扰下的路由与证据声明")
# SQLite/WAL 2 条
for g in seeds:
    if "900 倍" in g["question"] or ("WAL 后并发" in g["question"]):
        take(g, "P0：SQLite/WAL 薄弱主题（个人实验题，答案必须带局限）", extra_constraints=sba[g["id"]]["required_answer_constraints"])
# dyld 平台边界 2 条
for g in seeds:
    ql = g["question"].lower()
    if "dyld" in ql and ("分界" in g["question"] or "环境变量" in g["question"]):
        gg = dict(g)
        a = sba[g["id"]]
        if a["decision"] == "rewrite":
            gg["question"] = a["rewrite_question"]
        take(gg, "P0：dyld 平台边界（macOS 观察 vs iOS 未验证，必须带局限）",
             extra_constraints=a["required_answer_constraints"])
print("P0:", len(rows), dict(Counter(r["topic"] for r in rows)))

# ---------- P1 ----------
# 种子：hard 全部 + must_state 全部（未入 P0 的）
seed_pool = []
for g in seeds:
    a = sba[g["id"]]
    if a["decision"] == "remove":
        continue
    qq = a.get("rewrite_question") or g["question"]
    seed_pool.append((g, a, qq))
p1_seeds = 0
for g, a, qq in seed_pool:
    if g["difficulty"] == "hard" or a["must_state_limitations"]:
        gg = dict(g); gg["question"] = qq
        if not dup(gg):
            add("undercovered_seed", g["id"], gg, "P1",
                "P1：" + ("hard 级机制题" if g["difficulty"] == "hard" else "带平台/实验局限说明的题"),
                extra_constraints=a["required_answer_constraints"], layer="semantic_recall")
            p1_seeds += 1
# r3：follow_up 剩余 + comparison + cross 剩余 + symbol 剩余
for g in r3:
    if g["category"] in ("follow_up", "comparison", "cross_platform") and not dup(g):
        add("r3_gold", g["id"], g, "P1", "P1：追问/对比/跨平台全量保留（r3 红队已通过）")
for g in sym:
    if not dup(g):
        add("r3_gold", g["id"], g, "P1", "P1：精确符号全覆盖")
for g in ne[8:]:
    if not dup(g):
        add("r3_gold", g["id"], g, "P1", "P1：no_evidence 全量保留（各主题一个判定样本）")
print("after P1:", len(rows))

# ---------- P2：填充到 130 ----------
CAP = 130
for (g, a, qq) in seed_pool:
    if len(rows) >= CAP: break
    gg = dict(g); gg["question"] = qq
    if not dup(gg):
        add("undercovered_seed", g["id"], gg, "P2", "P2：薄弱主题种子（按容量填充）",
            extra_constraints=a["required_answer_constraints"], layer="semantic_recall")
for g in r3:
    if len(rows) >= CAP: break
    if g["expected_mode"] != "knowledge" or g["category"] in ("symbol", "follow_up", "comparison"):
        continue
    if not dup(g):
        add("r3_gold", g["id"], g, "P2", "P2：r3 红队通过的 knowledge 题（按容量填充）", layer="semantic_recall")

rows.sort(key=lambda r: ({"P0":0,"P1":1,"P2":2}[r["priority"]], r["id"]))
for i, r in enumerate(rows, 1):
    r["id"] = "pem-%06d" % i
with (HERE.parent / "production-eval-manifest-candidates.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("manifest:", len(rows))
print("priority:", dict(Counter(r["priority"] for r in rows)))
print("origin:", dict(Counter(r["origin"] for r in rows)))
print("layer:", dict(Counter(r["diagnostic_layer"] for r in rows)))
print("mode:", dict(Counter(r["expected_mode"] for r in rows)))
print("P0 topics:", dict(Counter(r["topic"] for r in rows if r["priority"]=="P0")))
