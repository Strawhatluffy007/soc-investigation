"""Pull table schemas from Microsoft Learn (official docs) into the catalog.

Only public documentation pages on learn.microsoft.com are requested; no
customer data is involved. Run from the web interface (Schema catalog →
Pull from Microsoft) or: `python -m app.catalog.fetch [catalog.md]`.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from app.catalog.model import Catalog, CatalogSchema, CatalogTable, Column, parse_catalog, render_catalog

ALLOWED_HOST = "learn.microsoft.com"
USER_AGENT = "soc-investigation-schema-catalog/1.0 (+local)"


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    index_url: str
    time_field: str
    kind: str  # "azure-monitor" | "defender"


SOURCES = [
    Source("sentinel", "Microsoft Sentinel (Log Analytics)",
           "https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables-category", "TimeGenerated",
           "azure-monitor"),
    Source("defender-xdr", "Microsoft Defender XDR (Advanced Hunting)",
           "https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-schema-tables", "Timestamp", "defender"),
]


class _Tables(HTMLParser):
    """Collect every <table> on a page as rows of cell text, plus links in cells."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.links: list[list[list[str]]] = []
        self.row = self.cell = self.cell_link = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([]); self.links.append([])
        elif tag == "tr" and self.tables:
            self.row, self.row_links = [], []
        elif tag in ("td", "th") and self.row is not None:
            self.cell, self.cell_link = "", ""
        elif tag == "a" and self.cell is not None and not self.cell_link:
            self.cell_link = dict(attrs).get("href", "")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", self.cell).strip()); self.row_links.append(self.cell_link or "")
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.tables[-1].append(self.row); self.links[-1].append(self.row_links); self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def _check_url(url: str) -> str:
    u = urlparse(url)
    if u.scheme != "https" or u.hostname != ALLOWED_HOST:
        raise ValueError(f"Refusing to fetch non-Microsoft Learn URL: {url}")
    return url


class RateLimited(RuntimeError):
    pass


class Fetcher:
    """Polite client: few workers, a pause between requests, backoff on 429,
    and a stop once Microsoft Learn keeps throttling (try again later)."""

    def __init__(self, timeout: float = 30.0, workers: int = 2, delay: float = 0.4, max_throttled: int = 12):
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        self.workers = workers
        self.delay = delay
        self.max_throttled = max_throttled
        self._throttled = 0
        self._lock = threading.Lock()

    def get(self, url: str) -> str:
        last: Exception | None = None
        for attempt in range(5):
            if self._throttled >= self.max_throttled:
                raise RateLimited("Microsoft Learn is rate-limiting requests (HTTP 429). Try again in 15-30 minutes; "
                                  "tables fetched so far are kept.")
            time.sleep(self.delay)
            try:
                r = self.client.get(_check_url(url))
                if r.status_code == 200 and urlparse(str(r.url)).hostname == ALLOWED_HOST:
                    with self._lock:
                        self._throttled = 0
                    return r.text
                last = RuntimeError(f"HTTP {r.status_code}")
                if r.status_code == 404:
                    break
                if r.status_code in (429, 503):
                    with self._lock:
                        self._throttled += 1
                    ra = r.headers.get("retry-after", "")
                    time.sleep(min(int(ra), 120) if ra.isdigit() else min(10 * 2 ** attempt, 90))
                    continue
            except httpx.HTTPError as e:
                last = e
            time.sleep(1 + attempt)
        raise RuntimeError(f"{url}: {last}")

    # -- index pages -------------------------------------------------------
    def list_tables(self, src: Source) -> list[tuple[str, str, str]]:
        """[(table, page_url, description)]"""
        html = self.get(src.index_url)
        if src.kind == "azure-monitor":
            m = re.search(r'<h[23][^>]*id="security"', html)
            if not m:
                raise RuntimeError("Security category not found on the Azure Monitor tables page")
            end = re.search(r"<h[23][^>]*id=", html[m.end():])
            seg = html[m.end(): m.end() + end.start()] if end else html[m.end():]
            out = [(unescape(name).strip(), urljoin(src.index_url, href), "")
                   for href, name in re.findall(r'href="(tables/[^"#?]+)"[^>]*>([^<]+)<', seg)]
        else:
            p = _Tables(); p.feed(html)
            out = []
            for rows, links in zip(p.tables, p.links):
                if not rows or not rows[0] or rows[0][0].lower() != "table name":
                    continue
                for row, link in zip(rows[1:], links[1:]):
                    if row and link and link[0]:
                        name = row[0].split()[0]
                        out.append((name, urljoin(src.index_url, link[0]), row[1] if len(row) > 1 else ""))
        seen, uniq = set(), []
        for name, url, desc in out:
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) and name not in seen:
                seen.add(name); uniq.append((name, url, desc))
        return uniq

    # -- table pages ---------------------------------------------------------
    def table(self, src: Source, name: str, url: str, desc: str) -> CatalogTable:
        html = self.get(url)
        p = _Tables(); p.feed(html)
        cols: list[Column] = []
        for rows in p.tables:
            if not rows:
                continue
            head = [h.lower() for h in rows[0]]
            if head and head[0] in ("column", "column name") and len(head) >= 2:
                for r in rows[1:]:
                    if r and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", r[0]):
                        cols.append(Column(r[0], r[1] if len(r) > 1 else "", r[2] if len(r) > 2 else ""))
                break
        if not cols:
            raise RuntimeError(f"{url}: no column table found")
        seen: set[str] = set()
        cols = [c for c in cols if not (c.name in seen or seen.add(c.name))]
        if not desc:
            m = re.search(r'<meta name="description" content="([^"]*)"', html)
            d = unescape(m.group(1)) if m else ""
            desc = "" if d.startswith("Reference for") else d
            if not desc:
                attrs = {r[0]: r[1] for t in p.tables for r in t if len(r) == 2}
                desc = "; ".join(f"{k}: {attrs[k]}" for k in ("Categories", "Solutions") if attrs.get(k))
        names = [c.name for c in cols]
        if src.kind == "azure-monitor" and "TimeGenerated" not in names:
            # standard column on every Log Analytics table, not always listed
            cols.append(Column("TimeGenerated", "datetime", "Date and time the record was ingested (standard column)"))
            names.append("TimeGenerated")
        # Snapshot/inventory tables (e.g. DeviceTvm*) have no event time: leave it empty.
        tf = src.time_field if src.time_field in names else next(
            (n for n in names if n.endswith("Timestamp")), "")
        return CatalogTable(name=name, description=desc, source=url, time_field=tf, columns=cols)


