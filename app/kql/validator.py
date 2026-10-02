"""Local KQL validation against a customer's schema.

This is static checking only. It never runs the query. It checks:
  * syntax basics: balanced brackets/quotes, known operator after each pipe
  * every table referenced exists in the customer schema
  * column names used exist in at least one referenced table (warning,
    because customer.md often lists only the relevant subset of columns)
  * a time filter is present
  * customer KQL settings (forbidden tables, required time filter)
"""
from __future__ import annotations

import re

from app.customers.store import CustomerProfile

LOCAL_NOTE = "Schema validation: Local schema validation only. Query execution has not been performed."

TABULAR_OPS = {
    "where", "filter", "project", "project-away", "project-keep", "project-rename", "project-reorder", "extend",
    "summarize", "order", "sort", "top", "take", "limit", "distinct", "count", "join", "union", "lookup",
    "mv-expand", "mv-apply", "parse", "parse-where", "parse-kv", "evaluate", "render", "as", "invoke",
    "make-series", "sample", "sample-distinct", "search", "serialize", "getschema", "facet", "fork",
    "partition", "scan", "top-nested", "top-hitters", "find", "consume", "reduce", "extract",
}
COLUMN_OPS = {"where", "filter", "project", "project-away", "project-keep", "project-reorder", "extend",
              "summarize", "order", "sort", "top", "distinct", "mv-expand", "make-series", "join", "lookup"}
KEYWORDS = {
    "and", "or", "not", "in", "has", "has_any", "has_all", "has_cs", "hasprefix", "hassuffix", "contains",
    "contains_cs", "startswith", "startswith_cs", "endswith", "endswith_cs", "matches", "regex", "between",
    "by", "asc", "desc", "nulls", "first", "last", "on", "kind", "with", "inner", "innerunique", "leftouter",
    "rightouter", "fullouter", "leftanti", "rightanti", "leftsemi", "rightsemi", "anti", "semi", "hint",
    "isfuzzy", "withsource", "step", "from", "to", "true", "false", "null", "let", "typeof", "string", "int",
    "long", "real", "double", "bool", "boolean", "datetime", "timespan", "dynamic", "guid", "decimal", "of",
    "like", "notlike", "remote", "strategy", "shufflekey", "bin", "range", "print", "materialize", "toscalar",
    "in~", "has_any_cs", "limit", "take", "count", "where", "project", "extend", "summarize", "order", "sort",
    "top", "distinct", "join", "union", "lookup", "as", "away", "rename", "reorder", "keep", "expand", "apply",
    "mv", "series", "bagexpansion", "itemindex", "to_typeof", "outer", "left", "right", "this", "row_number",
}
AUTO_COLUMN_RE = re.compile(r"^(count|dcount|sum|avg|min|max|make_set|make_list|make_bag|arg_max|arg_min|countif|"
                            r"dcountif|sumif|any|take_any|percentile|stdev|variance)_\w*$|^(count_|Column\d+)$")

_STRING_RE = re.compile(r'@"[^"]*"|@\'[^\']*\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')
_COMMENT_RE = re.compile(r"//[^\n]*")
_LITERAL_FUNC_RE = re.compile(r"\b(datetime|timespan|guid|dynamic)\s*\(([^()]*)\)", re.I)
_IDENT_RE = re.compile(r"(?<![\w.$\-])([A-Za-z_][A-Za-z0-9_]*)(?![\w-])")


