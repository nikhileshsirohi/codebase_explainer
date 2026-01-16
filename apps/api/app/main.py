from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.repos import ensure_indexes

from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search import router as search_router
from app.api.v1.chat import router as chat_router
from app.api.v1.debug import router as debug_router
from app.api.v1.repos import router as repos_router
from app.api.v1.overview import router as overview_router
from app.api.v1.entrypoints import router as entrypoints_router
from app.api.v1.architecture import router as architecture_router
from app.api.v1.ui import router as ui_router

logger = setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    @app.on_event("startup")
    async def _startup():
        await ensure_indexes()
        logger.info("Indexes ensured")
        
    app.include_router(ui_router, prefix="")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(debug_router, prefix="/api/v1")
    app.include_router(repos_router, prefix="/api/v1")
    app.include_router(overview_router, prefix="/api/v1")
    app.include_router(entrypoints_router, prefix="/api/v1")
    app.include_router(architecture_router, prefix="/api/v1")

    return app

app = create_app()