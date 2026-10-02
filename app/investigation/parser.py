"""Turn a raw log into structured fields, whatever its format.

Supports JSON (object, array, JSON lines), CSV with a header row,
key=value / key: value (syslog, CEF extensions, Windows event text) and
falls back to plain text. Only the first record's fields drive mapping,
but the record count is kept so the analyst knows a batch was pasted.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field

MAX_FLAT_KEYS = 400
_KV_RE = re.compile(r'(?:^|[\s|;,])([A-Za-z_][A-Za-z0-9_.\-]{0,60})\s*[=:]\s*("[^"]*"|\'[^\']*\'|[^\s|;,]+)')
_LINE_KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _.\-]{0,50}?)\s*:\s+(.+?)\s*$")


@dataclass
class ParsedLog:
    format: str
    records: int
    fields: dict[str, str] = field(default_factory=dict)  # flattened first record
    all_keys: set[str] = field(default_factory=set)       # leaf key names across records

    def get(self, *names: str) -> str | None:
        """Value for the first key whose leaf name matches (case-insensitive)."""
        lowered = {k.lower(): v for k, v in self.fields.items()}
        leaf = {k.rsplit(".", 1)[-1].lower(): v for k, v in self.fields.items()}
        for n in names:
            v = lowered.get(n.lower()) or leaf.get(n.lower())
            if v not in (None, "", "null", "None"):
                return v
        return None


def _flatten(obj, prefix: str = "", out: dict | None = None) -> dict[str, str]:
    out = {} if out is None else out
    if len(out) >= MAX_FLAT_KEYS:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            out[prefix] = ", ".join(str(x) for x in obj)
        else:
            for i, v in enumerate(obj[:20]):
                _flatten(v, f"{prefix}[{i}]", out)
    else:
        if isinstance(obj, str) and obj[:1] in "{[":
            try:  # Sentinel often stores nested JSON as a string column
                return _flatten(json.loads(obj), prefix, out)
            except (json.JSONDecodeError, RecursionError):
                pass
        out[prefix] = "" if obj is None else str(obj)
    return out


def _leaf_keys(fields: dict[str, str]) -> set[str]:
    return {re.sub(r"\[\d+\]", "", k).split(".")[0] for k in fields} | \
           {re.sub(r"\[\d+\]", "", k).rsplit(".", 1)[-1] for k in fields}


def _try_json(text: str) -> ParsedLog | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    records: list = []
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            # Common API wrappers: {"value": [...]}, {"Tables": [...]}, {"records": [...]}
            for key in ("value", "records", "Records", "events", "results"):
                if isinstance(data.get(key), list) and data[key] and isinstance(data[key][0], dict):
                    records = data[key]
                    break
            else:
                records = [data]
        elif isinstance(data, list):
            records = [r for r in data if isinstance(r, dict)]
    except json.JSONDecodeError:
        for line in stripped.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                return None
            if isinstance(obj, dict):
                records.append(obj)
    if not records:
        return None
    first = _flatten(records[0])
    keys: set[str] = set()
    for r in records[:50]:
        keys |= _leaf_keys(_flatten(r))
    return ParsedLog("json", len(records), first, keys)


def _try_csv(text: str) -> ParsedLog | None:
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    try:
        dialect = csv.Sniffer().sniff(lines[0], delimiters=",\t;")
    except csv.Error:
        return None
    header = next(csv.reader([lines[0]], dialect))
    if len(header) < 3 or not all(re.match(r"^[A-Za-z_][\w .\-\[\]]*$", h.strip()) for h in header):
        return None
    reader = csv.DictReader(io.StringIO("\n".join(lines)), dialect=dialect)
    rows = [r for r in reader]
    if not rows or len(rows[0]) != len(header):
        return None
    first = {}
    for k, v in rows[0].items():
        if k is None:
            continue
        first.update(_flatten(v, k.strip()) if isinstance(v, str) else {k: str(v)})
    return ParsedLog("csv", len(rows), first, set(h.strip() for h in header))


def _try_kv(text: str) -> ParsedLog | None:
    fields: dict[str, str] = {}
    for line in text.splitlines()[:500]:
        m = _LINE_KV_RE.match(line)
        if m:
            key = m.group(1).strip().replace(" ", "")
            fields.setdefault(key, m.group(2).strip())
            continue
        for k, v in _KV_RE.findall(line):
            fields.setdefault(k, v.strip("'\""))
        if len(fields) >= MAX_FLAT_KEYS:
            break
    if len(fields) < 2:
        return None
    return ParsedLog("key-value", 1, fields, set(fields))


def parse_log(text: str) -> ParsedLog:
    for parser in (_try_json, _try_csv, _try_kv):
        result = parser(text)
        if result:
            return result
    return ParsedLog("text", 1, {}, set())
