"""Runtime settings, read once from environment variables.

Nothing here has a secret default. Every value can be changed in `.env`
without touching source code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

LOCAL_BIND_ADDRS = {"127.0.0.1", "localhost", "::1", ""}


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    customers_dir: Path
    data_dir: Path
    default_template: Path
    catalog_path: Path
    catalog_fetch_enabled: bool

    # Exposure / auth
    bind_addr: str
    auth_user: str
    auth_password: str

    # Limits
    max_upload_bytes: int
    max_log_chars: int

    # LLM
    llm_provider: str  # none | anthropic | claude_cli | ollama
    llm_allow_external: bool
    llm_timeout: int
    llm_max_log_chars: int
    llm_max_context_chars: int
    anthropic_model: str
    anthropic_effort: str
    claude_bridge_url: str
    claude_bridge_token: str
    claude_cli_model: str
    ollama_url: str
    ollama_model: str
    ollama_is_local: bool
    ollama_num_ctx: int
    ollama_think: bool

    extra: dict = field(default_factory=dict)

    @property
    def auth_enabled(self) -> bool:
        return bool(self.auth_password)

    @property
    def exposed(self) -> bool:
        return self.bind_addr not in LOCAL_BIND_ADDRS


def load_settings() -> Settings:
    base = Path(__file__).resolve().parent.parent
    return Settings(
        customers_dir=Path(_str("SOC_CUSTOMERS_DIR", str(base / "customers"))),
        data_dir=Path(_str("SOC_DATA_DIR", str(base / "data"))),
        default_template=Path(_str("SOC_DEFAULT_TEMPLATE", str(base / "templates" / "incident-ticket.md"))),
        catalog_path=Path(_str("SOC_CATALOG_PATH", str(base / "catalog" / "schema-catalog.md"))),
        catalog_fetch_enabled=_bool("CATALOG_FETCH_ENABLED", True),
        bind_addr=_str("SOC_BIND_ADDR", "127.0.0.1"),
        auth_user=_str("SOC_AUTH_USER", "analyst"),
        auth_password=os.environ.get("SOC_AUTH_PASSWORD", ""),
        max_upload_bytes=_int("SOC_MAX_UPLOAD_BYTES", 5 * 1024 * 1024),
        max_log_chars=_int("SOC_MAX_LOG_CHARS", 2_000_000),
        llm_provider=_str("LLM_PROVIDER", "none").lower(),
        llm_allow_external=_bool("LLM_ALLOW_EXTERNAL", False),
        llm_timeout=_int("LLM_TIMEOUT_SECONDS", 240),
        llm_max_log_chars=_int("LLM_MAX_LOG_CHARS", 60_000),
        llm_max_context_chars=_int("LLM_MAX_CONTEXT_CHARS", 120_000),
        anthropic_model=_str("ANTHROPIC_MODEL", "claude-opus-5-5"),
        anthropic_effort=_str("ANTHROPIC_EFFORT", "medium"),
        claude_bridge_url=_str("CLAUDE_BRIDGE_URL", "http://host.docker.internal:8765"),
        claude_bridge_token=os.environ.get("CLAUDE_BRIDGE_TOKEN", ""),
        claude_cli_model=_str("CLAUDE_CLI_MODEL", ""),
        ollama_url=_str("OLLAMA_URL", "http://host.docker.internal:11434"),
        ollama_model=_str("OLLAMA_MODEL", "llama3.1:8b"),
        ollama_is_local=_bool("OLLAMA_IS_LOCAL", True),
        ollama_num_ctx=_int("OLLAMA_NUM_CTX", 8192),
        ollama_think=_bool("OLLAMA_THINK", False),
    )
