from fastapi import APIRouter, HTTPException
from app.schemas.ingest import IngestRepoRequest, IngestRepoResponse
from app.db.repos import create_repo, create_ingest_job

router = APIRouter(tags=["ingest"])

def _detect_provider(url: str) -> str:
    if "github.com" in url:
        return "github"
    return "unknown"

@router.post("/ingest", response_model=IngestRepoResponse)
async def ingest_repo(payload: IngestRepoRequest):
    repo_url = str(payload.repo_url)
    provider = _detect_provider(repo_url)
    if provider == "unknown":
        raise HTTPException(status_code=400, detail="Only GitHub URLs supported for now")

    repo = await create_repo(repo_url=repo_url, provider=provider)
    job = await create_ingest_job(repo_id=repo["_id"])

    return IngestRepoResponse(
        repo_id=str(repo["_id"]),
        job_id=str(job["_id"]),
        status=job["status"],
    )