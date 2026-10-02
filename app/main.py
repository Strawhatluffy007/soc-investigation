"""FastAPI app: security middleware, static UI, API routes."""
from __future__ import annotations

import base64
import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import build_router
from app.config import load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("soc")

STATIC = Path(__file__).resolve().parent.parent / "static"
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


def create_app(settings=None) -> FastAPI:
    settings = settings or load_settings()
    if settings.exposed and not settings.auth_enabled:
        raise RuntimeError(f"SOC_BIND_ADDR={settings.bind_addr} exposes the app beyond localhost, "
                           "but SOC_AUTH_PASSWORD is not set. Refusing to start.")

    app = FastAPI(title="SOC Investigation Interface", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings

    @app.middleware("http")
    async def security(request: Request, call_next):
        if settings.auth_enabled and request.url.path != "/healthz":
            user = _basic_user(request.headers.get("authorization", ""), settings)
            if not user:
                return Response("Authentication required", status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="SOC", charset="UTF-8"'})
            request.state.user = user
        else:
            request.state.user = ""
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    app.include_router(build_router(settings), prefix="/api")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Internal error. See server logs."}, status_code=500)

    return app


def _basic_user(header: str, settings) -> str:
    if not header.lower().startswith("basic "):
        return ""
    try:
        user, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except Exception:
        return ""
    ok_user = secrets.compare_digest(user.encode(), settings.auth_user.encode())
    ok_pw = secrets.compare_digest(pw.encode(), settings.auth_password.encode())
    return user if ok_user and ok_pw else ""


app = create_app()
