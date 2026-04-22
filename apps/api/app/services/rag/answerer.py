from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List
from bson import ObjectId
from pymongo.errors import OperationFailure

from app.db.mongo import get_db
from app.core.config import settings
from app.services.embeddings.ollama_embedder import OllamaEmbedder

from app.services.llm.gemini_chat import GeminiChatLLM
from app.services.llm.local_t5 import LocalT5LLM
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


STOP_WORDS = {
    "a", "an", "and", "api", "are", "code", "does", "end", "explain", "file",
    "files", "flow", "for", "from", "how", "in", "is", "main", "of", "or",
    "repo", "repository", "show", "the", "to", "what", "where", "which",
}


def _intent_profile(intent: str) -> Dict[str, List[str]]:
    if intent == "repo_ingestion":
        return {
            "path_hints": ["api/v1/ingest", "services/ingestion", "services/indexing"],
            "keywords": ["ingest", "ingestion", "index", "indexing", "chunk", "embedding", "repo_files", "code_chunks"],
        }
    if intent == "api_flow":
        return {
            "path_hints": ["api/v1/chat", "services/rag", "services/llm"],
            "keywords": ["ask", "chat", "session", "history", "answer", "retrieve", "rag", "sources"],
        }
    if intent == "github_fetch":
        return {
            "path_hints": ["services/ingestion", "github_client", "file_tree"],
            "keywords": ["github", "blob", "tree", "file", "contents", "download", "api_url"],
        }
    return {"path_hints": [], "keywords": []}


def _question_keywords(question: str, *, extra: List[str] | None = None) -> List[str]:
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_./-]{1,}", question.lower())
    out: List[str] = []
    seen = set()
    for token in [*tokens, *(extra or [])]:
        cleaned = token.strip().lower()
        if not cleaned or cleaned in STOP_WORDS or cleaned.isdigit():
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _build_keyword_regex(keywords: List[str]) -> str | None:
    terms = [re.escape(k) for k in keywords if k]
    if not terms:
        return None
    return "|".join(terms)


def _rank_candidate(row: Dict[str, Any], *, keywords: List[str], path_hints: List[str]) -> float:
    path = (row.get("path") or "").lower()
    text = (row.get("text") or "").lower()

    score = float(row.get("score", 0.0) or 0.0)
    if path.endswith(".py"):
        score += 0.2

    path_matches = sum(1 for hint in path_hints if hint and hint in path)
    term_matches = sum(1 for kw in keywords if kw in text)
    exact_path_terms = sum(1 for kw in keywords if kw in path)

    score += path_matches * 2.0
    score += exact_path_terms * 1.2
    score += min(term_matches, 6) * 0.35
    return score

def _format_chunks(chunks: List[RetrievedChunk]) -> str:
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(
            f"[{i}] {c.path}:{c.start_line}-{c.end_line}\n"
            f"```text\n{c.text}\n```"
        )
    return "\n\n".join(blocks)


def _is_local_vector_search_error(exc: Exception) -> bool:
    if not isinstance(exc, OperationFailure):
        return False
    return "$vectorSearch stage is only allowed on MongoDB Atlas" in str(exc)


async def _keyword_rows(
    repo_oid: ObjectId,
    *,
    keyword_regex: str | None,
    limit: int,
) -> List[Dict[str, Any]]:
    db = get_db()
    query: Dict[str, Any] = {"repo_id": repo_oid}
    if keyword_regex:
        query["$or"] = [
            {"text": {"$regex": keyword_regex, "$options": "i"}},
            {"path": {"$regex": keyword_regex, "$options": "i"}},
        ]

    cursor = db["code_chunks"].find(
        query,
        {"_id": 0, "path": 1, "start_line": 1, "end_line": 1, "text": 1},
    ).limit(limit)
    return await cursor.to_list(length=limit)

async def retrieve_chunks(repo_oid: ObjectId, question: str, k: int = 8) -> List[RetrievedChunk]:
    db = get_db()
    q = question.lower()
    flow_mode = any(
        x in q for x in (
            "end-to-end", "end to end", "flow", "pipeline",
            "how does", "how is", "steps", "process"
        )
    )

    intent = classify_intent(question)
    profile = _intent_profile(intent)
    path_hints = profile["path_hints"]
    keywords = _question_keywords(question, extra=profile["keywords"])
    keyword_regex = _build_keyword_regex(keywords)

    min_len = 40 if intent == "github_fetch" else 80
    fetch_limit = max(k * 8, 80) if flow_mode else max(k * 5, 40)
    filter_doc = {"repo_id": repo_oid}
    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": [],
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

    try:
        embedder = OllamaEmbedder()
        qvec = embedder.embed_text(question)
        pipeline[0]["$vectorSearch"]["queryVector"] = qvec
        rows = await db["code_chunks"].aggregate(pipeline).to_list(length=None)
    except Exception as exc:
        if not _is_local_vector_search_error(exc):
            raise
        rows = await _keyword_rows(repo_oid, keyword_regex=keyword_regex, limit=max(80, k * 10))

    rows.sort(key=lambda r: _rank_candidate(r, keywords=keywords, path_hints=path_hints), reverse=True)

    out: List[RetrievedChunk] = []
    seen: set[tuple[str, int, int]] = set()

    for r in rows:
        path = (r.get("path") or "")
        text = (r.get("text") or "").strip()

        lp = path.lower()
        if path_hints and not any(p in lp for p in path_hints) and not any(kw in lp for kw in keywords):
            continue
        if lp.endswith(".md") or lp in ("readme.md", "license", "license.md"):
            continue
        if lp.endswith(".gitignore") or lp.endswith(".dockerignore"):
            continue

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

    need_keyword_fallback = bool(keyword_regex) and (
        len(out) < min(k, 5) or flow_mode or intent in {"github_fetch", "api_flow"}
    )
    if need_keyword_fallback:
        extra = await _keyword_rows(repo_oid, keyword_regex=keyword_regex, limit=max(50, k * 8))
        extra.sort(key=lambda r: _rank_candidate(r, keywords=keywords, path_hints=path_hints), reverse=True)
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

            if len(out) >= max(k, 10 if flow_mode else k):
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
    if provider not in ("auto", "gemini", "ollama", "local"):
        provider = "auto"

    if provider == "ollama":
        answer = OllamaLLM(model=settings.OLLAMA_MODEL).generate(prompt)
    elif provider == "local":
        answer = LocalT5LLM().generate(prompt)
    else:
        try:
            answer = GeminiChatLLM().generate(prompt)
        except (LLMRateLimitError, Exception):
            # auto fallback OR if gemini fails and provider=auto
            if provider == "gemini":
                raise
            if provider == "auto":
                try:
                    answer = OllamaLLM(model=settings.OLLAMA_MODEL).generate(prompt)
                except Exception:
                    answer = LocalT5LLM().generate(prompt)
            else:
                raise

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
