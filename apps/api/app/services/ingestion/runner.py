from __future__ import annotations
from datetime import datetime
from bson import ObjectId
from app.db.mongo import get_db
from app.services.ingestion.file_tree import ingest_github_file_tree

async def run_ingest_job(repo_id: str, job_id: str) -> None:
    """
    Background job runner:
    - fetch repo + job docs from Mongo
    - run GitHub file tree ingestion
    - job status is updated inside ingest_github_file_tree()
    """
    db = get_db()

    repo = await db["repos"].find_one({"_id": ObjectId(repo_id)})
    job = await db["ingest_jobs"].find_one({"_id": ObjectId(job_id)})

    if not repo or not job:
        # nothing we can do; job will remain queued
        return

    try:
        await ingest_github_file_tree(repo_doc=repo, job_doc=job)
    except Exception as e:
        await db["ingest_jobs"].update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"status": "failed", "error": str(e), "updated_at": datetime.utcnow()}},
        )