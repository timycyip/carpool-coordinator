"""Health check response model.

Contract for `GET /health`. Defined as a Pydantic model so FastAPI
generates the OpenAPI schema automatically (contract-first pattern).
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response payload for the health check endpoint."""

    status: str
