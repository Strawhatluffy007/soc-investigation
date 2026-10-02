# data/

Runtime data written by the app (mounted into the container). **Ignored by git**; only this README and `.gitkeep` are tracked.

| Path | Purpose |
|---|---|
| `investigations/<customer>/INV-*.json` | One file per investigation. |
| `counter.json` | Next investigation number. |
| `audit.log` | JSONL audit log of investigation actions (metadata only). |
