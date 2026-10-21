"""FastAPI app: serves the static site and the optional /api endpoints.

Run from the project root:  uvicorn backend.app.main:app --reload
"""
from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import assistant as ai
from . import contact as ct
from .knowledge import load_portfolio, render_facts
from .ratelimit import RateLimiter
from .settings import ROOT, Settings, load_settings

log = logging.getLogger("portfolio")
MAX_BODY = 16 * 1024
mimetypes.add_type("image/webp", ".webp")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://api.github.com; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")


def client_ip(request: Request, trust_proxy: bool) -> str:
    """With TRUST_PROXY=1 we assume exactly one trusted proxy and use the last X-Forwarded-For entry
    (the one that proxy appended). Never enable it unless a proxy really sits in front."""
    if trust_proxy:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is None:
        load_dotenv(ROOT / ".env")  # local development only; the file is git-ignored
        settings = load_settings()
    s = settings
    facts = render_facts(load_portfolio(s.root))
    system = ai.SYSTEM.format(name=load_portfolio(s.root)["name"], facts=facts)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = httpx.AsyncClient()
        yield
        await app.state.http.aclose()

    app = FastAPI(title="Portfolio API", lifespan=lifespan,
                  docs_url="/docs" if s.enable_docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if s.enable_docs else None)
    app.state.settings = s
    app.state.contact_limiter = RateLimiter([(5, 600), (20, 86400)])
    app.state.chat_limiter = RateLimiter([(10, 60), (60, 3600)])

    if s.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(s.allowed_origins), allow_methods=["GET", "POST"],
                           allow_headers=["Content-Type"], max_age=600)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api") and int(request.headers.get("content-length") or 0) > MAX_BODY:
            return JSONResponse({"ok": False, "error": "payload_too_large"}, status_code=413)
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith("/api"):
            resp.headers.setdefault("Content-Security-Policy", CSP)
        return resp

    # ---------------- API ----------------
    @app.get("/api/health")
    async def health():
        return JSONResponse({"ok": True, "assistant": s.assistant_enabled, "contact": s.contact_enabled},
                            headers={"Cache-Control": "no-store"})

    @app.post("/api/contact")
    async def contact(data: ct.ContactIn, request: Request):
        if not s.contact_enabled:
            return JSONResponse({"ok": False, "error": "contact_unavailable"}, status_code=503)
        allowed, retry = app.state.contact_limiter.hit(client_ip(request, s.trust_proxy))
        if not allowed:
            return JSONResponse({"ok": False, "error": "rate_limited", "retry_after": retry}, status_code=429, headers={"Retry-After": str(retry)})
        if data.website.strip():  # honeypot tripped: pretend success so bots learn nothing
            log.info("contact honeypot tripped")
            return {"ok": True}
        errs = ct.validate_contact(data)
        if errs:
            return JSONResponse({"ok": False, "error": "validation", "fields": errs}, status_code=422)
        if data.elapsed_ms < s.min_fill_seconds * 1000:
            return JSONResponse({"ok": False, "error": "too_fast"}, status_code=400)
        try:
            await run_in_threadpool(ct.send_email, s, ct.build_email(s, data))
        except Exception as e:  # SMTP/network failure: never claim success
            log.error("contact delivery failed: %s", type(e).__name__)
            return JSONResponse({"ok": False, "error": "delivery_failed"}, status_code=502)
        return {"ok": True}

    @app.post("/api/chat")
    async def chat(data: ai.ChatIn, request: Request):
        if not s.assistant_enabled:
            return JSONResponse({"ok": False, "error": "assistant_unavailable"}, status_code=503)
        allowed, retry = app.state.chat_limiter.hit(client_ip(request, s.trust_proxy))
        if not allowed:
            return JSONResponse({"ok": False, "error": "rate_limited", "retry_after": retry}, status_code=429, headers={"Retry-After": str(retry)})
        try:
            msgs = ai.normalise(data.messages)
        except ValueError as e:
            return JSONResponse({"ok": False, "error": "validation", "detail": str(e)}, status_code=422)
        try:
            reply = await ai.ask_model(s, app.state.http, system, msgs)
        except ai.AssistantError as e:
            return JSONResponse({"ok": False, "error": e.code}, status_code=e.status)
        return {"ok": True, "reply": reply, "model": s.assistant_model}

    # ---------------- errors ----------------
    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError):
        fields = {str(e["loc"][-1]): "Invalid value." for e in exc.errors() if e.get("loc")}
        return JSONResponse({"ok": False, "error": "validation", "fields": fields}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            return HTMLResponse((s.root / "404.html").read_text(encoding="utf-8"), status_code=404)
        return JSONResponse({"ok": False, "error": "not_found" if exc.status_code == 404 else "http_error"},
                            status_code=exc.status_code, headers=getattr(exc, "headers", None))

    # ---------------- static site (explicit allow-list: never the project root) ----------------
    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(s.root / "index.html")

    app.mount("/assets", StaticFiles(directory=s.root / "assets"), name="assets")
    return app


app = create_app()
