"""Customer-specific KQL from templates.

Queries are assembled from the customer's own table and field names: a
builder asks the table for a *role* ("user", "ip", "time" ...) and gets
back that customer's column name, or None if the table lacks it, in which
case the query is skipped rather than generated with a guessed column.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from app.customers.schema import TableSchema
from app.customers.store import CustomerProfile
from app.observables.extract import primary

MAX_VALUES = 10


def kql_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def kql_list(values: list[str]) -> str:
    return "(" + ", ".join(kql_str(v) for v in values[:MAX_VALUES]) + ")"


def _duration(value: str, default: str) -> str:
    return value if re.fullmatch(r"\d+[dhm]", value or "") else default


def parse_event_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = raw.strip().replace("Z", "+00:00")
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)  # .NET 7-digit fractions
    for candidate in (s, s.replace(" ", "T", 1)):
        try:
            dt = datetime.fromisoformat(candidate)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class Ctx:
    """Everything a query builder needs."""

    def __init__(self, profile: CustomerProfile, tables: list[str], observables: list[dict],
                 event_time: datetime | None):
        self.profile = profile
        self.tables = [profile.tables[t] for t in tables if t in profile.tables]
        self.obs = observables
        self.event_time = event_time
        self.lookback = _duration(profile.default_lookback, "7d")
        self.window = _duration(profile.settings.get("event_window", ""), "1d")

        users = [u for u in primary(observables, "user") if " " not in u] or [o["value"] for o in observables if o["type"] == "email"]
        self.values: dict[str, list[str]] = {
            "user": users,
            "ip": [v for v in primary(observables, "ip")],
            "device": primary(observables, "hostname"),
            "sha256": primary(observables, "sha256"),
            "sha1": primary(observables, "sha1"),
            "md5": primary(observables, "md5"),
            "process": primary(observables, "process") or primary(observables, "file"),
            "domain": primary(observables, "domain"),
            "url": primary(observables, "url"),
        }
        emails = [o["value"] for o in observables if o["type"] == "email"]
        self.values["email_sender"] = emails[:1]
        self.values["email_recipient"] = emails[1:] or emails[:1]

    def time_filter(self, table: TableSchema, wide: bool = False) -> str:
        tf = table.role("time") or "TimeGenerated"
        if self.event_time:
            ts = self.event_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            before = self.lookback if wide else self.window
            return f"| where {tf} between (datetime({ts}) - {before} .. datetime({ts}) + {self.window})"
        return f"| where {tf} > ago({self.lookback})"

    def time_desc(self, wide: bool = False) -> str:
        if self.event_time:
            return (f"{self.lookback if wide else self.window} before to {self.window} after the event time "
                    f"({self.event_time.strftime('%Y-%m-%d %H:%M:%S')} UTC)")
        return f"last {self.lookback} (customer default lookback; no event timestamp found in the log)"

    def hash_filter(self, table: TableSchema) -> tuple[str, str] | None:
        """(field, value) for the first hash type this table can be filtered on."""
        for htype, fname in (("sha256", "SHA256"), ("sha1", "SHA1"), ("md5", "MD5")):
            field = table.resolve(fname)
            if field and self.values[htype]:
                return field, self.values[htype][0]
        return None


def project_fields(table: TableSchema, limit: int = 14) -> list[str]:
    order = ["time", "user", "ip", "device", "process", "command_line", "result", "location", "app",
             "url", "email_sender", "email_recipient", "hash"]
    out: list[str] = []
    for role in order:
        f = table.role(role)
        if f and f not in out:
            out.append(f)
    for f in table.fields:
        if len(out) >= limit:
            break
        if f not in out:
            out.append(f)
    return out[:limit]


def _fmt_project(fields: list[str]) -> str:
    return "| project\n    " + ",\n    ".join(fields)


def _eq(field: str, values: list[str]) -> str:
    if len(values) == 1:
        return f"{field} =~ {kql_str(values[0])}"
    return f"{field} in~ {kql_list(values)}"


def _q(ctx: Ctx, table: TableSchema, title: str, purpose: str, body: list[str], expected: str, rationale: str,
       wide: bool = False) -> dict:
    lines = [table.name, ctx.time_filter(table, wide)] + body
    return {
        "title": title, "purpose": purpose, "table": table.name, "query": "\n".join(lines),
        "expected_result": expected, "rationale": rationale, "time_range": ctx.time_desc(wide), "source": "rules",
    }


# ---------------------------------------------------------------- builders
def q_event_context(ctx: Ctx, t: TableSchema) -> dict | None:
    conds, used = [], []
    for role in ("user", "ip", "device", "process"):
        field, vals = t.role(role), ctx.values.get(role)
        if field and vals:
            conds.append(_eq(field, vals[:3]))
            used.append(f"{role} ({field})")
        if len(conds) == 2:
            break
    hf = ctx.hash_filter(t)
    if hf and len(conds) < 2:
        conds.append(f"{hf[0]} == {kql_str(hf[1])}")
        used.append(f"hash ({hf[0]})")
    if not conds:
        return None
    tf = t.role("time") or "TimeGenerated"
    body = [f"| where {c}" for c in conds] + [_fmt_project(project_fields(t)), f"| order by {tf} desc"]
    return _q(ctx, t, f"{t.name}: events matching the observed entities",
              "Reproduce the event and show surrounding activity for the same entities.", body,
              "The original event plus any other records for the same entities in the window. "
              "No rows means the event is not in this table or the window/values need adjusting.",
              f"Filters on {', '.join(used)}, the fields {ctx.profile.name}'s schema defines for these entities in {t.name}.")


def q_user_baseline(ctx: Ctx, t: TableSchema) -> dict | None:
    user, users = t.role("user"), ctx.values["user"]
    if not (user and users):
        return None
    group = [f for f in (t.role("ip"), t.role("location"), t.role("app"), t.role("device")) if f]
    if not group:
        return None
    result, tf = t.role("result"), t.role("time") or "TimeGenerated"
    aggs = ["Events = count()"]
    if result and result.lower() in {"resulttype", "errorcode"}:
        aggs += [f'Failures = countif(tostring({result}) != "0")', f'Successes = countif(tostring({result}) == "0")']
    aggs += [f"FirstSeen = min({tf})", f"LastSeen = max({tf})"]
    body = [f"| where {_eq(user, users[:1])}",
            f"| summarize {', '.join(aggs)}\n    by {', '.join(group[:3])}",
            "| order by Events desc"]
    return _q(ctx, t, f"{t.name}: activity baseline for {users[0]}",
              "Establish what is normal for this account so the event can be judged against it.", body,
              "One row per IP/location/app combination. A combination seen only around the event time stands out.",
              f"Groups the user's {t.name} records by {', '.join(group[:3])} over the wider lookback.", wide=True)


def q_ip_scope(ctx: Ctx, t: TableSchema) -> dict | None:
    ip, user = t.role("ip"), t.role("user")
    ips = [v for v in ctx.values["ip"] if ":" in v or not re.match(r"^(10|127|192\.168|172\.(1[6-9]|2\d|3[01]))\.", v)]
    if not (ip and user and ips):
        return None
    result, tf = t.role("result"), t.role("time") or "TimeGenerated"
    aggs = [f"Accounts = dcount({user})", "Events = count()"]
    if result and result.lower() in {"resulttype", "errorcode"}:
        aggs += [f'Failures = countif(tostring({result}) != "0")', f'Successes = countif(tostring({result}) == "0")']
    aggs += [f"SampleAccounts = make_set({user}, 25)", f"FirstSeen = min({tf})", f"LastSeen = max({tf})"]
    body = [f"| where {_eq(ip, ips[:5])}", f"| summarize {', '.join(aggs)}\n    by {ip}", "| order by Accounts desc"]
    return _q(ctx, t, f"{t.name}: scope of source IP activity",
              "Determine whether the external IP is targeting one account or many (spray / brute force).", body,
              "Accounts > 1 with many failures suggests password spraying; any success from the IP needs review.",
              f"Counts distinct {user} values per {ip}. External IPs only; internal addresses are excluded.", wide=True)


def q_process_tree(ctx: Ctx, t: TableSchema) -> dict | None:
    device, devices = t.role("device"), ctx.values["device"]
    parent = t.resolve("InitiatingProcessFileName")
    if not (device and devices and parent):
        return None
    tf = t.role("time") or "TimeGenerated"
    fields = [f for f in (tf, device, t.resolve("AccountName") or t.role("user"), parent,
                          t.resolve("InitiatingProcessCommandLine"), t.resolve("FileName"),
                          t.resolve("ProcessCommandLine"), t.resolve("FolderPath"), t.resolve("SHA256")) if f]
    procs = ctx.values["process"]
    body = [f"| where {_eq(device, devices[:1])}"]
    if procs and t.resolve("FileName"):
        body.append(f"| where {t.resolve('FileName')} in~ {kql_list(procs[:5])} or {parent} in~ {kql_list(procs[:5])}")
    body += [_fmt_project(list(dict.fromkeys(fields))), f"| order by {tf} asc"]
    return _q(ctx, t, f"{t.name}: process tree on {devices[0]}",
              "Reconstruct parent/child process activity on the device around the event.", body,
              "Chronological process launches showing which parent spawned the suspicious process and what it ran next.",
              f"Uses {parent} → FileName relationships in {t.name} for the observed device.")


def q_hash_prevalence(ctx: Ctx, t: TableSchema) -> dict | None:
    device = t.role("device")
    for htype, fname in (("sha256", "SHA256"), ("sha1", "SHA1"), ("md5", "MD5")):
        field, vals = t.resolve(fname), ctx.values[htype]
        if field and vals and device:
            tf = t.role("time") or "TimeGenerated"
            fn = t.resolve("FileName")
            by = ", ".join(x for x in (field, fn) if x)
            body = [f"| where {field} in~ {kql_list(vals)}",
                    f"| summarize Devices = dcount({device}), DeviceList = make_set({device}, 50),\n"
                    f"    FirstSeen = min({tf}), LastSeen = max({tf}), Events = count()\n    by {by}",
                    "| order by Devices desc"]
            return _q(ctx, t, f"{t.name}: prevalence of file hash",
                      "Find every device where the file appears, to scope spread.", body,
                      "Devices = 1 suggests an isolated event; many devices suggest a campaign or common software.",
                      f"Matches {fname} values from the log against {field} in {t.name}.", wide=True)
    return None


def q_destination_prevalence(ctx: Ctx, t: TableSchema) -> dict | None:
    device = t.role("device")
    ipf, urlf = t.resolve("RemoteIP") or t.role("ip"), t.resolve("RemoteUrl") or t.role("url")
    ips = [v for v in ctx.values["ip"] if not re.match(r"^(10|127|192\.168|172\.(1[6-9]|2\d|3[01]))\.", v)]
    domains = ctx.values["domain"]
    conds = []
    if ipf and ips:
        conds.append(f"{ipf} in ({', '.join(kql_str(i) for i in ips[:MAX_VALUES])})")
    if urlf and domains:
        conds.append(f"{urlf} has_any ({', '.join(kql_str(d) for d in domains[:MAX_VALUES])})")
    if not (conds and device):
        return None
    tf = t.role("time") or "TimeGenerated"
    proc = t.resolve("InitiatingProcessFileName")
    by = ", ".join(x for x in (ipf if ips else None, urlf if domains else None) if x)
    aggs = [f"Devices = dcount({device})", "Connections = count()", f"DeviceList = make_set({device}, 50)"]
    if proc:
        aggs.append(f"Processes = make_set({proc}, 20)")
    aggs += [f"FirstSeen = min({tf})", f"LastSeen = max({tf})"]
    body = [f"| where {' or '.join(conds)}", f"| summarize {', '.join(aggs)}\n    by {by}", "| order by Devices desc"]
    return _q(ctx, t, f"{t.name}: devices contacting the destination",
              "Scope which devices and processes communicated with the remote IP/domain.", body,
              "Rare destinations contacted by one device are more suspicious than ones contacted estate-wide.",
              f"Searches {by} in {t.name} for the external observables.", wide=True)


def q_email_sender(ctx: Ctx, t: TableSchema) -> dict | None:
    sender, recip = t.role("email_sender"), t.role("email_recipient")
    if not (sender and recip and ctx.values["email_sender"]):
        return None
    tf = t.role("time") or "TimeGenerated"
    subj = t.role("email_subject")
    aggs = [f"Recipients = dcount({recip})", f"RecipientList = make_set({recip}, 100)", "Messages = count()"]
    if subj:
        aggs.append(f"Subjects = make_set({subj}, 10)")
    da = t.resolve("DeliveryAction")
    if da:
        aggs.append(f"DeliveryActions = make_set({da})")
    aggs += [f"FirstSeen = min({tf})", f"LastSeen = max({tf})"]
    body = [f"| where {_eq(sender, ctx.values['email_sender'][:1])}",
            f"| summarize {', '.join(aggs)}\n    by {sender}"]
    return _q(ctx, t, f"{t.name}: all recipients from the sender",
              "Find every mailbox that received mail from the same sender.", body,
              "The full recipient list to scope purge and user follow-up.",
              f"Uses {sender} / {recip} from {ctx.profile.name}'s {t.name} schema.", wide=True)


BUILDERS: dict[str, Callable[[Ctx, TableSchema], dict | None]] = {
    "context": q_event_context,
    "user_baseline": q_user_baseline,
    "ip_scope": q_ip_scope,
    "process_tree": q_process_tree,
    "hash_prevalence": q_hash_prevalence,
    "destination": q_destination_prevalence,
    "email_sender": q_email_sender,
}
PLAN: dict[str, list[str]] = {
    "entra_signin": ["context", "user_baseline", "ip_scope"],
    "mfa": ["context", "user_baseline", "ip_scope"],
    "impossible_travel": ["context", "user_baseline", "ip_scope"],
    "account_modification": ["context", "user_baseline"],
    "privilege_escalation": ["context", "user_baseline", "process_tree"],
    "process_execution": ["context", "process_tree", "hash_prevalence", "destination"],
    "network_connection": ["context", "destination", "process_tree"],
    "malware": ["context", "hash_prevalence", "process_tree"],
    "phishing": ["context", "email_sender", "destination"],
    "email": ["context", "email_sender"],
    "defender_alert": ["context", "hash_prevalence", "destination"],
    "cloud_alert": ["context", "user_baseline"],
    "device_logon": ["context", "user_baseline", "ip_scope"],
}


def generate_queries(profile: CustomerProfile, tables: list[str], event_types: list[dict],
                     observables: list[dict], event_time: datetime | None, limit: int = 6) -> list[dict]:
    ctx = Ctx(profile, tables, observables, event_time)
    plan: list[str] = []
    for et in event_types[:2]:
        plan += [b for b in PLAN.get(et["type"], ["context"]) if b not in plan]
    if not plan:
        plan = ["context", "user_baseline", "ip_scope", "hash_prevalence", "destination"]

    out, seen = [], set()
    for builder_name in plan:
        for table in ctx.tables:
            q = BUILDERS[builder_name](ctx, table)
            if q and q["query"] not in seen:
                seen.add(q["query"])
                out.append(q)
                if builder_name != "context":
                    break  # one table per non-context builder is enough
        if len(out) >= limit:
            break
    for i, q in enumerate(out, 1):
        q["id"] = f"Q{i}"
    return out
