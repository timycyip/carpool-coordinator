"""Carpool Coordinator backend application.

FastAPI application with Mangum handler for AWS Lambda deployment.
The handler export is the Lambda entry point; the app export is used
by uvicorn for local development and by TestClient in tests.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.api.admin import router as admin_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router

app = FastAPI(
    title="Carpool Coordinator",
    version="0.1.0",
    description="Carpool coordination platform for events.",
)
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(audit_router)
app.include_router(sessions_router)
app.include_router(admin_router)


@app.exception_handler(HTTPException)
async def _envelope_http_exception(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Unwrap ``HTTPException(detail={"error": ...})`` to the contract envelope.

    The shared ``ErrorResponse`` envelope is ``{"error": {...}}`` (see
    ``docs/api_contracts.md`` §2). When a route raises ``HTTPException``
    with a ``detail`` dict already shaped as the envelope, return that
    dict as the top-level body so clients see the canonical shape
    rather than FastAPI's default ``{"detail": <detail>}`` wrapping.
    """
    detail = exc.detail
    if (
        isinstance(detail, dict)
        and set(detail.keys()) == {"error"}
        and isinstance(detail["error"], dict)
    ):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=exc.headers,
    )


handler = Mangum(app)

__all__ = ["app", "handler"]
