"""Carpool Coordinator backend application.

FastAPI application with Mangum handler for AWS Lambda deployment.
The handler export is the Lambda entry point; the app export is used
by uvicorn for local development and by TestClient in tests.
"""

from fastapi import FastAPI
from mangum import Mangum

from app.api.health import router as health_router

app = FastAPI(
    title="Carpool Coordinator",
    version="0.1.0",
    description="Carpool coordination platform for events.",
)
app.include_router(health_router)

handler = Mangum(app)
