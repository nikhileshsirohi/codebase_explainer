from collections import defaultdict
from bson import ObjectId
from app.db.mongo import get_db

KEY_COMPONENTS = {
    "ingestion": ["services/ingestion", "github_client", "file_tree"],
    "indexing": ["indexing", "chunk", "embedding"],
    "search": ["rag", "search", "vector"],
    "api": ["api/v1"],
}

TECH_KEYWORDS = {
    "FastAPI": ["fastapi", "APIRouter"],
    "MongoDB": ["motor", "pymongo"],
    "Ollama": ["ollama"],
    "Gemini": ["gemini"],
}

async def build_overview(repo_id: ObjectId) -> dict:
    db = get_db()
    rows = await db["code_chunks"].find(
        {"repo_id": repo_id},
        {"path": 1, "text": 1},
    ).to_list(length=None)

    components = defaultdict(set)
    tech_stack = set()

    for r in rows:
        path = r["path"].lower()
        text = (r.get("text") or "").lower()

        for comp, hints in KEY_COMPONENTS.items():
            if any(h in path for h in hints):
                components[comp].add(r["path"])

        for tech, keys in TECH_KEYWORDS.items():
            if any(k in text or k in path for k in keys):
                tech_stack.add(tech)

    confidence = "high" if len(rows) > 150 else "medium" if len(rows) > 50 else "low"

    return {
        "components": [
            {"name": k.capitalize(), "files": sorted(v)}
            for k, v in components.items()
        ],
        "tech_stack": sorted(tech_stack),
        "confidence": confidence,
    }