def refresh_catalog(path: Path, sources: list[Source] = SOURCES, progress=None, fetcher: Fetcher | None = None) -> dict:
    """Rebuild the Microsoft sections of the catalog; custom sections are kept.
    progress(done, total, message) is called as pages complete."""
    f = fetcher or Fetcher()
    old = parse_catalog(path.read_text(encoding="utf-8")) if path.is_file() else Catalog()
    progress = progress or (lambda *a: None)
    jobs = []
    index_errors = []
    for src in sources:
        progress(0, 0, f"Reading table index: {src.name}")
        try:
            jobs += [(src, *t) for t in f.list_tables(src)]
        except Exception as e:  # keep this source's previous tables
            index_errors.append(f"{src.id} index: {e}"[:300])
    if index_errors and not jobs:
        raise RuntimeError("; ".join(index_errors))
    total, done, errors, lock = len(jobs), 0, list(index_errors), threading.Lock()
    results: dict[str, dict[str, CatalogTable]] = {s.id: {} for s in sources}

    def work(job):
        nonlocal done
        src, name, url, desc = job
        try:
            t = f.table(src, name, url, desc)
            with lock:
                results[src.id][name] = t
        except RateLimited as e:
            with lock:
                if not any(x.startswith("rate-limited") for x in errors):
                    errors.append(f"rate-limited: {e}")
        except Exception as e:  # keep going; report at the end
            with lock:
                errors.append(f"{src.id}/{name}: {e}"[:300])
        with lock:
            done += 1
            progress(done, total, f"{src.name}: {name}")

    with ThreadPoolExecutor(max_workers=f.workers) as pool:
        list(pool.map(work, jobs))

    new = Catalog(preamble=(
        f"Generated from Microsoft Learn on {datetime.now(timezone.utc).isoformat(timespec='minutes')}.\n"
        "Refresh it from the web interface (Schema catalog → Pull from Microsoft) or with "
        "`python -m app.catalog.fetch`.\n\n"
        "Sections with `Origin: microsoft` are replaced on every refresh. Add your own tables (custom logs, "
        "third-party connectors) under a section like `## Schema: Custom` with `Origin: custom`; those are kept."))
    for src in sources:
        tables = results[src.id]
        prev = old.schemas.get(src.id)
        if prev:  # keep tables whose page failed this time
            for name, t in prev.tables.items():
                tables.setdefault(name, t)
        new.schemas[src.id] = CatalogSchema(id=src.id, name=src.name, origin="microsoft", source=src.index_url,
                                            time_field=src.time_field,
                                            tables=dict(sorted(tables.items(), key=lambda kv: kv[0].lower())))
    for sid, s in old.schemas.items():
        if s.origin != "microsoft" and sid not in new.schemas:
            new.schemas[sid] = s
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(render_catalog(new), encoding="utf-8")
    tmp.replace(path)
    fetched = sum(1 for src in sources for t in results[src.id].values() if t.source.startswith("https://"))
    return {"tables": sum(len(s.tables) for s in new.schemas.values()), "fetched": min(fetched, total),
            "errors": errors}


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "catalog/schema-catalog.md")
    res = refresh_catalog(target, progress=lambda d, t, m: print(f"[{d}/{t}] {m}", file=sys.stderr) if d % 25 == 0 else None)
    print(res["tables"], "tables;", len(res["errors"]), "errors")
    for e in res["errors"][:20]:
        print("  ", e)
