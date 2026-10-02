"""HTTP API. Every investigation route is nested under its customer, and the
store checks the pair, so one customer's investigation can't be opened
through another customer's URL."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.audit import AuditLog
from app.catalog.store import CatalogStore
from app.config import Settings
from app.customers.store import CustomerProfile, CustomerStore
from app.investigation.engine import analyze
from app.kql.validator import validate_kql
from app.llm.base import LLMError
from app.llm.factory import LLMGate
from app.security import InputError, clean_text, decode_upload
from app.storage.investigations import SEVERITIES, STATUSES, InvestigationStore
from app.tickets.render import render_ticket


class CustomerIn(BaseModel):
    name: str
    id: str | None = None


class RenameIn(BaseModel):
    name: str


class FileIn(BaseModel):
    content: str
    filename: str = ""


class AnalyzeIn(BaseModel):
    use_llm: bool = False
    confirm_external: bool = False


class UpdateIn(BaseModel):
    title: str | None = None
    status: str | None = None
    severity: str | None = None
    findings: str | None = None
    analyst_notes: str | None = None
    context: str | None = None
    ticket: str | None = None
    assigned_to: str | None = None


class SelectionIn(BaseModel):
    selection: dict[str, list[str]] = {}
    scope: str = "selected"


class KQLIn(BaseModel):
    query: str


_NAME_RE = re.compile(r"[^\w .@'-]")


def build_router(settings: Settings) -> APIRouter:
    r = APIRouter()
    customers = CustomerStore(settings.customers_dir, settings.default_template)
    store = InvestigationStore(settings.data_dir)
    audit = AuditLog(settings.data_dir / "audit.log")
    gate = LLMGate(settings)
    catalog = CatalogStore(settings.catalog_path)
    job = {"running": False, "done": 0, "total": 0, "message": "", "started_at": "", "finished_at": "",
           "result": None, "error": ""}
    job_lock = threading.Lock()

    def analyst(request: Request) -> str:
        if request.state.user:
            return request.state.user
        name = _NAME_RE.sub("", request.headers.get("x-analyst", ""))[:60].strip()
        return name or "analyst"

    def profile(cid: str) -> CustomerProfile:
        try:
            return customers.load(cid)
        except InputError as e:
            raise HTTPException(400, str(e))
        except KeyError:
            raise HTTPException(404, "Customer not found")

    def get_inv(cid: str, iid: str) -> dict:
        try:
            return store.get(cid, iid)
        except InputError as e:
            raise HTTPException(400, str(e))
        except KeyError:
            raise HTTPException(404, "Investigation not found")

    def run_analysis(request: Request, prof: CustomerProfile, inv: dict, use_llm: bool, confirm: bool) -> dict:
        try:
            provider = gate.for_run(prof, use_llm, confirm)
        except LLMError as e:
            raise HTTPException(400, str(e))
        who = analyst(request)
        if provider is not None:
            audit.record("llm.send", analyst=who, customer=prof.id, investigation=inv["id"],
                         provider=provider.name, model=provider.model, external=provider.is_external,
                         log_chars=min(len(inv["raw_log"]), settings.llm_max_log_chars))
        result = analyze(prof, inv["raw_log"], inv.get("context", ""), provider,
                         settings.llm_max_log_chars, settings.llm_max_context_chars)
        audit.record("investigation.analyze", analyst=who, customer=prof.id, investigation=inv["id"],
                     mode=result["engine"]["mode"], llm_error=bool(result["engine"]["error"]),
                     queries=len(result["kql_queries"]))
        return store.save_analysis(prof.id, inv["id"], result, who)

    # ------------------------------------------------------------ status
    @r.get("/status")
    def status(request: Request):
        return {"analyst": analyst(request), "auth": settings.auth_enabled, "llm": gate.status(),
                "statuses": STATUSES, "severities": SEVERITIES[1:],
                "limits": {"upload_bytes": settings.max_upload_bytes, "log_chars": settings.max_log_chars}}

    # ------------------------------------------------------------ schema catalog
    @r.get("/catalog")
    def get_catalog():
        return {**catalog.summary(), "fetch_enabled": settings.catalog_fetch_enabled}

    @r.get("/catalog/tables/{schema_id}/{table}")
    def catalog_table(schema_id: str, table: str):
        try:
            return catalog.table(schema_id, table)
        except KeyError:
            raise HTTPException(404, "Table not in catalog")

    @r.get("/catalog/custom")
    def catalog_custom():
        return {"content": catalog.custom_markdown()}

    @r.put("/catalog/custom")
    def save_catalog_custom(body: FileIn, request: Request):
        try:
            res = catalog.save_custom(clean_text(body.content, 2_000_000))
        except InputError as e:
            raise HTTPException(400, str(e))
        audit.record("catalog.custom.write", analyst=analyst(request), **res)
        return res

    @r.get("/catalog/refresh")
    def refresh_status():
        return job

    @r.post("/catalog/refresh", status_code=202)
    def refresh_start(request: Request):
        if not settings.catalog_fetch_enabled:
            raise HTTPException(403, "Pulling from Microsoft Learn is disabled (CATALOG_FETCH_ENABLED=false).")
        with job_lock:
            if job["running"]:
                return job
            job.update(running=True, done=0, total=0, message="Starting", result=None, error="",
                       started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), finished_at="")
        who = analyst(request)
        audit.record("catalog.refresh.start", analyst=who)

        def progress(done, total, message):
            job.update(done=done, total=total or job["total"], message=message)

        def run():
            from app.catalog.fetch import refresh_catalog
            try:
                job["result"] = refresh_catalog(settings.catalog_path, progress=progress)
                audit.record("catalog.refresh.done", analyst=who, tables=job["result"]["tables"],
                             errors=len(job["result"]["errors"]))
            except Exception as e:
                job["error"] = f"{type(e).__name__}: {e}"[:500]
                audit.record("catalog.refresh.failed", analyst=who, error=job["error"])
            finally:
                job.update(running=False, finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))

        threading.Thread(target=run, daemon=True, name="catalog-refresh").start()
        return job

    @r.get("/customers/{cid}/catalog-selection")
    def get_selection(cid: str):
        profile(cid)
        return catalog.selection(customers, cid)

    @r.put("/customers/{cid}/catalog-selection")
    def put_selection(cid: str, body: SelectionIn, request: Request):
        profile(cid)
        try:
            res = catalog.apply(customers, cid, body.selection, body.scope)
        except InputError as e:
            raise HTTPException(400, str(e))
        audit.record("customer.schema.apply", analyst=analyst(request), customer=cid, scope=body.scope,
                     tables=res["selected_tables"], files=res["written"])
        return res

    # ------------------------------------------------------------ customers
    @r.get("/customers")
    def list_customers():
        return customers.list()

    @r.post("/customers", status_code=201)
    def create_customer(body: CustomerIn, request: Request):
        try:
            prof = customers.create(clean_text(body.name, 200), body.id)
        except InputError as e:
            raise HTTPException(400, str(e))
        audit.record("customer.create", analyst=analyst(request), customer=prof.id)
        return prof.summary()

    @r.get("/customers/{cid}")
    def get_customer(cid: str):
        prof = profile(cid)
        return {**prof.to_dict(), "llm": gate.status(prof)}

    @r.patch("/customers/{cid}")
    def rename_customer(cid: str, body: RenameIn, request: Request):
        old = profile(cid).name
        try:
            prof = customers.rename(cid, body.name)
        except InputError as e:
            raise HTTPException(400, str(e))
        audit.record("customer.rename", analyst=analyst(request), customer=cid, old_name=old, new_name=prof.name)
        return {**prof.to_dict(), "llm": gate.status(prof)}

    @r.delete("/customers/{cid}/files/{kind}")
    def delete_file(cid: str, kind: str, request: Request, filename: str = ""):
        profile(cid)
        try:
            customers.delete_file(cid, kind, filename)
        except InputError as e:
            raise HTTPException(400, str(e))
        except (KeyError, FileNotFoundError):
            raise HTTPException(404, "File not found")
        audit.record("customer.file.delete", analyst=analyst(request), customer=cid, kind=kind, filename=filename)
        prof = profile(cid)
        return {"ok": True, "warnings": prof.warnings, "tables": len(prof.tables)}

    @r.get("/customers/{cid}/files/{kind}")
    def read_file(cid: str, kind: str, filename: str = ""):
        prof = profile(cid)
        if kind == "template" and prof.ticket_template_source == "default":
            return {"content": prof.ticket_template, "source": "default"}
        try:
            return {"content": customers.read_file(cid, kind, filename), "source": "customer"}
        except InputError as e:
            raise HTTPException(400, str(e))
        except (KeyError, FileNotFoundError):
            raise HTTPException(404, "File not found")

    @r.put("/customers/{cid}/files/{kind}")
    def write_file(cid: str, kind: str, body: FileIn, request: Request):
        profile(cid)
        try:
            customers.write_file(cid, kind, clean_text(body.content), body.filename)
        except InputError as e:
            raise HTTPException(400, str(e))
        audit.record("customer.file.write", analyst=analyst(request), customer=cid, kind=kind,
                     filename=body.filename, chars=len(body.content))
        prof = profile(cid)
        return {"ok": True, "warnings": prof.warnings, "tables": len(prof.tables)}

    @r.post("/customers/{cid}/kql/validate")
    def validate(cid: str, body: KQLIn):
        return validate_kql(body.query[:50_000], profile(cid))

    @r.get("/customers/{cid}/audit")
    def customer_audit(cid: str, limit: int = 100):
        profile(cid)
        return audit.tail(min(limit, 500), customer=cid)

    # ------------------------------------------------------------ investigations
    @r.get("/customers/{cid}/investigations")
    def list_investigations(cid: str):
        profile(cid)
        return store.list(cid)

    @r.post("/customers/{cid}/investigations", status_code=201)
    async def create_investigation(cid: str, request: Request, title: str = Form(""), raw_log: str = Form(""),
                                   context: str = Form(""), analyze_now: bool = Form(True),
                                   use_llm: bool = Form(False), confirm_external: bool = Form(False),
                                   file: UploadFile | None = File(None)):
        prof = profile(cid)
        source = ""
        try:
            if file is not None and file.filename:
                data = await file.read(settings.max_upload_bytes + 1)
                upload = decode_upload(data, settings.max_upload_bytes)
                raw_log = (raw_log + "\n" + upload).strip() if raw_log.strip() else upload
                source = re.sub(r"[^\w.\-]", "_", file.filename)[:120]
            raw_log = clean_text(raw_log, settings.max_log_chars)
            context = clean_text(context, 20_000)
        except InputError as e:
            raise HTTPException(400, str(e))
        if not raw_log.strip():
            raise HTTPException(400, "Paste a log or upload a file.")
        who = analyst(request)
        inv = store.create(cid, title=clean_text(title, 300), raw_log=raw_log, context=context, analyst=who,
                           source_name=source)
        audit.record("investigation.create", analyst=who, customer=cid, investigation=inv["id"],
                     log_chars=len(raw_log), upload=bool(source))
        if analyze_now:
            from starlette.concurrency import run_in_threadpool
            inv = await run_in_threadpool(run_analysis, request, prof, inv, use_llm, confirm_external)
        return inv

    @r.get("/customers/{cid}/investigations/{iid}")
    def get_investigation(cid: str, iid: str, request: Request):
        inv = get_inv(cid, iid)
        audit.record("investigation.view", analyst=analyst(request), customer=cid, investigation=iid)
        return inv

    @r.patch("/customers/{cid}/investigations/{iid}")
    def update_investigation(cid: str, iid: str, body: UpdateIn, request: Request):
        get_inv(cid, iid)
        changes = {k: clean_text(v, 200_000) for k, v in body.model_dump().items() if v is not None}
        try:
            inv = store.update(cid, iid, changes, analyst(request))
        except InputError as e:
            raise HTTPException(400, str(e))
        audit.record("investigation.update", analyst=analyst(request), customer=cid, investigation=iid,
                     fields=sorted(changes))
        return inv

    @r.post("/customers/{cid}/investigations/{iid}/analyze")
    def reanalyze(cid: str, iid: str, body: AnalyzeIn, request: Request):
        prof = profile(cid)
        return run_analysis(request, prof, get_inv(cid, iid), body.use_llm, body.confirm_external)

    @r.post("/customers/{cid}/investigations/{iid}/ticket")
    def ticket(cid: str, iid: str, request: Request):
        prof = profile(cid)
        inv = get_inv(cid, iid)
        who = analyst(request)
        text, missing = render_ticket(prof.ticket_template, inv, prof, who)
        store.save_ticket(cid, iid, text, who)
        audit.record("ticket.generate", analyst=who, customer=cid, investigation=iid,
                     template=prof.ticket_template_source, missing=missing)
        return {"ticket": text, "missing": missing, "template_source": prof.ticket_template_source}

    return r
