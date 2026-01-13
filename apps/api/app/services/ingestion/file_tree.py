from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.db.mongo import get_db
from app.services.ingestion.github_client import GitHubClient, GitHubAPIError
from app.utils.repo_url import parse_github_owner_repo
from app.services.indexing.indexer import build_embeddings_for_job

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

        content_stats = await ingest_file_contents(repo_doc=repo_doc, job_doc=job_doc)

        emb_stats = await build_embeddings_for_job(repo_doc["_id"], job_id)

        await _set_job(job_id, "done", extra={"stats": {"files_indexed": len(files), **content_stats, **emb_stats}})
        return {"default_branch": default_branch, "files_indexed": len(files), **content_stats, **emb_stats}

    except (GitHubAPIError, ValueError) as e:
        await _set_job(job_id, "failed", error=str(e))
        raise


REPO_FILE_CONTENTS = "repo_file_contents"

MAX_TEXT_BYTES = 200_000  # 200KB per file for MVP (production-safe)

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php",
    ".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".ini",
    ".sql", ".sh", ".bash", ".zsh",
    ".html", ".css", ".scss",
    ".dockerfile", ".gitignore",
}

def _is_likely_text(path: str) -> bool:
    p = path.lower()
    if p.endswith("dockerfile"):
        return True
    return any(p.endswith(ext) for ext in TEXT_EXTENSIONS)

def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data  # null byte check

async def ingest_file_contents(repo_doc: Dict[str, Any], job_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch contents for files already saved in repo_files for this job.
    """
    db = get_db()
    job_id = job_doc["_id"]
    gh = GitHubClient()

    cursor = db[REPO_FILES].find({"job_id": job_id}, projection={"path": 1, "size": 1, "url": 1, "sha": 1})
    files = await cursor.to_list(length=None)

    fetched = 0
    skipped_large = 0
    skipped_binary = 0
    skipped_nontext = 0
    failed = 0

    # Clean old content for this job (idempotent)
    await db[REPO_FILE_CONTENTS].delete_many({"job_id": job_id})

    for f in files:
        path = f.get("path") or ""
        size = f.get("size") or 0
        blob_url = f.get("url")

        if not _is_likely_text(path):
            skipped_nontext += 1
            continue

        if size and size > MAX_TEXT_BYTES:
            skipped_large += 1
            continue

        try:
            blob_json = await gh.get_blob_by_api_url(blob_url)
            raw_bytes = gh.decode_blob_content(blob_json)

            if len(raw_bytes) > MAX_TEXT_BYTES:
                skipped_large += 1
                continue

            if _looks_binary(raw_bytes):
                skipped_binary += 1
                continue

            text = raw_bytes.decode("utf-8", errors="replace")

            await db[REPO_FILE_CONTENTS].insert_one({
                "repo_id": repo_doc["_id"],
                "job_id": job_id,
                "path": path,
                "sha": f.get("sha"),
                "size": size,
                "text": text,
                "created_at": datetime.utcnow(),
            })
            fetched += 1

        except Exception:
            failed += 1
            # keep going; we don't want one file to kill ingestion

    return {
        "files_fetched": fetched,
        "skipped_large": skipped_large,
        "skipped_binary": skipped_binary,
        "skipped_nontext": skipped_nontext,
        "files_failed": failed,
    }