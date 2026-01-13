from __future__ import annotations

from typing import List, Optional
from google import genai

from app.core.config import settings


class GeminiEmbedder:
    def __init__(self, api_key: Optional[str] = None, dim: Optional[int] = None):
        key = api_key or settings.GEMINI_API_KEY
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=key)
        self.dim = dim or settings.EMBEDDING_DIM

    def embed_text(self, text: str) -> List[float]:
        # In the new SDK, optional inputs go under `config`  [oai_citation:2‡Google AI for Developers](https://ai.google.dev/gemini-api/docs/migrate?utm_source=chatgpt.com)
        res = self.client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config={"output_dimensionality": self.dim},
        )
        return list(res.embeddings[0].values)