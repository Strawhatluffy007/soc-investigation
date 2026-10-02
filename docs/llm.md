# LLM integration

The deterministic rules engine always runs. An LLM, if enabled, adds to it:

- a summary
- Observed, Inferred and Unknown statements
- hypotheses, extra KQL and next steps

LLM queries go through the same local schema validation and are labelled **LLM-suggested**. If the LLM call fails, you get the rules result plus the error message.

## Providers (`LLM_PROVIDER`)

| Value | What it does | External? |
|---|---|---|
| `none` (default) | Rules engine only | – |
| `anthropic` | Claude API via the Anthropic SDK (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_EFFORT`) | **Yes** |
| `claude_pro` (alias `claude_cli`) | Claude Pro/Max subscription through the Claude Code CLI on the host (no API key) via `bridge/claude_bridge.py` | **Yes** (inference runs at Anthropic) |
| `ollama` | Local model via Ollama `/api/chat` | No, unless `OLLAMA_IS_LOCAL=false` |

### Data-sending gates

For an external provider, every gate must allow it:

1. `LLM_ALLOW_EXTERNAL=true` (global kill switch, default `false`).
2. The customer doesn't set `allow_external_llm: false`.
3. The analyst picks **Rules + LLM** for this run.
4. The analyst ticks *"I confirm this data may leave this system"*.

The UI header shows whether an external LLM is available. Each investigation records `llm_used`, and every send is written to the audit log (provider, model and size; never content).

### What is sent

- The raw log, secret-scrubbed and truncated to `LLM_MAX_LOG_CHARS`.
- The analyst context.
- That customer's `customer.md`, truncated to `LLM_MAX_CONTEXT_CHARS`.
- That customer's table list.
- The rules engine's classification and observables.

No other customer's data is ever included. The log goes inside `<untrusted_log>` tags, and the system prompt says to treat it as data, not instructions.

## Option A: Claude API

```
LLM_PROVIDER=anthropic
LLM_ALLOW_EXTERNAL=true
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-5-5
ANTHROPIC_EFFORT=medium        # low | medium | high
```

The request uses:

- structured JSON output (a JSON schema)
- adaptive thinking
- server-side refusal fallbacks (`fallbacks="default"`)

## Option B: local Claude Code CLI (uses your Claude login, no API key)

1. Create a token: `python3 -c "import secrets;print(secrets.token_urlsafe(32))"`.
2. `cp .env.bridge.example .env.bridge`, then set `CLAUDE_BRIDGE_TOKEN`. Keep `CLAUDE_BRIDGE_HOST=172.30.90.1`, the gateway of the app's docker network.
3. In `.env`, set:
   - `LLM_PROVIDER=claude_pro`
   - `LLM_ALLOW_EXTERNAL=true`
   - the same `CLAUDE_BRIDGE_TOKEN`
4. Start the bridge. The app must be up first, because the bridge binds to the network the app creates:

```bash
docker compose up -d
mkdir -p ~/.config/systemd/user && cp bridge/claude-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now claude-bridge
loginctl enable-linger $USER
docker compose up -d --force-recreate
```

The bridge runs `claude -p` with no tools, no MCP servers, no settings and no session persistence, in an empty temporary directory, one request at a time. A typical analysis takes 30 to 90 seconds.

## Adding a provider

1. Subclass `app.llm.base.LLMProvider`: set `name` and `is_external`, and implement `analyze(system, prompt, schema) -> dict`.
2. Register it in `app/llm/factory.py`.

## Using a Claude Pro subscription (no API key)

`LLM_PROVIDER=claude_pro` sends analysis requests to `bridge/claude_bridge.py` on the host. The bridge runs
`claude -p` under your Claude Code login (`claude auth login` with your Pro account; check it with
`claude auth status`, which should show `"authMethod": "claude.ai"`).

- The bridge removes `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the CLI's environment, so requests always use the subscription and never API billing.
- Usage counts against your Pro limits: about 1–2 minutes per analysis, one at a time.
- To change the model, set `CLAUDE_CLI_MODEL` (for example `sonnet` or `opus`). Leave it empty for your plan's default.
- Pro is a consumer plan, so data you send is governed by your claude.ai privacy settings. Check them before sending customer logs; use `allow_external_llm: false` for customers that must stay local.
- To manage the bridge: `systemctl --user status|restart claude-bridge`; logs: `journalctl --user -u claude-bridge -n 50`.
