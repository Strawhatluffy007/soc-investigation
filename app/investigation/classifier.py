"""Score a parsed log against every playbook and map it to customer tables."""
from __future__ import annotations

import re

from app.customers.store import CustomerProfile
from app.investigation.parser import ParsedLog
from app.investigation.playbooks import PLAYBOOKS


def classify(text: str, parsed: ParsedLog, context: str = "") -> list[dict]:
    """Ranked event types with the evidence that triggered them."""
    haystack = (text[:200_000] + "\n" + context).lower()
    keys_lower = {k.lower() for k in parsed.all_keys} | {k.rsplit(".", 1)[-1].lower() for k in parsed.fields}
    results = []
    for etype, pb in PLAYBOOKS.items():
        score, evidence = 0.0, []
        for sig in pb["signals"]:
            m = re.search(sig, haystack)
            if m:
                score += 1.0
                evidence.append(f"text matches '{m.group(0)}'")
        for key in pb.get("keys", []):
            if key.lower() in keys_lower:
                score += 1.5
                evidence.append(f"field {key} present")
        if score:
            results.append({"type": etype, "label": pb["label"], "product": pb["product"], "score": score,
                            "evidence": evidence[:8]})
    results.sort(key=lambda r: r["score"], reverse=True)
    if results:
        top = results[0]["score"]
        for r in results:
            r["confidence"] = "high" if r["score"] >= 5 and r["score"] == top else (
                "medium" if r["score"] >= 3 else "low")
    return results[:4]


def map_tables(profile: CustomerProfile, parsed: ParsedLog, event_types: list[dict], limit: int = 3) -> list[dict]:
    """Pick the customer tables that best fit the event.

    Two signals: the playbook's preferred tables (if the customer has them),
    and field-name overlap between the log and each table's schema (an
    exported SigninLogs row overlaps SigninLogs almost completely).
    """
    log_keys = {k.lower() for k in parsed.all_keys}
    scored: dict[str, dict] = {}

    for rank, et in enumerate(event_types[:2]):
        for pos, tname in enumerate(PLAYBOOKS[et["type"]]["tables"]):
            table = profile.tables.get(tname)
            if not table:
                continue
            entry = scored.setdefault(tname, {"table": tname, "score": 0.0, "reasons": []})
            entry["score"] += max(0.5, 3.0 - pos * 0.5) / (rank + 1)
            entry["reasons"].append(f"recommended for {et['label']}")

    if log_keys:
        for tname, table in profile.tables.items():
            overlap = [f for f in table.fields if f.lower() in log_keys]
            if len(overlap) >= 3:
                entry = scored.setdefault(tname, {"table": tname, "score": 0.0, "reasons": []})
                ratio = len(overlap) / max(1, len(table.fields))
                entry["score"] += 2.0 + 4.0 * ratio
                entry["reasons"].append(f"{len(overlap)} of {len(table.fields)} schema fields appear in the log")
    if "Type" in parsed.fields or "type" in parsed.fields:
        declared = parsed.fields.get("Type") or parsed.fields.get("type")
        if declared in profile.tables:
            entry = scored.setdefault(declared, {"table": declared, "score": 0.0, "reasons": []})
            entry["score"] += 5
            entry["reasons"].append("log declares Type = " + declared)

    ranked = sorted(scored.values(), key=lambda e: e["score"], reverse=True)[:limit]
    for e in ranked:
        t = profile.tables[e["table"]]
        e["product"] = t.product
        e["source"] = t.source
    return ranked
