"""Investigation persistence: one JSON file per investigation, stored under
the owning customer's directory. Every lookup takes the customer id, so an
investigation can only be reached through its own customer.
"""
from __future__ import annotations

import fcntl
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.security import INV_ID_RE, InputError, valid_slug

STATUSES = ["New", "Investigating", "Pending Information", "Escalated", "Resolved", "Closed"]
SEVERITIES = ["", "Informational", "Low", "Medium", "High", "Critical"]
EDITABLE = {"title", "status", "severity", "findings", "analyst_notes", "context", "ticket", "assigned_to"}
MAX_TEXT = 200_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class InvestigationStore:
    def __init__(self, root: Path):
        self.root = root / "investigations"
        self.root.mkdir(parents=True, exist_ok=True)
        self.counter = root / "counter.json"
        self._lock = threading.Lock()

    # -------------------------------------------------------------- paths
    def _cdir(self, customer_id: str) -> Path:
        if not valid_slug(customer_id):
            raise InputError("Invalid customer id")
        return self.root / customer_id

    def _path(self, customer_id: str, inv_id: str) -> Path:
        if not INV_ID_RE.match(inv_id or ""):
            raise InputError("Invalid investigation id")
        return self._cdir(customer_id) / f"{inv_id}.json"

    # -------------------------------------------------------------- ids
    def next_id(self) -> str:
        year = datetime.now().year
        with self._lock, open(self.counter, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            try:
                data = json.loads(fh.read() or "{}")
            except json.JSONDecodeError:
                data = {}
            n = int(data.get(str(year), 0)) + 1
            data[str(year)] = n
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(data))
            fh.flush()
            os.fsync(fh.fileno())
        return f"INV-{year}-{n:06d}"

    # -------------------------------------------------------------- crud
    def _write(self, inv: dict) -> None:
        path = self._path(inv["customer_id"], inv["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(inv, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def create(self, customer_id: str, *, title: str, raw_log: str, context: str, analyst: str,
               source_name: str = "") -> dict:
        self._cdir(customer_id)
        now = _now()
        inv = {
            "id": self.next_id(), "customer_id": customer_id, "title": title.strip()[:300] or "Untitled investigation",
            "status": "New", "severity": "", "created": now, "updated": now, "created_by": analyst,
            "assigned_to": analyst, "source_name": source_name[:200], "raw_log": raw_log, "context": context,
            "findings": "", "analyst_notes": "", "analysis": None, "ticket": "", "llm_used": [], "history": [],
        }
        self._event(inv, analyst, "created")
        self._write(inv)
        return inv

    def get(self, customer_id: str, inv_id: str) -> dict:
        path = self._path(customer_id, inv_id)
        if not path.is_file():
            raise KeyError(inv_id)
        inv = json.loads(path.read_text(encoding="utf-8"))
        if inv.get("customer_id") != customer_id:  # defence in depth
            raise KeyError(inv_id)
        return inv

    def list(self, customer_id: str) -> list[dict]:
        cdir = self._cdir(customer_id)
        if not cdir.is_dir():
            return []
        out = []
        for p in sorted(cdir.glob("INV-*.json"), reverse=True):
            try:
                inv = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            a = inv.get("analysis") or {}
            out.append({k: inv.get(k) for k in ("id", "title", "status", "severity", "created", "updated",
                                                "assigned_to")}
                       | {"event_type": (a.get("event_types") or [{}])[0].get("label", "") if a else ""})
        return out

    def update(self, customer_id: str, inv_id: str, changes: dict, analyst: str) -> dict:
        inv = self.get(customer_id, inv_id)
        changed = []
        for key, value in changes.items():
            if key not in EDITABLE or value is None:
                continue
            value = str(value)[:MAX_TEXT]
            if key == "status" and value not in STATUSES:
                raise InputError(f"Invalid status '{value}'")
            if key == "severity" and value not in SEVERITIES:
                raise InputError(f"Invalid severity '{value}'")
            if inv.get(key) != value:
                if key in ("status", "severity"):
                    self._event(inv, analyst, f"{key} changed", f"{inv.get(key) or '-'} → {value}")
                inv[key] = value
                changed.append(key)
        if changed:
            inv["updated"] = _now()
            self._write(inv)
        return inv

    def save_analysis(self, customer_id: str, inv_id: str, analysis: dict, analyst: str) -> dict:
        inv = self.get(customer_id, inv_id)
        inv["analysis"] = analysis
        eng = analysis.get("engine", {})
        if eng.get("mode") == "rules+llm":
            inv["llm_used"].append({"at": _now(), "provider": eng.get("provider"), "model": eng.get("model"),
                                    "external": eng.get("external")})
        if inv["status"] == "New":
            inv["status"] = "Investigating"
        self._event(inv, analyst, "analysed", eng.get("mode", "rules"))
        inv["updated"] = _now()
        self._write(inv)
        return inv

    def save_ticket(self, customer_id: str, inv_id: str, ticket: str, analyst: str) -> dict:
        inv = self.get(customer_id, inv_id)
        inv["ticket"] = ticket
        self._event(inv, analyst, "ticket generated")
        inv["updated"] = _now()
        self._write(inv)
        return inv

    @staticmethod
    def _event(inv: dict, analyst: str, action: str, detail: str = "") -> None:
        inv.setdefault("history", []).append({"at": _now(), "by": analyst, "action": action, "detail": detail})
        inv["history"] = inv["history"][-200:]
