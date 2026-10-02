# tests/

Run with `.venv/bin/python -m pytest -q`. Tests copy `samples/customers/` into a temp folder, so your real customer data is never touched.

| File | Covers |
|---|---|
| `conftest.py` | Fixtures: sample customer store, profiles, example logs. |
| `test_api.py` | End-to-end API flow, customer separation, LLM gating, rename and file management, follow-ups, template editor preview, SOC standard template, LLM ticket drafts. |
| `test_catalog.py` | Catalog parse/render round trip, categories, apply and scoping, URL allowlist, refresh with a fake fetcher. |
| `test_customers.py` | Customer loading, per-customer conventions, role hints, path-traversal rejection, creation from the template. |
| `test_kql.py` | Query generation with customer field names and validation. |
| `test_parsing_observables.py` | Log parsing, observable extraction, classification and table mapping. |
| `test_tickets_storage.py` | Investigation ids and storage, status validation, ticket rendering, secret redaction. |
