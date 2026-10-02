# 🧠 `app/investigation/`

> Analysis pipeline

<sub>[🏠 Home](../../README.md) › [app/](../README.md) › **investigation/**</sub>

| File | Purpose |
|---|---|
| `parser.py` | Turns a raw log (JSON, JSON lines, CSV/TSV, key=value, syslog, free text) into structured fields. |
| `playbooks.py` | Event types the local engine recognises: signals, preferred tables, hypotheses, unknowns and recommended steps. Add a new event type here. |
| `classifier.py` | Scores a parsed log against every playbook and maps it to the customer's tables. |
| `engine.py` | The analysis pipeline: parse → classify → map tables → observables → KQL → optional LLM → validate every query against the customer schema. Follow-up logs are parsed separately and their observables merged. The rules-based result is always kept, even if the LLM fails. |
