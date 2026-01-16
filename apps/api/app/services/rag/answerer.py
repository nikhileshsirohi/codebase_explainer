from __future__ import annotations

from dataclasses import dataclass
from email.mime import text
from typing import Any, Dict, List
from bson import ObjectId

from app.db.mongo import get_db
from app.core.config import settings
from app.services.embeddings.ollama_embedder import OllamaEmbedder

from app.services.llm.gemini_chat import GeminiChatLLM
from app.services.llm.ollama_llm import OllamaLLM
from app.services.llm.gemini_chat import LLMRateLimitError

from app.services.rag.symbols import extract_python_symbols
from app.services.rag.links import extract_python_links
from app.services.rag.intent import classify_intent

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
    embedder = OllamaEmbedder()
    qvec = embedder.embed_text(question)

    q = question.lower()
    flow_mode = any(
        x in q for x in (
            "end-to-end", "end to end", "flow", "pipeline",
            "how does", "how is", "steps", "process"
        )
    )

    intent = classify_intent(question)

    path_filters = []
    if intent == "repo_ingestion":
        path_filters = ["services/ingestion", "services/indexing"]
        keywords = ["ingest", "ingestion", "chunk", "embedding", "index", "repo_files", "code_chunks"]
    elif intent == "api_flow":
        path_filters = ["api/v1/chat.py"]
    elif intent == "github_fetch":
        path_filters = ["services/ingestion", "github_client", "file_tree"]
        keywords = ["github", "blob", "get_blob", "file", "contents", "raw", "download", "api_url"]
    else:
        keywords = ["chunk", "embed", "search"]

    fetch_limit = max(k * 8, 80) if flow_mode else max(k * 5, 40)
    filter_doc = {"repo_id": repo_oid}
    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": qvec,
                "filter": filter_doc,
                "numCandidates": max(400, fetch_limit * 5),
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
    rows.sort(key=lambda r: 0 if (r.get("path","").lower().endswith(".py")) else 1)

    out: List[RetrievedChunk] = []
    seen: set[tuple[str, int, int]] = set()

    for r in rows:
        path = (r.get("path") or "")
        text = (r.get("text") or "").strip()

        lp = path.lower()
        if path_filters and not any(p in lp for p in path_filters):
            continue
        if lp.endswith(".md") or lp in ("readme.md", "license", "license.md"):
            continue
        if lp.endswith(".gitignore") or lp.endswith(".dockerignore"):
            continue
        min_len = 40 if intent == "github_fetch" else 80
        if len(text) < min_len:
            continue

        start_line = int(r.get("start_line", 0) or 0)
        end_line = int(r.get("end_line", 0) or 0)
        key = (path, start_line, end_line)
        if key in seen:
            continue
        seen.add(key)

        out.append(
            RetrievedChunk(
                path=path,
                start_line=start_line,
                end_line=end_line,
                text=text,
                score=float(r.get("score", 0.0) or 0.0),
            )
        )

        # For normal Qs, stop early. For flow_mode, collect more before slicing.
        if not flow_mode and len(out) >= k:
            break

    # Keyword fallback only when flow question lacks coverage
    need_keyword_fallback = (flow_mode and len(out) < min(5, k)) or (intent == "github_fetch" and len(out) < k)
    if need_keyword_fallback:
        cursor = db["code_chunks"].find(
            {
                "repo_id": repo_oid,
                "text": {"$regex": "|".join(keywords), "$options": "i"},
            },
            {"path": 1, "start_line": 1, "end_line": 1, "text": 1},
        ).limit(50)

        extra = await cursor.to_list(length=50)
        for r in extra:
            path = (r.get("path") or "")
            text = (r.get("text") or "").strip()
            if len(text) < 80:
                continue

            lp = path.lower()
            if lp.endswith(".md") or lp in ("readme.md", "license", "license.md"):
                continue

            start_line = int(r.get("start_line", 0) or 0)
            end_line = int(r.get("end_line", 0) or 0)
            key = (path, start_line, end_line)
            if key in seen:
                continue
            seen.add(key)

            out.append(
                RetrievedChunk(
                    path=path,
                    start_line=start_line,
                    end_line=end_line,
                    text=text,
                    score=0.0,  # keyword fallback
                )
            )

            if len(out) >= k:
                break

    return out[:k]

