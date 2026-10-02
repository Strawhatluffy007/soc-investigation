"""Provider interface. Every LLM backend returns a dict that matches
ANALYSIS_SCHEMA (see prompts.py) or raises LLMError."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"
    #: True when prompts leave this machine (shown to the analyst before sending).
    is_external: bool = False
    model: str = ""

    @abstractmethod
    def analyze(self, system: str, prompt: str, schema: dict) -> dict:
        """Return a JSON object matching `schema`."""

    def describe(self) -> dict:
        return {"provider": self.name, "external": self.is_external, "model": self.model}


class NoLLM(LLMProvider):
    """Deterministic-only mode; the engine never calls analyze() on it."""
    name = "none"

    def analyze(self, system: str, prompt: str, schema: dict) -> dict:  # pragma: no cover
        raise LLMError("LLM disabled")
