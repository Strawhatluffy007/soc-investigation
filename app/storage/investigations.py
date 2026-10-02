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
EDITABLE = {"title", "status", "severity", "findings", "analyst_notes", "context", "ticket", "assigned_to",
            "risk", "soc_actions", "client_actions"}
MAX_TEXT = 200_000
MAX_FOLLOWUPS = 100
FOLLOWUP_KINDS = ("log", "note")


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

    def add_followup(self, customer_id: str, inv_id: str, *, kind: str, text: str, analyst: str,
                     source_name: str = "", max_log_chars: int = 2_000_000) -> dict:
        """Append analyst input given after the first analysis: more logs
        (Defender, raw) or a general note/question. Logs count towards the
        same size cap as the original log."""
        if kind not in FOLLOWUP_KINDS:
            raise InputError("Follow-up kind must be 'log' or 'note'.")
        if not text.strip():
            raise InputError("Follow-up input is empty.")
        inv = self.get(customer_id, inv_id)
        fus = inv.setdefault("followups", [])
        if len(fus) >= MAX_FOLLOWUPS:
            raise InputError(f"An investigation can hold at most {MAX_FOLLOWUPS} follow-ups.")
        if kind == "log" and len(combined_log(inv)) + len(text) > max_log_chars:
            raise InputError(f"Combined log would exceed {max_log_chars:,} characters.")
        fus.append({"id": f"F{len(fus) + 1}", "at": _now(), "by": analyst, "kind": kind,
                    "source_name": source_name[:200], "text": text[:MAX_TEXT], "chars": len(text)})
        self._event(inv, analyst, "follow-up added",
                    ("log" + (f" ({source_name})" if source_name else "")) if kind == "log" else "note")
        if inv["status"] in ("Resolved", "Closed"):
            self._event(inv, analyst, "status changed", f"{inv['status']} → Investigating")
            inv["status"] = "Investigating"
        inv["updated"] = _now()
        self._write(inv)
        return inv

    def set_followup_output(self, customer_id: str, inv_id: str, fid: str, output: dict) -> dict:
        """Attach what a follow-up produced (answer, new findings, ticket) so the
        timeline shows each input with its own result."""
        inv = self.get(customer_id, inv_id)
        for f in inv.get("followups") or []:
            if f["id"] == fid:
                f["output"] = output | {"at": _now()}
                self._write(inv)
                break
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


def followup_logs(inv: dict) -> list[dict]:
    return [f for f in inv.get("followups") or [] if f.get("kind") == "log"]


def combined_log(inv: dict) -> str:
    """Original log followed by every follow-up log, each under a separator."""
    parts = [inv.get("raw_log", "")]
    for f in followup_logs(inv):
        parts.append(f"# --- Additional log {f['id']}" + (f" ({f['source_name']})" if f.get("source_name") else "")
                     + f", added {f['at']} ---\n{f['text']}")
    return "\n\n".join(parts)


def followup_notes(inv: dict) -> str:
    """Analyst follow-up notes/questions, oldest first, for the LLM context."""
    return "\n\n".join(f"[{f['id']} {f['at']} by {f['by']}]\n{f['text']}"
                         for f in inv.get("followups") or [] if f.get("kind") == "note")
