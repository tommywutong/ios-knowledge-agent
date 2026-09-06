#!/usr/bin/env python3
"""生成 failure-triage.jsonl 的定义类条目；案例类由 gen_triage_cases.py 从 FTS 抽样补充。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "failure-triage.jsonl"

DEFS = [
    ("missing_source", "问题指向的主题在全部已索引来源中不存在原始资料",
     ["该主题在 coverage 清单和 FTS/向量检索中是否零命中？", "是否属于 WWDC/文档/笔记均未覆盖的新 API？", "用户是否问的是 iOS 之外的平台？"],
     ["检索 top50 候选列表", "来源覆盖清单", "问题主题词"],
     "把主题登记进资料缺口清单，等待人工决定是否补充资料或扩评测集",
     "用通用模型常识补答案；把 no_evidence 伪装成知识回答"),
    ("source_quality", "证据块存在，但内容是目录页/坏转换/低相关，不构成可引用证据",
     ["命中的块正文密度如何？是否只有链接或标题？", "块是否来自 oss 镜像/周报等第三方层级？", "是否来自已排除的旧版目录？"],
     ["命中块的正文摘录", "来源路径与 source/type", "块长度"],
     "登记 quality-findings 并继续用其它证据复核",
     "直接修改或删除原始语料文件"),
    ("lexical_recall", "问题与预期来源用词不同（别名/中英差异/口语改写）导致 FTS 未命中",
     ["FTS 是否零命中或只命中弱相关？", "问题关键词在预期文件中是否存在其它写法？", "术语别名表是否覆盖该改写？"],
     ["查询词与 FTS 分词结果", "预期来源全文", "别名表条目"],
     "把缺失别名加入离线别名候选并补充评测集",
     "未经验证直接调整生产 FTS 分词或权重"),
    ("semantic_recall", "FTS 无法覆盖的语义问题（同义改写/跨语言）在无向量路径上必然薄弱",
     ["该问题是否为纯语义表述而缺少关键词重叠？", "向量召回（生产 Vectorize）是否命中而 FTS 未命中？", "bge-m3 距离是否超过 max_vector_distance？"],
     ["向量检索结果与距离", "FTS 结果对比", "问题语义关键词"],
     "在离线用 embedding 复现后登记差距，等待人工评估",
     "据此宣称生产 Vectorize 链路有问题或直接调参"),
    ("rerank", "召回阶段命中了预期来源，但重排后跌出最终 top-k",
     ["预期来源的召回名次是多少？重排后名次变成多少？", "type 权重是否把 source_code/ blog 压到预期文档之后？", "reranker 是否回退（失败自动跳过）？"],
     ["召回名次与重排名次对比", "type_weights 配置", "reranker 日志"],
     "记录名次变化证据，提交人工评估排序策略",
     "擅自改 type_weights 或 reranker 参数"),
    ("routing", "问题被路由到错误的模式（iOS 问题走 general、闲聊走检索、无证据却答知识）",
     ["路由判定日志的当前轮次类别是什么？", "问题是否为问候/感谢/确认等确定性分支？", "边界技术问题是否走了证据探测？"],
     ["路由决策记录", "问题文本", "上一轮模式"],
     "把该问题加入 adversarial-routing 评测集并人工复核路由规则",
     "直接修改生产路由代码或关键词黑名单"),
    ("follow_up_context", "追问未继承上一轮上下文，或新话题错误继承旧上下文",
     ["上一轮模式是否随请求回传？", "追问是否含明确指代（那/为什么/它）？", "前端是否把无关历史混入检索词？"],
     ["完整对话历史", "请求携带的上下文字段", "最终检索词"],
     "用 follow-up 评测集复现并记录期望行为",
     "把全部历史无差别送入提示词"),
    ("citation_validation", "回答引用编号越界/格式漂移/无有效引用导致退款",
     ["模型输出使用了哪些引用格式？", "是否出现越界编号被移除后正文悬空？", "最终是否触发 invalid_citations？"],
     ["模型原始输出", "引用校验日志", "来源列表"],
     "把该格式样例加入引用兼容用例，人工评估是否需扩解析",
     "自动伪造 [1] 或把无引用段落强行归给第一个来源"),
    ("answer_prompt", "检索正确但回答质量差：过简、跑题、编造、或隐藏思考挤占正文预算",
     ["答案是否只复述了上下文的一部分？", "max_tokens 是否被 reasoning 消耗殆尽？", "提示词是否要求展开机制/条件/示例？"],
     ["最终答案全文", "token 用量统计", "提示词版本"],
     "记录失败样例，等待人工调整提示词或生成预算",
     "在评测框架内宣称某模型配置更优"),
    ("unknown", "证据不足以归入以上类别",
     ["是否收集了召回、路由、引用、回答四段完整证据？", "失败是否只在特定时间段/部署版本出现？"],
     ["一次完整的请求级证据链"],
     "挂起待人工会诊，先归 unknown",
     "凭猜测归因并启动修复"),
]

lines = []
for i, (cls, symptom, diag, ev, safe, mustnot) in enumerate(DEFS, 1):
    lines.append({
        "id": "triage-%06d" % i,
        "failure_class": cls,
        "symptom": symptom,
        "diagnostic_questions": diag,
        "evidence_needed": ev,
        "safe_next_step": safe,
        "must_not_do": mustnot,
        "case_ref": None,
    })
# 每类定义补 1-2 条具体症状变体，凑足定义侧覆盖
VARIANTS = [
    ("lexical_recall", "问题包含精确符号（如 cache_t）但 FTS 返回的全是博客/周报而非源码或笔记",
     "把符号题（batch-005）纳入例行 FTS 评测", "不得为改善命中率提高 source_code 权重而不做验证"),
    ("lexical_recall", "中文口语问题（『oc 方法找不到会咋样』）无法命中英文术语文档",
     "扩充口语别名候选", ""),
    ("missing_source", "SwiftUI/Combine/Swift Concurrency 等新框架主题在评测集中被判 no_evidence",
     "登记资料缺口，评估是否引入对应官方文档", "不要用博客二手内容冒充官方证据"),
    ("source_quality", "FTS 命中了 oss 镜像里的周报链接页而非正文",
     "在 quality-findings 中登记并人工复核 oss 子目录", "不要直接从索引剔除整个来源"),
    ("routing", "『那这个和前者有什么区别？』这类无前文的追问被当作新话题",
     "验证追问继承逻辑并记录期望", ""),
    ("citation_validation", "DeepSeek 输出【资料1】或[来源：2]等中文格式导致引用全部失效",
     "把该格式加入引用解析兼容样例", "不要伪造引用编号"),
    ("rerank", "预期官方文档召回了，但最终 8 条全是 oss 镜像",
     "对比召回名次与重排名次并记录", ""),
    ("answer_prompt", "复杂题回答只有两三句，正文被隐藏思考耗尽",
     "确认隐藏思考关闭与 token 预算配置", ""),
]
for j, (cls, symptom, safe, mustnot) in enumerate(VARIANTS, 1):
    lines.append({
        "id": "triage-%06d" % (len(lines) + 1),
        "failure_class": cls,
        "symptom": symptom,
        "diagnostic_questions": ["复现该症状所需的输入是什么？", "四段证据（召回/重排/路由/回答）哪一段先断？"],
        "evidence_needed": ["查询文本", "检索候选列表", "最终回答或错误码"],
        "safe_next_step": safe,
        "must_not_do": mustnot or "未经人工复核直接修改生产配置",
        "case_ref": None,
    })
with OUT.open("w", encoding="utf-8") as f:
    for r in lines:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("definitions written:", len(lines))
