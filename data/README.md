# 💾 `data/`

> Runtime data (git-ignored)

<sub>[🏠 Home](../README.md) › **data/**</sub>

Runtime data written by the app and mounted into the container.

> [!WARNING]
> **Git ignores this folder.** Only this README and `.gitkeep` are tracked. Investigations contain customer logs, so never force-add them.

| Path | Purpose |
|---|---|
| `investigations/<customer>/INV-*.json` | One file per investigation. |
| `counter.json` | Next investigation number. |
| `audit.log` | JSONL audit log of investigation actions (metadata only). |
