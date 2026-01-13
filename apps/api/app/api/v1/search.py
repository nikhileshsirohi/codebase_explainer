from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.core.config import settings
from app.db.mongo import get_db
from app.services.embeddings.gemini_embedder import GeminiEmbedder

router = APIRouter(tags=["search"])

@router.get("/repos/{repo_id}/search")
async def semantic_search(repo_id: str, q: str, k: int = 8):
    db = get_db()
    try:
        repo_oid = ObjectId(repo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid repo_id")

    embedder = GeminiEmbedder()
    query_vec = embedder.embed_text(q)

    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.MONGODB_VECTOR_INDEX,
                "path": "embedding",
                "queryVector": query_vec,
                "filter": {"repo_id": repo_oid},
                "numCandidates": max(50, k * 10),
                "limit": k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "path": 1,
                "start_line": 1,
                "end_line": 1,
                "text": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    # $vectorSearch must be first stage; score returned via vectorSearchScore  [oai_citation:8‡MongoDB](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/)
    results = await db["code_chunks"].aggregate(pipeline).to_list(length=k)
    return {"results": results}