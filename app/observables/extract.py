"""Deterministic observable (IOC / entity) extraction.

Two passes:
  1. Regex over the whole text (defanged forms like hxxp and [.] are
     normalised first).
  2. Key-aware pass over parsed fields, so `DeviceName: WS-01` becomes a
     hostname and `UserPrincipalName` a user even when regex alone can't tell.

Every observable records where it came from. Nothing here is inferred by
an LLM; these are facts present in the log.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

MAX_PER_TYPE = 100

TYPE_LABELS = {
    "ip": "IP address", "domain": "Domain", "url": "URL", "email": "Email address",
    "user": "User account", "hostname": "Hostname / device", "process": "Process",
    "file": "File name", "file_path": "File path", "command_line": "Command line",
    "sha256": "SHA256", "sha1": "SHA1", "md5": "MD5", "guid": "Azure / Entra identifier",
    "sid": "Windows SID",
}

_URL_RE = re.compile(r"\b(?:https?|ftp)://[^\s\"'<>()\[\]{}|\\^`]+", re.I)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")
_IPV4_RE = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")
_IPV6_RE = re.compile(r"(?<![:\w])(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{1,4})*(?![:\w])")
_GUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HASH_RE = re.compile(r"(?<![0-9a-fA-F-])([0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32})(?![0-9a-fA-F-])")
_SID_RE = re.compile(r"\bS-1-\d+(?:-\d+){1,14}\b")
_DOMAIN_RE = re.compile(r"(?<![\w@.-])((?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24})(?![\w-])")
_WINPATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\\s\"'<>|:*?]+\\)*[^\\\s\"'<>|:*?]+")
_EXE_RE = re.compile(r"(?<![\w.-])([\w.-]{1,100}\.(?:exe|dll|ps1|psm1|bat|cmd|vbs|vbe|js|jse|hta|scr|msi|lnk|"
                     r"iso|img|docm|xlsm|pptm|jar|py|sh|elf|bin|so|zip|rar|7z))(?![\w-])", re.I)

# File extensions and namespaces that look like domains but aren't.
_NOT_TLD = {
    "exe", "dll", "ps1", "psm1", "bat", "cmd", "vbs", "js", "hta", "scr", "msi", "lnk", "iso", "img", "doc",
    "docx", "docm", "xls", "xlsx", "xlsm", "ppt", "pptx", "pdf", "txt", "log", "json", "xml", "csv", "yaml",
    "yml", "tmp", "dat", "ini", "cfg", "conf", "jar", "py", "sh", "zip", "rar", "png", "jpg", "jpeg", "gif",
    "html", "htm", "aspx", "php", "md", "sys", "drv", "evtx", "etl", "mui", "cab", "manifest", "config",
    "local", "lan", "internal", "corp", "home", "localdomain",
}
_COMMON_TLDS = {
    "com", "net", "org", "io", "co", "info", "biz", "gov", "edu", "mil", "int", "app", "dev", "cloud", "xyz",
    "top", "online", "site", "club", "shop", "store", "live", "tech", "ai", "me", "tv", "cc", "ws", "su",
    "onion", "link", "click", "help", "support", "zip", "mov", "icu", "buzz", "cyou", "rest", "sbs", "lol",
    "pw", "win", "work", "today", "email", "page", "network", "digital", "services", "solutions", "microsoft",
}
_KEY_ROLES = [
    (re.compile(r"(?i)(commandline|cmdline|command_line)$"), "command_line"),
    (re.compile(r"(?i)(sha256)$"), "sha256"),
    (re.compile(r"(?i)(sha1)$"), "sha1"),
    (re.compile(r"(?i)(md5)$"), "md5"),
    (re.compile(r"(?i)(folderpath|filepath|path)$"), "file_path"),
    (re.compile(r"(?i)(processfilename|processname|^filename$|initiatingprocessfilename|newprocessname)$"), "process"),
    (re.compile(r"(?i)(devicename|computer|computername|hostname|host|workstationname|destinationdevicename)$"), "hostname"),
    (re.compile(r"(?i)(userprincipalname|accountupn|upn|accountname|username|user|targetusername|"
                r"subjectusername|initiatingprocessaccountname|initiatingprocessaccountupn|identity)$"), "user"),
    (re.compile(r"(?i)(remoteurl|url|requesturl)$"), "url"),
]
_SKIP_VALUES = {"", "-", "n/a", "na", "null", "none", "unknown", "system", "local system", "0", "true", "false"}


@dataclass
class Observable:
    type: str
    value: str
    sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"type": self.type, "label": TYPE_LABELS.get(self.type, self.type), "value": self.value,
                "sources": self.sources[:5], "tags": self.tags}


def refang(text: str) -> str:
    return (text.replace("hxxps://", "https://").replace("hxxp://", "http://")
            .replace("[.]", ".").replace("(.)", ".").replace("[:]", ":").replace("[@]", "@"))


class _Collector:
    def __init__(self):
        self.items: dict[tuple[str, str], Observable] = {}

    def add(self, otype: str, value: str, source: str, tags: list[str] | None = None) -> None:
        value = value.strip().strip(".,;:'\"()[]{}<>")
        if not value or value.lower() in _SKIP_VALUES or len(value) > 2000:
            return
        key_value = value if otype in {"command_line", "file_path"} else value.lower()
        key = (otype, key_value)
        if key not in self.items:
            if sum(1 for t, _ in self.items if t == otype) >= MAX_PER_TYPE:
                return
            self.items[key] = Observable(otype, value, [], list(tags or []))
        obs = self.items[key]
        if source not in obs.sources:
            obs.sources.append(source)
        for t in tags or []:
            if t not in obs.tags:
                obs.tags.append(t)

    def has(self, otype: str, value: str) -> bool:
        return (otype, value.lower()) in self.items


def _ip_tags(value: str) -> list[str] | None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    if ip.is_loopback:
        return ["loopback"]
    if ip.is_private or ip.is_link_local or ip.is_reserved:
        return ["internal"]
    if ip.is_multicast or ip.is_unspecified:
        return ["non-routable"]
    return ["external"]


def _looks_like_domain(candidate: str) -> bool:
    labels = candidate.lower().split(".")
    tld = labels[-1]
    if tld in _NOT_TLD or len(labels) < 2:
        return False
    if not (tld in _COMMON_TLDS or len(tld) == 2):
        return False
    # Reject dotted identifiers such as DeviceDetail.browser or System.Net
    if any(c.isupper() for c in candidate[1:]) and tld not in _COMMON_TLDS:
        return False
    return True


def extract_observables(text: str, fields: dict[str, str] | None = None) -> list[dict]:
    text = refang(text or "")
    c = _Collector()

    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:)")
        c.add("url", url, "text")
        host = re.sub(r"^[a-z]+://", "", url, flags=re.I).split("/")[0].split(":")[0].split("@")[-1]
        if _ip_tags(host):
            c.add("ip", host, "url host", _ip_tags(host))
        elif host:
            c.add("domain", host, "url host")

    for m in _EMAIL_RE.finditer(text):
        c.add("email", m.group(0), "text")

    for m in _IPV4_RE.finditer(text):
        c.add("ip", m.group(0), "text", _ip_tags(m.group(0)))
    for m in _IPV6_RE.finditer(text):
        val = m.group(0)
        if val.count(":") >= 2 and _ip_tags(val):
            c.add("ip", val, "text", _ip_tags(val))

    guid_spans = []
    for m in _GUID_RE.finditer(text):
        c.add("guid", m.group(0), "text")
        guid_spans.append(m.span())

    for m in _HASH_RE.finditer(text):
        h = m.group(1)
        if any(s <= m.start() < e for s, e in guid_spans) or h.isdigit():
            continue
        c.add({64: "sha256", 40: "sha1", 32: "md5"}[len(h)], h.lower(), "text")

    for m in _SID_RE.finditer(text):
        c.add("sid", m.group(0), "text")

    for m in _WINPATH_RE.finditer(text):
        c.add("file_path", m.group(0), "text")

    for m in _EXE_RE.finditer(text):
        c.add("file", m.group(1), "text")

    email_domains = {o.value.split("@")[-1].lower() for (t, _), o in c.items.items() if t == "email"}
    for m in _DOMAIN_RE.finditer(text):
        cand = m.group(1).rstrip(".")
        if _looks_like_domain(cand) and not _ip_tags(cand):
            tags = ["email-domain"] if cand.lower() in email_domains else []
            c.add("domain", cand, "text", tags)

    # Key-aware pass: the field name says what the value is.
    for key, value in (fields or {}).items():
        if not value:
            continue
        leaf = re.sub(r"\[\d+\]", "", key).rsplit(".", 1)[-1]
        for pattern, otype in _KEY_ROLES:
            if pattern.search(leaf):
                if otype == "process" and "\\" in value:
                    value = value.rsplit("\\", 1)[-1]
                if otype == "url" and not re.match(r"^[a-z]+://", value, re.I):
                    if _looks_like_domain(value.split("/")[0]):
                        c.add("domain", value.split("/")[0], f"field {key}")
                    break
                if otype == "user" and _ip_tags(value):
                    break
                c.add(otype, value, f"field {key}")
                break
        if _GUID_RE.fullmatch(value.strip()):
            c.add("guid", value.strip(), f"field {key}", [leaf])

    # Emails in user-ish fields are accounts too.
    for key, value in (fields or {}).items():
        leaf = key.rsplit(".", 1)[-1].lower()
        if "@" in (value or "") and any(k in leaf for k in ("user", "upn", "account", "identity")):
            c.add("user", value.strip(), f"field {key}")

    order = list(TYPE_LABELS)
    result = sorted(c.items.values(), key=lambda o: (order.index(o.type) if o.type in order else 99, o.value.lower()))
    return [o.to_dict() for o in result]


def primary(observables: list[dict], otype: str) -> list[str]:
    """Values of one type, internal IPs last."""
    vals = [o for o in observables if o["type"] == otype]
    vals.sort(key=lambda o: ("internal" in o["tags"] or "loopback" in o["tags"], 0))
    return [o["value"] for o in vals]
