# Follow-ups

You can keep adding to an investigation after the first analysis. Open its **Follow-up** tab.

## Two kinds of input

| Kind | Use it for | What happens |
|---|---|---|
| **More logs (Defender / raw)** | Defender alert or evidence JSON, advanced hunting results, raw logs. Paste them or upload a file. | Each log is parsed on its own, so mixed formats are fine. Its observables are merged with the original's and tagged with their source (`follow-up F1`, …). The Raw log tab, the ticket evidence and `{{analyst_notes}}` all include it. |
| **Question / general input** | "User confirmed travel", "Is this a true positive?", "Create a ticket for this incident" | Stored as an analyst note. If you re-analyse with an LLM, it answers the latest note. If the note asks for a ticket (for example "create / generate / raise … ticket"), a ticket is generated. |

Options for each follow-up:

- **Re-analyse:** runs the analysis again over the original log, all follow-up logs and all notes.
- **Use LLM:** uses the same per-customer gates and external-LLM confirmation as the first analysis.
- **Generate ticket:** generates a ticket from the customer's template.

Adding a follow-up reopens a Resolved or Closed investigation as **Investigating**.

## Output

Each follow-up is listed under the timeline, with its output:

- which engine ran, and any error
- the LLM's answer to your input (also shown on the Summary tab)
- the updated summary
- event types, observables and KQL queries that are **new** since that follow-up
- whether a ticket was generated, which fields still need analyst input, and which were drafted by the LLM

## Limits and security

- At most 100 follow-ups per investigation. A note can be up to 20,000 characters.
- The original log plus all follow-up logs must stay under `SOC_MAX_LOG_CHARS`. Uploads are limited to `SOC_MAX_UPLOAD_BYTES`, binary files are rejected, and control characters are stripped.
- Follow-up logs are sent to an LLM the same way as the original log: secret-scrubbed, in their own `<untrusted_log>` blocks, sharing the `LLM_MAX_LOG_CHARS` budget. Notes come from the analyst and go into `<analyst_context>`.
- The audit log (`investigation.followup`) records only the kind and size of the input, never its text.
- Follow-ups belong to their customer's investigation. A request through another customer's path returns 404.

## API

`POST /api/customers/{cid}/investigations/{id}/followups` (multipart form)

| Field | Meaning |
|---|---|
| `kind` | `log` or `note` |
| `text` / `file` | the content: pasted text, an uploaded file, or both. An uploaded file makes it a `log`, labelled with the file name. |
| `reanalyze` | default `true` |
| `use_llm`, `confirm_external`, `llm_provider` | as for `/analyze` |
| `generate_ticket` | `true` to always generate a ticket |

The response is `{inv, ticket}`. `ticket` is `null` unless a ticket was generated.
