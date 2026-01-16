import httpx

class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model
        self.url = "http://localhost:11434/api/embeddings"

    def embed_text(self, text: str) -> list[float]:
        r = httpx.post(
            self.url,
            json={"model": self.model, "prompt": text},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["embedding"]