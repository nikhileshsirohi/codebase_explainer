from fastapi import APIRouter
from app.db.mongo import get_db
import httpx
from app.core.config import settings

async def mongo_ok() -> bool:
    try:
        db = get_db()
        await db.command("ping")
        return True
    except Exception:
        return False
    

async def ollama_ok() -> bool:
    try:
        print("OLLAMA_BASE_URL =", settings.OLLAMA_BASE_URL)
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(
                f"{settings.OLLAMA_BASE_URL}/api/tags"
            )
            return r.status_code == 200
    except Exception as e:
        print("ollama_ok failed:", repr(e))
        return False
    
router = APIRouter(tags=["health"])

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "mongo": await mongo_ok(),
        "ollama": await ollama_ok(),
    }

@router.get("/health/db")
async def health_db():
    db = get_db()
    await db.command("ping")
    return {"status": "ok", "db": "mongo"}