"""Health check endpoint.

Provides a liveness probe for load balancers and monitoring.
No authentication required; no side effects (no DB, no network).
"""

from fastapi import APIRouter

from app.models.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return service liveness status.

    Returns 200 with `{"status": "ok"}` when the application is running.
    Intended for ALB target-group health checks and Lambda cold-start
    verification. Does not check downstream dependencies (DynamoDB, ORS).
    """
    return HealthResponse(status="ok")
