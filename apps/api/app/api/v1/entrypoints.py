from fastapi import APIRouter
from bson import ObjectId
from app.db.mongo import get_db
from app.services.analysis.entrypoints import extract_entrypoints

router = APIRouter(tags=["entrypoints"])

@router.get("/repos/{repo_id}/entrypoints")
async def repo_entrypoints(repo_id: str):
    repo_oid = ObjectId(repo_id)
    db = get_db()

    chunks = await db.code_chunks.find(
        {"repo_id": repo_oid, "path": {"$regex": "\\.py$"}}
    ).to_list(length=500)

    entrypoints = extract_entrypoints(chunks)

    return {
        "repo_id": repo_id,
        "framework": "FastAPI",
        "entrypoints": entrypoints,
        "confidence": "high" if entrypoints["application"] else "medium"
    }