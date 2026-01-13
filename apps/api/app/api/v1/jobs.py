from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.db.mongo import get_db

router = APIRouter(tags=["jobs"])

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    db = get_db()
    try:
        oid = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    job = await db["ingest_jobs"].find_one({"_id": oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job["_id"] = str(job["_id"])
    job["repo_id"] = str(job["repo_id"])
    return job