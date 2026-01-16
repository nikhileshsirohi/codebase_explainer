from __future__ import annotations

import re
from typing import Dict, List, Set
from bson import ObjectId

from app.db.mongo import get_db


# -----------------------------
# Regex patterns (tight + safe)
# -----------------------------

FASTAPI_APP = re.compile(r"\bFastAPI\s*\(")

ROUTE_DECORATOR = re.compile(
    r"@(router|app)\.(get|post|put|delete|patch)\s*\(",
    re.IGNORECASE,
)

BACKGROUND_TASK = re.compile(
    r"\b(background_tasks\.add_task|add_task\s*\(|run_ingest_job)\b",
    re.IGNORECASE,
)


# -----------------------------
# High-level extraction
# -----------------------------

def extract_entrypoints(chunks: List[dict]) -> Dict[str, List[dict]]:
    """
    Extract entrypoints from code chunks.
    Chunk-safe and deduplicated.
    """
    entrypoints = {
        "application": [],
        "api_routes": [],
        "background_jobs": [],
    }

    seen_app: Set[str] = set()
    seen_routes: Set[str] = set()
    seen_jobs: Set[str] = set()

    for c in chunks:
        path = c.get("path", "")
        text = c.get("text", "")

        # ---- Application entrypoint ----
        if FASTAPI_APP.search(text) and path not in seen_app:
            entrypoints["application"].append(
                {
                    "file": path,
                    "symbol": "FastAPI()",
                    "description": "Application startup",
                }
            )
            seen_app.add(path)

        # ---- API routes ----
        if ROUTE_DECORATOR.search(text) and path not in seen_routes:
            entrypoints["api_routes"].append(
                {
                    "file": path,
                    "symbol": "API route",
                    "description": "HTTP endpoint",
                }
            )
            seen_routes.add(path)

        # ---- Background jobs ----
        if BACKGROUND_TASK.search(text) and path not in seen_jobs:
            entrypoints["background_jobs"].append(
                {
                    "file": path,
                    "symbol": "background task",
                    "description": "Async / background execution",
                }
            )
            seen_jobs.add(path)

    return entrypoints


# -----------------------------
# API-style route detection
# -----------------------------

async def detect_entrypoints(repo_id: ObjectId) -> List[str]:
    db = get_db()
    entrypoints: set[str] = set()

    cursor = db["code_chunks"].find(
        {
            "repo_id": repo_id,
            "path": {"$regex": "\\.py$", "$options": "i"},
            "text": {"$regex": "@router\\.(get|post|put|delete)", "$options": "i"},
        },
        {"path": 1, "text": 1},
    )

    async for r in cursor:
        text = r.get("text", "")

        if "/ingest" in text or "ingest" in text:
            entrypoints.add("POST /ingest")
        if "/repos/{repo_id}/ask" in text or "/ask" in text or "ask_repo" in text:
            entrypoints.add("POST /repos/{repo_id}/ask")

    return sorted(entrypoints)

# -----------------------------
# Call-graph walking (used by /architecture)
# -----------------------------

def walk_graph(
    graph: Dict[str, Set[str]],
    start: str,
    max_depth: int = 6,
) -> List[str]:
    """
    Walk a call graph safely with depth control.
    """
    path: List[str] = []
    visited: Set[str] = set()

    def dfs(node: str, depth: int):
        if depth > max_depth or node in visited:
            return
        visited.add(node)
        path.append(node)
        for child in graph.get(node, []):
            dfs(child, depth + 1)

    dfs(start, 0)
    return path