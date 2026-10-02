# bridge/

Lets the container use your **Claude Pro/Max subscription** through the Claude Code CLI on the host, without an API key. Only needed when `LLM_PROVIDER=claude_pro`. See `docs/llm.md`.

| File | Purpose |
|---|---|
| `claude_bridge.py` | Small HTTP server (stdlib only) on the host. Accepts analysis requests from the container (bearer token `CLAUDE_BRIDGE_TOKEN`), runs `claude -p` with a JSON schema, and returns the result. Strips API-key variables so the subscription login is used. Configured by `.env.bridge`. |
| `claude-bridge.service` | systemd **user** unit to run the bridge at login: copy it to `~/.config/systemd/user/`, adjust the paths, then `systemctl --user enable --now claude-bridge`. |
