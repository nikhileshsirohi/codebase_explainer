# apps/api/app/services/analysis/architecture.py

from collections import defaultdict
from typing import Dict, Set, List
from bson import ObjectId

from app.db.mongo import get_db
from app.services.rag.links import extract_python_links
from app.services.analysis.entrypoints import detect_entrypoints, walk_graph


async def build_call_graph(repo_id: ObjectId) -> Dict[str, Set[str]]:
    db = get_db()
    graph: Dict[str, Set[str]] = defaultdict(set)

    cursor = db["code_chunks"].find(
        {"repo_id": repo_id, "path": {"$regex": "\\.py$", "$options": "i"}},
        {"path": 1, "text": 1},
    )

    async for r in cursor:
        path = r.get("path", "")
        text = r.get("text", "") or ""

        links = extract_python_links(text)
        for link in links:
            if link.kind == "calls":
                graph[path].add(link.name)

    return graph


async def build_architecture(repo_id: ObjectId) -> List[dict]:
    graph = await build_call_graph(repo_id)
    entrypoints = await detect_entrypoints(repo_id)

    flows = []
    for ep in entrypoints:
        if "ingest" in ep:
            start_fn = "ingest_repo"
        elif "ask" in ep:
            start_fn = "ask_repo"
        else:
            continue

        path = walk_graph(graph, start_fn)
        flows.append({"entrypoint": ep, "path": path})

    return flows