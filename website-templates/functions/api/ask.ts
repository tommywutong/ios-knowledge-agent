// Cloudflare Pages Function：iOS 知识库问答接口（第三阶段）
// 复制到 tommywu-lab/functions/api/ask.ts 使用，所需绑定见同目录 README。
// 流程：问题 → Workers AI bge-m3 embedding → Vectorize 检索 → DeepSeek 生成 → 回答+引用

interface Env {
  AI: Ai; // Workers AI 绑定（用 @cf/baai/bge-m3，与本地建库同款模型）
  VECTORIZE: VectorizeIndex; // Vectorize 索引绑定（名称 ios-kb）
  RATE_KV: KVNamespace; // 限流计数
  DEEPSEEK_API_KEY: string; // secret：wrangler pages secret put DEEPSEEK_API_KEY
}

const DAILY_LIMIT = 10; // 每 IP 每天次数
const TOP_K = 8;

const TYPE_NAME: Record<string, string> = {
  note: "个人笔记",
  doc: "官方文档",
  wwdc: "WWDC",
  blog: "博客",
  source_code: "源码",
  card: "知识卡片",
};

const SYSTEM_PROMPT = `你是 TommyWu 的 iOS 知识库问答助手。严格依据提供的编号材料回答问题：
- 每个论点标注来源编号，如 [1][3]；
- 材料不足以回答时，明确说"知识库中没有足够材料"，不要编造；
- 用中文、Markdown 格式回答，可给代码示例；
- 不要在结尾重复来源列表（由前端展示）。`;

export const onRequestPost: PagesFunction<Env> = async (ctx) => {
  const { request, env } = ctx;

  // 限流：每 IP 每天 DAILY_LIMIT 次
  const ip = request.headers.get("cf-connecting-ip") ?? "unknown";
  const day = new Date().toISOString().slice(0, 10);
  const rateKey = `ask:${ip}:${day}`;
  const used = parseInt((await env.RATE_KV.get(rateKey)) ?? "0", 10);
  if (used >= DAILY_LIMIT) {
    return json({ error: `今日提问次数已用完（${DAILY_LIMIT} 次/天），明天再来～` }, 429);
  }

  let question: string;
  try {
    const body = (await request.json()) as { question?: string };
    question = (body.question ?? "").trim();
  } catch {
    return json({ error: "请求体需为 JSON：{question: string}" }, 400);
  }
  if (!question || question.length > 500) {
    return json({ error: "问题不能为空且不超过 500 字" }, 400);
  }

  await env.RATE_KV.put(rateKey, String(used + 1), { expirationTtl: 86400 * 2 });

  // 1. 问题 embedding（与建库同款 bge-m3，向量空间一致）
  const emb = (await env.AI.run("@cf/baai/bge-m3", { text: [question] })) as {
    data: number[][];
  };

  // 2. Vectorize 检索
  const hits = await env.VECTORIZE.query(emb.data[0], {
    topK: TOP_K,
    returnMetadata: "all",
  });

  const sources = hits.matches.map((m, i) => {
    const md = (m.metadata ?? {}) as Record<string, string>;
    return {
      n: i + 1,
      type: TYPE_NAME[md.type] ?? md.type,
      path: md.path,
      title_path: md.title_path,
      lines: md.lines,
      score: m.score,
    };
  });

  const context = hits.matches
    .map((m, i) => {
      const md = (m.metadata ?? {}) as Record<string, string>;
      return `[${i + 1}] 【${TYPE_NAME[md.type] ?? md.type}】${md.path} › ${md.title_path}（第${md.lines}行）\n${md.text}`;
    })
    .join("\n\n");

  // 3. DeepSeek 生成
  const dsResp = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${env.DEEPSEEK_API_KEY}`,
    },
    body: JSON.stringify({
      model: "deepseek-chat",
      stream: false,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: `材料：\n\n${context}\n\n问题：${question}` },
      ],
    }),
  });
  if (!dsResp.ok) {
    return json({ error: `上游模型服务异常（${dsResp.status}）` }, 502);
  }
  const ds = (await dsResp.json()) as {
    choices: { message: { content: string } }[];
  };

  return json({
    answer: ds.choices[0]?.message?.content ?? "",
    sources,
    remaining: DAILY_LIMIT - used - 1,
  });
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
