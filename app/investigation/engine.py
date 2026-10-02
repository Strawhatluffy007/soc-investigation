"""Analysis pipeline: parse → classify → map tables → observables → KQL →
(optional LLM) → validate every query against the customer's schema.

The deterministic path always runs. An LLM, when used, adds to it; if the
LLM fails, the deterministic result is returned with the error noted.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.customers.schema import parse_bullets
from app.customers.store import CustomerProfile
from app.investigation.classifier import classify, map_tables
from app.investigation.parser import ParsedLog, parse_log
from app.investigation.playbooks import playbook
from app.kql.generator import generate_queries, parse_event_time
from app.kql.validator import validate_kql
from app.llm.base import LLMError, LLMProvider
from app.llm.prompts import ANALYSIS_SCHEMA, SYSTEM_PROMPT, build_prompt
from app.observables.extract import extract_observables

TIME_KEYS = ("TimeGenerated", "Timestamp", "CreatedDateTime", "createdDateTime", "EventTime", "eventTime",
             "TimeCreated", "@timestamp", "timestamp", "time", "date", "DateTime", "ReceivedTime", "StartTime")
_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")

FACT_KEYS = [
    ("User", ("UserPrincipalName", "AccountUpn", "AccountName", "TargetUserName", "UserName", "user", "Identity")),
    ("Source IP", ("IPAddress", "IpAddress", "SourceIP", "SrcIp", "ClientIP", "RemoteIP", "CallerIpAddress")),
    ("Device", ("DeviceName", "Computer", "HostName", "WorkstationName")),
    ("Application", ("AppDisplayName", "Application", "ClientAppUsed")),
    ("Result", ("ResultType", "ResultDescription", "Status", "Result", "ActionType", "DeliveryAction")),
    ("Location", ("Location", "Country", "City")),
    ("Process", ("FileName", "ProcessName", "NewProcessName")),
    ("Command line", ("ProcessCommandLine", "CommandLine")),
    ("Parent process", ("InitiatingProcessFileName", "ParentProcessName")),
    ("Alert", ("AlertName", "Title", "DisplayName")),
    ("Severity (from log)", ("Severity", "AlertSeverity")),
    ("Sender", ("SenderFromAddress", "SenderMailFromAddress", "Sender")),
    ("Recipient", ("RecipientEmailAddress", "Recipient")),
    ("Subject", ("Subject",)),
    ("Operation", ("OperationName", "Operation", "EventID", "EventName")),
]


def event_time(parsed: ParsedLog, text: str) -> tuple[datetime | None, str]:
    raw = parsed.get(*TIME_KEYS)
    dt = parse_event_time(raw)
    if not dt:
        m = _ISO_RE.search(text[:50_000])
        raw = m.group(0) if m else None
        dt = parse_event_time(raw)
    return dt, (raw or "")


def _facts(parsed: ParsedLog, into: dict[str, list[str]]) -> dict[str, list[str]]:
    """Labelled key fields (User, Device, Application…) used by ticket
    placeholders such as {{who}} and {{where}}."""
    for label, keys in FACT_KEYS:
        v = parsed.get(*keys)
        if v and len(v) < 400 and v not in into.setdefault(label, []):
            into[label].append(v)
    return {k: v for k, v in into.items() if v}


def _observed(parsed: ParsedLog, observables: list[dict], ts_raw: str) -> list[str]:
    out = [f"Log format: {parsed.format}" + (f", {parsed.records} records" if parsed.records > 1 else "")]
    if ts_raw:
        out.append(f"Event time: {ts_raw}")
    for label, keys in FACT_KEYS:
        v = parsed.get(*keys)
        if v and len(v) < 400:
            out.append(f"{label}: {v}")
    ext = [o["value"] for o in observables if o["type"] == "ip" and "external" in o["tags"]]
    if ext:
        out.append("External IPs present: " + ", ".join(ext[:10]))
    return out


def _inferred(event_types: list[dict], mapping: list[dict], observables: list[dict]) -> list[str]:
    out = []
    for et in event_types[:2]:
        out.append(f"Event type is likely '{et['label']}' ({et['confidence']} confidence) based on: "
                   + "; ".join(et["evidence"][:4]))
    if mapping:
        out.append("Best matching customer tables: " + ", ".join(
            f"{m['table']} ({'; '.join(m['reasons'][:2])})" for m in mapping))
    if any("internal" in o["tags"] for o in observables if o["type"] == "ip") and \
            any("external" in o["tags"] for o in observables if o["type"] == "ip"):
        out.append("The event involves both internal and external addresses (internal ↔ external communication).")
    return out


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for i in items:
        k = i.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(i.strip())
    return out


def analyze(profile: CustomerProfile, raw_log: str, context: str = "", provider: LLMProvider | None = None,
            llm_max_log_chars: int = 60_000, llm_max_context_chars: int = 120_000,
            extra_logs: list[dict] | None = None, notes: str = "") -> dict:
    """`extra_logs` are follow-up logs ({id, source_name, at, text}) added after
    the first analysis; `notes` is the analyst's follow-up input. Each extra
    log is parsed on its own (it may be a different format) and its
    observables are merged with the original's."""
    extra_logs = extra_logs or []
    parsed = parse_log(raw_log)
    all_text = "\n".join([raw_log] + [f["text"] for f in extra_logs])
    event_types = classify(all_text, parsed, "\n".join(x for x in (context, notes) if x))
    mapping = map_tables(profile, parsed, event_types)
    observables = extract_observables(raw_log, parsed.fields)
    seen = {(o["type"], o["value"].lower()) for o in observables}
    facts = _facts(parsed, {})
    for f in extra_logs:
        p = parse_log(f["text"])
        facts = _facts(p, facts)
        for o in extract_observables(f["text"], p.fields):
            if (o["type"], o["value"].lower()) not in seen:
                seen.add((o["type"], o["value"].lower()))
                observables.append(o | {"sources": [f"follow-up {f['id']}"] + o["sources"][:4]})
    ts, ts_raw = event_time(parsed, raw_log)

    tables = [m["table"] for m in mapping]
    queries = generate_queries(profile, tables, event_types, observables, ts)
    primary_pb = playbook(event_types[0]["type"] if event_types else "")

    unknown = list(primary_pb["unknowns"])
    if not ts:
        unknown.append("Event timestamp (none found in the log); queries use the customer default lookback")
    if not mapping:
        unknown.append(f"Which {profile.name} table holds this event (no confident schema match)")
    if not queries:
        unknown.append("No query could be generated: the mapped tables lack fields for the extracted entities")

    customer_steps = [f"[{profile.name}] {b}" for b in parse_bullets(profile.section("investigation"))]

    result = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "parsed": {"format": parsed.format, "records": parsed.records, "field_count": len(parsed.fields),
                   "followup_logs": len(extra_logs)},
        "event_time": ts.isoformat() if ts else None,
        "event_types": event_types,
        "summary": (primary_pb["label"] + ("" if primary_pb["label"].lower().endswith("event") else " event")
                    if event_types else "Unclassified event")
                   + (f" involving {len(observables)} observables" if observables else "")
                   + (f", mapped to {', '.join(tables)}." if tables else "; no matching customer table found."),
        "observed": _observed(parsed, observables, ts_raw),
        "inferred": _inferred(event_types, mapping, observables),
        "unknown": unknown,
        "hypotheses": [{"title": t, "rationale": r, "source": "rules"} for t, r in primary_pb["hypotheses"]],
        "kql_queries": queries,
        "recommended_steps": _dedupe(primary_pb["steps"] + customer_steps),
        "mapping": {"tables": mapping},
        "observables": observables,
        "facts": facts,
        "engine": {"mode": "rules", "provider": "none", "external": False, "model": "", "error": ""},
    }

    if provider is not None:
        result["engine"].update(provider.describe())
        try:
            prompt = build_prompt(profile, raw_log, context, result, llm_max_log_chars, llm_max_context_chars,
                                  extra_logs, notes)
            llm = provider.analyze(SYSTEM_PROMPT, prompt, ANALYSIS_SCHEMA)
            _merge_llm(result, llm)
            result["engine"]["mode"] = "rules+llm"
        except LLMError as e:
            result["engine"]["error"] = f"{e}. Showing local rules-based analysis only."
        except Exception as e:  # never lose the deterministic result
            result["engine"]["error"] = f"LLM analysis failed ({type(e).__name__}). Showing local analysis only."

    for q in result["kql_queries"]:
        q["validation"] = validate_kql(q["query"], profile)
    return result


