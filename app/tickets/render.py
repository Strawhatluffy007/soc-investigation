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

from app.customers.store import CustomerProfile
from app.security import scrub_secrets

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


def build_values(inv: dict, profile: CustomerProfile, analyst: str) -> dict[str, str]:
    a = inv.get("analysis") or {}
    ets = a.get("event_types") or []
    raw = inv.get("raw_log", "")
    excerpt = raw[:EVIDENCE_CHARS] + ("\n… (truncated)" if len(raw) > EVIDENCE_CHARS else "")
    sources = sorted({m.get("product") or m["table"] for m in a.get("mapping", {}).get("tables", [])})
    return {
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
        "analyst_notes": inv.get("analyst_notes", ""),
        "investigation_id": inv.get("id", ""),
        "analyst": analyst or inv.get("assigned_to", ""),
        "status": inv.get("status", ""),
        "event_type": ets[0]["label"] if ets else "",
        "created": inv.get("created", ""),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "hypotheses": "\n".join(f"- {h['title']}" for h in a.get("hypotheses", [])),
        "unknowns": _bullets(a.get("unknown", [])),
    }


# Placeholders that must be supplied by a human rather than defaulting to "Unknown".
ANALYST_FIELDS = {"severity", "findings"}


def render_ticket(template: str, inv: dict, profile: CustomerProfile, analyst: str = "") -> tuple[str, list[str]]:
    """Returns (ticket_markdown, placeholders_needing_input)."""
    values = build_values(inv, profile, analyst)
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        name = m.group(1).lower()
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
    return scrub_secrets(text), sorted(set(missing))
