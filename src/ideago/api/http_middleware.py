"""HTTP middleware registration helpers for FastAPI."""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ideago.api.errors import ErrorCode
from ideago.auth.session import AUTH_SESSION_COOKIE_NAME
from ideago.config.settings import get_settings
from ideago.observability.metrics import metrics as app_metrics

_TURNSTILE_ORIGIN = "https://challenges.cloudflare.com"
_GOOGLE_FONTS_STYLES_ORIGIN = "https://fonts.googleapis.com"
_GOOGLE_FONTS_ASSETS_ORIGIN = "https://fonts.gstatic.com"
_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_EXEMPT_PATHS = {"/api/v1/billing/webhook"}


def _normalize_origin(value: str) -> str:
    return value.strip().rstrip("/")


def _extract_request_origin(request: Request) -> str:
    origin = str(request.headers.get("origin", "")).strip()
    if origin:
        return _normalize_origin(origin)
    referer = str(request.headers.get("referer", "")).strip()
    if not referer:
        return ""
    if "://" not in referer:
        return ""
    scheme, remainder = referer.split("://", 1)
    host = remainder.split("/", 1)[0]
    return _normalize_origin(f"{scheme}://{host}")


def _request_uses_cookie_session(request: Request) -> bool:
    cookie_jar = getattr(request, "cookies", {}) or {}
    return bool(str(cookie_jar.get(AUTH_SESSION_COOKIE_NAME, "")).strip())


def register_trace_id_middleware(app: FastAPI) -> None:
    """Attach a trace ID and request timing metrics to every request."""

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        start = time.monotonic()
        try:
            response: Response = await call_next(request)
        except Exception:
            latency_ms = (time.monotonic() - start) * 1000
            app_metrics.record(request.url.path, 500, latency_ms)
            raise
        latency_ms = (time.monotonic() - start) * 1000
        app_metrics.record(request.url.path, response.status_code, latency_ms)
        response.headers["X-Trace-Id"] = trace_id
        return response


def register_csrf_protection_middleware(app: FastAPI) -> None:
    """Reject mutating cross-origin requests without the SPA header."""

    @app.middleware("http")
    async def csrf_protection(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if (
            request.method in _CSRF_METHODS
            and request.url.path.startswith("/api/")
            and request.url.path not in _CSRF_EXEMPT_PATHS
        ):
            if not request.headers.get("X-Requested-With"):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": ErrorCode.CSRF_MISSING_HEADER.value,
                            "message": "Missing required header: X-Requested-With",
                        }
                    },
                )
            if _request_uses_cookie_session(request):
                settings = get_settings()
                allowed_origins = settings.get_cors_allow_origins()
                if allowed_origins != ["*"]:
                    request_origin = _extract_request_origin(request)
                    normalized_origins = {
                        _normalize_origin(origin) for origin in allowed_origins
                    }
                    if request_origin and request_origin not in normalized_origins:
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": {
                                    "code": ErrorCode.NOT_AUTHORIZED.value,
                                    "message": "Origin not allowed for cookie-backed request",
                                }
                            },
                        )
        return await call_next(request)


def register_security_headers_middleware(app: FastAPI, *, environment: str) -> None:
    """Add CSP and standard security headers to every response."""
    strict_csp = (
        "default-src 'self'; "
        f"script-src 'self' {_TURNSTILE_ORIGIN}; "
        f"style-src 'self' 'unsafe-inline' {_GOOGLE_FONTS_STYLES_ORIGIN}; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        f"frame-src 'self' {_TURNSTILE_ORIGIN}; "
        f"font-src 'self' data: {_GOOGLE_FONTS_ASSETS_ORIGIN}; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    docs_csp = (
        "default-src 'self' https:; "
        "script-src 'self' 'unsafe-inline' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self' data: https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    docs_paths = {path for path in (app.docs_url, app.redoc_url) if path}

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            docs_csp if request.url.path in docs_paths else strict_csp
        )
        if environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
