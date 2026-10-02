"""The LLM providers the app knows about, grouped by how they authenticate:

  login    a subscription you sign in to on the Pi (no API key): Claude Pro/Max
           through the Claude Code CLI, ChatGPT Plus/Pro through the Codex CLI.
           Both CLIs run on the host and are reached through bridge/claude_bridge.py.
  api_key  pay-as-you-go APIs that need a key.
  local    a model on your own network (no key, nothing leaves if it is local).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    vendor: str
    auth: str  # login | api_key | local | none
    default_model: str = ""
    key_env: str = ""          # env var that holds the key (api_key providers)
    base_url: str = ""         # default endpoint (OpenAI-compatible providers)
    base_url_editable: bool = False
    cli: str = ""              # login providers: CLI the bridge runs
    login_cmd: str = ""        # run this on the Pi to sign in
    models_hint: str = ""
    docs: str = ""


SPECS: dict[str, ProviderSpec] = {s.id: s for s in (
    ProviderSpec("none", "None (local rules engine only)", "", "none"),
    ProviderSpec("claude_pro", "Claude Pro / Max", "Anthropic", "login", cli="claude",
                 login_cmd="claude auth login", models_hint="blank = CLI default, or opus / sonnet / haiku",
                 docs="https://docs.claude.com/en/docs/claude-code/setup"),
    ProviderSpec("chatgpt", "ChatGPT Plus / Pro", "OpenAI", "login", cli="codex",
                 login_cmd="codex login --device-auth", models_hint="blank = Codex default, e.g. gpt-5-codex",
                 docs="https://developers.openai.com/codex/cli"),
    ProviderSpec("anthropic", "Anthropic API", "Anthropic", "api_key", "claude-opus-5-5", "ANTHROPIC_API_KEY",
                 models_hint="claude-opus-5-5, claude-sonnet-5-5, claude-haiku-4-5",
                 docs="https://console.anthropic.com/settings/keys"),
    ProviderSpec("openai", "OpenAI API", "OpenAI", "api_key", "gpt-5", "OPENAI_API_KEY",
                 "https://api.openai.com/v1", models_hint="e.g. gpt-5, gpt-5-mini",
                 docs="https://platform.openai.com/api-keys"),
    ProviderSpec("gemini", "Google Gemini API", "Google", "api_key", "gemini-2.5-pro", "GEMINI_API_KEY",
                 "https://generativelanguage.googleapis.com/v1beta/openai", models_hint="e.g. gemini-2.5-pro, gemini-2.5-flash",
                 docs="https://aistudio.google.com/apikey"),
    ProviderSpec("openai_compatible", "OpenAI-compatible API", "OpenRouter, Groq, Mistral, DeepSeek…", "api_key",
                 "", "OPENAI_COMPAT_API_KEY", "https://openrouter.ai/api/v1", base_url_editable=True,
                 models_hint="the provider's model id, e.g. openai/gpt-5 on OpenRouter"),
    ProviderSpec("ollama", "Ollama", "Local", "local", "llama3.1:8b", base_url_editable=True,
                 models_hint="any pulled model, e.g. llama3.1:8b"),
)}

ALIASES = {"claude_cli": "claude_pro"}


def spec(provider_id: str) -> ProviderSpec | None:
    return SPECS.get(ALIASES.get(provider_id, provider_id))
