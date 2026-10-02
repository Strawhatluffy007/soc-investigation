"""Local model via Ollama's native /api/chat with JSON-schema output."""
from __future__ import annotations

import json
import re

import httpx

from app.llm.base import LLMError, LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, url: str, model: str, is_local: bool, timeout: int, num_ctx: int = 8192, think: bool = False):
        self.url = url.rstrip("/")
        self.model = model
        self.is_external = not is_local
        self.timeout = timeout
        self.num_ctx = num_ctx  # Ollama's default window is small and silently drops the start of long prompts
        self.think = think  # reasoning models (qwen3, deepseek-r1): off keeps output to the JSON schema

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        options = {"temperature": 0.1} | ({"num_ctx": self.num_ctx} if self.num_ctx > 0 else {})
        body = {"model": self.model, "stream": False, "format": schema, "options": options, "think": self.think,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        try:
            r = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
            r.raise_for_status()
            content = re.sub(r"<think>.*?</think>", "", r.json()["message"]["content"], flags=re.S)
            return json.loads(content.strip())
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama request failed: {type(e).__name__}") from e
        except (KeyError, ValueError) as e:
            raise LLMError("Ollama returned invalid JSON") from e
