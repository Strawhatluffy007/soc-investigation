"""Deterministic ticket rendering from a customer template.

`{{placeholder}}` values come only from the investigation record: the
analysis, the analyst's findings and notes. Nothing is generated. Empty
values become "Unknown / Not observed"; placeholders the app doesn't know
become "[Analyst input required: name]". The finished ticket is passed
through scrub_secrets so credentials found in logs never reach a ticket.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.customers.store import CustomerProfile
from app.security import scrub_secrets
from app.storage.investigations import combined_log

UNKNOWN = "Unknown / Not observed"
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
EVIDENCE_CHARS = 3000


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else ""


def _observables(analysis: dict) -> str:
    rows = [o for o in analysis.get("observables", []) if o["type"] not in ("command_line",)]
    if not rows:
        return ""
    lines = ["| Type | Value | Notes |", "|---|---|---|"]
    for o in rows[:60]:
        val = o["value"].replace("|", "\\|")[:200]
        lines.append(f"| {o['label']} | `{val}` | {', '.join(o['tags'])} |")
    cmd = [o["value"] for o in analysis.get("observables", []) if o["type"] == "command_line"]
    if cmd:
        lines += ["", "Command lines:"] + [f"```\n{c[:1000]}\n```" for c in cmd[:5]]
    return "\n".join(lines)


def _kql(analysis: dict) -> str:
    out = []
    for q in analysis.get("kql_queries", []):
        v = q.get("validation", {})
        out.append(f"**{q['id']}: {q['title']}** ({'LLM-suggested' if q.get('source') == 'llm' else 'rule-based'}; "
                   f"local validation: {v.get('status', 'n/a')}; not executed by this tool)\n"
                   f"```kql\n{q['query']}\n```")
    return "\n\n".join(out)


def _investigation(analysis: dict) -> str:
    parts = []
    if analysis.get("inferred"):
        parts.append("Assessment (inferred, requires analyst confirmation):\n" + _bullets(analysis["inferred"]))
    tables = [m["table"] for m in analysis.get("mapping", {}).get("tables", [])]
    if tables:
        parts.append("Data sources reviewed/recommended: " + ", ".join(tables))
    return "\n\n".join(parts)


def _followup_notes(inv: dict) -> str:
    notes = [f for f in inv.get("followups") or [] if f.get("kind") == "note"]
    return ("Follow-up input:\n" + "\n".join(f"- {f['at'][:16].replace('T', ' ')} {f['by']}: "
                                               + " ".join(f["text"].split())[:500] for f in notes)) if notes else ""


UK = ZoneInfo("Europe/London")


def _when_uk(iso: str | None) -> str:
    """Event time in British time, e.g. '28/09/2026 08:42:19 BST (07:42:19 UTC)'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    uk = dt.astimezone(UK)
    return f"{uk:%d/%m/%Y %H:%M:%S} {uk.tzname()} ({dt.astimezone(timezone.utc):%H:%M:%S} UTC)"


def _obs(a: dict, *types: str) -> list[str]:
    return [o["value"] for o in a.get("observables", []) if o["type"] in types]


def _uniq(values: list[str], limit: int = 6) -> list[str]:
    seen, out = set(), []
    for v in values:
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out[:limit]


def _who(a: dict) -> str:
    facts = a.get("facts", {})
    return ", ".join(_uniq(facts.get("User", []) + _obs(a, "user", "email") + facts.get("Sender", [])))


def _where(a: dict) -> str:
    facts = a.get("facts", {})
    rows = [("Device", facts.get("Device", []) + _obs(a, "hostname")),
            ("Application", facts.get("Application", [])),
            ("File path", _obs(a, "file_path")),
            ("File", facts.get("Process", []) + _obs(a, "file")),
            ("Source IP", facts.get("Source IP", [])),
            ("Location", facts.get("Location", []))]
    return "\n".join(f"- {label}: {', '.join(_uniq(v, 4))}" for label, v in rows if v)


LLM_TAG = "_(LLM draft, review before sending)_"


