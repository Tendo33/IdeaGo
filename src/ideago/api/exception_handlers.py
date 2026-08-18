"""Centralized FastAPI exception-handler registration."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ideago.api.errors import AppError, ErrorCode
from ideago.observability.error_catalog import AlertLevel, log_error_event

_STATUS_TO_ERROR_CODE = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.NOT_AUTHORIZED,
    403: ErrorCode.NOT_AUTHORIZED,
    404: ErrorCode.NOT_FOUND,
    503: ErrorCode.DEPENDENCY_UNAVAILABLE,
}


def register_exception_handlers(
    app: FastAPI,
    logger,  # type: ignore[no-untyped-def]
    *,
    log_error_event_fn=log_error_event,
) -> None:
    """Register the shared JSON error envelope for API exceptions."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        log_error_event_fn(
            logger,
            error_code=exc.code.value,
            subsystem="api",
            trace_id=getattr(request.state, "trace_id", ""),
            message="application error",
            details={"status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = " → ".join(str(part) for part in first.get("loc", []))
            message = f"{loc}: {first.get('msg', 'Validation error')}"
        else:
            message = "Request validation failed"
        log_error_event_fn(
            logger,
            error_code=ErrorCode.VALIDATION_ERROR.value,
            subsystem="api",
            trace_id=getattr(request.state, "trace_id", ""),
            message="request validation failed",
            details={"errors_count": len(errors)},
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": message,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc, AppError):
            return await _app_error_handler(request, exc)
        status_code = int(exc.status_code)
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        code = _STATUS_TO_ERROR_CODE.get(status_code, ErrorCode.INTERNAL_ERROR)
        alert_level = AlertLevel.WARNING if status_code in {401, 403} else None
        log_error_event_fn(
            logger,
            error_code=code.value,
            subsystem="api",
            trace_id=getattr(request.state, "trace_id", ""),
            message="http exception",
            details={"status_code": status_code},
            alert_level=alert_level,
        )
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code.value, "message": message}},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", "")
        # Registering a catch-all Exception handler stops the exception
        # propagating to Sentry's middleware, so unhandled errors were being
        # logged locally and never reported. Capture explicitly.
        _capture_unhandled(exc, trace_id=trace_id, path=request.url.path)
        log_error_event_fn(
            logger,
            error_code=ErrorCode.INTERNAL_ERROR.value,
            subsystem="api",
            trace_id=trace_id,
            message="unhandled exception",
            include_exception=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "message": "Internal Server Error",
                }
            },
        )


def _capture_unhandled(exc: Exception, *, trace_id: str, path: str) -> None:
    """Report to Sentry when it is configured, tagging the trace id."""
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - sentry is a hard dependency today
        return
    if sentry_sdk.Hub.current.client is None:
        return
    with sentry_sdk.push_scope() as scope:
        if trace_id:
            scope.set_tag("trace_id", trace_id)
        scope.set_tag("path", path)
        sentry_sdk.capture_exception(exc)
