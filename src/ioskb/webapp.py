"""本地网页版：模型常驻内存的问答服务（ioskb web 启动）。"""
import json
import subprocess
import threading
import urllib.parse
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import db, llm, qa
from .config import load_config, resolve_path
from .embedder import Embedder
from .retrieve import search

MAX_HISTORY_TURNS = 6  # 送给 LLM 的最近对话轮数（问+答算两条）

app = FastAPI(title="iOS 知识库")
cfg = load_config()
embedder = Embedder(cfg)
_model_ready = threading.Event()
_encode_lock = threading.Lock()
_model_error = None


def _warmup():
    global _model_error
    try:
        embedder.encode(["warmup"])
    except BaseException as error:
        _model_error = str(error) or error.__class__.__name__
    finally:
        _model_ready.set()


threading.Thread(target=_warmup, daemon=True).start()

# 允许通过 /api/open 打开的目录白名单：所有语料根目录 + 项目目录
_ALLOWED_ROOTS = [resolve_path(s["path"]) for s in cfg["sources"]] + [
    resolve_path(".")
]


class AskBody(BaseModel):
    question: str
    history: list[dict] = []
    provider: str | None = None


class OpenBody(BaseModel):
    path: str


@app.get("/", response_class=HTMLResponse)
def home():
    html = Path(__file__).parent / "web_static" / "index.html"
    return html.read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    con = db.open_db(cfg)
    try:
        total = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        vectorized = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE vectorized=1"
        ).fetchone()[0]
        files = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    finally:
        con.close()
    providers = [k for k in cfg["llm"] if isinstance(cfg["llm"][k], dict)]
    return {
        "model_ready": _model_ready.is_set(),
        "model_error": _model_error,
        "chunks": total,
        "vectorized": vectorized,
        "files": files,
        "providers": providers,
        "default_provider": cfg["llm"]["provider"],
    }


@app.post("/api/ask")
def api_ask(body: AskBody):
    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)
    try:
        client, model = llm.get_client(cfg, body.provider)
    except SystemExit as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    def stream():
        _model_ready.wait()
        if _model_error:
            yield json.dumps(
                {"type": "error", "message": f"向量模型加载失败：{_model_error}"},
                ensure_ascii=False,
            ) + "\n"
            return
        con = db.open_db(cfg)
        try:
            with _encode_lock:
                # 最终回答只引用原始资料；模型生成的知识卡片不进入证据上下文。
                chunks = search(con, cfg, question, embedder, exclude_types={"card"})
        finally:
            con.close()
        sources = [
            {
                "n": i + 1,
                "type": c["type"],
                "path": c["file_path"],
                "title_path": c["title_path"],
                "lines": f"{c['start_line']}-{c['end_line']}",
            }
            for i, c in enumerate(chunks)
        ]
        yield json.dumps({"type": "sources", "sources": sources}, ensure_ascii=False) + "\n"

        history = body.history[-MAX_HISTORY_TURNS:]
        messages = [{"role": "system", "content": qa.SYSTEM_PROMPT}]
        messages += [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        materials = qa.build_context(chunks)
        messages.append(
            {"role": "user", "content": f"材料：\n\n{materials}\n\n问题:{question}"}
        )
        try:
            for delta in llm.chat_stream(client, model, messages):
                yield json.dumps({"type": "delta", "text": delta}, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"模型调用失败：{e}"}, ensure_ascii=False) + "\n"
            return
        yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/open")
def api_open(body: OpenBody):
    p = Path(body.path)
    if not p.is_absolute() or not p.exists():
        return JSONResponse({"error": "路径不存在"}, status_code=400)
    if not any(p.is_relative_to(root) for root in _ALLOWED_ROOTS):
        return JSONResponse({"error": "路径不在允许范围内"}, status_code=403)
    if p.is_relative_to("/Users/tommywu/Obsidian") and p.suffix == ".md":
        uri = "obsidian://open?path=" + urllib.parse.quote(str(p))
        subprocess.run(["open", uri], check=False)
    else:
        subprocess.run(["open", "-R", str(p)], check=False)  # 访达中显示
    return {"ok": True}