def _draft(a: dict) -> dict:
    return a.get("ticket_draft") or {} if a.get("engine", {}).get("mode") == "rules+llm" else {}


def _why(inv: dict, a: dict) -> str:
    if inv.get("risk", "").strip():
        return inv["risk"].strip()
    ets = a.get("event_types") or []
    if not ets:
        return ""
    lines = [f"Raised for {', '.join(e['label'] for e in ets[:3])}"
             + (f" ({inv['severity']} severity)" if inv.get("severity") else "") + "."]
    hyps = [h["title"] for h in a.get("hypotheses", [])[:4]]
    if hyps:
        lines.append("Risk / possibilities to rule out:")
        lines += [f"- {t}" for t in hyps]
    return "\n".join(lines)


def _soc_actions(inv: dict, a: dict) -> str:
    """Analyst-written actions first, then what the record shows was done.
    Queries are only listed as prepared: this app never runs them."""
    out = [inv["soc_actions"].strip()] if inv.get("soc_actions", "").strip() else []
    if a:
        logs = 1 + len([f for f in inv.get("followups") or [] if f.get("kind") == "log"])
        done = [f"Investigated the alert and reviewed {logs} log source{'s' if logs > 1 else ''}."]
        if a.get("observables"):
            done.append(f"Extracted {len(a['observables'])} observables (IPs, accounts, devices, files) for scoping.")
        if a.get("kql_queries"):
            done.append(f"Prepared {len(a['kql_queries'])} KQL hunting queries against the customer's tables.")
        out.append("\n".join("- " + d for d in done))
    return "\n\n".join(out)


def _prefer(values: dict, drafted: set, name: str, analyst_text: str, llm_text: str) -> None:
    """Analyst text wins; otherwise the LLM draft (labelled); otherwise keep the rules-based value."""
    if analyst_text.strip():
        values[name] = analyst_text.strip()
    elif llm_text.strip():
        values[name] = f"{llm_text.strip()}\n{LLM_TAG}"
        drafted.add(name)


def build_values(inv: dict, profile: CustomerProfile, analyst: str) -> dict[str, str]:
    return _build(inv, profile, analyst)[0]


def _build(inv: dict, profile: CustomerProfile, analyst: str) -> tuple[dict[str, str], set[str]]:
    """Facts (when/who/where/observables/evidence) come from the logs; narrative
    fields (description, outcome, why, client actions) from the analyst, else
    the LLM's draft, else rules."""
    a = inv.get("analysis") or {}
    ets = a.get("event_types") or []
    raw = combined_log(inv)
    excerpt = raw[:EVIDENCE_CHARS] + ("\n… (truncated)" if len(raw) > EVIDENCE_CHARS else "")
    sources = sorted({m.get("product") or m["table"] for m in a.get("mapping", {}).get("tables", [])})
    values = {
        "title": inv.get("title", ""),
        "severity": inv.get("severity", ""),
        "customer": profile.name,
        "customer_id": profile.id,
        "source": ", ".join(sources) or (ets[0]["product"] if ets else ""),
        "timestamp": a.get("event_time") or "",
        "description": a.get("summary", ""),
        "evidence": f"```\n{excerpt}\n```" if raw.strip() else "",
        "observed": _bullets(a.get("observed", [])),
        "observables": _observables(a),
        "investigation": _investigation(a),
        "kql": _kql(a),
        "findings": inv.get("findings", ""),
        "recommendations": _bullets(a.get("recommended_steps", [])),
        "analyst_notes": "\n\n".join(x for x in (inv.get("analyst_notes", ""), _followup_notes(inv)) if x),
        "investigation_id": inv.get("id", ""),
        "analyst": analyst or inv.get("assigned_to", ""),
        "status": inv.get("status", ""),
        "event_type": ets[0]["label"] if ets else "",
        "created": inv.get("created", ""),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "hypotheses": "\n".join(f"- {h['title']}" for h in a.get("hypotheses", [])),
        "unknowns": _bullets(a.get("unknown", [])),
        "when_uk": _when_uk(a.get("event_time")),
        "who": _who(a),
        "where": _where(a),
        "why": _why(inv, a),
        "soc_actions": _soc_actions(inv, a),
        "client_actions": inv.get("client_actions", ""),
    }
    d, drafted = _draft(a), set()
    _prefer(values, drafted, "description", "", d.get("description", ""))
    _prefer(values, drafted, "findings", inv.get("findings", ""), d.get("outcome", ""))
    _prefer(values, drafted, "why", inv.get("risk", ""), d.get("why", ""))
    _prefer(values, drafted, "client_actions", inv.get("client_actions", ""),
            _bullets(d.get("client_actions") or []))
    return values, drafted


