# samples/customers/

Fictional customers used by the tests and for demos.

| Folder | What it shows |
|---|---|
| `contoso/` | Sentinel + Defender XDR customer. External LLM allowed. Schema in `customer.md` plus `schemas/defender-xdr.md`; examples: failed sign-in, encoded PowerShell. |
| `fabrikam/` | Defender XDR only. External LLM forbidden; `SigninLogs`, `AuditLogs` and `SecurityEvent` forbidden in KQL. Uses its own sign-in table names (`schemas/endpoint-email.md`); examples: phishing CSV, sign-in from a new country. |
| `_template/` | Blank customer copied by **+ Customer** in the UI. |

Each folder has `customer.md`, `schemas/`, `templates/incident-ticket.md` and `examples/`. See `docs/customers.md` for the format.
