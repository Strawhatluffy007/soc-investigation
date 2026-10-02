# ⚡ `app/`

> The FastAPI backend

<sub>[🏠 Home](../README.md) › **app/**</sub>

> [!NOTE]
> Everything runs locally. The only code here that calls out to the internet is the optional LLM providers (`llm/`) and the schema catalog pull (`catalog/fetch.py`, learn.microsoft.com only).

| Path | Purpose |
|---|---|
| `main.py` | Creates the FastAPI app: HTTP Basic auth (when `SOC_AUTH_PASSWORD` is set), security headers and CSP, static files, API router. Refuses to start on a non-local bind address without a password. |
| `config.py` | `Settings`, read once from environment variables (see the root README for the full list). |
| `security.py` | Input sanitising, secret scrubbing (used before tickets and LLM prompts), id/filename validation. |
| `audit.py` | Append-only JSONL audit trail of investigation actions (metadata only, never log content). |
| `api/` | REST API routes. |
| `catalog/` | Global schema catalog: pull from Microsoft Learn, categories, per-customer table selection. |
| `customers/` | Loads customer knowledge from `customers/<id>/`. |
| `investigation/` | Log parsing, event classification, table mapping, analysis pipeline. |
| `kql/` | Customer-specific KQL generation and local validation. |
| `llm/` | Optional LLM providers and the gates that control them. |
| `observables/` | IOC / entity extraction. |
| `storage/` | Investigation persistence. |
| `tickets/` | Ticket rendering from customer templates. |
