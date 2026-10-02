# 🧭 `app/kql/`

> KQL generation & validation

<sub>[🏠 Home](../../README.md) › [app/](../README.md) › **kql/**</sub>

| File | Purpose |
|---|---|
| `generator.py` | Builds customer-specific KQL from role-based query builders, using that customer's own table and field names and a time window around the event. |
| `validator.py` | Local, offline KQL checks against the customer schema: unknown tables/columns, missing time filter, risky operators. Queries are never executed. |