def _strs(v) -> list[str]:
    return [str(x) for x in v if isinstance(x, (str, int, float)) and str(x).strip()] if isinstance(v, list) else []


def _merge_llm(result: dict, llm: dict) -> None:
    if not isinstance(llm, dict):
        raise LLMError("LLM output was not an object")
    if llm.get("event_summary"):
        result["summary"] = str(llm["event_summary"])
    if llm.get("event_type"):
        result["llm_event_type"] = str(llm["event_type"])[:200]
    result["observed"] = _dedupe(result["observed"] + _strs(llm.get("observed")))
    result["inferred"] = _dedupe(_strs(llm.get("inferred")) + result["inferred"])
    result["unknown"] = _dedupe(_strs(llm.get("unknown")) + result["unknown"])
    hyps = [{"title": str(h.get("title", "")), "rationale": str(h.get("rationale", "")), "source": "llm"}
            for h in llm.get("hypotheses") or [] if isinstance(h, dict) and h.get("title")]
    result["hypotheses"] = hyps + result["hypotheses"]
    n = len(result["kql_queries"])
    for i, q in enumerate([q for q in llm.get("kql_queries") or [] if isinstance(q, dict) and q.get("query")][:6]):
        result["kql_queries"].append({
            "id": f"Q{n + i + 1}", "title": str(q.get("title", "LLM query")), "purpose": str(q.get("purpose", "")),
            "table": str(q.get("table", "")), "query": str(q["query"]).strip(),
            "expected_result": str(q.get("expected_result", "")), "rationale": str(q.get("rationale", "")),
            "time_range": "as written in the query", "source": "llm",
        })
    result["recommended_steps"] = _dedupe(_strs(llm.get("recommended_steps")) + result["recommended_steps"])
    if str(llm.get("analyst_response") or "").strip():
        result["analyst_response"] = str(llm["analyst_response"]).strip()[:20_000]
    t = llm.get("ticket") if isinstance(llm.get("ticket"), dict) else {}
    draft = {k: str(t.get(k) or "").strip()[:4000] for k in ("description", "outcome", "why")}
    draft["client_actions"] = _strs(t.get("client_actions"))[:12]
    if any(draft.values()):
        result["ticket_draft"] = draft
