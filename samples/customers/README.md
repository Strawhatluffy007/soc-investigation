# 🧪 `samples/customers/`

> Fictional sample customers

<sub>[🏠 Home](../../README.md) › [samples/](../README.md) › **customers/**</sub>

Fictional customers used by the tests and for demos. All names, domains and IP addresses are made up (IPs come from the documentation ranges 192.0.2.0/24, 198.51.100.0/24 and 203.0.113.0/24).

> [!TIP]
> To try them:
> ```bash
> cp -r samples/customers/*/ customers/
> ```

| Folder | What it shows |
|---|---|
| 🔷 `contoso/` | Sentinel + Defender XDR customer. External LLM allowed. Schema in `customer.md` plus `schemas/defender-xdr.md`; examples: failed sign-in, encoded PowerShell. |
| 🟥 `fabrikam/` | Defender XDR only. External LLM forbidden; `SigninLogs`, `AuditLogs` and `SecurityEvent` forbidden in KQL. Uses its own sign-in table names (`schemas/endpoint-email.md`); examples: phishing CSV, sign-in from a new country. |
| 🧭 `northwind/` | Northwind Traders: Sentinel only, no Defender XDR. External LLM allowed. `schemas/catalog-sentinel.md` shows the category-grouped, table-format file that **Schema selection → Apply** writes (Alerts & behaviors, Apps & identities, Network, Cloud infrastructure, Threat intelligence), and `customer.md` adds a custom `PaloAltoThreat_CL` table with role hints. Examples: new inbox forwarding rule (JSON), Palo Alto C2 threat log (CEF syslog). |
| ✈️ `tailspin/` | Tailspin Toys: Defender XDR Advanced Hunting only (`Timestamp` columns). External LLM forbidden by contract; `SecurityEvent`, `Syslog` and `SigninLogs` forbidden in KQL. `schemas/defender-xdr.md` uses list format grouped by Defender category. Examples: mass file rename on a file server (JSON array, ransomware suspicion), OAuth consent to an unverified app. |
| 📄 `_template/` | Blank customer, copied by **Add customer** in the UI. |

Each folder has `customer.md`, `schemas/`, `templates/incident-ticket.md` and `examples/`. See `docs/customers.md` for the format.
