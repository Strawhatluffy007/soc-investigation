# app/llm/

Optional LLM analysis. Off by default (`LLM_PROVIDER=none`).

| File | Purpose |
|---|---|
| `base.py` | Provider interface and `LLMError`. |
| `factory.py` | Builds the configured provider and enforces the gates for external LLMs: global switch (`LLM_ALLOW_EXTERNAL`), per-customer allowance, per-run analyst confirmation. |
| `prompts.py` | System prompt, JSON output schema, and prompt assembly (truncation and secret scrubbing, customer schema within a size budget). |
| `claude_cli.py` | Claude Pro/Max subscription through the local Claude Code CLI, via `bridge/claude_bridge.py` on the host. |
| `anthropic_provider.py` | Claude via the Anthropic API (`ANTHROPIC_API_KEY`). |
| `ollama.py` | Local model via Ollama. |
