import copy

from .llm import chat_stream, get_client
from .retrieve import search

TYPE_NAMES = {
    "note": "个人笔记",
    "doc": "官方文档",
    "wwdc": "WWDC",
    "blog": "博客",
    "source_code": "源码",
    "card": "知识卡片",
}

SYSTEM_PROMPT = """你是 TommyWu 的 iOS 知识问答助手。TommyWu 是一名正在深入学习 iOS 底层原理的开发者，你的回答服务于他的学习理解和面试准备。

回答规则：
1. 只依据用户消息中提供的编号材料回答。不得引入材料之外的事实性内容来下结论；组织语言所需的常识表述除外。
2. 回答中的每个论点、结论、数值都必须标注来源编号，紧跟在句子后，格式如 [1] 或 [2][5]。
3. 如果材料不足以回答问题，明确说"知识库中没有足够材料"，并具体说明缺少哪方面的材料。绝不编造。
4. 材料之间说法冲突时，指出冲突并分别标注各自来源，不要强行调和。
5. 用中文回答，Markdown 格式。先给核心结论，再展开原理细节；讲解底层原理时可配少量代码或伪代码。
6. 材料中【源码】类型是 objc4/CF 等真实源码片段，引用它时可以点出关键函数名与做法。
7. 不要在结尾罗列来源清单，程序会单独打印。"""


def build_context(chunks):
    parts = []
    for i, c in enumerate(chunks, 1):
        tname = TYPE_NAMES.get(c["type"], c["type"])
        title = c["title_path"] or "(全文)"
        parts.append(
            f"[{i}] 【{tname}】{c['file_path']} › {title}"
            f"（第{c['start_line']}-{c['end_line']}行）\n{c['text']}\n"
        )
    return "\n".join(parts)


def format_citation(i, c):
    tname = TYPE_NAMES.get(c["type"], c["type"])
    title = c["title_path"] or "(全文)"
    return f"[{i}]【{tname}】{c['file_path']} › {title}（第{c['start_line']}-{c['end_line']}行）"


def ask(cfg, con, embedder, question, provider=None, k=None):
    if k:
        cfg = copy.deepcopy(cfg)
        cfg["retrieval"]["final_top"] = k
    chunks = search(con, cfg, question, embedder)
    context = build_context(chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"以下是从我的 iOS 知识库中检索到的材料：\n\n<materials>\n{context}\n</materials>\n\n"
                f"我的问题：{question}"
            ),
        },
    ]
    client, model = get_client(cfg, provider)
    return chunks, chat_stream(client, model, messages)
