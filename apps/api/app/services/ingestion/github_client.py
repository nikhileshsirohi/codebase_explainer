from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings


class GitHubAPIError(Exception):
    pass


@dataclass
class GitHubRateLimit:
    remaining: Optional[int]
    reset_epoch: Optional[int]


class GitHubClient:
    def __init__(self, token: Optional[str] = None) -> None:
        self.base = "https://api.github.com"
        self.token = token or getattr(settings, "GITHUB_TOKEN", None)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "codebase-explainer-bot/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _rate_limit(self, resp: httpx.Response) -> GitHubRateLimit:
        def _to_int(v: Optional[str]) -> Optional[int]:
            try:
                return int(v) if v is not None else None
            except ValueError:
                return None

        remaining = _to_int(resp.headers.get("x-ratelimit-remaining"))
        reset = _to_int(resp.headers.get("x-ratelimit-reset"))
        return GitHubRateLimit(remaining=remaining, reset_epoch=reset)

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers(), params=params)

        if resp.status_code in (403, 429):
            rl = self._rate_limit(resp)
            # GitHub recommends not retrying when remaining is 0 until reset  [oai_citation:2‡GitHub Docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?utm_source=chatgpt.com)
            raise GitHubAPIError(
                f"GitHub rate limit or forbidden. status={resp.status_code} "
                f"remaining={rl.remaining} reset={rl.reset_epoch} body={resp.text[:200]}"
            )

        if resp.status_code >= 400:
            raise GitHubAPIError(f"GitHub API error status={resp.status_code} body={resp.text[:300]}")

        return resp.json()

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        return await self._get(f"/repos/{owner}/{repo}")

    async def get_ref(self, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        return await self._get(f"/repos/{owner}/{repo}/git/refs/heads/{branch}")

    async def get_commit(self, owner: str, repo: str, commit_sha: str) -> Dict[str, Any]:
        return await self._get(f"/repos/{owner}/{repo}/git/commits/{commit_sha}")

    async def get_tree(self, owner: str, repo: str, tree_sha: str) -> Dict[str, Any]:
        # recursive=1 is the standard approach for full tree  [oai_citation:3‡GitHub Docs](https://docs.github.com/rest/git/trees?utm_source=chatgpt.com)
        return await self._get(f"/repos/{owner}/{repo}/git/trees/{tree_sha}", params={"recursive": "1"})
    

    async def get_blob_by_api_url(self, blob_api_url: str) -> dict:
        # blob_api_url is like: https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(blob_api_url, headers=self._headers())

        if resp.status_code in (403, 429):
            rl = self._rate_limit(resp)
            raise GitHubAPIError(
                f"GitHub rate limit or forbidden. status={resp.status_code} "
                f"remaining={rl.remaining} reset={rl.reset_epoch} body={resp.text[:200]}"
            )

        if resp.status_code >= 400:
            raise GitHubAPIError(f"GitHub API error status={resp.status_code} body={resp.text[:300]}")

        return resp.json()

    @staticmethod
    def decode_blob_content(blob_json: dict) -> bytes:
        # GitHub returns base64 with newlines sometimes
        enc = blob_json.get("encoding")
        content = blob_json.get("content", "")
        if enc != "base64":
            return content.encode("utf-8", errors="ignore")
        content = content.replace("\n", "")
        return base64.b64decode(content)