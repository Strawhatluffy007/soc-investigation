"""Subscription logins (no API key) through a CLI on the host, reached via
bridge/claude_bridge.py: Claude Pro/Max (Claude Code CLI, `cli="claude"`) and
ChatGPT Plus/Pro (Codex CLI, `cli="codex"`). The CLI runs locally but inference
happens at Anthropic / OpenAI, so these providers are external."""
from __future__ import annotations

import httpx

from app.llm.base import LLMError, LLMProvider


class ClaudeCLIProvider(LLMProvider):
    name = "claude_pro"
    is_external = True

    def __init__(self, url: str, token: str, model: str, timeout: int, cli: str = "claude",
                 name: str = "claude_pro", label: str = "Claude Pro"):
        if not token:
            raise LLMError("CLAUDE_BRIDGE_TOKEN is not set")
        self.url = url.rstrip("/")
        self.token = token
        self.name, self.cli = name, cli
        self.model = f"{label} ({model or 'default model'})"
        self._model_arg = model
        self.timeout = timeout

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        try:
            r = httpx.post(f"{self.url}/analyze",
                           json={"system": system, "prompt": prompt, "schema": schema, "model": self._model_arg,
                                 "cli": self.cli},
                           headers={"Authorization": f"Bearer {self.token}"}, timeout=self.timeout + 15)
        except httpx.TimeoutException as e:
            raise LLMError("LLM bridge timed out") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach LLM bridge at {self.url}") from e
        if r.status_code != 200:
            try:
                detail = r.json().get("error", "")
            except ValueError:
                detail = ""
            raise LLMError(f"LLM bridge error {r.status_code}: {detail[:300]}")
        data = r.json()
        if not isinstance(data.get("result"), dict):
            raise LLMError("LLM bridge returned no structured result")
        return data["result"]


def bridge_request(url: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    """Status / sign-in calls to the bridge (no customer data)."""
    if not token:
        raise LLMError("CLAUDE_BRIDGE_TOKEN is not set, so the login bridge can't be reached")
    try:
        r = httpx.request(method, url.rstrip("/") + path, json=body, timeout=30,
                          headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the LLM bridge at {url}. Is the claude-bridge service running?") from e
    if r.status_code == 404:
        raise LLMError("The LLM bridge is out of date; restart it: systemctl --user restart claude-bridge")
    if r.status_code != 200:
        raise LLMError(f"LLM bridge error {r.status_code}")
    return r.json()
