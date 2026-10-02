# Changelog

This file records the notable changes to the SOC Investigation Interface. Newest entries come first, and dates are in YYYY-MM-DD format.

## [Unreleased]

## 2026-10-03: Follow-ups, ticket template editor, SOC standard ticket, LLM ticket drafts

### Added
- **Follow-ups.** You can keep adding to an investigation after the first analysis, either with more logs (Defender alert or evidence, hunting results, raw logs) or with a question or general input.
  - Each log is parsed separately, and its observables are merged with the rest and tagged with their source.
  - You can re-analyse with everything gathered so far.
  - With an LLM, the latest question gets an answer.
  - A note that asks for a ticket generates one.
  - The output of each follow-up appears under the timeline.
  - See [docs/followups.md](docs/followups.md).
- **Ticket template editor**, opened from **Ticket template** in the sidebar or **Edit template** on the Ticket tab:
  - a list of placeholders that you click to insert
  - a live preview against any of the customer's investigations
  - a check for unknown placeholders
  - a **Load starter** menu with the built-in templates
- **SOC standard ticket template** (`templates/soc-standard-ticket.md`), with the sections Subject, Description and outcome, When (UK time), Who, Where, Why, Additional Details, Action taken by SOC and Action to take by client. New customers get it by default.
- **New placeholders:** `when_uk`, `who`, `where`, `why`, `soc_actions` and `client_actions`.
- **New fields on the Findings & notes tab:** Why / risk, Action taken by SOC and Action for client.
- **LLM ticket drafts.** An LLM analysis now also drafts the description, outcome, why and client actions.
  - The ticket uses a draft only where the analyst hasn't written their own text, and labels it as an LLM draft.
  - When, Who and Where always come from the logs.
- **Light/dark theme** with a toggle. It follows the system setting by default.
- **New docs and API routes:**
  - the document `docs/followups.md`
  - the API routes `/ticket-placeholders`, `/ticket-templates` and `/customers/{cid}/ticket-template/preview`

### Fixed
- The LLM provider picker no longer shows a stray "nullnull".

## 2026-10-03: Sample customer Woodgrove Bank
### Added
- Fictional sample customer Woodgrove Bank under `customers/`. It includes settings, investigation notes, 18 Defender XDR and Sentinel tables, a ticket template and three example logs.

## 2026-10-03: Multiple LLM providers
### Added
- **LLM providers:**
  - Claude Pro and ChatGPT, signed in through a bridge on the host
  - Anthropic, OpenAI and Gemini
  - any OpenAI-compatible API
  - Ollama
- **Provider settings:**
  - an **LLM settings** page
  - choosing the provider for each investigation and each re-analysis
  - API keys stored with mode 0600; a key set in the environment takes priority
- **External-LLM controls:** a switch to turn external LLMs on or off while the app runs, and a per-customer allowance.
- **Docs and samples:**
  - `docs/adding-an-llm.md`
  - the sample customers Northwind (Sentinel) and Tailspin (Defender XDR)

## 2026-10-03: Initial release
### Added
- A local, containerised SOC triage app built with FastAPI and a vanilla JS single-page app.
- **Per customer:** schemas, templates and investigation notes.
- **Analysis:** log parsing and classification, observable extraction, and KQL generated and validated for each customer.
- **Workflow:** investigations with status and history, and tickets generated from each customer's template.
- **Optional LLM:** Claude Pro through the Claude Code CLI bridge, the Claude API, or Ollama.
- **Schema catalog:** pulled from Microsoft Learn, with Defender-style categories and per-customer table selection.
- **Security:**
  - local by default
  - basic auth when the app is exposed beyond localhost
  - secrets redacted from tickets and prompts
  - an audit log
  - customer data kept out of git