def _strip(query: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    q = _COMMENT_RE.sub("", query)
    q = _STRING_RE.sub('""', q)
    if q.count('"') % 2 or q.count("'") % 2:
        errors.append("Unterminated string literal.")
    q = _LITERAL_FUNC_RE.sub(lambda m: f"{m.group(1)}()", q)
    return q, errors


def _balanced(q: str) -> list[str]:
    pairs, stack, errs = {")": "(", "]": "[", "}": "{"}, [], []
    for ch in q:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                errs.append(f"Unbalanced '{ch}'.")
                return errs
            stack.pop()
    if stack:
        errs.append(f"Unclosed '{stack[-1]}'.")
    return errs


def _split_pipes(body: str) -> list[str]:
    """Split on top-level pipes (not inside parentheses)."""
    parts, depth, buf = [], 0, []
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def _operator(segment: str) -> str:
    m = re.match(r"\s*([a-z][a-z\-]*)", segment)
    return m.group(1) if m else ""


def validate_kql(query: str, profile: CustomerProfile) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not query or not query.strip():
        return {"status": "error", "errors": ["Query is empty."], "warnings": [], "tables": [], "note": LOCAL_NOTE}

    q, errs = _strip(query)
    errors += errs + _balanced(q)

    statements = [s for s in q.split(";") if s.strip()]
    let_names: set[str] = set()
    tables: list[str] = []
    bodies: list[str] = []
    for stmt in statements:
        m = re.match(r"\s*let\s+([A-Za-z_]\w*)\s*=\s*(.*)$", stmt, re.S)
        if m:
            let_names.add(m.group(1))
            bodies.append(m.group(2))
        else:
            bodies.append(stmt)

    def note_table(name: str) -> None:
        if name not in let_names and name not in tables:
            tables.append(name)

    for body in bodies:
        lead = re.match(r"\s*\(?\s*([A-Za-z_]\w*)\s*(\||$|\))", body)
        if lead and lead.group(1) not in KEYWORDS | {"print", "range", "datatable", "externaldata", "union", "search", "find"}:
            note_table(lead.group(1))
        for m in re.finditer(r"\b(?:join|lookup)\b(?:\s+kind\s*=\s*\w+)?(?:\s+hint\.\w+\s*=\s*\w+)*\s*\(\s*([A-Za-z_]\w*)", body):
            note_table(m.group(1))
        for m in re.finditer(r"\b(?:join|lookup)\b(?:\s+kind\s*=\s*\w+)?\s+([A-Za-z_]\w*)\s+on\b", body):
            note_table(m.group(1))
        for m in re.finditer(r"\bunion\b((?:\s+\w+\s*=\s*\w+)*)\s+([A-Za-z_][\w\s,*]*)", body):
            for name in re.split(r"[\s,]+", m.group(2).split("|")[0]):
                if name and name not in KEYWORDS and "*" not in name:
                    note_table(name)

    known_tables = profile.tables
    for t in tables:
        if t not in known_tables:
            close = [k for k in known_tables if k.lower() == t.lower()]
            hint = f" Did you mean {close[0]}?" if close else ""
            errors.append(f"Table '{t}' is not in {profile.name}'s schema.{hint}")

    forbidden = {x.strip() for x in profile.settings.get("kql_forbidden_tables", "").split(",") if x.strip()}
    for t in tables:
        if t in forbidden:
            errors.append(f"Table '{t}' is not permitted by {profile.name}'s KQL guidelines.")

    # Operators and columns
    aliases: set[str] = set()
    for m in re.finditer(r"(?<![=!<>~])\b([A-Za-z_]\w*)\s*=(?![=~])", q):
        aliases.add(m.group(1))
    for m in re.finditer(r"\bas\s+([A-Za-z_]\w*)", q):
        aliases.add(m.group(1))
    for m in re.finditer(r"\(\s*([A-Za-z_]\w*)\s*:\s*\w+", q):  # datatable / function params
        aliases.add(m.group(1))

    valid_fields: set[str] = set()
    for t in tables:
        if t in known_tables:
            valid_fields |= set(known_tables[t].fields)
    unknown_fields: list[str] = []
    has_time_filter = False
    time_fields = {tb.role("time") for tb in known_tables.values() if tb.role("time")} | {"TimeGenerated", "Timestamp"}

    for body in bodies:
        segments = _split_pipes(body)
        for i, seg in enumerate(segments):
            if i == 0:
                continue
            if not seg.strip():
                errors.append("Empty pipe segment ('| |' or trailing '|').")
                continue
            op = _operator(seg)
            if op not in TABULAR_OPS:
                errors.append(f"Unknown operator after pipe: '{op or seg.strip()[:20]}'.")
                continue
            if op in ("where", "filter") and re.search(r"\b(" + "|".join(time_fields) + r")\b\s*(>|>=|between|<)", seg):
                has_time_filter = True
            if op not in COLUMN_OPS or not valid_fields:
                continue
            check = seg
            if op == "join":
                on = re.search(r"\bon\b(.*)$", seg, re.S)
                check = on.group(1) if on else ""
                check = re.sub(r"\$(left|right)\.", "", check)
            for m in _IDENT_RE.finditer(check):
                name = m.group(1)
                after = check[m.end():m.end() + 3].lstrip()
                if after.startswith("("):
                    continue  # function call
                if (name in valid_fields or name in aliases or name in let_names or name in tables
                        or name.lower() in KEYWORDS or name == op or AUTO_COLUMN_RE.match(name)
                        or name in known_tables):
                    continue
                if name not in unknown_fields:
                    unknown_fields.append(name)

    if unknown_fields:
        warnings.append("Columns not listed in the customer schema for "
                        f"{', '.join(tables) or 'the referenced tables'}: {', '.join(unknown_fields[:12])}. "
                        "They may exist but are not documented in customer.md/schemas.")
    require_time = profile.settings.get("kql_require_time_filter", "true").lower() not in {"false", "no", "0"}
    if tables and require_time and not has_time_filter:
        warnings.append("No time filter found. Add a `where <time field> > ago(...)` or `between (...)` clause.")
    if re.search(r"\bsearch\s+\*|\bunion\s+\*", q):
        warnings.append("Wildcard search/union is expensive; prefer explicit tables.")

    status = "error" if errors else ("warning" if warnings else "ok")
    return {"status": status, "errors": errors, "warnings": warnings, "tables": tables,
            "unknown_fields": unknown_fields, "note": LOCAL_NOTE}
