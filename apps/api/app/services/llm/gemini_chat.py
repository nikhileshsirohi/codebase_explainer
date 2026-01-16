from __future__ import annotations
from typing import Optional
from google import genai
from google.genai.errors import ClientError

from app.core.config import settings


class LLMRateLimitError(Exception):
    pass


class GeminiChatLLM:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        key = api_key or settings.GEMINI_API_KEY
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=key)
        self.model = model or settings.GEMINI_CHAT_MODEL

    def generate(self, prompt: str) -> str:
        try:
            res = self.client.models.generate_content(model=self.model, contents=prompt)
            return (res.text or "").strip()
        except ClientError as e:
            # 429 quota/rate-limit
            if getattr(e, "status_code", None) == 429:
                raise LLMRateLimitError(str(e)) from e
            raise