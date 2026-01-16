from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(tags=["ui"])

@router.get("/", include_in_schema=False)
async def ui_home():
    html_path = Path(__file__).resolve().parents[2] / "static" / "index.html"
    return FileResponse(str(html_path))