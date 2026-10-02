# 🗂️ `app/catalog/`

> Global schema catalog

<sub>[🏠 Home](../../README.md) › [app/](../README.md) › **catalog/**</sub>

The global schema catalog: one Markdown file (`catalog/schema-catalog.md`) listing every schema, table and column, pulled from Microsoft Learn plus your own custom tables. Each customer selects the tables they actually have.

| File | Purpose |
|---|---|
| `model.py` | Dataclasses (`Catalog`, `CatalogSchema`, `CatalogTable`, `Column`) and the Markdown parser/renderer. Round-trips losslessly. |
| `fetch.py` | Pulls Sentinel / Log Analytics security tables and Defender XDR advanced hunting tables from learn.microsoft.com (the only allowed host). Polite: few workers, delays, backs off on HTTP 429, keeps previously fetched tables on failure. CLI: `python -m app.catalog.fetch catalog/schema-catalog.md`. |
| `categories.py` | Puts each table in a category named after the Defender portal schema groups (Alerts & behaviors, Apps & identities, Email & collaboration, Devices, ...). A `Category:` line in the catalog overrides it. |
| `store.py` | `CatalogStore`: cached loading, custom schema editing, reading and applying a customer's selection (writes `customers/<id>/schemas/catalog-<schema>.md` and sets `schema_scope`). |
