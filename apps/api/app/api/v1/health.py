from fastapi import APIRouter
from app.db.mongo import get_db

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/health/db")
async def health_db():
    db = get_db()
    await db.command("ping")
    return {"status": "ok", "db": "mongo"}