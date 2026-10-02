"""Parse customer markdown into table schemas.

Tables are read from:
  * any `##` section of customer.md whose heading contains "table" or "schema"
  * every file in the customer's `schemas/` directory

Inside those, each `### TableName` heading starts a table. Supported lines:

    ### SigninLogs
    Product: Microsoft Entra ID
    Time field: TimeGenerated
    Description: Interactive user sign-ins
    - UserPrincipalName
    - IPAddress (ip)            <- optional role hint in () or []
    - `ResultType` - 0 = success
    | DeviceName | string |     <- markdown table rows also work

Roles tell the KQL generator which field holds the user, IP, host, etc.
Most are inferred from common Microsoft field names; a hint overrides that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Role -> field names, in priority order. Matched case-sensitively first,
# then case-insensitively.
ROLE_CANDIDATES: dict[str, list[str]] = {
    "time": ["TimeGenerated", "Timestamp", "EventTime", "CreatedDateTime"],
    "user": ["UserPrincipalName", "AccountUpn", "InitiatingProcessAccountUpn", "UserId",
             "AccountName", "InitiatingProcessAccountName", "Identity", "TargetUserName",
             "SubjectUserName", "Account", "User"],
    "ip": ["IPAddress", "RemoteIP", "IpAddress", "ClientIP", "SourceIP", "SrcIpAddr",
           "CallerIpAddress", "SenderIPv4", "LocalIP", "DestinationIP", "IP"],
    "device": ["DeviceName", "Computer", "HostName", "DestinationDeviceName", "DeviceId", "Hostname"],
    "hash": ["SHA256", "SHA1", "MD5", "InitiatingProcessSHA256", "InitiatingProcessSHA1", "FileHash"],
    "process": ["FileName", "InitiatingProcessFileName", "ProcessName", "NewProcessName", "Process"],
    "command_line": ["ProcessCommandLine", "InitiatingProcessCommandLine", "CommandLine"],
    "file": ["FileName", "FolderPath", "FilePath"],
    "url": ["RemoteUrl", "Url", "UrlDomain", "RequestURL"],
    "domain": ["RemoteUrl", "UrlDomain", "DestinationHostName", "DnsQuery", "QueryName", "SenderFromDomain"],
    "email_sender": ["SenderFromAddress", "SenderMailFromAddress", "Sender"],
    "email_recipient": ["RecipientEmailAddress", "Recipient"],
    "email_subject": ["Subject"],
    "result": ["ResultType", "ActionType", "Result", "ResultDescription", "Status"],
    "location": ["Location", "Country", "LocationDetails"],
    "app": ["AppDisplayName", "Application", "ResourceDisplayName"],
    "alert_id": ["AlertId", "SystemAlertId"],
    "object_id": ["UserId", "AccountObjectId", "TargetResources", "ObjectId"],
}
KNOWN_ROLES = set(ROLE_CANDIDATES)

_FIELD_LINE = re.compile(r"^\s*[-*+]\s+`?([A-Za-z_][A-Za-z0-9_]*)`?(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\|")
_ROLE_HINT = re.compile(r"[(\[]\s*(?:role\s*[:=]\s*)?([a-z_]+)\s*[)\]]")
_KV_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**(product|time field|description|source)\**\s*:\s*(.+)$", re.I)
_SKIP_ROW = {"Field", "Fields", "Name", "Column", "Columns"}


@dataclass
class TableSchema:
    name: str
    fields: list[str] = field(default_factory=list)
    product: str = ""
    description: str = ""
    source: str = ""  # file the definition came from
    role_hints: dict[str, str] = field(default_factory=dict)
    time_field_hint: str = ""

    def has(self, name: str) -> bool:
        return name in self.fields

    def resolve(self, name: str) -> str | None:
        """Exact field name for `name`, matching case-insensitively."""
        if name in self.fields:
            return name
        low = name.lower()
        return next((f for f in self.fields if f.lower() == low), None)

    def role(self, role: str) -> str | None:
        if role == "time" and self.time_field_hint:
            return self.resolve(self.time_field_hint) or self.time_field_hint
        if role in self.role_hints:
            return self.role_hints[role]
        for cand in ROLE_CANDIDATES.get(role, []):
            hit = self.resolve(cand)
            if hit:
                return hit
        return None

    def roles(self) -> dict[str, str]:
        return {r: f for r in KNOWN_ROLES if (f := self.role(r))}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "product": self.product,
            "description": self.description,
            "source": self.source,
            "fields": self.fields,
            "roles": self.roles(),
        }


def split_sections(markdown: str, level: int = 2) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) pairs at the given heading level."""
    marker = "#" * level + " "
    sections: list[tuple[str, str]] = []
    heading, buf = "", []
    in_code = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith(marker):
            if heading or any(s.strip() for s in buf):
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = line[len(marker):].strip(), []
        else:
            buf.append(line)
    if heading or any(s.strip() for s in buf):
        sections.append((heading, "\n".join(buf).strip()))
    return sections


def parse_tables(markdown: str, source: str) -> list[TableSchema]:
    tables: list[TableSchema] = []
    for heading, body in split_sections(markdown, level=3):
        if not heading:
            continue
        name_match = re.match(r"`?([A-Za-z_][A-Za-z0-9_]*)`?", heading)
        if not name_match:
            continue
        table = TableSchema(name=name_match.group(1), source=source)
        in_code = False
        for line in body.splitlines():
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code or line.lstrip().startswith("#"):
                continue
            kv = _KV_LINE.match(line)
            if kv:
                key, value = kv.group(1).lower(), kv.group(2).strip().strip("`")
                if key == "product":
                    table.product = value
                elif key == "time field":
                    table.time_field_hint = value
                elif key == "description":
                    table.description = value
                continue
            m = _FIELD_LINE.match(line) or _TABLE_ROW.match(line)
            if not m:
                continue
            fname = m.group(1)
            if fname in table.fields:
                continue
            if fname in _SKIP_ROW:
                cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
                if m.re is _FIELD_LINE or len(cells) < 2 or cells[1] in ("type", "data type", "role", "description", ""):
                    continue  # header row (a real column named Name/Field has a type such as `string`)
            table.fields.append(fname)
            rest = m.group(2) if m.re is _FIELD_LINE else ""
            hint = _ROLE_HINT.search(rest or "")
            if hint and hint.group(1) in KNOWN_ROLES:
                table.role_hints.setdefault(hint.group(1), fname)
        if table.fields:
            tables.append(table)
    return tables


def parse_settings(body: str) -> dict[str, str]:
    """`- key: value` bullets from a `## Settings` section."""
    out: dict[str, str] = {}
    for line in body.splitlines():
        m = re.match(r"^\s*[-*]\s+`?([A-Za-z0-9_ ]+?)`?\s*:\s*(.+?)\s*$", line)
        if m:
            out[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip().strip("`")
    return out


def parse_bullets(body: str) -> list[str]:
    return [m.group(1).strip() for line in body.splitlines()
            if (m := re.match(r"^\s*[-*+]\s+(.+)$", line))]
