"""Session CRUD endpoints (API contracts §3.3–§3.7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request, Response, status

from app.config import app_data_table_name
from app.db import get_ddb_client
from app.middleware.audit import (
    EVENT_SESSION_CREATED,
    EVENT_SESSION_DELETED,
    EVENT_SESSION_UPDATED,
    AuditLogger,
    audit_dependency,
)
from app.middleware.rbac import require_role
from app.models.auth import TokenPayload
from app.models.roles import Role
from app.models.session import SessionCreate, SessionResponse, SessionUpdate
from app.repositories.session import SessionRepository
from app.services.session import SessionService

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _service(client: "DynamoDBClient") -> SessionService:
    return SessionService(
        SessionRepository(table_name=app_data_table_name(), client=client)
    )


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    body: SessionCreate,
    request: Request,
    response: Response,
    actor: TokenPayload = Depends(require_role(Role.MANAGER)),
    audit: AuditLogger = Depends(audit_dependency),
    client: "DynamoDBClient" = Depends(get_ddb_client),
) -> SessionResponse:
    """Create a session for a Manager or Superuser."""
    result = await _service(client).create(body, actor)
    response.headers["Location"] = f"/sessions/{result.session_code}"
    await audit.log(
        event_type=EVENT_SESSION_CREATED,
        actor_sub=actor.sub,
        session_code=result.session_code,
        details={"status": result.status.value},
        request=request,
    )
    return result


@router.get("/{code}", response_model=SessionResponse)
async def get_session(
    code: str,
    actor: TokenPayload = Depends(require_role(Role.PASSENGER)),
    client: "DynamoDBClient" = Depends(get_ddb_client),
) -> SessionResponse:
    """Return session details to an authenticated session participant/admin."""
    return await _service(client).get(code, actor)


@router.patch("/{code}", response_model=SessionResponse)
async def update_session(
    code: str,
    body: SessionUpdate,
    request: Request,
    actor: TokenPayload = Depends(require_role(Role.SESSION_ADMIN)),
    audit: AuditLogger = Depends(audit_dependency),
    client: "DynamoDBClient" = Depends(get_ddb_client),
) -> SessionResponse:
    """Update session configuration or perform an allowed status transition."""
    result = await _service(client).update(code, body, actor)
    await audit.log(
        event_type=EVENT_SESSION_UPDATED,
        actor_sub=actor.sub,
        session_code=result.session_code,
        details={"updated_fields": sorted(body.model_dump(exclude_unset=True))},
        request=request,
    )
    return result


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    code: str,
    request: Request,
    actor: TokenPayload = Depends(require_role(Role.SUPERUSER)),
    audit: AuditLogger = Depends(audit_dependency),
    client: "DynamoDBClient" = Depends(get_ddb_client),
) -> Response:
    """Hard-delete the session and its session-partition records."""
    await _service(client).delete(code, actor)
    await audit.log(
        event_type=EVENT_SESSION_DELETED,
        actor_sub=actor.sub,
        session_code=code.upper(),
        details={},
        request=request,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
