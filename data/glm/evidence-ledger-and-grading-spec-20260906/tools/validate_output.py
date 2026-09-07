#!/usr/bin/env python3
"""r5 校验器：证据账本/平台边界/判分契约/对照集的合法性与真实性。"""
import json, re, sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R4 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/seed-evidence-boundary-and-eval-manifest-20260906")
R3 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-red-team-r3-20260906")

errors = []
def err(m): errors.append(m)

def load(fp):
    rows = []
    for i, ln in enumerate(open(fp, encoding="utf-8"), 1):
        ln = ln.strip()
        if not ln: err(f"{fp}:{i} 空行"); continue
        try: rows.append(json.loads(ln))
        except Exception as e: err(f"{fp}:{i} JSON 非法: {e}")
    return rows

manifest = {r["id"]: r for r in load(R4 / "production-eval-manifest-candidates.jsonl")}
LEDGER_STATUS = {"direct", "partial", "no_evidence", "mixed", "needs_human"}
E_KINDS = {"Apple_source", "iOS_public_api", "macOS_observation", "personal_experiment",
           "user_note_inference", "historical_reference"}
S_LEVELS = {"direct", "contextual", "contradictory"}

# ---------- evidence-ledger ----------
ledger = load(BASE / "evidence-ledger.jsonl")
led_ids = set()
led_by_mid = {}
for r in ledger:
    if r["id"] in led_ids: err(f"ledger 重复 id {r['id']}")
    led_ids.add(r["id"])
    if r["manifest_id"] in led_by_mid: err(f"ledger 重复 manifest {r['manifest_id']}")
    led_by_mid[r["manifest_id"]] = r
    if r["manifest_id"] not in manifest: err(f"{r['id']} manifest_id 不存在")
    if r["evidence_status"] not in LEDGER_STATUS: err(f"{r['id']} evidence_status 非法")
    if not (1 <= len(r["core_claims"]) <= 4): err(f"{r['id']} core_claims 数量非法")
    if not r.get("answer_boundary"): err(f"{r['id']} 缺 answer_boundary")
    if not r.get("citation_acceptance_rule"): err(f"{r['id']} 缺 citation_acceptance_rule")
    if r["confidence"] not in {"low","medium","high"}: err(f"{r['id']} confidence 非法")
    if r["evidence_status"] == "no_evidence":
        if not r["unsupported_claims"]: err(f"{r['id']} no_evidence 缺 unsupported_claims")
        if "no_evidence" not in r["citation_acceptance_rule"] or "泛资料" not in r["citation_acceptance_rule"]:
            err(f"{r['id']} no_evidence 引用规则不完整")
    elif r["expected_mode"] == "knowledge":
        if not r["evidence_items"]: err(f"{r['id']} knowledge 缺 evidence_items")
    for it in r["evidence_items"]:
        if it["evidence_kind"] not in E_KINDS: err(f"{r['id']} evidence_kind 非法")
        if it["support_level"] not in S_LEVELS: err(f"{r['id']} support_level 非法")
        p = it["source_path"]
        if not p or not Path(p).is_file(): err(f"{r['id']} 证据路径不存在"); continue
        n = len(Path(p).read_text(encoding='utf-8', errors='replace').split('\n'))
        if not (1 <= it["start_line"] <= it["end_line"] <= n): err(f"{r['id']} 行号非法"); continue
        seg = "\n".join(Path(p).read_text(encoding='utf-8', errors='replace').split("\n")[it["start_line"]-1:it["end_line"]])
        qa = it.get("quoted_anchor", "")
        if not qa: err(f"{r['id']} 缺 quoted_anchor")
        elif qa not in seg: err(f"{r['id']} quoted_anchor 与行号区间不一致: {qa[:40]}")
        if len(it.get("excerpt_summary", "")) > 200: err(f"{r['id']} excerpt_summary 超长")
if set(led_by_mid) != set(manifest):
    err(f"ledger 覆盖不符: 缺 {set(manifest)-set(led_by_mid)} 多 {set(led_by_mid)-set(manifest)}")

