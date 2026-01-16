from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.db.mongo import get_db
from app.core.config import settings
from app.schemas.chat import AskRequest, AskResponse
from app.services.rag.answerer import generate_answer
from app.services.llm.gemini_chat import LLMRateLimitError

router = APIRouter(tags=["chat"])

SESSIONS = "chat_sessions"
MESSAGES = "chat_messages"
CODE_CHUNKS = "code_chunks"

async def _get_recent_history(session_oid: ObjectId) -> List[Dict[str, str]]:
    db = get_db()
    # last N turns = 2N messages (user+assistant)
    limit = settings.CHAT_HISTORY_MAX_TURNS * 2
    cursor = db[MESSAGES].find(
        {"session_id": session_oid},
        projection={"role": 1, "content": 1, "_id": 0},
    ).sort("created_at", -1).limit(limit)
    msgs = await cursor.to_list(length=limit)
    msgs.reverse()
    return [{"role": m["role"], "content": m["content"]} for m in msgs]

@router.post("/repos/{repo_id}/ask", response_model=AskResponse)
async def ask_repo(repo_id: str, payload: AskRequest):
    db = get_db()

    try:
        repo_oid = ObjectId(repo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    # Guard: repo must be indexed (code_chunks exist)
    existing = await db[CODE_CHUNKS].find_one({"repo_id": repo_oid}, projection={"_id": 1})
    if not existing:
        raise HTTPException(status_code=409, detail="Repo not indexed yet. Run /ingest and wait for job done.")

    # Session handling
    if payload.session_id:
        try:
            session_oid = ObjectId(payload.session_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid session_id")
        sess = await db[SESSIONS].find_one({"_id": session_oid, "repo_id": repo_oid})
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found for this repo")
    else:
        res = await db[SESSIONS].insert_one({"repo_id": repo_oid, "created_at": datetime.utcnow()})
        session_oid = res.inserted_id

    # Save user message
    await db[MESSAGES].insert_one({
        "session_id": session_oid,
        "repo_id": repo_oid,
        "role": "user",
        "content": payload.question,
        "created_at": datetime.utcnow(),
    })

    history = await _get_recent_history(session_oid)

    try:
        rag = await generate_answer(repo_oid, payload.question, history=history, k=payload.top_k)
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail="LLM quota exceeded. Add billing/paid tier for Gemini, or switch to a local fallback model."
        )

    # Save assistant message
    await db[MESSAGES].insert_one({
        "session_id": session_oid,
        "repo_id": repo_oid,
        "role": "assistant",
        "content": rag["answer"],
        "created_at": datetime.utcnow(),
    })

    return AskResponse(session_id=str(session_oid), answer=rag["answer"], sources=rag["sources"])