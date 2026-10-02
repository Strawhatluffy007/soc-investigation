"""Claude via the Anthropic API (external: logs are sent to Anthropic)."""
from __future__ import annotations

import json

from app.llm.base import LLMError, LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    is_external = True

    def __init__(self, api_key: str, model: str, effort: str, timeout: int):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        import anthropic  # imported lazily so the app runs without it configured

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
        self.model = model
        self.effort = effort

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        a = self._anthropic
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except a.AuthenticationError as e:
            raise LLMError("Anthropic authentication failed (check ANTHROPIC_API_KEY)") from e
        except a.RateLimitError as e:
            raise LLMError("Anthropic rate limit reached; try again shortly") from e
        except a.APITimeoutError as e:
            raise LLMError("Anthropic request timed out") from e
        except a.APIConnectionError as e:
            raise LLMError("Could not reach the Anthropic API") from e
        except a.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}") from e

        if resp.stop_reason == "refusal":
            raise LLMError("Claude declined to analyse this content")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Claude response was truncated (max_tokens)")
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError("Claude returned invalid JSON") from e

    def test(self) -> str:
        """Check the key without spending tokens."""
        a = self._anthropic
        try:
            self.client.models.list(limit=1)
        except a.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key") from e
        except a.APIConnectionError as e:
            raise LLMError("Could not reach the Anthropic API") from e
        except a.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}") from e
        return "Anthropic API accepted the key."
