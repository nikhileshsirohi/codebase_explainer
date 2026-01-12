from fastapi import APIRouter, HTTPException
from app.schemas.ingest import IngestRepoRequest, IngestRepoResponse
from app.db.repos import create_repo, create_ingest_job
from app.utils.repo_url import canonicalize_repo_url

router = APIRouter(tags=["ingest"])

def _detect_provider(url: str) -> str:
    if "github.com" in url:
        return "github"
    return "unknown"

@router.post("/ingest", response_model=IngestRepoResponse)
async def ingest_repo(payload: IngestRepoRequest):
    raw_url = str(payload.repo_url)

    canonical_url = canonicalize_repo_url(raw_url)
    provider = _detect_provider(canonical_url)
    if provider == "unknown":
        raise HTTPException(status_code=400, detail="Only GitHub URLs supported for now")

    repo = await create_repo(repo_url=raw_url, canonical_repo_url=canonical_url, provider=provider)
    job = await create_ingest_job(repo_id=repo["_id"])

    return IngestRepoResponse(
        repo_id=str(repo["_id"]),
        job_id=str(job["_id"]),
        status=job["status"],
    )