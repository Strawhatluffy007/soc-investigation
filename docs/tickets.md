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
| `{{when_uk}}` | Event time in British time (GMT/BST) with UTC, e.g. `28/09/2026 08:42:19 BST (07:42:19 UTC)` |
| `{{who}}` | User accounts / email addresses from the log and follow-up logs |
| `{{where}}` | Device, application, file path, file, source IP, location (bullets) |
| `{{why}}` | **Why / risk** from Findings & notes; otherwise the event types and hypotheses to rule out |
| `{{soc_actions}}` | **Action taken by SOC** from Findings & notes, plus what the record shows (logs reviewed, observables, KQL prepared; never "ran") |
| `{{client_actions}}` | **Action for client** from Findings & notes, otherwise *[Analyst input required]* |
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

## SOC standard template

`templates/soc-standard-ticket.md` follows the SOC ticket format: Subject, Description (with outcome), When (UK time),
Who, Where, Why, Additional Details, Action Taken by SOC, Action to take by Client. New customers get it from
`customers/_template`. For an existing customer, open **Ticket template** → **Load starter** → **SOC standard**,
check the preview and click **Save template**. Fill **Findings / outcome**, **Why / risk**, **Action taken by SOC** and
**Action for client** on the Findings & notes tab before generating the ticket.

Where each section comes from:

| Section | Source |
|---|---|
| When, Who, Where, observables, evidence | Extracted from the raw log and follow-up logs, never from the LLM |
| Description | LLM draft, else the rules engine's event summary |
| Outcome (`findings`), Why (`why`), Action for client (`client_actions`) | Your text on the Findings & notes tab; else the LLM draft; else a rules fallback for Why, or "[Analyst input required]" |
| Action taken by SOC | Your text, then the facts the record shows (logs reviewed, observables extracted, KQL *prepared*) |
| Severity | Always yours |

LLM drafts are produced only when the investigation was analysed with an LLM. Each one is followed by
"_(LLM draft, review before sending)_", and the Ticket tab lists the drafted fields. The Findings & notes tab shows each
draft under its box; **Copy into box to edit** turns a draft into your own text.
