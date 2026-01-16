from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.services.analysis.architecture import build_architecture

router = APIRouter(tags=["analysis"])

@router.get("/repos/{repo_id}/architecture")
async def repo_architecture(repo_id: str):
    try:
        rid = ObjectId(repo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    flows = await build_architecture(rid)
    return {"repo_id": repo_id, "flows": flows}