# app/customers/

| File | Purpose |
|---|---|
| `schema.py` | Parses customer Markdown (`customer.md` sections and `schemas/*.md`) into `TableSchema` objects: tables, columns, field roles (user, ip, device, ...), time field and product hints. |
| `store.py` | `CustomerStore`: lists and loads customers from `customers/<id>/` (cached by file mtime), applies `schema_scope`, creates customers from `_template`, renames, and adds/edits/deletes their files. |
