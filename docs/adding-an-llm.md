# Adding another LLM

The app ships with these providers: Claude Pro/Max and ChatGPT Plus/Pro (login), Anthropic, OpenAI, Google Gemini and
any OpenAI-compatible API (API key), and Ollama (local). Pick and configure them in **LLM settings**. See
[llm.md](llm.md) for what each one does and which data is sent.

Choose the path that matches the new LLM:

| The new LLM… | Effort | Go to |
|---|---|---|
| has an OpenAI-style `/chat/completions` API (OpenRouter, Groq, Mistral, DeepSeek, Together, xAI, LM Studio, vLLM…) | none, no code | [A. Use the OpenAI-compatible slot](#a-use-the-openai-compatible-slot-no-code) |
| has an OpenAI-style API and you want it as its own named entry with its own key | ~10 lines | [B. Add a named OpenAI-compatible provider](#b-add-a-named-openai-compatible-provider) |
| has its own API or SDK (for example AWS Bedrock or Azure AI with a different auth scheme) | one small class | [C. Write a provider class](#c-write-a-provider-class) |
| is a subscription you sign in to through a CLI (like Claude Code or Codex) | class + bridge runner | [D. Add a login (CLI) provider](#d-add-a-login-cli-provider) |

Whatever you add automatically gets the safety gates: the `LLM_ALLOW_EXTERNAL` env cap, the **External LLM** switch,
each customer's `allow_external_llm`, and the per-run confirmation. It also gets the per-run picker in
**Analysis mode** and audit logging. The prompt already has secrets redacted and size limits applied before any
provider sees it.

---

## A. Use the OpenAI-compatible slot (no code)

1. Open **LLM settings** → **API key** → **OpenAI-compatible API**.
2. Set **Endpoint URL** to the provider's base URL (the part before `/chat/completions`) and **Model** to its model
   id, then click **Save**.

   | Provider | Endpoint URL | Model example |
   |---|---|---|
   | OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-5-5` |
   | Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
   | Mistral | `https://api.mistral.ai/v1` | `mistral-large-latest` |
   | DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
   | LM Studio (local) | `http://host.docker.internal:1234/v1` | the loaded model |

3. Paste the API key and click **Save key** (or set `OPENAI_COMPAT_API_KEY` in `.env` and recreate the container).
4. Click **Test**. It lists models with your key and sends no prompt.
5. Click **Use this**, or pick it per investigation in **Analysis mode**.

The provider first asks for JSON-schema output. If the endpoint rejects that with HTTP 400, it retries in plain JSON
mode with the schema in the system prompt.

## B. Add a named OpenAI-compatible provider

Do this when you want, say, both Groq *and* OpenRouter configured at the same time. Add one entry to `SPECS` in
[`app/llm/registry.py`](../app/llm/registry.py):

```python
ProviderSpec("groq", "Groq", "Groq", "api_key", "llama-3.3-70b-versatile", "GROQ_API_KEY",
             "https://api.groq.com/openai/v1", models_hint="e.g. llama-3.3-70b-versatile",
             docs="https://console.groq.com/keys"),
```

Fields, in order: `id`, `label`, `vendor`, `auth` (`api_key`), `default_model`, `key_env` (env var for the key),
`base_url`. Add `base_url_editable=True` to let users change the endpoint in the UI.

That's all. The factory falls through to `OpenAICompatProvider` for any `api_key` provider it doesn't know. The new
entry appears in LLM settings and in the per-run picker. Its key can be pasted in the UI (stored in
`data/secrets/llm-keys.json`, mode 0600) or set as `GROQ_API_KEY` in `.env`. Add the variable, empty, to
`.env.example`.

## C. Write a provider class

1. Create `app/llm/<name>_provider.py`:

   ```python
   from app.llm.base import LLMError, LLMProvider

   class AcmeProvider(LLMProvider):
       name = "acme"
       is_external = True            # True if prompts leave this machine. It drives the gates and UI warnings.

       def __init__(self, api_key: str, model: str, timeout: int):
           if not api_key:
               raise LLMError("No API key for Acme. Add one in LLM settings or set ACME_API_KEY.")
           self.model, self.timeout = model, timeout
           ...                         # build the SDK client (import it here so the app runs without it)

       def analyze(self, system: str, prompt: str, schema: dict) -> dict:
           """Return a dict that matches `schema` (ANALYSIS_SCHEMA in prompts.py), or raise LLMError."""
           ...

       def test(self) -> str:        # optional: used by the Test button. Must not send a prompt.
           ...
           return "Acme accepted the key."
   ```

   Rules:
   - Raise `LLMError` with a short, safe message for every failure (auth, rate limit, timeout, bad JSON).
     Never include the prompt, the log or the key in the message, because it is shown in the UI.
   - Use the provider's structured-output / JSON-schema feature where it has one, and parse the JSON yourself
     otherwise.
   - Don't log the prompt or the response.
   - Add the SDK to `requirements.txt` only if you need it. Plain `httpx` (already installed) is fine.

2. Register it in `SPECS` in `app/llm/registry.py` with `auth="api_key"` (or `"local"`) and a `key_env`.
3. Build it in `build_provider_for()` in [`app/llm/factory.py`](../app/llm/factory.py), before the
   OpenAI-compatible fall-through:

   ```python
   if s.id == "acme":
       from app.llm.acme_provider import AcmeProvider
       return AcmeProvider(store.key("acme"), model or s.default_model, settings.llm_timeout)
   ```

   `store.key()` returns the env key if set, otherwise the key saved in the UI. `store.options(id)` holds the model and
   endpoint saved in the UI.

4. Add a test in `tests/test_llm_providers.py` that monkeypatches the HTTP call. See
   `test_openai_compat_falls_back_to_json_mode`. Run `.venv/bin/python -m pytest -q`.
5. Rebuild: `docker compose up -d --build`.

## D. Add a login (CLI) provider

Login providers use a subscription that a CLI on the Pi is signed in to. The container can't run host binaries, so
calls go through [`bridge/claude_bridge.py`](../bridge/claude_bridge.py), a small HTTP service on the host.

1. **Bridge:** write `run_<cli>(system, prompt, schema, model) -> dict`. Run the CLI non-interactively in an empty temp
   directory with no tools, and with a read-only sandbox if it has one. Use `env=SUBSCRIPTION_ENV`, and add the CLI's
   API-key variables to the exclusion list so it can't fall back to API billing. Then:
   - add the runner to `RUNNERS`;
   - add its install and login check to `cli_status()`;
   - add `Environment=<CLI>_BIN=%h/.local/bin/<cli>` to the systemd unit;
   - restart the bridge: `systemctl --user daemon-reload && systemctl --user restart claude-bridge`.
2. **Registry:** add `ProviderSpec("<id>", "<Label>", "<Vendor>", "login", cli="<cli>", login_cmd="<cli> login")`.
3. **Factory:** nothing to do. Every `auth="login"` spec is built as `ClaudeCLIProvider(..., cli=s.cli)`, which
   posts `{"cli": "<cli>"}` to the bridge.
4. Optional browser sign-in: if the CLI has a device-code flow, follow `DeviceLogin` in the bridge (it parses the URL
   and code from the CLI output) and allow the new `cli` in the `/llm/providers/{pid}/login` routes.

## Checklist

- [ ] `is_external` is correct. If unsure, `True`.
- [ ] No key in source code, logs, error messages or tickets. Keys come from `store.key()` only.
- [ ] Errors are `LLMError` with safe messages.
- [ ] **Test** in LLM settings works without sending a prompt.
- [ ] Tests pass, and `docs/llm.md` lists the new provider.
