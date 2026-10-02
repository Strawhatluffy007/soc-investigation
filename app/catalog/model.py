"""Read and write `catalog/schema-catalog.md`.

Layout:
    # Schema catalog
    ## Schema: <name>            one section per schema / product
    Id: <slug>
    Origin: microsoft | custom    `microsoft` sections are replaced on refresh
    Source: <url>
    Time field: <column>
    ### <TableName>               one block per table
    Category: Apps & identities   optional; defaults to app/catalog/categories.py
    Description: ...
    Source: <url>
    | Column | Type | Description |
    |---|---|---|
    | TimeGenerated | datetime | ... |
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.catalog.categories import categorize, order
from app.customers.schema import split_sections
from app.security import slugify

_KV = re.compile(r"^\s*(id|origin|source|time field|description|product|category)\s*:\s*(.*)$", re.I)
_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\s*(?:\(([^)]*)\))?\s*(?:[-:–]\s*(.*))?$")
_HEADER_TYPES = {"type", "data type", "role", "description"}
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class Column:
    name: str
    type: str = ""
    description: str = ""


@dataclass
class CatalogTable:
    name: str
    description: str = ""
    source: str = ""
    time_field: str = ""
    columns: list[Column] = field(default_factory=list)
    category: str = ""

    @property
    def group(self) -> str:
        return self.category or categorize(self.name)

    def summary(self) -> dict:
        return {"name": self.name, "description": self.description, "source": self.source,
                "time_field": self.time_field, "field_count": len(self.columns), "category": self.group}


@dataclass
class CatalogSchema:
    id: str
    name: str
    origin: str = "custom"
    source: str = ""
    time_field: str = ""
    tables: dict[str, CatalogTable] = field(default_factory=dict)

    def summary(self) -> dict:
        return {"id": self.id, "name": self.name, "origin": self.origin, "source": self.source,
                "time_field": self.time_field, "tables": [t.summary() for t in sort_tables(self.tables.values())]}


@dataclass
class Catalog:
    preamble: str = ""
    schemas: dict[str, CatalogSchema] = field(default_factory=dict)


def _cell(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("|", "/")).strip()


def parse_catalog(markdown: str) -> Catalog:
    cat = Catalog()
    for heading, body in split_sections(markdown, level=2):
        if not heading:
            cat.preamble = "\n".join(l for l in body.splitlines() if not l.startswith("# ")).strip()
            continue
        if not heading.lower().startswith("schema:"):
            continue
        name = heading.split(":", 1)[1].strip()
        schema = CatalogSchema(id=slugify(name), name=name)
        head, _, _ = body.partition("\n### ")
        for line in head.splitlines():
            kv = _KV.match(line)
            if kv:
                key, val = kv.group(1).lower(), kv.group(2).strip()
                if key == "id" and val:
                    schema.id = slugify(val)
                elif key == "origin":
                    schema.origin = val.lower()
                elif key == "source":
                    schema.source = val
                elif key == "time field":
                    schema.time_field = val
        for theading, tbody in split_sections(body, level=3):
            m = re.match(r"`?([A-Za-z_][A-Za-z0-9_]*)`?", theading or "")
            if not m:
                continue
            table = CatalogTable(name=m.group(1), time_field=schema.time_field)
            for line in tbody.splitlines():
                kv = _KV.match(line)
                if kv:
                    key, val = kv.group(1).lower(), kv.group(2).strip()
                    if key == "description":
                        table.description = val
                    elif key == "source":
                        table.source = val
                    elif key == "time field":
                        table.time_field = val
                    elif key == "category":
                        table.category = _cell(val)[:60]
                    continue
                row = _ROW.match(line)
                if row:
                    cells = [c.strip().strip("`") for c in row.group(1).split("|")]
                    if not _NAME.match(cells[0]) or (len(cells) > 1 and cells[1].lower() in _HEADER_TYPES):
                        continue
                    cells += ["", ""]
                    table.columns.append(Column(cells[0], cells[1], cells[2]))
                    continue
                b = _BULLET.match(line)
                if b:
                    table.columns.append(Column(b.group(1), (b.group(2) or ""), (b.group(3) or "").strip()))
            seen, cols = set(), []
            for c in table.columns:
                if c.name not in seen:
                    seen.add(c.name)
                    cols.append(c)
            table.columns = cols
            if table.columns:
                schema.tables[table.name] = table
        cat.schemas[schema.id] = schema
    return cat


def sort_tables(tables) -> list[CatalogTable]:
    return sorted(tables, key=lambda t: (order(t.group), t.group.lower(), t.name.lower()))


def render_table(table: CatalogTable, product: str = "") -> str:
    out = [f"### {table.name}"]
    if product:
        out.append(f"Product: {product}")
    out.append(f"Category: {table.group}")
    if table.time_field:
        out.append(f"Time field: {table.time_field}")
    if table.description:
        out.append(f"Description: {_cell(table.description)}")
    if table.source:
        out.append(f"Source: {table.source}")
    out += ["", "| Column | Type | Description |", "|---|---|---|"]
    out += [f"| {c.name} | {_cell(c.type)} | {_cell(c.description)[:200].strip()} |" for c in table.columns]
    return "\n".join(out) + "\n"


def render_schema(schema: CatalogSchema) -> str:
    out = [f"## Schema: {schema.name}", f"Id: {schema.id}", f"Origin: {schema.origin}"]
    if schema.source:
        out.append(f"Source: {schema.source}")
    if schema.time_field:
        out.append(f"Time field: {schema.time_field}")
    out.append("")
    for t in sort_tables(schema.tables.values()):
        out.append(render_table(t))
    return "\n".join(out)


def render_catalog(cat: Catalog) -> str:
    parts = ["# Schema catalog", "", cat.preamble.strip(), ""]
    for s in cat.schemas.values():
        parts.append(render_schema(s))
    return "\n".join(parts).rstrip() + "\n"
