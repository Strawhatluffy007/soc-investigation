"""Local model via Ollama's native /api/chat with JSON-schema output."""
from __future__ import annotations

import json

import httpx

from app.llm.base import LLMError, LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, url: str, model: str, is_local: bool, timeout: int):
        self.url = url.rstrip("/")
        self.model = model
        self.is_external = not is_local
        self.timeout = timeout

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        body = {"model": self.model, "stream": False, "format": schema, "options": {"temperature": 0.1},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        try:
            r = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
            r.raise_for_status()
            return json.loads(r.json()["message"]["content"])
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama request failed: {type(e).__name__}") from e
        except (KeyError, ValueError) as e:
            raise LLMError("Ollama returned invalid JSON") from e
