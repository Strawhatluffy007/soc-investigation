# customers/

The live customer folders used by the app (mounted into the container at `/app/customers`).

**Only `_template/` is in git.** Real customer folders are ignored by `.gitignore` so customer data never ends up in the repository. To try the app with sample data:

```bash
cp -r samples/customers/contoso samples/customers/fabrikam customers/
```

Each customer folder looks like this (see `docs/customers.md`):

| Path | Purpose |
|---|---|
| `customer.md` | Name, environment, settings (`allow_external_llm`, `schema_scope`, ...), investigation notes, tables and field roles. |
| `schemas/*.md` | Table definitions. `catalog-<schema>.md` files are written by **Schema selection → Apply**. |
| `templates/incident-ticket.md` | The customer's ticket template. |
| `examples/` | Example logs for testing. |
| `_template/` | Copied when you create a new customer in the UI. |
