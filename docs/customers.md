# Customers, schemas and KQL validation

Each customer is a folder under `customers/`:

```
customers/<id>/
  customer.md                 # profile, settings, tables, notes, KQL guidelines
  schemas/*.md                # optional extra table definitions
  templates/incident-ticket.md  # optional; falls back to templates/incident-ticket.md
  examples/                   # sample logs (not read by the app)
```

`<id>` is lowercase letters, digits and dashes. Folders starting with `_` (such as `_template`) are not listed as customers.

## Add a customer

**From the UI:** click **+ Customer**, enter a name, then edit `customer.md` in the config screen.

**On disk:**

```bash
cp -r customers/_template customers/northwind
sed -i 's/{{customer_name}}/Northwind Traders/' customers/northwind/customer.md
```

There's no need to restart. The app re-reads the files on every request.

## customer.md format

```markdown
# Customer: Northwind Traders

## Environment
- Microsoft Sentinel workspace: nw-prod

## Settings
- default_lookback: 7d          # lookback when the log has no timestamp, and for baseline queries
- event_window: 1d              # ± window around the event time
- allow_external_llm: false     # per-customer switch for external LLMs
- kql_require_time_filter: true
- kql_forbidden_tables: SigninLogs, AuditLogs

## Sentinel Tables               # any ## heading containing "Table" or "Schema"

### SigninLogs
Product: Microsoft Entra ID
Time field: TimeGenerated
- TimeGenerated
- UserPrincipalName (user)      # optional role hint
- IPAddress (ip)
- ResultType

## Investigation Notes           # bullets become customer-specific recommended steps
- VPN egress 203.0.113.0/24 is expected.

## KQL Guidelines                # passed to the LLM
## Ticket Requirements           # passed to the LLM
```

Fields can also be written as markdown table rows (`| FieldName | type |`).

## Modify or add a schema

- Edit the table blocks in `customer.md`, or add or edit `customers/<id>/schemas/<name>.md`. You can also use **Customer config** in the UI, which validates file names and shows parse warnings.
- A table defined in both places is merged.
- Only list fields you actually use. The validator treats undocumented columns as **warnings**, not errors.

### Field roles

Query generation finds columns by *role*: time, user, ip, device, process, command_line, hash, url, email_sender, email_recipient, email_subject, result, location, app, alert_id, object_id and others.

- Roles are inferred from common Microsoft column names, such as `AccountUpn` → user and `RemoteIP` → ip.
- If a customer uses unusual names, add a hint: `- SrcAddr (ip)`.
- Set the time column per table with `Time field:`.

## KQL validation

Every generated or pasted query is checked locally:

| Check | Result |
|---|---|
| Table not in this customer's schema | error |
| Table listed in `kql_forbidden_tables` | error |
| Unbalanced brackets, unterminated string, unknown operator after `\|`, empty pipe | error |
| Column not documented for the referenced tables | warning |
| No time filter on the table's time field | warning |
| `search *` / `union *` | warning |

Every result carries the note *"Schema validation: Local schema validation only. Query execution has not been performed."* The app never runs queries.

## Editing in the web interface

Select the customer, then click **Customer config**.

- **Customer details:** change the display name and click **Save name**. This rewrites the `# Customer: …` title in `customer.md`. The id and folder do not change, so existing investigations stay linked.
- **Files:** pick `customer.md`, the ticket template, any `schemas/*.md` or `examples/*` file, edit it, and click **Save file**.
  - **Add file** creates a new schema (`.md`) or example log (`.json .jsonl .csv .tsv .txt .log .xml .md`).
  - **Delete file** removes a schema or example. For the ticket template the button reads **Revert to default template**.
  - `customer.md` cannot be deleted.
  - You are warned before switching away from unsaved changes.

Renames, saves and deletes are recorded in the audit log.

## Schema catalog and per-customer table selection

`catalog/schema-catalog.md` is one Markdown file listing every schema, table and field:

```
## Schema: Microsoft Sentinel / Log Analytics
Id: sentinel
Origin: microsoft
### SigninLogs
Description: ...
Time field: TimeGenerated
| Column | Type | Description |
```

**Pull from Microsoft.** Open **Schema catalog** in the sidebar and click **Pull from Microsoft**. The app reads the
official table references on learn.microsoft.com (Azure Monitor security tables for Sentinel, and the Defender XDR
advanced hunting schema). It fetches only from `https://learn.microsoft.com`. A refresh rewrites only the
`Origin: microsoft` sections. If Microsoft Learn rate-limits the pull (HTTP 429), tables already fetched are kept;
try again later. You can also run it from the CLI: `python -m app.catalog.fetch catalog/schema-catalog.md`.
Set `CATALOG_FETCH_ENABLED=false` to disable pulling.

**Custom schemas.** On the same page, add your own `## Schema:` sections (for example, custom `_CL` tables).
Custom sections survive refreshes.

**Selecting tables for a customer.** Go to **Customer config**, open the **Schema selection** tab, choose
*Only selected tables*, tick the schemas and tables, then click **Apply**. This writes one
`customers/<id>/schemas/catalog-<schema>.md` per schema and sets `- schema_scope: selected` in `customer.md`.

When the scope is `selected`, mapping, KQL generation and validation, and the LLM prompt use only the selected tables.
Tables from the customer's other schema files are ignored (their field role hints still merge into a selected table
with the same name). With scope `all` (the default for existing customers), every table in the customer's schema
files is used.

**Categories.** Every table belongs to a category, so you can tick a whole group at once. The names follow the
Microsoft Defender portal's advanced hunting Schema tab: Alerts & behaviors, Apps & identities, Email & collaboration,
Devices, Threat & vulnerability management, Exposure management. Sentinel-only data adds Network,
Cloud infrastructure, Data security & compliance, Threat intelligence, Business applications and Microsoft Sentinel.
Microsoft Learn doesn't publish a per-table grouping for Sentinel, so the mapping lives in
`app/catalog/categories.py`. To override it for one table, add a `Category: <name>` line under that table in the
catalog; custom tables without one go to "Other". The customer files written by Apply group tables under
`## <category>` headings.
