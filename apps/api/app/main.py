from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.health import router as health_router

logger = setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)
    app.include_router(health_router, prefix="/api/v1")
    return app

app = create_app()