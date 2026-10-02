"""Input sanitisation, secret scrubbing and identifier validation."""
from __future__ import annotations

import re

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
INV_ID_RE = re.compile(r"^INV-\d{4}-\d{6}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.md$")
EXAMPLE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.(json|jsonl|csv|tsv|txt|log|xml|md)$")

# C0 controls except \t \n \r, plus DEL.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InputError(ValueError):
    """Raised for user input that must be rejected (shown to the analyst)."""


def valid_slug(value: str) -> bool:
    return bool(SLUG_RE.match(value or ""))


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug[:63]


def decode_upload(data: bytes, max_bytes: int) -> str:
    """Decode an uploaded log file, rejecting oversized or binary content."""
    if len(data) > max_bytes:
        raise InputError(f"File is larger than the {max_bytes // 1024} KiB limit.")
    if data.count(b"\x00") > len(data) // 100 + 1:
        raise InputError("File looks binary. Upload a text log export (JSON, CSV, syslog, txt).")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            text = data.decode("utf-16")
        else:
            text = data.decode("latin-1")
    return clean_text(text)


def clean_text(text: str, max_chars: int | None = None) -> str:
    """Strip control characters but preserve layout (tabs, newlines)."""
    text = _CONTROL_RE.sub("", text or "").replace("\r\n", "\n")
    if max_chars is not None and len(text) > max_chars:
        raise InputError(f"Input is larger than the {max_chars:,} character limit.")
    return text


# Secrets that must never reach a ticket. Each pattern keeps the key name and
# masks the value so the analyst can still see that something was present.
_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|client_secret|api[_-]?key|access[_-]?key|"
                r"token|refresh_token|access_token|sharedaccesskey|accountkey)\b(\s*[\"']?\s*[:=]\s*[\"']?)"
                r"([^\s\"',;&}]{4,})"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]{16,}=*"), "Bearer [REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "[REDACTED-JWT]"),
    (re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
                r"xox[baprs]-[A-Za-z0-9-]{10,})"), "[REDACTED-KEY]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED-PRIVATE-KEY]"),
    (re.compile(r"(?i)(sig=)[A-Za-z0-9%+/=]{10,}"), r"\1[REDACTED]"),
]


def scrub_secrets(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text
