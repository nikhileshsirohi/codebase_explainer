from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
import hashlib

from bson import ObjectId

from app.db.mongo import get_db
from app.services.embeddings.gemini_embedder import GeminiEmbedder
from app.services.indexing.chunker import chunk_text_by_lines

REPO_FILE_CONTENTS = "repo_file_contents"
CODE_CHUNKS = "code_chunks"
INGEST_JOBS = "ingest_jobs"

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()

async def _set_job(job_id, extra: Dict[str, Any]):
    db = get_db()
    await db[INGEST_JOBS].update_one(
        {"_id": job_id},
        {"$set": {"updated_at": datetime.utcnow(), **extra}},
    )

async def build_embeddings_for_job(repo_id: ObjectId, job_id: ObjectId) -> Dict[str, Any]:
    db = get_db()
    embedder = GeminiEmbedder()

    # clean old chunks for this job (idempotent)
    await db[CODE_CHUNKS].delete_many({"job_id": job_id})

    cursor = db[REPO_FILE_CONTENTS].find(
        {"repo_id": repo_id, "job_id": job_id},
        projection={"path": 1, "text": 1},
    )
    files = await cursor.to_list(length=None)

    total_chunks = 0
    total_embedded = 0

    batch: List[Dict[str, Any]] = []
    BATCH_INSERT = 200  # Mongo bulk insert batching

    for f in files:
        path = f.get("path") or ""
        text = f.get("text") or ""
        if not text.strip():
            continue

        chunks = chunk_text_by_lines(text, max_chars=1800, overlap_lines=10)

        for idx, ch in enumerate(chunks):
            # small “prefix” improves retrieval for codebases
            # (keeps embeddings aware of file context)
            embed_input = f"FILE: {path}\nLINES: {ch.start_line}-{ch.end_line}\n\n{ch.text}"

            vec = embedder.embed_text(embed_input)

            doc = {
                "repo_id": repo_id,
                "job_id": job_id,
                "path": path,
                "chunk_index": idx,
                "start_line": ch.start_line,
                "end_line": ch.end_line,
                "text": ch.text,
                "embedding": vec,
                "text_hash": _sha1(embed_input),
                "created_at": datetime.utcnow(),
            }
            batch.append(doc)
            total_chunks += 1
            total_embedded += 1

            if len(batch) >= BATCH_INSERT:
                await db[CODE_CHUNKS].insert_many(batch)
                batch.clear()

        # update partial progress occasionally
        if total_chunks and total_chunks % 200 == 0:
            await _set_job(job_id, {"stats.embedded_chunks": total_embedded})

    if batch:
        await db[CODE_CHUNKS].insert_many(batch)

    stats = {"chunk_count": total_chunks, "embedded_chunks": total_embedded}
    await _set_job(job_id, {"stats": {**(await db[INGEST_JOBS].find_one({"_id": job_id}, {"stats": 1}) or {}).get("stats", {}), **stats}})
    return stats