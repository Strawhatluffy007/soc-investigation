# LLM integration

The deterministic rules engine always runs. An LLM, if enabled, adds to it:

- a summary
- Observed, Inferred and Unknown statements
- hypotheses, extra KQL and next steps

LLM queries go through the same local schema validation and are labelled **LLM-suggested**. If the LLM call fails, you get the rules result plus the error message.

## Providers

Pick the active provider, models, endpoints and API keys in the web UI: **LLM settings** in the sidebar. `LLM_PROVIDER` in `.env` is only the starting choice until you pick one there. The choice is saved in `data/llm.json`.

| Id | How it signs in | What it does | External? |
|---|---|---|---|
| `none` | – | Rules engine only | – |
| `claude_pro` (alias `claude_cli`) | **Login**: `claude auth login` on the Pi | Claude Pro/Max subscription through the Claude Code CLI, via `bridge/claude_bridge.py` | **Yes** |
| `chatgpt` | **Login**: `codex login --device-auth` on the Pi, or **Sign in from browser** in LLM settings | ChatGPT Plus/Pro subscription through the OpenAI Codex CLI (`codex exec`, read-only sandbox), via the same bridge | **Yes** |
| `anthropic` | **API key** `ANTHROPIC_API_KEY` | Claude API via the Anthropic SDK | **Yes** |
| `openai` | **API key** `OPENAI_API_KEY` | OpenAI Chat Completions with JSON-schema output | **Yes** |
| `gemini` | **API key** `GEMINI_API_KEY` | Google Gemini through its OpenAI-compatible endpoint | **Yes** |
| `openai_compatible` | **API key** `OPENAI_COMPAT_API_KEY` + endpoint URL | OpenRouter, Groq, Mistral, DeepSeek or any other `/chat/completions` API | **Yes** |
| `ollama` | – | Local model via Ollama `/api/chat`. Set `OLLAMA_NUM_CTX` to fit the prompt; see [windows.md](windows.md) for sizing on a small GPU | No, unless `OLLAMA_IS_LOCAL=false` |

**API keys.** A key in `.env` always wins and can't be changed from the UI. A key pasted in the UI is stored in `data/secrets/llm-keys.json` (mode 0600, git-ignored). The API never returns a key, and the audit log records only that a key was set or removed (`settings.llm_key.set` / `.delete`). Every provider switch and settings change is audited too.

**Test** in LLM settings checks the key (by listing models) or the CLI sign-in. It sends no prompt and no customer data.

**ChatGPT login.** Install the Codex CLI on the Pi (official release binary `codex-aarch64-unknown-linux-musl` from github.com/openai/codex, or `npm i -g @openai/codex`) into `~/.local/bin/codex`. Then either run `codex login --device-auth`, or press **Sign in from browser**, which shows a link and a one-time code. The bridge removes `OPENAI_API_KEY` from the CLI's environment, so it always uses your ChatGPT plan. Set `Environment=CODEX_BIN=%h/.local/bin/codex` in the bridge's systemd unit, then restart it with `systemctl --user daemon-reload && systemctl --user restart claude-bridge`.

### Data-sending gates

For an external provider, every gate must allow it:

1. `LLM_ALLOW_EXTERNAL=true` (global kill switch, default `false`). This is the hard cap: when it is `false`, nothing in the UI can turn external use on.
2. The **External LLM** switch in the header is on. It is stored in `data/settings.json` (default on), applies to everyone, takes effect immediately without a restart, and every change is audited (`settings.external_llm`). API: `PUT /api/settings/external-llm {"enabled": true|false}`.
3. The customer doesn't set `allow_external_llm: false`. You can tick or untick **Allow external LLM for this customer** in Customer config → Customer details (audited as `customer.external_llm`; API `PUT /api/customers/<id>/external-llm`).
4. The analyst picks **Rules + LLM** for this run.
5. The analyst ticks *"I confirm this data may leave this system"*.

The UI header shows whether an external LLM is available. Each investigation records `llm_used`, and every send is written to the audit log (provider, model and size; never content).

### What is sent

- The raw log, secret-scrubbed and truncated to `LLM_MAX_LOG_CHARS`.
- The analyst context, and any follow-up logs and notes added to the investigation (same redaction and size limit).
- That customer's `customer.md`, truncated to `LLM_MAX_CONTEXT_CHARS`.
- That customer's table list.
- The rules engine's classification and observables.

The LLM also returns a ticket draft (description, outcome, why, client actions). This draft is used in the ticket only where the analyst has not written their own text, and it is labelled there as an LLM draft.

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

See [adding-an-llm.md](adding-an-llm.md). For any OpenAI-style API there is no code to write: use the
**OpenAI-compatible API** entry, or add one `ProviderSpec` line to `app/llm/registry.py`.

## Using a Claude Pro subscription (no API key)

`LLM_PROVIDER=claude_pro` sends analysis requests to `bridge/claude_bridge.py` on the host. The bridge runs
`claude -p` under your Claude Code login (`claude auth login` with your Pro account; check it with
`claude auth status`, which should show `"authMethod": "claude.ai"`).

- The bridge removes `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the CLI's environment, so requests always use the subscription and never API billing.
- Usage counts against your Pro limits: about 1–2 minutes per analysis, one at a time.
- To change the model, set `CLAUDE_CLI_MODEL` (for example `sonnet` or `opus`). Leave it empty for your plan's default.
- Pro is a consumer plan, so data you send is governed by your claude.ai privacy settings. Check them before sending customer logs; use `allow_external_llm: false` for customers that must stay local.
- To manage the bridge: `systemctl --user status|restart claude-bridge`; logs: `journalctl --user -u claude-bridge -n 50`.
