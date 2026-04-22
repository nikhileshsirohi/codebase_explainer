from __future__ import annotations
import httpx

from app.core.config import settings

class OllamaLLM:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ):
        self.model = model or settings.OLLAMA_MODEL
        base = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.url = f"{base}/api/generate"
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self.url, json=payload)
            r.raise_for_status()
            data = r.json()

        return (data.get("response") or "").strip()
