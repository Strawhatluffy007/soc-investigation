"""Any OpenAI-style /chat/completions API: OpenAI, Google Gemini (OpenAI
endpoint), OpenRouter, Groq, Mistral, DeepSeek and others. External."""
from __future__ import annotations

import json
import re

import httpx

from app.llm.base import LLMError, LLMProvider


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if m:
        text = m.group(1)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


class OpenAICompatProvider(LLMProvider):
    is_external = True

    def __init__(self, name: str, label: str, base_url: str, api_key: str, model: str, timeout: int,
                 key_env: str = ""):
        if not api_key:
            raise LLMError(f"No API key for {label}. Add one in LLM settings" + (f" or set {key_env}." if key_env else "."))
        if not base_url:
            raise LLMError(f"No endpoint URL set for {label}")
        if not model:
            raise LLMError(f"No model set for {label}")
        self.name, self.label = name, label
        self.url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def _post(self, body: dict) -> httpx.Response:
        try:
            return httpx.post(f"{self.url}/chat/completions", json=body, headers=self._headers, timeout=self.timeout)
        except httpx.TimeoutException as e:
            raise LLMError(f"{self.label} request timed out") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach {self.label} at {self.url}") from e

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": messages,
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "soc_analysis", "schema": schema, "strict": False}}}
        r = self._post(body)
        if r.status_code == 400:  # endpoint without json_schema support: fall back to plain JSON mode
            hint = "\n\nReply with only a JSON object matching this JSON Schema:\n" + json.dumps(schema)
            body = {"model": self.model, "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system + hint}, messages[1]]}
            r = self._post(body)
        if r.status_code in (401, 403):
            raise LLMError(f"{self.label} rejected the API key ({r.status_code})")
        if r.status_code == 429:
            raise LLMError(f"{self.label} rate limit or quota reached; try again later")
        if r.status_code != 200:
            raise LLMError(f"{self.label} error {r.status_code}")
        try:
            choice = r.json()["choices"][0]
            if choice.get("finish_reason") == "length":
                raise LLMError(f"{self.label} response was truncated")
            return _parse_json(choice["message"]["content"] or "")
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise LLMError(f"{self.label} returned invalid JSON") from e

    def test(self) -> str:
        """Check the key/endpoint without spending tokens."""
        try:
            r = httpx.get(f"{self.url}/models", headers=self._headers, timeout=20)
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach {self.label} at {self.url}") from e
        if r.status_code in (401, 403):
            raise LLMError(f"{self.label} rejected the API key ({r.status_code})")
        if r.status_code != 200:
            raise LLMError(f"{self.label} returned {r.status_code}")
        return f"{self.label} accepted the key."
