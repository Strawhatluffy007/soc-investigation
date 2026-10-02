# 💾 `app/storage/`

> Investigation storage

<sub>[🏠 Home](../../README.md) › [app/](../README.md) › **storage/**</sub>

| File | Purpose |
|---|---|
| `investigations.py` | One JSON file per investigation under `data/investigations/<customer>/`, ids like `INV-2026-000123`. Every lookup needs the customer id, so customers stay separated. Also follow-ups (extra logs and notes, with their output) and helpers that combine them with the original log. |
