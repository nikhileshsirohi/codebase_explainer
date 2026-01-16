from fastapi import APIRouter
from bson import ObjectId
from app.db.mongo import get_db

router = APIRouter(tags=["debug"])

def _stringify_ids(doc):
    if not doc:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "repo_id" in doc:
        doc["repo_id"] = str(doc["repo_id"])
    return doc

@router.get("/debug/repos/{repo_id}/chunk_count")
async def chunk_count(repo_id: str):
    db = get_db()
    repo_oid = ObjectId(repo_id)
    n = await db["code_chunks"].count_documents({"repo_id": repo_oid})
    sample = await db["code_chunks"].find_one(
        {"repo_id": repo_oid},
        {"_id": 1, "repo_id": 1, "path": 1}
    )
    return {"repo_id": repo_id, "count": n, "sample": _stringify_ids(sample)}