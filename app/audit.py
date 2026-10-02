"""Append-only audit trail of investigation actions.

Records who did what to which investigation. Never records raw log content,
findings text or ticket bodies, only identifiers and sizes.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("soc.audit")


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, action: str, *, analyst: str = "", customer: str = "",
               investigation: str = "", **details) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": action,
            "analyst": analyst,
            "customer": customer,
            "investigation": investigation,
            **details,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        log.info("audit %s customer=%s inv=%s", action, customer, investigation)

    def tail(self, limit: int = 200, customer: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-5000:]
        out = []
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if customer and entry.get("customer") != customer:
                continue
            out.append(entry)
            if len(out) >= limit:
                break
        return out
