from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.db.mongo import get_db
from app.schemas.repo import RepoOut
from datetime import datetime, timedelta
from app.core.config import settings

router = APIRouter(tags=["repos"])

@router.get("/repos", response_model=list[RepoOut])
async def list_repos():
    db = get_db()
    cursor = db["repos"].find().sort("created_at", -1)

    out = []
    async for r in cursor:
        rid = r["_id"]

        latest = await db["ingest_jobs"].find_one(
            {"repo_id": rid},
            sort=[("updated_at", -1)],
            projection={"status": 1, "updated_at": 1, "error": 1},
        )

        if latest and latest.get("status") == "running":
            updated_at = latest.get("updated_at")
            if updated_at and datetime.utcnow() - updated_at > timedelta(minutes=settings.INGEST_TIMEOUT_MINUTES):
                await db["ingest_jobs"].update_one(
                    {"_id": latest["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error": "Ingestion timed out",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

        latest["status"] = "failed"
        latest["error"] = "Ingestion timed out"
        out.append(
            RepoOut(
                repo_id=str(rid),
                repo_url=r.get("repo_url", ""),
                canonical_repo_url=r.get("canonical_repo_url", ""),
                provider=r.get("provider", ""),
                default_branch=r.get("default_branch"),
                created_at=r["created_at"],
                latest_job_id=str(latest["_id"]) if latest else None,
                latest_job_status=latest.get("status") if latest else None,
                latest_job_updated_at=latest.get("updated_at") if latest else None,
                latest_job_error=latest.get("error") if latest else None,
            )
        )

    return out

@router.get("/repos/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: str):
    db = get_db()
    try:
        rid = ObjectId(repo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    r = await db["repos"].find_one({"_id": rid})
    if not r:
        raise HTTPException(status_code=404, detail="Repo not found")

    latest = await db["ingest_jobs"].find_one(
        {"repo_id": rid},
        sort=[("updated_at", -1)],
        projection={"status": 1, "updated_at": 1, "error": 1, "stats": 1},
    )
    if latest and latest.get("status") == "running":
        updated_at = latest.get("updated_at")
        if updated_at and datetime.utcnow() - updated_at > timedelta(minutes=settings.INGEST_TIMEOUT_MINUTES):
            await db["ingest_jobs"].update_one(
                {"_id": latest["_id"]},
                {
                    "$set": {
                        "status": "failed",
                        "error": "Ingestion timed out",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            latest["status"] = "failed"
            latest["error"] = "Ingestion timed out"
    return RepoOut(
        repo_id=str(rid),
        repo_url=r.get("repo_url", ""),
        canonical_repo_url=r.get("canonical_repo_url", ""),
        provider=r.get("provider", ""),
        default_branch=r.get("default_branch"),
        created_at=r["created_at"],
        latest_job_id=str(latest["_id"]) if latest else None,
        latest_job_status=latest.get("status") if latest else None,
        latest_job_updated_at=latest.get("updated_at") if latest else None,
        latest_job_error=latest.get("error") if latest else None,
        latest_job_stats=latest.get("stats") if latest else None,
    )