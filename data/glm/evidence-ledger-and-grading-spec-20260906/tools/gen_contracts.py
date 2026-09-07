#!/usr/bin/env python3
"""阶段 C：P0/P1 条目的判分契约候选（回溯证据账本）。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ledger = {r["manifest_id"]: r for r in (json.loads(l) for l in (BASE / "evidence-ledger.jsonl").read_text(encoding="utf-8").splitlines())}
pbr = {r["manifest_id"]: r for r in (json.loads(l) for l in (BASE / "platform-boundary-review.jsonl").read_text(encoding="utf-8").splitlines())}
manifest = {r["id"]: r for r in (json.loads(l) for l in (Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/seed-evidence-boundary-and-eval-manifest-20260906") / "production-eval-manifest-candidates.jsonl").read_text(encoding="utf-8").splitlines())}

rows = []
for mid, m in manifest.items():
    if m["priority"] not in ("P0", "P1"):
        continue
    led = ledger[mid]
    mode = m["expected_mode"]
    cat = m["category"]
    pbr_row = pbr.get(mid)
    # 引用要求
    if mode == "no_evidence":
        cit = "不得出现任何知识性引用；返回 no_evidence 且退款"
        min_ret = "路由为 no_evidence；不得用同主题泛资料（一般介绍类）拼凑证据"
        pass_c = ["返回 no_evidence 并退款", "不调用模型生成知识正文", "无虚构引用"]
        partial_c = ["路由正确但输出了少量『资料未覆盖』的免责声明式回答"]
        fail_c = ["用同主题泛资料拼接出看似有据的回答", "返回 general 冒充", "出现虚构引用"]
        refund, manual = True, False
        must_not = ["用同主题泛资料冒充具体主张的证据", "虚构引用或来源", "给出确定性技术结论"]
    elif cat == "follow_up":
        cit = "引用需落在追问所涉锚定区间；不得引用上一轮未涉及的新主题来源"
        min_ret = "继承上一轮模式与话题后检索；检索词不含无关旧话题"
        pass_c = ["正确继承上一轮模式与相关历史", "回答锚定在追问所涉小节并带有效引用"]
        partial_c = ["继承正确但引用仅部分覆盖追问点"]
        fail_c = ["把追问当新话题检索", "混入无关旧主题上下文", "无引用或引用越界"]
        refund, manual = False, True
        must_not = ["脱离上一轮语境强行回答", "把合成占位对话当作真实来源事实"]
    elif pbr_row:
        cit = pbr_row["required_citation_rule"]
        min_ret = "预期来源出现在候选中；引用覆盖机制/事实段"
        pass_c = ["正确路由为 knowledge", "引用有效且覆盖核心主张",
                  "回答包含局限说明（平台/实验条件），措辞接近安全示例"]
        partial_c = ["机制回答正确但缺少局限说明（平台/个人实验未声明）"]
        fail_c = ["把个人实验数字/macOS 观察说成普遍 iOS 事实（接近不安全示例）", "无有效引用", "路由为 no_evidence 或 general"]
        refund, manual = False, True
        must_not = [pbr_row["unsafe_answer_wording"], "未声明证据局限即外推"]
    elif cat == "symbol":
        cit = "至少一条引用命中正确源码/文档文件；仅提到同名符号的博客/周报不得作为唯一引用"
        min_ret = "预期源码/文档文件进入最终候选"
        pass_c = ["引用命中标注的源码或文档文件", "符号定义位置与标注区间一致"]
        partial_c = ["命中正确文件但引用区间偏移较大"]
        fail_c = ["只命中提到同名符号的第三方文章", "无引用"]
        refund, manual = False, False
        must_not = ["用博客提及替代源码/文档出处"]
    elif cat == "alias":
        cit = "引用与该概念的标准条目一致（口语表述不影响证据要求）"
        min_ret = "口语/别称查询能命中标准条目所在文件"
        pass_c = ["正确识别口语所指概念并引用标准小节"]
        partial_c = ["回答正确但引用了同文件的相邻小节"]
        fail_c = ["检索失败返回 no_evidence", "答非所指"]
        refund, manual = False, False
        must_not = ["因表述口语化而降低证据要求"]
    elif cat == "comparison":
        cit = "引用需同时覆盖（或分别覆盖）两个技术对象的出处"
        min_ret = "两个对象的证据均进入最终候选"
        pass_c = ["两侧对象都有证据支撑，比较不偏向单侧"]
        partial_c = ["仅一侧有有效引用，另一侧声明缺资料"]
        fail_c = ["只答一侧且伪装成完整对比", "对比对象为标题碎片仍强行比较"]
        refund, manual = False, False
        must_not = ["把单一对象的资料冒充双对象对比证据"]
    else:
        cit = "至少一条引用落在标注区间并支撑核心主张" + ("；须遵守 ledger 的 citation_acceptance_rule 细则" if led["unsupported_claims"] else "，不得越过 answer_boundary")
        min_ret = "预期来源出现在最终候选；引用覆盖核心主张"
        pass_c = ["正确路由为 knowledge", "引用有效且覆盖核心主张", "回答不越过 answer_boundary"]
        partial_c = (["核心主张覆盖但部分次要主张无证据支撑（见 unsupported_claims）"]
                     if led["unsupported_claims"] else ["回答正确但引用区间偏移"])
        fail_c = ["无有效引用", "回答越过来源边界（编造未覆盖内容）", "路由错误"]
        refund, manual = False, bool(led["unsupported_claims"])
        must_not = (["把 unsupported_claims 中的内容当作已证实"] if led["unsupported_claims"]
                    else ["引用与标注区间无关仍宣称有据"])
    rows.append({
        "id": "gcon-%06d" % (len(rows) + 1),
        "manifest_id": mid,
        "question": m["question"],
        "expected_mode": mode,
        "minimum_retrieval_requirements": min_ret,
        "citation_requirements": cit,
        "answer_boundary_requirements": (led["answer_boundary"] + ("；须满足 required_answer_constraints" if led["required_answer_constraints"] else "")),
        "must_not_claim": must_not,
        "pass_conditions": pass_c,
        "partial_conditions": partial_c,
        "fail_conditions": fail_c,
        "refund_expected": refund,
        "manual_review_required": manual,
        "manual_review_reason": ("追问语境为合成占位，需人工确认衔接" if cat == "follow_up" else
                                 ("平台/实验局限表述需人工判读是否充分" if pbr_row or led["required_answer_constraints"] else "")),
        "diagnostic_layer": m["diagnostic_layer"],
        "priority": m["priority"],
    })
with (BASE / "grading-contract-candidates.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print("contracts:", len(rows), dict(Counter(r["priority"] for r in rows)))
print("refund:", sum(1 for r in rows if r["refund_expected"]), "| manual:", sum(1 for r in rows if r["manual_review_required"]))
