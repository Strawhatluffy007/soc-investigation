"""Which LLM provider is active, per-provider model/endpoint, and API keys.

- data/llm.json            active provider + model / base_url per provider
- data/secrets/llm-keys.json  API keys entered in the UI (mode 0600, never
                              returned by the API, never logged, git-ignored)

An API key set in the environment (e.g. OPENAI_API_KEY in .env) always wins
over a key saved from the UI, and can't be changed or removed from the UI.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from app.llm.registry import SPECS, spec

_KEY_RE = re.compile(r"^[A-Za-z0-9._:\-]{8,400}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/@\-]{0,120}$")


class ConfigError(ValueError):
    pass


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: dict, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, mode)
    tmp.replace(path)


class LLMConfigStore:
    def __init__(self, data_dir: Path, default_provider: str = "none"):
        self.path = data_dir / "llm.json"
        self.keys_path = data_dir / "secrets" / "llm-keys.json"
        self.default_provider = default_provider

    # ---------------------------------------------------------------- active
    @property
    def active(self) -> str:
        p = _read(self.path).get("active") or self.default_provider or "none"
        s = spec(p)
        return s.id if s else p  # unknown ids surface as a config error in the factory

    def set_active(self, provider_id: str) -> None:
        if provider_id not in SPECS:
            raise ConfigError(f"Unknown provider '{provider_id}'")
        data = _read(self.path)
        data["active"] = provider_id
        _write(self.path, data)

    # ---------------------------------------------------------------- per provider options
    def options(self, provider_id: str) -> dict:
        return dict(_read(self.path).get("providers", {}).get(provider_id, {}))

    def set_options(self, provider_id: str, model: str | None = None, base_url: str | None = None) -> None:
        s = SPECS.get(provider_id)
        if not s or s.auth == "none":
            raise ConfigError(f"Unknown provider '{provider_id}'")
        data = _read(self.path)
        opts = data.setdefault("providers", {}).setdefault(provider_id, {})
        if model is not None:
            model = model.strip()
            if not _MODEL_RE.match(model):
                raise ConfigError("Model name may only contain letters, digits and . _ : / @ -")
            opts["model"] = model
        if base_url is not None:
            if not s.base_url_editable:
                raise ConfigError(f"The endpoint for {s.label} can't be changed")
            base_url = base_url.strip().rstrip("/")
            if base_url and not re.match(r"^https?://[A-Za-z0-9.\-]+(:\d+)?(/[A-Za-z0-9._~/\-]*)?$", base_url):
                raise ConfigError("Endpoint must be an http(s) URL without query string or credentials")
            opts["base_url"] = base_url
        _write(self.path, data)

    # ---------------------------------------------------------------- keys
    def key(self, provider_id: str) -> str:
        s = SPECS.get(provider_id)
        if not s or not s.key_env:
            return ""
        return os.environ.get(s.key_env, "") or _read(self.keys_path).get(provider_id, "")

    def key_source(self, provider_id: str) -> str:
        s = SPECS.get(provider_id)
        if not s or not s.key_env:
            return ""
        if os.environ.get(s.key_env):
            return "env"
        return "saved" if _read(self.keys_path).get(provider_id) else ""

    def set_key(self, provider_id: str, api_key: str) -> None:
        s = SPECS.get(provider_id)
        if not s or s.auth != "api_key":
            raise ConfigError(f"{provider_id} does not use an API key")
        if os.environ.get(s.key_env):
            raise ConfigError(f"The key is set by {s.key_env} in the server environment; change it there")
        api_key = api_key.strip()
        if not _KEY_RE.match(api_key):
            raise ConfigError("That does not look like an API key (8-400 chars, no spaces)")
        keys = _read(self.keys_path)
        keys[provider_id] = api_key
        _write(self.keys_path, keys, 0o600)

    def delete_key(self, provider_id: str) -> bool:
        keys = _read(self.keys_path)
        if provider_id not in keys:
            return False
        del keys[provider_id]
        _write(self.keys_path, keys, 0o600)
        return True
