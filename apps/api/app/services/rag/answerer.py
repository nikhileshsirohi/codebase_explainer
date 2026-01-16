from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
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
            f"[{i}] {c.path}:{c.start_line}-{c.end_line} (score={c.score:.3f})\n"
            f"```text\n{c.text}\n```"
        )
    return "\n\n".join(blocks)

async def retrieve_chunks(repo_oid: ObjectId, question: str, k: int = 8) -> List[RetrievedChunk]:
    db = get_db()
    embedder = GeminiEmbedder()
    qvec = embedder.embed_text(question)

    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": qvec,
                "filter": {"repo_id": repo_oid},
                "numCandidates": max(60, k * 10),
                "limit": k,
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

    rows = await db["code_chunks"].aggregate(pipeline).to_list(length=k)
    out: List[RetrievedChunk] = []
    for r in rows:
        out.append(
            RetrievedChunk(
                path=r.get("path", ""),
                start_line=int(r.get("start_line", 0) or 0),
                end_line=int(r.get("end_line", 0) or 0),
                text=r.get("text", "") or "",
                score=float(r.get("score", 0.0) or 0.0),
            )
        )
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

    return f"""You are a senior software engineer.
Answer concisely and accurately.
Base answers ONLY on the provided code context.
Use citations like [1] path:start-end.
Do not repeat the question or instructions.

Conversation (recent):
{history_text}

User question:
{question}

Code context:
{context}

Now write:
1) A direct answer (bulleted if helpful)
2) Where in the code (citations)
3) If unsure, what to check next
"""

async def generate_answer(repo_oid: ObjectId, question: str, history: List[Dict[str, str]], k: int = 8) -> Dict[str, Any]:
    chunks = await retrieve_chunks(repo_oid, question, k=k)
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