"""Builds the configured provider and decides whether it may be used for a
given customer. The external-LLM gates, in order:

  1. LLM_PROVIDER must be something other than "none"
  2. LLM_ALLOW_EXTERNAL=true (global kill switch, default false). This caps
     everything below: nothing in the UI can turn external use on if it is false.
  3. the runtime switch in the web UI (data/settings.json, default on), which an
     analyst can flip without restarting the container
  4. the customer's `allow_external_llm` setting is not false
  5. the analyst ticked the confirmation for this run
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import Settings
from app.customers.store import CustomerProfile
from app.llm.base import LLMError, LLMProvider, NoLLM
from app.llm.config_store import LLMConfigStore
from app.llm.registry import SPECS, spec

PROVIDERS = tuple(SPECS)


def build_provider(settings: Settings, store: LLMConfigStore | None = None) -> LLMProvider:
    store = store or LLMConfigStore(settings.data_dir, settings.llm_provider)
    return build_provider_for(settings, store, store.active)


def build_provider_for(settings: Settings, store: LLMConfigStore, p: str) -> LLMProvider:
    s = spec(p)
    if s is None:
        raise LLMError(f"Unknown LLM provider '{p}' (expected one of {', '.join(PROVIDERS)})")
    opts = store.options(s.id)
    model = opts.get("model") or ""
    if s.id == "none":
        return NoLLM()
    if s.id == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(store.key("anthropic"), model or settings.anthropic_model,
                                 settings.anthropic_effort, settings.llm_timeout)
    if s.auth == "login":  # Claude Pro/Max or ChatGPT Plus/Pro via the CLI on the host
        from app.llm.claude_cli import ClaudeCLIProvider
        return ClaudeCLIProvider(settings.claude_bridge_url, settings.claude_bridge_token,
                                 model or (settings.claude_cli_model if s.id == "claude_pro" else ""),
                                 settings.llm_timeout, cli=s.cli, name=s.id, label=s.label)
    if s.id == "ollama":
        from app.llm.ollama import OllamaProvider
        return OllamaProvider(opts.get("base_url") or settings.ollama_url, model or settings.ollama_model,
                              settings.ollama_is_local, settings.llm_timeout)
    from app.llm.openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(s.id, s.label, opts.get("base_url") or s.base_url, store.key(s.id),
                                model or s.default_model, settings.llm_timeout, s.key_env)


class LLMGate:
    def __init__(self, settings: Settings, state_file: Path | None = None):
        self.settings = settings
        self.error = ""
        self.state_file = state_file or settings.data_dir / "settings.json"
        self.store = LLMConfigStore(self.state_file.parent, settings.llm_provider)
        self.reload()

    def reload(self) -> None:
        """Rebuild the provider after the active provider, model, endpoint or key changed."""
        self.error = ""
        self._cache: dict[str, tuple[LLMProvider, str]] = {}
        try:
            self.provider = build_provider(self.settings, self.store)
        except LLMError as e:
            self.provider = NoLLM()
            self.error = str(e)

    @property
    def configured(self) -> bool:
        return not isinstance(self.provider, NoLLM)

    def _state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @property
    def external_switch(self) -> bool:
        """The runtime on/off switch from the UI (independent of the env cap)."""
        return self._state().get("external_llm_enabled", True) is True

    @property
    def external_enabled(self) -> bool:
        return self.settings.llm_allow_external and self.external_switch

    def set_external(self, enabled: bool) -> None:
        if enabled and not self.settings.llm_allow_external:
            raise LLMError("External LLM use is disabled by LLM_ALLOW_EXTERNAL=false in the server config.")
        state = {**self._state(), "external_llm_enabled": bool(enabled)}
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def status(self, profile: CustomerProfile | None = None) -> dict:
        blocked, reason = self._check(self.provider, self.error, profile)
        return {**self.provider.describe(), "active": self.store.active, "configured": self.configured,
                "allow_external": self.external_enabled, "env_allow_external": self.settings.llm_allow_external,
                "external_switch": self.external_switch, "available": not blocked, "blocked_by": blocked,
                "reason": reason, "config_error": self.error, "choices": self.choices(profile)}

    # ---------------------------------------------------------------- per-run choice
    def _built(self, pid: str) -> tuple[LLMProvider, str]:
        """Provider `pid` (cached until the next reload) and its config error, if any."""
        if pid == self.store.active:
            return self.provider, self.error
        if pid not in self._cache:
            try:
                self._cache[pid] = (build_provider_for(self.settings, self.store, pid), "")
            except LLMError as e:
                self._cache[pid] = (NoLLM(), str(e))
        return self._cache[pid]

    def choices(self, profile: CustomerProfile | None = None) -> list[dict]:
        """Every provider an analyst could pick for a single run, with whether it can be used now."""
        out = []
        for s in SPECS.values():
            if s.auth == "none":
                continue
            prov, err = self._built(s.id)
            blocked, reason = self._check(prov, err, profile)
            out.append({"id": s.id, "label": s.label, "model": prov.model, "external": prov.is_external
                        if not isinstance(prov, NoLLM) else s.auth != "local", "auth": s.auth,
                        "default": s.id == self.store.active, "available": not blocked, "blocked_by": blocked,
                        "reason": reason})
        return out

    # ---------------------------------------------------------------- gates
    def _check(self, provider: LLMProvider, error: str, profile: CustomerProfile | None) -> tuple[str, str]:
        """("", "") when usable, else (which gate blocks it, why)."""
        if isinstance(provider, NoLLM):
            return "config", error or "No LLM provider selected. Local rules engine only."
        if provider.is_external:
            if not self.settings.llm_allow_external:
                return "env", "External LLM use is disabled (LLM_ALLOW_EXTERNAL=false)."
            if not self.external_switch:
                return "switch", "External LLM use is switched off (header switch). Local rules engine only."
            if profile is not None and not profile.allow_external_llm:
                return "customer", f"{profile.name} does not permit external LLM processing (allow_external_llm: false)."
        return "", ""

    def allowed(self, profile: CustomerProfile | None) -> tuple[bool, str]:
        blocked, reason = self._check(self.provider, self.error, profile)
        return not blocked, reason

    def for_run(self, profile: CustomerProfile, requested: bool, confirmed_external: bool,
                provider_id: str = "") -> LLMProvider | None:
        """Provider to use for this analysis (the default one, or `provider_id`), or None for rules only."""
        if not requested:
            return None
        if provider_id and provider_id not in SPECS:
            raise LLMError(f"Unknown LLM provider '{provider_id}'")
        provider, error = self._built(provider_id) if provider_id else (self.provider, self.error)
        blocked, reason = self._check(provider, error, profile)
        if blocked:
            raise LLMError(reason)
        if provider.is_external and not confirmed_external:
            raise LLMError("Sending data to an external LLM requires explicit confirmation.")
        return provider
