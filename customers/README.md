# 🏢 `customers/`

> Live customer folders

<sub>[🏠 Home](../README.md) › **customers/**</sub>

The live customer folders used by the app (mounted into the container at `/app/customers`).

> [!WARNING]
> **Only `_template/` and the fictional sample `woodgrove/` are in git.** `.gitignore` excludes real customer folders, so customer data never ends up in the repository.

🏦 `woodgrove/` (Woodgrove Bank, fictional) is a complete example of a configured customer: environment and settings in `customer.md`, 18 Defender XDR + Sentinel tables chosen with **Schema selection** (`schemas/catalog-*.md`), a customer ticket template, and three example logs (impossible-travel sign-in, Office macro launching PowerShell, phishing click). Use it as a model for your own customers.

> [!TIP]
> More fictional samples (Contoso, Fabrikam, Northwind, Tailspin) are in `samples/customers/`. To load them too:

> ```bash
> cp -r samples/customers/*/ customers/
> ```

Each customer folder looks like this (see `docs/customers.md`):

| Path | Purpose |
|---|---|
| `customer.md` | Name, environment, settings (`allow_external_llm`, `schema_scope`, ...), investigation notes, tables and field roles. |
| `schemas/*.md` | Table definitions. `catalog-<schema>.md` files are written by **Schema selection → Apply**. |
| `templates/incident-ticket.md` | The customer's ticket template. |
| `examples/` | Example logs for testing. |
| `_template/` | Copied when you create a new customer in the UI. |
