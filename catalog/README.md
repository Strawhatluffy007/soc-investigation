# 📚 `catalog/`

> Schema catalog data

<sub>[🏠 Home](../README.md) › **catalog/**</sub>

| File | Purpose |
|---|---|
| `schema-catalog.md` | The single list of all schemas, tables and columns. Generated from Microsoft Learn (Sentinel / Log Analytics security tables and Defender XDR advanced hunting tables, about 305 tables) plus your custom schemas. Each table has `Category:`, `Time field:`, `Description:`, `Source:` and a column table. |

Refresh it from the web UI (**Schema catalog → Pull from Microsoft**) or with `python -m app.catalog.fetch catalog/schema-catalog.md`. Refreshes replace only `Origin: microsoft` sections; custom sections are kept. This folder is mounted into the container at `/app/catalog`.
