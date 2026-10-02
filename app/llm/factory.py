"""Builds the configured provider and decides whether it may be used for a
given customer. The external-LLM gates, in order:

  1. LLM_PROVIDER must be something other than "none"
  2. LLM_ALLOW_EXTERNAL=true (global kill switch, default false)
  3. the customer's `allow_external_llm` setting is not false
  4. the analyst ticked the confirmation for this run
"""
from __future__ import annotations

import os

from app.config import Settings
from app.customers.store import CustomerProfile
from app.llm.base import LLMError, LLMProvider, NoLLM

PROVIDERS = ("none", "claude_pro", "claude_cli", "anthropic", "ollama")


def build_provider(settings: Settings) -> LLMProvider:
    p = settings.llm_provider
    if p in ("", "none"):
        return NoLLM()
    if p == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(os.environ.get("ANTHROPIC_API_KEY", ""), settings.anthropic_model,
                                 settings.anthropic_effort, settings.llm_timeout)
    if p in ("claude_pro", "claude_cli"):  # Claude Pro/Max subscription via the Claude Code CLI
        from app.llm.claude_cli import ClaudeCLIProvider
        return ClaudeCLIProvider(settings.claude_bridge_url, settings.claude_bridge_token,
                                 settings.claude_cli_model, settings.llm_timeout)
    if p == "ollama":
        from app.llm.ollama import OllamaProvider
        return OllamaProvider(settings.ollama_url, settings.ollama_model, settings.ollama_is_local,
                              settings.llm_timeout)
    raise LLMError(f"Unknown LLM_PROVIDER '{p}' (expected one of {', '.join(PROVIDERS)})")


class LLMGate:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.error = ""
        try:
            self.provider = build_provider(settings)
        except LLMError as e:
            self.provider = NoLLM()
            self.error = str(e)

    @property
    def configured(self) -> bool:
        return not isinstance(self.provider, NoLLM)

    def status(self, profile: CustomerProfile | None = None) -> dict:
        allowed, reason = self.allowed(profile)
        return {**self.provider.describe(), "configured": self.configured,
                "allow_external": self.settings.llm_allow_external, "available": allowed,
                "reason": reason, "config_error": self.error}

    def allowed(self, profile: CustomerProfile | None) -> tuple[bool, str]:
        if not self.configured:
            return False, self.error or "No LLM provider configured (LLM_PROVIDER=none). Local rules engine only."
        if self.provider.is_external:
            if not self.settings.llm_allow_external:
                return False, "External LLM use is disabled (LLM_ALLOW_EXTERNAL=false)."
            if profile is not None and not profile.allow_external_llm:
                return False, f"{profile.name} does not permit external LLM processing (allow_external_llm: false)."
        return True, ""

    def for_run(self, profile: CustomerProfile, requested: bool, confirmed_external: bool) -> LLMProvider | None:
        """Provider to use for this analysis, or None for rules only."""
        if not requested:
            return None
        ok, reason = self.allowed(profile)
        if not ok:
            raise LLMError(reason)
        if self.provider.is_external and not confirmed_external:
            raise LLMError("Sending data to an external LLM requires explicit confirmation.")
        return self.provider
