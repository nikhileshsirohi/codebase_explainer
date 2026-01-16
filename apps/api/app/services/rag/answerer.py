from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from bson import ObjectId

from app.db.mongo import get_db
from app.core.config import settings
from app.services.embeddings.gemini_embedder import GeminiEmbedder

from app.services.llm.gemini_chat import GeminiChatLLM
from app.services.llm.ollama_llm import OllamaLLM

from app.services.llm.gemini_chat import LLMRateLimitError

@dataclass
class RetrievedChunk:
    path: str
    start_line: int
    end_line: int
    text: str
    score: float

def _format_chunks(chunks: List[RetrievedChunk]) -> str:
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(
            f"[{i}] {c.path}:{c.start_line}-{c.end_line}\n"
            f"```text\n{c.text}\n```"
        )
    return "\n\n".join(blocks)

async def retrieve_chunks(repo_oid: ObjectId, question: str, k: int = 8) -> List[RetrievedChunk]:
    db = get_db()
    embedder = GeminiEmbedder()
    qvec = embedder.embed_text(question)

    fetch_limit = max(k * 5, 40)  # fetch more, then filter down to k

    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": qvec,
                "filter": {"repo_id": repo_oid},
                "numCandidates": max(200, fetch_limit * 5),
                "limit": fetch_limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "path": 1,
                "start_line": 1,
                "end_line": 1,
                "text": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    rows = await db["code_chunks"].aggregate(pipeline).to_list(length=None)

    out: List[RetrievedChunk] = []
    for r in rows:
        path = (r.get("path") or "")
        text = (r.get("text") or "").strip()

        lp = path.lower()
        if lp.endswith(".md") or lp in ("readme.md", "license", "license.md"):
            continue
        if len(text) < 80:
            continue

        out.append(
            RetrievedChunk(
                path=path,
                start_line=int(r.get("start_line", 0) or 0),
                end_line=int(r.get("end_line", 0) or 0),
                text=text,
                score=float(r.get("score", 0.0) or 0.0),
            )
        )
        if len(out) >= k:
            break

    return out

def build_prompt(question: str, chunks: List[RetrievedChunk], history: List[Dict[str, str]]) -> str:
    history_text = ""
    if history:
        # history items: {"role": "user"/"assistant", "content": "..."}
        parts = []
        for m in history:
            role = m["role"].upper()
            parts.append(f"{role}: {m['content']}")
        history_text = "\n".join(parts)

    context = _format_chunks(chunks) if chunks else "(no relevant context found)"

    return f"""SYSTEM:
You are a senior software engineer.
Use ONLY the CODE CONTEXT. Do not guess.

If the CODE CONTEXT does not contain enough information to answer, reply exactly:
Not found in this repository.

CHAT HISTORY:
{history_text if history_text else "(none)"}

QUESTION:
{question}

CODE CONTEXT:
{context}

RESPONSE FORMAT (follow strictly):
If found:
Answer: <1-4 sentences>
Evidence: [n] path:start-end, ...
Next checks: <1-2 bullets>

If not found:
Not found in this repository.
Next checks: <1-3 bullets of what files/keywords to search>
"""


async def generate_answer(repo_oid: ObjectId, question: str, history: List[Dict[str, str]], k: int = 8) -> Dict[str, Any]:
    chunks = await retrieve_chunks(repo_oid, question, k=k)
    # Deduplicate overlaps
    seen = set()
    deduped = []
    for c in chunks:
        key = (c.path, c.start_line, c.end_line)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    chunks = deduped    

    prompt = build_prompt(question, chunks, history)

    provider = (settings.LLM_PROVIDER or "auto").lower()
    if provider not in ("auto", "gemini", "ollama"):
        provider = "auto"

    if provider == "ollama":
        answer = OllamaLLM(model=settings.OLLAMA_MODEL).generate(prompt)
    else:
        try:
            answer = GeminiChatLLM().generate(prompt)
        except (LLMRateLimitError, Exception):
            # auto fallback OR if gemini fails and provider=auto
            if provider == "gemini":
                raise
            answer = OllamaLLM(model=settings.OLLAMA_MODEL).generate(prompt)

    return {
        "answer": answer,
        "sources": [
            {"n": i + 1, "path": c.path, "start_line": c.start_line, "end_line": c.end_line, "score": c.score}
            for i, c in enumerate(chunks)
        ],
    }