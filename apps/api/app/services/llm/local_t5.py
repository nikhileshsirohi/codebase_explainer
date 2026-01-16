from __future__ import annotations

from functools import lru_cache

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from app.core.config import settings


def _pick_device() -> str:
    # Apple Silicon (MPS) if available, else CPU
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def _load_model():
    model_name = settings.LOCAL_LLM_MODEL
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    device = _pick_device()
    model.to(device)
    model.eval()
    return tok, model, device


class LocalT5LLM:
    def generate(self, prompt: str, max_new_tokens: int = 350) -> str:
        tok, model, device = _load_model()
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=2048).to(device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        return tok.decode(out[0], skip_special_tokens=True).strip()