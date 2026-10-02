# 🌉 `bridge/`

> Host bridge to the Claude Code CLI

<sub>[🏠 Home](../README.md) › **bridge/**</sub>

Lets the container use your **Claude Pro/Max** (Claude Code CLI) or **ChatGPT Plus/Pro** (Codex CLI) subscription on the host, without an API key.

> [!NOTE]
> You only need the bridge for the `claude_pro` and `chatgpt` providers. See [docs/llm.md](../docs/llm.md).

| File | Purpose |
|---|---|
| `claude_bridge.py` | Small HTTP server (stdlib only) on the host. Accepts analysis requests from the container (bearer token `CLAUDE_BRIDGE_TOKEN`), runs `claude -p` with a JSON schema, and returns the result. Strips API-key variables so the subscription login is used. Configured by `.env.bridge`. |
| `claude-bridge.service` | systemd **user** unit to run the bridge at login: copy it to `~/.config/systemd/user/`, adjust the paths, then `systemctl --user enable --now claude-bridge`. |