# Shown in the template editor. Keys must match build_values().
PLACEHOLDER_DOCS = {
    "title": "Investigation title",
    "severity": "Severity set by the analyst (required)",
    "status": "Investigation status",
    "customer": "Customer display name",
    "customer_id": "Customer id",
    "investigation_id": "Investigation id, e.g. INV-2026-000123",
    "analyst": "Analyst generating the ticket",
    "created": "When the investigation was created",
    "generated": "When the ticket was generated",
    "event_type": "Primary event type",
    "source": "Products / tables the event maps to",
    "timestamp": "Event time from the log",
    "description": "Short description (LLM draft, else event summary)",
    "evidence": "Log excerpt incl. follow-up logs (code block, secrets redacted)",
    "observed": "Observed facts (bullets)",
    "observables": "Observables table",
    "investigation": "Assessment, mapped tables and reasoning",
    "hypotheses": "Hypotheses (bullets)",
    "unknowns": "What is unknown (bullets)",
    "kql": "KQL queries with purpose",
    "recommendations": "Recommended steps (bullets)",
    "findings": "Findings / outcome (analyst's text, else LLM draft; required)",
    "analyst_notes": "Analyst notes and follow-up input",
    "when_uk": "Event time in British time (GMT/BST) with UTC",
    "who": "Actor: user accounts / email addresses involved",
    "where": "Device, application, file path, file, source IP, location",
    "why": "Why raised / risk (analyst's text, else LLM draft, else event type + hypotheses)",
    "soc_actions": "Action taken by SOC (analyst's text + what was done)",
    "client_actions": "Action for the client (analyst's text, else LLM recommendations; required)",
}

# Placeholders that must be supplied by a human rather than defaulting to "Unknown".
ANALYST_FIELDS = {"severity", "findings", "client_actions"}


def render_ticket(template: str, inv: dict, profile: CustomerProfile, analyst: str = "") -> tuple[str, list[str]]:
    """Returns (ticket_markdown, placeholders_needing_input)."""
    text, missing, _ = render_ticket_full(template, inv, profile, analyst)
    return text, missing


def render_ticket_full(template: str, inv: dict, profile: CustomerProfile,
                       analyst: str = "") -> tuple[str, list[str], list[str]]:
    """Returns (ticket_markdown, placeholders_needing_input, placeholders_filled_by_llm_draft)."""
    values, drafted = _build(inv, profile, analyst)
    missing: list[str] = []
    used: set[str] = set()

    def sub(m: re.Match) -> str:
        name = m.group(1).lower()
        used.add(name)
        if name not in values:
            missing.append(name)
            return f"[Analyst input required: {name}]"
        val = (values[name] or "").strip()
        if not val:
            if name in ANALYST_FIELDS:
                missing.append(name)
                return f"[Analyst input required: {name}]"
            return UNKNOWN
        return val

    text = PLACEHOLDER_RE.sub(sub, template)
    return scrub_secrets(text), sorted(set(missing)), sorted(drafted & used)


def template_placeholders(template: str) -> tuple[list[str], list[str]]:
    """(placeholders used, placeholders that don't exist)."""
    used = list(dict.fromkeys(m.group(1).lower() for m in PLACEHOLDER_RE.finditer(template)))
    return used, [u for u in used if u not in PLACEHOLDER_DOCS]
