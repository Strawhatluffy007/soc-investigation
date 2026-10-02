# 🤖 `app/llm/`

> Optional LLM providers & gates

<sub>[🏠 Home](../../README.md) › [app/](../README.md) › **llm/**</sub>

> [!NOTE]
> LLM analysis is optional and **off by default** (`LLM_PROVIDER=none`). Choose the provider in the web UI under **LLM settings**. External providers must pass four gates: the env cap, the UI switch, the per-customer allowance and the analyst's confirmation on each run.

| File | Purpose |
|---|---|
| `base.py` | Provider interface and `LLMError`. |
| `registry.py` | The providers the app knows about, grouped by sign-in type (login / API key / local). |
| `config_store.py` | Active provider and per-provider model and endpoint (`data/llm.json`), plus API keys pasted in the UI (`data/secrets/llm-keys.json`, mode 0600; an env key wins). |
| `factory.py` | Builds the active provider and enforces the gates for external LLMs: env cap (`LLM_ALLOW_EXTERNAL`), the UI on/off switch, per-customer allowance, per-run analyst confirmation. |
| `prompts.py` | System prompt, JSON output schema (analysis, answer to the latest follow-up, ticket draft), and prompt assembly (truncation and secret scrubbing, follow-up logs and notes, customer schema within a size budget). |
| `claude_cli.py` | Subscription logins through a CLI on the host, via `bridge/claude_bridge.py`: Claude Pro/Max (Claude Code) and ChatGPT Plus/Pro (Codex). Also the bridge status and sign-in client. |
| `openai_compat.py` | OpenAI, Gemini and any OpenAI-compatible `/chat/completions` API. |
| `anthropic_provider.py` | Claude via the Anthropic API (`ANTHROPIC_API_KEY`). |
| `ollama.py` | Local model via Ollama. |
