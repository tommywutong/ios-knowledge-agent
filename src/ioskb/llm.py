import os

from openai import OpenAI


def get_client(cfg, provider=None):
    name = provider or cfg["llm"]["provider"]
    pc = cfg["llm"].get(name)
    if pc is None:
        raise SystemExit(f"未知的 LLM provider：{name}（config.yaml 的 llm 段中没有这一项）")
    key_env = pc["api_key_env"]
    key = os.environ.get(key_env, "").strip()
    if not key:
        raise SystemExit(
            f"缺少 API key：环境变量 {key_env} 未设置。\n"
            f"请在项目根目录执行：cp .env.example .env\n"
            f"然后编辑 .env，把 {key_env} 填成你的真实 key（DeepSeek key 在 platform.deepseek.com 获取）。"
        )
    client = OpenAI(base_url=pc["base_url"], api_key=key)
    return client, pc["model"]


def chat_stream(client, model, messages):
    stream = client.chat.completions.create(model=model, messages=messages, stream=True)
    for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


def chat(client, model, messages):
    content, _ = chat_with_usage(client, model, messages)
    return content


def chat_with_usage(client, model, messages):
    resp = client.chat.completions.create(model=model, messages=messages)
    usage = resp.usage
    usage_data = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        "prompt_cache_hit_tokens": getattr(usage, "prompt_cache_hit_tokens", 0) or 0,
        "prompt_cache_miss_tokens": getattr(usage, "prompt_cache_miss_tokens", 0) or 0,
    }
    return resp.choices[0].message.content, usage_data
