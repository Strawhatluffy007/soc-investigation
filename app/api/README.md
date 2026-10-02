# app/api/

| File | Purpose |
|---|---|
| `routes.py` | All HTTP endpoints under `/api`. Investigation routes are nested under their customer (`/customers/{cid}/investigations/{id}`) and the store checks the pair, so one customer's investigation can't be reached through another. Also: customer rename and file management, the schema catalog (`/catalog`, `/catalog/refresh`, `/catalog/custom`) and per-customer table selection (`/customers/{cid}/catalog-selection`). State-changing actions are written to the audit log. |
