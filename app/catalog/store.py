"""Catalog access and applying a table selection to a customer.

Applying writes one `schemas/catalog-<schema>.md` per selected schema into
the customer's folder and sets `schema_scope: selected` in customer.md, so
analysis, KQL generation and validation only see the selected tables.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.catalog.model import Catalog, CatalogSchema, parse_catalog, render_schema, render_table, sort_tables
from app.customers.store import CATALOG_PREFIX, CustomerStore
from app.security import InputError

_CUSTOM_HELP = """## Schema: Custom
Id: custom
Origin: custom
Time field: TimeGenerated

### MyApp_CL
Description: Example custom log table
| Column | Type | Description |
|---|---|---|
| TimeGenerated | datetime | Ingestion time |
| UserName_s | string | User |
"""


class CatalogStore:
    def __init__(self, path: Path):
        self.path = path
        self._cache: tuple[float, Catalog] | None = None
        self._lock = threading.Lock()

    def load(self) -> Catalog:
        if not self.path.is_file():
            return Catalog()
        mtime = self.path.stat().st_mtime
        with self._lock:
            if not self._cache or self._cache[0] != mtime:
                self._cache = (mtime, parse_catalog(self.path.read_text(encoding="utf-8")))
            return self._cache[1]

    def summary(self) -> dict:
        cat = self.load()
        generated = next((l for l in cat.preamble.splitlines() if l.startswith("Generated")), "")
        return {"exists": self.path.is_file(), "generated": generated,
                "schemas": [s.summary() for s in cat.schemas.values()]}

    def table(self, schema_id: str, name: str) -> dict:
        s = self.load().schemas.get(schema_id)
        t = s.tables.get(name) if s else None
        if not t:
            raise KeyError(name)
        return {**t.summary(), "schema": s.name,
                "columns": [{"name": c.name, "type": c.type, "description": c.description} for c in t.columns]}

    # -- custom sections (editable in the UI) --------------------------------
    def custom_markdown(self) -> str:
        custom = [render_schema(s) for s in self.load().schemas.values() if s.origin != "microsoft"]
        return "\n".join(custom) or _CUSTOM_HELP

    def save_custom(self, markdown: str) -> dict:
        parsed = parse_catalog(markdown)
        for s in parsed.schemas.values():
            if s.origin == "microsoft":
                raise InputError(f"Schema '{s.name}' has Origin: microsoft; custom sections must use Origin: custom.")
            s.origin = s.origin or "custom"
        cat = self.load()
        if any(sid in cat.schemas and cat.schemas[sid].origin == "microsoft" for sid in parsed.schemas):
            raise InputError("A custom schema id clashes with a Microsoft schema id; choose another Id.")
        from app.catalog.model import render_catalog
        merged = Catalog(preamble=cat.preamble or "Custom schema catalog.",
                         schemas={sid: s for sid, s in cat.schemas.items() if s.origin == "microsoft"})
        merged.schemas.update(parsed.schemas)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(render_catalog(merged), encoding="utf-8")
        tmp.replace(self.path)
        return {"schemas": len(parsed.schemas), "tables": sum(len(s.tables) for s in parsed.schemas.values())}

    # -- customer selection ----------------------------------------------------
    @staticmethod
    def selection(customers: CustomerStore, cid: str) -> dict:
        prof = customers.load(cid)
        sel: dict[str, list[str]] = {}
        for fname, text in prof.schema_files.items():
            if fname.startswith(CATALOG_PREFIX):
                sid = fname[len(CATALOG_PREFIX):-3]
                sel[sid] = re.findall(r"^### ([A-Za-z_][A-Za-z0-9_]*)", text, re.M)
        return {"scope": prof.schema_scope, "selection": sel, "ignored_tables": prof.ignored_tables,
                "table_count": len(prof.tables)}

    def apply(self, customers: CustomerStore, cid: str, selection: dict[str, list[str]], scope: str) -> dict:
        if scope not in ("selected", "all"):
            raise InputError("scope must be 'selected' or 'all'.")
        prof = customers.load(cid)
        cat = self.load()
        files: dict[str, str] = {}
        total = 0
        for sid, names in (selection or {}).items():
            schema: CatalogSchema | None = cat.schemas.get(sid)
            if not schema:
                raise InputError(f"Unknown schema '{sid}'. Refresh the page; the catalog may have changed.")
            missing = [n for n in names if n not in schema.tables]
            if missing:
                raise InputError(f"Not in the {schema.name} catalog: {', '.join(missing[:10])}")
            if not names:
                continue
            sub = CatalogSchema(id=sid, name=schema.name, origin=schema.origin, source=schema.source,
                                time_field=schema.time_field,
                                tables={n: schema.tables[n] for n in sorted(set(names), key=str.lower)})
            body = _by_category(sub)
            files[f"{CATALOG_PREFIX}{sid}.md"] = (
                f"# {prof.name}: {schema.name}\n\n"
                f"<!-- Generated from the schema catalog on {datetime.now(timezone.utc).isoformat(timespec='minutes')}. "
                "Change it in Customer config → Schema selection; manual edits are overwritten on the next apply. -->\n\n"
                + "\n".join(_with_product(body, schema.name)))
            total += len(sub.tables)
        if scope == "selected" and not total:
            raise InputError("Select at least one table, or choose 'Use all tables in the customer files'.")
        customers.replace_catalog_files(cid, files)
        customers.set_setting(cid, "schema_scope", scope)
        return {**self.selection(customers, cid), "written": sorted(files), "selected_tables": total}


def _by_category(schema: CatalogSchema) -> str:
    """Schema header lines, then tables under one `## <category>` heading each."""
    head = render_schema(CatalogSchema(id=schema.id, name=schema.name, origin=schema.origin,
                                       source=schema.source, time_field=schema.time_field))
    out = [head.split("\n", 1)[1].strip(), ""]
    current = None
    for t in sort_tables(schema.tables.values()):
        if t.group != current:
            current = t.group
            out += [f"## {current}", ""]
        out.append(render_table(t))
    return "\n".join(out)


def _with_product(body: str, product: str) -> list[str]:
    out = []
    for line in body.splitlines():
        out.append(line)
        if line.startswith("### "):
            out.append(f"Product: {product}")
    return out