def build_prompt(question: str, chunks: List[RetrievedChunk], history: List[Dict[str, str]]) -> str:
    history_text = ""
    if history:
        parts = []
        for m in history:
            role = m["role"].upper()
            parts.append(f"{role}: {m['content']}")
        history_text = "\n".join(parts)

    context = _format_chunks(chunks) if chunks else "(no relevant context found)"

    evidence_refs = "\n".join(
        [f"[{i+1}] {c.path}:{c.start_line}-{c.end_line}" for i, c in enumerate(chunks)]
    ) or "(none)"


    return f"""SYSTEM:
You are a senior software engineer.
Use ONLY the CODE CONTEXT. Do not guess.

If the CODE CONTEXT does not contain enough information to answer, reply exactly:
Not found in this repository.

CHAT HISTORY:
{history_text if history_text else "(none)"}

QUESTION:
{question}

EVIDENCE REFERENCES (verbatim excerpts from the repository):
{context}

EVIDENCE CITATIONS (copy EXACTLY; do not invent):
{evidence_refs}

PIPELINE HINTS (use these to explain "what calls what"; do not invent names):
{_pipeline_hints(chunks)}

SYMBOL HINTS (use these names if relevant; do not invent new names):
{_symbol_hints(chunks)}

RESPONSE FORMAT (follow strictly):

If found:
Answer:
- 1–3 sentences.
- Include a 2–4 step flow (A -> B -> C) using names from PIPELINE HINTS / SYMBOL HINTS.

Evidence:
- Copy one or more lines from EVIDENCE CITATIONS exactly.

Next checks:
- 1–2 bullets referencing specific files or symbols.

If not found:
Not found in this repository.

Next checks:
- 1–3 bullets with concrete files, folders, or keywords to search.
"""

async def generate_answer(repo_oid: ObjectId, question: str, history: List[Dict[str, str]], k: int = 8) -> Dict[str, Any]:
    chunks = await retrieve_chunks(repo_oid, question, k=k)
    # Deduplicate overlaps
    seen_text = set()
    deduped = []
    for c in chunks:
        key = (c.path, c.start_line, c.end_line)  # cheap signature
        if key in seen_text:
            continue
        seen_text.add(key)
        deduped.append(c)
    chunks = deduped[:k]    

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

    if answer.strip().startswith("Not found in this repository."):
        return {"answer": answer, "sources": []}
    return {
        "answer": answer,
        "sources": [
            {"n": i + 1, "path": c.path, "start_line": c.start_line, "end_line": c.end_line, "score": c.score}
            for i, c in enumerate(chunks)
        ],
    }

def _symbol_hints(chunks: List[RetrievedChunk]) -> str:
    hints = []
    for c in chunks:
        if not c.path.lower().endswith(".py"):
            continue
        hits = extract_python_symbols(c.text)
        for h in hits:
            hints.append(f"- {h.kind}: `{h.name}` (from {c.path}:{c.start_line}-{c.end_line})")
    # de-dupe while preserving order
    seen = set()
    out = []
    for x in hints:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return "\n".join(out[:12]) if out else "(none)"

def _pipeline_hints(chunks: List[RetrievedChunk]) -> str:
    items = []
    for c in chunks:
        if not c.path.lower().endswith(".py"):
            continue
        hints = extract_python_links(c.text)
        for h in hints:
            if h.kind == "calls":
                items.append(f"- calls: `{h.name}()` (seen in {c.path}:{c.start_line}-{c.end_line})")
            else:
                items.append(f"- imports: `{h.name}` (seen in {c.path}:{c.start_line}-{c.end_line})")

    # de-dupe preserve order
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)

    out.sort(key=lambda s: _priority(s))
    return "\n".join(out[:20]) if out else "(none)"

def _priority(name: str) -> int:
    n = name.lower()
    if "ingest" in n:
        return 0
    if "embed" in n or "embedding" in n:
        return 1
    if "chunk" in n:
        return 2
    if "search" in n or "retrieve" in n:
        return 3
    return 9