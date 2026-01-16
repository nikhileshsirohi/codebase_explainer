from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.schemas.overview import RepoOverview
from app.services.overview.builder import build_overview
from app.services.overview.summary import generate_summary

router = APIRouter(tags=["overview"])

@router.get("/repos/{repo_id}/overview", response_model=RepoOverview)
async def repo_overview(repo_id: str):
    try:
        rid = ObjectId(repo_id)
    except Exception:
        raise HTTPException(400, "Invalid repo_id")

    base = await build_overview(rid)
    if not base["components"]:
        raise HTTPException(404, "Repo not indexed")

    summary = generate_summary(
        components=base["components"],
        tech_stack=base["tech_stack"],
    )

    return RepoOverview(
        repo_id=repo_id,
        summary=summary,
        components=base["components"],
        data_flow=[
            "GitHub repository → file tree → chunks",
            "Chunks → embeddings → vector index",
            "Query → retrieval → answer",
        ],
        tech_stack=base["tech_stack"],
        confidence=base["confidence"],
    )