<div align="center">

# 📝 Changelog

**All notable changes to the SOC Investigation Interface.**<br>
Newest first · dates are `YYYY-MM-DD` · format inspired by [Keep a Changelog](https://keepachangelog.com/)

![Releases](https://img.shields.io/badge/updates-4-blue)
![Latest](https://img.shields.io/badge/latest-2026--10--03-2ea44f)

[🏠 Back to README](README.md)

</div>

| Legend | |
|---|---|
| ✨ **Added** | New features |
| 🔧 **Changed** | Changes to existing behaviour |
| 🐛 **Fixed** | Bug fixes |
| 🔒 **Security** | Security-related changes |
| 📚 **Docs** | Documentation |

---

## 🚧 [Unreleased]

### ✨ Added

- 🪟 **Windows support:** `docker-compose.windows.yml` (Docker Desktop override) and [docs/windows.md](docs/windows.md), which covers Docker Desktop and a local Ollama model on an NVIDIA GPU.
- 🦙 **Ollama settings:** `OLLAMA_NUM_CTX` sets the context window. Ollama's small default silently cut long prompts. `OLLAMA_THINK` (default off) controls the reasoning mode of models such as qwen3, and leftover `<think>` blocks are stripped.
- `.gitattributes` keeps LF line endings on Windows checkouts.
- `tzdata` is installed on Windows, for UK time in tickets.

### 🔧 Changed

- The customer schema in the LLM prompt is limited to a third of `LLM_MAX_CONTEXT_CHARS`, so it shrinks along with the other limits for small local models.

### 📚 Docs

- 🎨 Restyled the README with a logo, badges, Mermaid workflow and architecture diagrams, collapsible sections and callouts.
- 🧭 Every folder README now has a consistent header and a breadcrumb back to the project root.
- 🐛 Corrected outdated READMEs: `samples/` now lists four sample customers, the bridge README covers ChatGPT, and `docs/` lists every doc.

---

## 🎫 2026-10-03: Follow-ups, ticket editor and LLM ticket drafts

> [!NOTE]
> This update covers continuing an investigation after the first analysis, and producing tickets in your own SOC format.

### ✨ Added

- ➕ **Follow-ups.** You can keep adding to an investigation after the first analysis:
  - **More logs** (Defender alert or evidence, hunting results, raw logs). Each log is parsed separately, and its observables are merged and tagged with their source (`follow-up F1`, …).
  - **Questions / general input.** With an LLM, the latest question gets an answer. A note that asks for a ticket generates one.
  - You can re-analyse with everything gathered so far.
  - The **output of each follow-up appears under the timeline**: the answer, plus new event types, observables and KQL.
- 🛠️ **Ticket template editor:**
  - placeholder chips that you click to insert
  - a live preview against any of the customer's investigations
  - a check for unknown placeholders
  - **Load starter**, **Revert to default**
- 🎫 **SOC standard ticket template**, with the sections Subject · Description & outcome · When (UK time) · Who · Where · Why · Additional details · Action taken by SOC · Action to take by client. New customers get it by default.
- 🏷️ **New placeholders:** `when_uk`, `who`, `where`, `why`, `soc_actions` and `client_actions`.
- 📝 **New fields on the Findings & notes tab:** Why / risk, Action taken by SOC and Action for client.
- 🤖 **LLM ticket drafts.** The LLM drafts the description, outcome, why and client actions. The ticket uses a draft only where you haven't written your own text, and labels it *"LLM draft, review before sending"*. When, Who and Where always come from the logs.
- 🌗 **Light / dark theme.** It follows the system setting, and <kbd>T</kbd> toggles it.
- 🔌 **New API routes:** `/followups`, `/ticket-placeholders`, `/ticket-templates` and `/ticket-template/preview`.

### 🔒 Security

- 📜 The audit log records only the kind and size of follow-up input, never its text.
- 🧱 Follow-ups and template previews are scoped to their customer, so a request through another customer's path returns 404.

### 🐛 Fixed

- The LLM provider picker no longer shows a stray "nullnull".

### 📚 Docs

- New [docs/followups.md](docs/followups.md).
- [docs/tickets.md](docs/tickets.md) now has a table showing where each ticket section comes from (log, LLM or analyst).
- Updated [docs/llm.md](docs/llm.md), the folder READMEs and this changelog.

---

## 🏦 2026-10-03: Sample customer Woodgrove Bank

### ✨ Added

- 🏦 A fictional customer, **Woodgrove Bank**, under `customers/woodgrove/`. It includes:
  - settings and investigation notes
  - **18 Defender XDR and Sentinel tables**
  - its own ticket template
  - three example logs: an impossible-travel sign-in, an Office macro launching PowerShell, and a phishing click

---

## 🤖 2026-10-03: Multiple LLM providers

### ✨ Added

- 🔌 **LLM providers:**
  - Claude Pro and ChatGPT, signed in through a bridge on the host
  - Anthropic, OpenAI and Gemini
  - any OpenAI-compatible API
  - Ollama
- ⚙️ **LLM settings page.** You can choose or switch the provider for each investigation and each re-analysis.
- 🚦 **External-LLM controls:** a switch to turn external LLMs on or off while the app runs, and a per-customer allowance. When a run is blocked, a message says why.
- 🏢 **Sample customers** Northwind (Sentinel) and Tailspin (Defender XDR).

### 🔒 Security

- 🔑 API keys are stored with mode 0600, and a key set in the environment takes priority. Keys are never returned by the API or written to the audit log.

### 📚 Docs

- [docs/adding-an-llm.md](docs/adding-an-llm.md).

---

## 🎉 2026-10-03: Initial release

### ✨ Added

- 🛡️ A local, containerised SOC triage app built with **FastAPI** and a **vanilla JS** single-page app.
- 🏢 **Per customer:** schemas, KQL guidelines, investigation notes and ticket templates.
- 🔎 **Analysis:**
  - log parsing (JSON, CSV, key=value, syslog, text)
  - classification
  - observable extraction
- 🧭 **KQL:** generated for each customer and validated offline. Queries are never executed.
- 🗂️ **Workflow:** investigations with status and history, and tickets generated from templates.
- 🤖 **Optional LLM:** Claude Pro through the Claude Code CLI bridge, the Claude API, or Ollama.
- 📚 **Schema catalog:** pulled from Microsoft Learn, with Defender-style categories and per-customer table selection.

### 🔒 Security

- 🏠 Local by default.
- 🔐 Basic auth when the app is exposed beyond localhost.
- 🙈 Secrets redacted from tickets and prompts.
- 📜 An audit log.
- 🚫 Customer data kept out of git.

---

<div align="center">
<sub>🔝 <a href="#-changelog">Back to top</a></sub>
</div>
