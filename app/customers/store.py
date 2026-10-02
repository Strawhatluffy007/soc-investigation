"""Customer knowledge, loaded from `customers/<id>/`.

Layout per customer:
    customer.md               environment, tables, notes, KQL and ticket guidance
    schemas/*.md              additional table definitions (same format)
    templates/incident-ticket.md   optional ticket template override
    examples/                 sample logs (not loaded into analysis)

Every path is resolved from a validated slug and checked to stay inside
that customer's directory, so one customer's request can never read
another's files.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app.customers.schema import TableSchema, parse_bullets, parse_settings, parse_tables, split_sections
from app.security import EXAMPLE_NAME_RE, FILENAME_RE, InputError, clean_text, slugify, valid_slug

TEMPLATE_DIR_NAME = "_template"
CATALOG_PREFIX = "catalog-"  # schemas/catalog-<schema>.md are written by the schema catalog


@dataclass
class CustomerProfile:
    id: str
    name: str
    markdown: str
    environment: list[str] = field(default_factory=list)
    settings: dict[str, str] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)
    tables: dict[str, TableSchema] = field(default_factory=dict)
    schema_files: dict[str, str] = field(default_factory=dict)
    example_files: list[str] = field(default_factory=list)
    ignored_tables: list[str] = field(default_factory=list)
    ticket_template: str = ""
    ticket_template_source: str = ""
    warnings: list[str] = field(default_factory=list)

    def section(self, *keywords: str) -> str:
        """Body of the first `##` section whose heading contains any keyword."""
        for heading, body in self.sections.items():
            low = heading.lower()
            if any(k in low for k in keywords):
                return body
        return ""

    @property
    def default_lookback(self) -> str:
        return self.settings.get("default_lookback", "7d")

    @property
    def allow_external_llm(self) -> bool:
        return self.settings.get("allow_external_llm", "true").lower() in {"true", "yes", "1"}

    @property
    def schema_scope(self) -> str:
        return "selected" if self.settings.get("schema_scope", "").lower() == "selected" else "all"

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "environment": self.environment,
            "table_count": len(self.tables),
            "allow_external_llm": self.allow_external_llm,
        }

    def to_dict(self) -> dict:
        return {
            **self.summary(),
            "settings": self.settings,
            "tables": [t.to_dict() for t in self.tables.values()],
            "schema_files": sorted(self.schema_files),
            "example_files": self.example_files,
            "schema_scope": self.schema_scope,
            "ignored_tables": self.ignored_tables,
            "ticket_template_source": self.ticket_template_source,
            "investigation_notes": self.section("investigation"),
            "kql_guidelines": self.section("kql"),
            "ticket_requirements": self.section("ticket"),
            "warnings": self.warnings,
        }


class CustomerStore:
    def __init__(self, root: Path, default_template: Path):
        self.root = root
        self.default_template = default_template
        root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[tuple, CustomerProfile]] = {}

    # -- paths -----------------------------------------------------------
    def _dir(self, customer_id: str) -> Path:
        if not valid_slug(customer_id):
            raise InputError("Invalid customer id.")
        path = (self.root / customer_id).resolve()
        if path.parent != self.root.resolve():
            raise InputError("Invalid customer id.")
        return path

    def exists(self, customer_id: str) -> bool:
        try:
            return (self._dir(customer_id) / "customer.md").is_file()
        except InputError:
            return False

    # -- read ------------------------------------------------------------
    def list(self) -> list[dict]:
        out = []
        for child in sorted(self.root.iterdir()):
            if child.is_dir() and valid_slug(child.name) and (child / "customer.md").is_file():
                try:
                    out.append(self.load(child.name).summary())
                except Exception as exc:  # a broken file must not hide the others
                    out.append({"id": child.name, "name": child.name, "error": str(exc)})
        return out

    def load(self, customer_id: str) -> CustomerProfile:
        cdir = self._dir(customer_id)
        md_path = cdir / "customer.md"
        if not md_path.is_file():
            raise KeyError(customer_id)
        sig = self._signature(cdir)
        cached = self._cache.get(customer_id)
        if cached and cached[0] == sig:
            return cached[1]
        profile = self._load(customer_id, cdir, md_path)
        self._cache[customer_id] = (sig, profile)
        return profile

    def _signature(self, cdir: Path) -> tuple:
        items = []
        for p in [cdir / "customer.md", *(cdir / d for d in ("schemas", "templates", "examples")), self.default_template]:
            if p.is_dir():
                items += [(f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in sorted(p.iterdir())]
                items.append((str(p), p.stat().st_mtime_ns))
            elif p.is_file():
                items.append((str(p), p.stat().st_mtime_ns, p.stat().st_size))
        return tuple(items)

    def _load(self, customer_id: str, cdir: Path, md_path: Path) -> CustomerProfile:
        markdown = md_path.read_text(encoding="utf-8")
        profile = CustomerProfile(id=customer_id, name=customer_id, markdown=markdown)

        for line in markdown.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                profile.name = title.split(":", 1)[1].strip() if title.lower().startswith("customer:") else title
                break

        for heading, body in split_sections(markdown, level=2):
            if not heading:
                continue
            profile.sections[heading] = body
            low = heading.lower()
            if low.startswith("environment"):
                profile.environment = parse_bullets(body)
            elif low.startswith("settings"):
                profile.settings = parse_settings(body)
            elif "table" in low or "schema" in low:
                for t in parse_tables(body, "customer.md"):
                    profile.tables[t.name] = t

        schema_dir = cdir / "schemas"
        if schema_dir.is_dir():
            for f in sorted(schema_dir.glob("*.md")):
                text = f.read_text(encoding="utf-8")
                profile.schema_files[f.name] = text
                for t in parse_tables(text, f"schemas/{f.name}"):
                    if t.name in profile.tables:
                        existing = profile.tables[t.name]
                        existing.fields += [x for x in t.fields if x not in existing.fields]
                        existing.product = existing.product or t.product
                        existing.description = existing.description or t.description
                        existing.time_field_hint = existing.time_field_hint or t.time_field_hint
                        for role, fname in t.role_hints.items():
                            existing.role_hints.setdefault(role, fname)
                    else:
                        profile.tables[t.name] = t

        ex_dir = cdir / "examples"
        if ex_dir.is_dir():
            profile.example_files = sorted(f.name for f in ex_dir.iterdir()
                                           if f.is_file() and EXAMPLE_NAME_RE.match(f.name))

        tpl = cdir / "templates" / "incident-ticket.md"
        if tpl.is_file():
            profile.ticket_template = tpl.read_text(encoding="utf-8")
            profile.ticket_template_source = "customer"
        elif self.default_template.is_file():
            profile.ticket_template = self.default_template.read_text(encoding="utf-8")
            profile.ticket_template_source = "default"

        if profile.schema_scope == "selected":
            selected = {t.name for f, text in profile.schema_files.items() if f.startswith(CATALOG_PREFIX)
                        for t in parse_tables(text, f)}
            profile.ignored_tables = sorted(n for n in profile.tables if n not in selected)
            profile.tables = {n: t for n, t in profile.tables.items() if n in selected}
            if not selected:
                profile.warnings.append("schema_scope is 'selected' but no catalog tables are selected. "
                                        "Use Customer config → Schema selection.")

        if not profile.tables:
            profile.warnings.append("No tables found. Add `### TableName` blocks under a "
                                    "'## ... Tables' section or in schemas/*.md.")
        for t in profile.tables.values():
            if not t.role("time") and not t.source.startswith("schemas/" + CATALOG_PREFIX):
                profile.warnings.append(f"Table {t.name} has no time field (TimeGenerated/Timestamp).")
        return profile

    # -- write -----------------------------------------------------------
    def create(self, name: str, customer_id: str | None = None) -> CustomerProfile:
        cid = customer_id or slugify(name)
        if not valid_slug(cid) or cid == TEMPLATE_DIR_NAME:
            raise InputError("Customer id must be lowercase letters, digits and dashes.")
        cdir = self._dir(cid)
        if cdir.exists():
            raise InputError(f"Customer '{cid}' already exists.")
        template = self.root / TEMPLATE_DIR_NAME
        if template.is_dir():
            shutil.copytree(template, cdir)
            md = (cdir / "customer.md").read_text(encoding="utf-8")
            md = md.replace("{{customer_name}}", name.strip() or cid)
        else:
            cdir.mkdir()
            md = f"# Customer: {name.strip() or cid}\n\n## Environment\n\n## Defender Tables\n"
        (cdir / "customer.md").write_text(md, encoding="utf-8")
        for sub in ("schemas", "templates", "examples"):
            (cdir / sub).mkdir(exist_ok=True)
        return self.load(cid)

    def rename(self, customer_id: str, name: str) -> CustomerProfile:
        """Change the display name (the `# ` title of customer.md). The id and
        folder stay the same so existing investigations keep working."""
        name = clean_text(name, 200).replace("\n", " ").strip()
        if not name:
            raise InputError("Customer name cannot be empty.")
        path = self._file(customer_id, "customer", "")
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith("# "):
                prefix = "Customer: " if line[2:].strip().lower().startswith("customer:") else ""
                lines[i] = f"# {prefix}{name}"
                break
        else:
            lines.insert(0, f"# Customer: {name}")
        self.write_file(customer_id, "customer", "\n".join(lines) + "\n")
        return self.load(customer_id)

    def set_setting(self, customer_id: str, key: str, value: str) -> None:
        """Set `- key: value` under `## Settings` in customer.md (adding the section if needed)."""
        path = self._file(customer_id, "customer", "")
        lines = path.read_text(encoding="utf-8").splitlines()
        start = next((i for i, l in enumerate(lines) if l.lower().startswith("## settings")), None)
        entry = f"- {key}: {value}"
        if start is None:
            title = next((i for i, l in enumerate(lines) if l.startswith("# ")), -1)
            lines[title + 1:title + 1] = ["", "## Settings", entry]
        else:
            end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            idx = next((i for i in range(start + 1, end)
                        if re.match(rf"^\s*[-*]\s+`?{re.escape(key)}`?\s*:", lines[i], re.I)), None)
            if idx is not None:
                lines[idx] = entry
            else:
                last = max([i for i in range(start + 1, end) if lines[i].strip()] or [start])
                lines.insert(last + 1, entry)
        self.write_file(customer_id, "customer", "\n".join(lines) + "\n")

    def replace_catalog_files(self, customer_id: str, files: dict[str, str]) -> None:
        """Write schemas/catalog-*.md exactly as given; remove other catalog-*.md files."""
        sdir = self._dir(customer_id) / "schemas"
        sdir.mkdir(exist_ok=True)
        for name in files:
            if not (name.startswith(CATALOG_PREFIX) and FILENAME_RE.match(name)):
                raise InputError(f"Bad catalog file name {name}")
        for old in sdir.glob(CATALOG_PREFIX + "*.md"):
            if old.name not in files:
                old.unlink()
        for name, text in files.items():
            tmp = sdir / (name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(sdir / name)

    def delete_file(self, customer_id: str, kind: str, filename: str = "") -> None:
        if kind == "customer":
            raise InputError("customer.md cannot be deleted.")
        path = self._file(customer_id, kind, filename)
        if not path.is_file():
            raise FileNotFoundError(filename or kind)
        path.unlink()

    def read_file(self, customer_id: str, kind: str, filename: str = "") -> str:
        return self._file(customer_id, kind, filename).read_text(encoding="utf-8")

    def write_file(self, customer_id: str, kind: str, content: str, filename: str = "") -> None:
        if len(content) > 1_000_000:
            raise InputError("File too large (1 MB max).")
        path = self._file(customer_id, kind, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    def _file(self, customer_id: str, kind: str, filename: str) -> Path:
        cdir = self._dir(customer_id)
        if not (cdir / "customer.md").is_file():
            raise KeyError(customer_id)
        if kind == "customer":
            return cdir / "customer.md"
        if kind == "template":
            return cdir / "templates" / "incident-ticket.md"
        if kind == "schema":
            if not FILENAME_RE.match(filename or ""):
                raise InputError("Schema file name must look like 'defender-xdr.md'.")
            return cdir / "schemas" / filename
        if kind == "example":
            if not EXAMPLE_NAME_RE.match(filename or ""):
                raise InputError("Example file name must look like 'failed-signin.json' (.json .jsonl .csv .tsv .txt .log .xml .md).")
            return cdir / "examples" / filename
        raise InputError("Unknown file kind.")
