# 🎫 `app/tickets/`

> Ticket rendering

<sub>[🏠 Home](../../README.md) › [app/](../README.md) › **tickets/**</sub>

| File | Purpose |
|---|---|
| `render.py` | Fills a customer's ticket template (`{{placeholder}}` syntax, see `docs/tickets.md`). Facts (When in UK time, Who, Where, observables, evidence) come from the logs; narrative fields (description, outcome, why, client actions) from the analyst, else the LLM's labelled draft, else rules. Missing values become "Unknown" or "[Analyst input required]"; secrets are redacted. Also lists the placeholders (`PLACEHOLDER_DOCS`) for the template editor. |
