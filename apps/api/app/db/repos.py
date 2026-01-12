from datetime import datetime
from typing import Any, Dict, Optional
from app.db.mongo import get_db

REPOS = "repos"
INGEST_JOBS = "ingest_jobs"

async def ensure_indexes():
    db = get_db()
    await db[REPOS].create_index("canonical_repo_url", unique=True)
    await db[INGEST_JOBS].create_index("repo_id")
    await db[INGEST_JOBS].create_index("status")
    await db[INGEST_JOBS].create_index("created_at")

async def create_repo(repo_url: str, canonical_repo_url: str,provider: str, default_branch: Optional[str] = None) -> Dict[str, Any]:
    db = get_db()
    now = datetime.utcnow()

    insert_doc = {
        "canonical_repo_url": canonical_repo_url,  # normalized (unique key)
        "provider": provider,
        "default_branch": default_branch,
        "created_at": now,
    }

    # IMPORTANT: updated_at ONLY in $set (not in $setOnInsert)
    await db[REPOS].update_one(
        {"canonical_repo_url": canonical_repo_url},
        {
            "$setOnInsert": insert_doc,
            "$set": {
                "updated_at": now, 
                "repo_url": repo_url,
            },
        },
        upsert=True,
    )

    return await db[REPOS].find_one({"canonical_repo_url": canonical_repo_url})

async def create_ingest_job(repo_id, requested_by: str = "anonymous") -> Dict[str, Any]:
    db = get_db()
    job = {
        "repo_id": repo_id,
        "status": "queued",  # queued -> running -> done/failed
        "requested_by": requested_by,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "error": None,
    }
    result = await db[INGEST_JOBS].insert_one(job)
    job["_id"] = result.inserted_id
    return job