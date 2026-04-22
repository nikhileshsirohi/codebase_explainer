import httpx

from app.core.config import settings

class OllamaEmbedder:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or settings.OLLAMA_EMBED_MODEL
        base = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.url = f"{base}/api/embeddings"

    def embed_text(self, text: str) -> list[float]:
        r = httpx.post(
            self.url,
            json={"model": self.model, "prompt": text},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["embedding"]
