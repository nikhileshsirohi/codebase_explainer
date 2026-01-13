from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.db.mongo import get_db
from app.services.ingestion.github_client import GitHubClient, GitHubAPIError
from app.utils.repo_url import parse_github_owner_repo

REPO_FILES = "repo_files"
INGEST_JOBS = "ingest_jobs"
REPOS = "repos"


async def _set_job(job_id, status: str, error: str | None = None, extra: Dict[str, Any] | None = None):
    db = get_db()
    update: Dict[str, Any] = {"status": status, "updated_at": datetime.utcnow(), "error": error}
    if extra:
        update.update(extra)
    await db[INGEST_JOBS].update_one({"_id": job_id}, {"$set": update})


async def ingest_github_file_tree(repo_doc: Dict[str, Any], job_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch GitHub tree and store file metadata.
    Stores only blobs (files), not trees (folders).
    """
    db = get_db()
    job_id = job_doc["_id"]

    await _set_job(job_id, "running")

    try:
        owner, repo = parse_github_owner_repo(repo_doc["canonical_repo_url"])
        gh = GitHubClient()

        repo_info = await gh.get_repo(owner, repo)
        default_branch = repo_info.get("default_branch")

        ref = await gh.get_ref(owner, repo, default_branch)
        commit_sha = ref["object"]["sha"]

        commit = await gh.get_commit(owner, repo, commit_sha)
        tree_sha = commit["tree"]["sha"]

        tree = await gh.get_tree(owner, repo, tree_sha)

        items: List[Dict[str, Any]] = tree.get("tree", [])
        files = []
        for it in items:
            if it.get("type") != "blob":
                continue
            files.append({
                "repo_id": repo_doc["_id"],
                "job_id": job_id,
                "path": it.get("path"),
                "sha": it.get("sha"),
                "size": it.get("size"),
                "url": it.get("url"),
                "mode": it.get("mode"),
                "created_at": datetime.utcnow(),
            })

        # Replace files for this job (idempotent for same job)
        await db[REPO_FILES].delete_many({"job_id": job_id})
        if files:
            await db[REPO_FILES].insert_many(files)

        # persist default_branch on repo
        await db[REPOS].update_one(
            {"_id": repo_doc["_id"]},
            {"$set": {"default_branch": default_branch, "updated_at": datetime.utcnow()}},
        )

        await _set_job(job_id, "done", extra={"stats": {"files_indexed": len(files)}})
        return {"default_branch": default_branch, "files_indexed": len(files)}

    except (GitHubAPIError, ValueError) as e:
        await _set_job(job_id, "failed", error=str(e))
        raise