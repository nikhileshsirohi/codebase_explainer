from __future__ import annotations
import httpx

class OllamaLLM:
    def __init__(
        self,
        model: str = "qwen2.5-coder:7b-instruct",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        self.model = model
        self.url = f"{base_url}/api/generate"
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