"""Claude Pro/Max subscription via the local Claude Code CLI (no API key), reached through bridge/claude_bridge.py
on the host. The CLI runs locally but inference happens at Anthropic, so this
provider is external."""
from __future__ import annotations

import httpx

from app.llm.base import LLMError, LLMProvider


class ClaudeCLIProvider(LLMProvider):
    name = "claude_pro"
    is_external = True

    def __init__(self, url: str, token: str, model: str, timeout: int):
        if not token:
            raise LLMError("CLAUDE_BRIDGE_TOKEN is not set")
        self.url = url.rstrip("/")
        self.token = token
        self.model = f"Claude Pro ({model or 'default model'})"
        self._model_arg = model
        self.timeout = timeout

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        try:
            r = httpx.post(f"{self.url}/analyze",
                           json={"system": system, "prompt": prompt, "schema": schema, "model": self._model_arg},
                           headers={"Authorization": f"Bearer {self.token}"}, timeout=self.timeout + 15)
        except httpx.TimeoutException as e:
            raise LLMError("Claude bridge timed out") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach Claude bridge at {self.url}") from e
        if r.status_code != 200:
            try:
                detail = r.json().get("error", "")
            except ValueError:
                detail = ""
            raise LLMError(f"Claude bridge error {r.status_code}: {detail[:300]}")
        data = r.json()
        if not isinstance(data.get("result"), dict):
            raise LLMError("Claude bridge returned no structured result")
        return data["result"]
