# SOC Investigation Interface

A local web app for triaging security events across many customers. You:

1. Pick a customer.
2. Paste or upload a log.
3. Get the event type, the matching tables in *that customer's* schema, extracted observables, customer-specific KQL validated against their schema, hypotheses and next steps.
4. Record findings.
5. Generate a ticket from the customer's template.

It works fully offline. An LLM (your Claude Pro subscription via the Claude Code CLI, the Claude API, or a local Ollama model) is optional, off by default, and gated per customer.

## Run

```bash
cp .env.example .env          # defaults: localhost only, no LLM
cp -r samples/customers/*/ customers/   # optional: 4 fictional sample customers
docker compose up -d --build
# open http://127.0.0.1:8090
docker compose logs --tail 50 soc
docker compose down
```

To run without Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --port 8090
```

To run the tests: `.venv/bin/python -m pytest -q`

### Exposing beyond localhost

1. Set `SOC_BIND_ADDR=0.0.0.0` (or a LAN IP) **and** `SOC_AUTH_PASSWORD` in `.env`. Without the password the app refuses to start.
2. Put it behind TLS (a reverse proxy) if it leaves the host.

## Workflow

1. **Select a customer** in the header. The sidebar lists only that customer's investigations.
2. **New investigation:** paste a log (JSON, JSON lines, CSV, key=value, syslog or text) or upload a file (5 MB max, text only). Add optional context and choose the analysis mode. You get an ID like `INV-2026-000123`.
3. **Summary:** event types with evidence; Observed / Inferred / Unknown; recommended steps, including the customer's own investigation notes.
4. **KQL:** queries built from the customer's table and field names.
   - Each card shows the purpose, time range, why those fields were used, and the expected result.
   - A local validation badge shows on every card. Edit the query and re-validate, or use the scratchpad.
   - Queries are **never executed** by this app.
5. **Findings & notes:** record what your queries actually showed.
6. **Ticket:** fill the customer template, then edit, copy or download it.
7. **Status:** New → Investigating → Pending Information → Escalated → Resolved → Closed. Changes are recorded in History.

**Schema catalog:** in the sidebar, **Schema catalog** → **Pull from Microsoft** builds `catalog/schema-catalog.md` from the official Sentinel and Defender XDR table references. Then go to **Customer config** → **Schema selection**, tick the tables the customer has, and click **Apply**. That customer's analysis then uses only those tables. See [docs/customers.md](docs/customers.md).

## Architecture

```
static/            vanilla JS SPA (no build, no CDN, CSP 'self', textContent only)
app/main.py        FastAPI app: basic auth, security headers, static files
app/api/routes.py  REST API; all investigation routes are /customers/{cid}/investigations/{id}
app/customers/     customer.md + schemas/*.md parser → TableSchema (fields + roles)
app/investigation/ parser (JSON/CSV/KV/text) → classifier (playbooks) → table mapping → engine
app/observables/   IOC/entity extraction (defang-aware, key-aware, internal/external IP tags)
app/kql/           generator (role-based query builders) and local validator
app/llm/           providers (registry.py): Claude Pro / ChatGPT login via host bridge, Anthropic, OpenAI, Gemini, any OpenAI-compatible API, Ollama; gates and prompts
app/tickets/       {{placeholder}} renderer with Unknown handling and secret redaction
app/storage/       JSON file per investigation under data/investigations/<customer>/
app/audit.py       JSONL audit log (actions and metadata only, never log content)
app/catalog/       schema catalog: pull from Microsoft Learn, categories, per-customer table selection
bridge/            host-side HTTP bridge to the Claude Code CLI (+ systemd unit)
catalog/           schema-catalog.md (all schemas, tables and columns)
customers/         live customer data (git-ignored except _template/)
samples/customers/ fictional sample customers (Contoso, Fabrikam, Northwind, Tailspin), also used by the tests
.claude/           Claude Code agents and skills for developing this project
```

Every folder has its own README.md describing its files.

`./customers` and `./data` are bind-mounted. The container is read-only, non-root, runs with all capabilities dropped and `no-new-privileges`.

To teach the engine a new event type, add an entry to `app/investigation/playbooks.py` (signals, keys, preferred tables, hypotheses, unknowns, steps) and map it to query builders in `PLAN` in `app/kql/generator.py`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SOC_BIND_ADDR` | `127.0.0.1` | Host address the port is published on; non-local requires auth |
| `SOC_PORT` | `8090` | Host port |
| `SOC_AUTH_USER` / `SOC_AUTH_PASSWORD` | `analyst` / empty | HTTP Basic auth (enabled when a password is set) |
| `SOC_UID` / `SOC_GID` | `1000` | Container user; must be able to write `./data` and `./customers` |
| `SOC_MAX_UPLOAD_BYTES` | `5242880` | Upload size limit |
| `SOC_MAX_LOG_CHARS` | `2000000` | Pasted log size limit |
| `LLM_PROVIDER` | `none` | Default provider: `none` \| `claude_pro` \| `chatgpt` \| `anthropic` \| `openai` \| `gemini` \| `openai_compatible` \| `ollama`. Can be changed in **LLM settings** and per investigation |
| `LLM_ALLOW_EXTERNAL` | `false` | Global kill switch for external LLMs |
| `LLM_TIMEOUT_SECONDS` | `240` | Per-request LLM timeout |
| `LLM_MAX_LOG_CHARS` / `LLM_MAX_CONTEXT_CHARS` | `60000` / `120000` | Truncation before sending to an LLM |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` / `ANTHROPIC_EFFORT` | – / `claude-opus-5-5` / `medium` | Claude API |
| `CLAUDE_BRIDGE_URL` / `CLAUDE_BRIDGE_TOKEN` / `CLAUDE_CLI_MODEL` | `http://host.docker.internal:8765` / – / CLI default | Claude Code CLI bridge |
| `SOC_CATALOG_PATH` / `CATALOG_FETCH_ENABLED` | `catalog/schema-catalog.md` / `true` | Schema catalog file; allow pulling it from learn.microsoft.com |
| `OLLAMA_URL` / `OLLAMA_MODEL` / `OLLAMA_IS_LOCAL` | `http://host.docker.internal:11434` / `llama3.1:8b` / `true` | Ollama |

## Docs

- [docs/customers.md](docs/customers.md): adding customers, schema format, field roles, KQL validation
- [docs/tickets.md](docs/tickets.md): ticket templates and placeholders
- [docs/llm.md](docs/llm.md): LLM providers (login, API key, local), the external-LLM switches, and what data is sent
- [docs/adding-an-llm.md](docs/adding-an-llm.md): how to add another LLM provider

## Security notes

- **Local by default.** No LLM is used, and the app binds to `127.0.0.1`.
- **External LLM use** requires the global switch, a per-customer allowance, and per-run analyst confirmation. It is labelled in the UI and recorded per investigation and in the audit log.
- **Credentials** are kept out of tickets: secrets are redacted from tickets and from LLM prompts.
- **API keys** come from environment variables only.
- **Customer separation.** Data is split per customer on disk, and every API route is customer-scoped. Ids are validated against path traversal.
- **Uploads.** Size is limited, binary files are rejected, and control characters are stripped.
- **Audit log** is at `data/audit.log`, in JSONL.
- **No customer data in git.** `customers/*` (except `_template/`), `data/`, `.env` and `.env.bridge` are git-ignored; the repository holds only fictional sample data.
