# Ticket templates

The template is chosen in this order: `customers/<id>/templates/incident-ticket.md`, then `templates/incident-ticket.md`.

You can edit it under **Customer config → Ticket template**. Saving the default template from a customer creates a customer-specific copy.

## Placeholders

| Placeholder | Filled from |
|---|---|
| `{{title}}` `{{status}}` `{{investigation_id}}` `{{created}}` | Investigation record |
| `{{severity}}` | Analyst-selected severity, otherwise *[Analyst input required]* |
| `{{customer}}` `{{customer_id}}` | Customer profile |
| `{{analyst}}` | Logged-in user / analyst name |
| `{{timestamp}}` | Event time parsed from the log |
| `{{source}}` | Product of the mapped tables |
| `{{event_type}}` | Top classification |
| `{{description}}` | Analysis summary |
| `{{observed}}` `{{unknowns}}` `{{hypotheses}}` | Analysis lists |
| `{{observables}}` | Observable table and command lines |
| `{{investigation}}` | Inferred assessment and data sources |
| `{{kql}}` | Queries, each marked as locally validated and not executed |
| `{{findings}}` | Analyst findings, otherwise *[Analyst input required]* |
| `{{recommendations}}` | Recommended steps |
| `{{analyst_notes}}` | Analyst notes |
| `{{evidence}}` | First 3,000 characters of the raw log |
| `{{generated}}` | Render time |

## Rules

- Nothing is generated. An empty value becomes **Unknown / Not observed**.
- An unrecognised placeholder (for example `{{alert_id}}`) becomes **[Analyst input required: alert_id]**. Its name is listed in the UI so the analyst fills it in.
- The whole ticket goes through secret redaction before it is shown or saved. That covers passwords, tokens, API keys, JWTs, private keys and SAS signatures.
- The ticket stays editable. **Save edits** stores your version. **Regenerate** replaces it, after a confirmation.