# ---------- platform-boundary-review ----------
REQUIRED_PB = {"pem-000028","pem-000029","pem-000030","pem-000031","pem-000032","pem-000034","pem-000035","pem-000053","pem-000054"}
pb = load(BASE / "platform-boundary-review.jsonl")
pb_ids = set()
for r in pb:
    if r["manifest_id"] in pb_ids: err(f"platform-boundary 重复 {r['manifest_id']}")
    pb_ids.add(r["manifest_id"])
    for f in ("specific_claim","confirmed_scope","not_confirmed_scope","safe_answer_wording",
              "unsafe_answer_wording","required_citation_rule","correction_reason"):
        if r.get(f) is None: err(f"{r['manifest_id']} 缺 {f}")
    if not isinstance(r.get("correction_needed_in_manifest"), bool): err(f"{r['manifest_id']} correction 非布尔")
    if r["correction_needed_in_manifest"]:
        led = led_by_mid.get(r["manifest_id"])
        if led:
            if not led["unsupported_claims"]: err(f"{r['manifest_id']} correction=true 但 ledger 无 unsupported_claims")
            if not any(k in led["citation_acceptance_rule"] for k in ("局限", "平台", "外推", "个人实验")):
                err(f"{r['manifest_id']} correction=true 但 ledger 引用规则未体现平台限制")
missing_pb = REQUIRED_PB - pb_ids
if missing_pb: err(f"platform-boundary 缺指定条目: {missing_pb}")

# ---------- grading-contract-candidates ----------
expect_contracts = {mid for mid, m in manifest.items() if m["priority"] in ("P0", "P1")}
gcon = load(BASE / "grading-contract-candidates.jsonl")
g_ids = set()
g_mids = set()
for r in gcon:
    if r["id"] in g_ids: err(f"grading 重复 id {r['id']}")
    g_ids.add(r["id"])
    if r["manifest_id"] not in manifest: err(f"{r['id']} manifest_id 不存在")
    g_mids.add(r["manifest_id"])
    if manifest[r["manifest_id"]]["priority"] not in ("P0","P1"): err(f"{r['id']} 非 P0/P1 却有契约")
    led = led_by_mid.get(r["manifest_id"])
    if led is None: err(f"{r['id']} 无法回溯 ledger"); continue
    if r["expected_mode"] != led["expected_mode"]: err(f"{r['id']} expected_mode 与 ledger 不一致")
    if r["refund_expected"] != (r["expected_mode"] == "no_evidence"): err(f"{r['id']} refund_expected 与模式不符")
    for f in ("minimum_retrieval_requirements","citation_requirements","answer_boundary_requirements",
              "pass_conditions","fail_conditions","must_not_claim"):
        if not r.get(f): err(f"{r['id']} 缺 {f}")
    if r["manual_review_required"] and not r.get("manual_review_reason"): err(f"{r['id']} manual 缺原因")
if g_mids != expect_contracts:
    err(f"契约覆盖不符: 缺 {expect_contracts-g_mids} 多 {g_mids-expect_contracts}")
if not (90 <= len(gcon) <= 110): err(f"契约数量 {len(gcon)} 超出 90-110")

# ---------- adversarial-pairs ----------
PTYPES = {"scope_shift","platform_shift","internal_vs_public","symbol_vs_natural_language",
          "follow_up_context","no_evidence_near_miss","citation_boundary"}
pairs = load(BASE / "adversarial-pairs.jsonl")
if not (40 <= len(pairs) <= 70): err(f"对照对数量 {len(pairs)} 超出 40-70")
seen = set()
for r in pairs:
    if r["id"] in seen: err(f"pairs 重复 id {r['id']}")
    seen.add(r["id"])
    if r["pair_type"] not in PTYPES: err(f"{r['id']} pair_type 非法")
    if r["base_manifest_id"] not in manifest: err(f"{r['id']} base_manifest_id 不存在")
    if r["question_a"] == r["question_b"]: err(f"{r['id']} 两端相同，不构成对照")
    if not r.get("expected_difference") or not r.get("why_different"): err(f"{r['id']} 缺差异说明")
    if r["pair_type"] == "follow_up_context":
        if manifest[r["base_manifest_id"]]["category"] != "follow_up":
            err(f"{r['id']} follow_up 对的 base 不是追问条目")

print(f"ledger: {len(ledger)} | platform-boundary: {len(pb)} | contracts: {len(gcon)} | pairs: {len(pairs)}")
print("ledger status:", dict(Counter(r["evidence_status"] for r in ledger)))
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors[:25]: print(" -", e)
    sys.exit(1)
print("ALL CHECKS PASSED")
