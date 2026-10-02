"""Session-admin assignment endpoint (API contracts §3.17)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import app_data_table_name
from app.db import get_ddb_client
from app.middleware.audit import (
    EVENT_SESSION_ADMIN_ASSIGN,
    AuditLogger,
    audit_dependency,
)
from app.middleware.rbac import require_role
from app.models.admin import AdminAssignRequest, AdminAssignResponse
from app.models.auth import TokenPayload
from app.models.error import ErrorBody, ErrorResponse
from app.models.roles import Role
from app.repositories.session import SessionRepository
from app.repositories.user import UserRepository

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

router = APIRouter(prefix="/sessions", tags=["session-admin"])


def _not_found(code: str, message: str, **details: str) -> HTTPException:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or None)
    )
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=body.model_dump())


def _is_conditional_failure(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


@router.post(
    "/{code}/admin",
    response_model=AdminAssignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_session_admin(
    code: str,
    body: AdminAssignRequest,
    request: Request,
    response: Response,
    actor: TokenPayload = Depends(require_role(Role.MANAGER)),
    audit: AuditLogger = Depends(audit_dependency),
    client: "DynamoDBClient" = Depends(get_ddb_client),
) -> AdminAssignResponse:
    """Grant a known user Session Admin access to an existing open session."""
    session_code = code.upper()
    table_name = app_data_table_name()
    sessions = SessionRepository(table_name=table_name, client=client)
    users = UserRepository(table_name=table_name, client=client)
    session = await sessions.get_by_code(session_code)
    if session is None:
        raise _not_found("SESSION_CODE_NOT_FOUND", "Session not found.")
    if session.get("status") == "closed":
        raise _not_found(
            "SESSION_CODE_NOT_FOUND",
            "Session is not in an assignable state.",
            reason="session_closed",
        )

    user = await users.get_by_sub(body.user.sub)
    if user is None:
        raise _not_found(
            "TARGET_USER_UNKNOWN",
            "Target user has not authenticated.",
        )

    key = {"PK": f"SESSION#{session_code}", "SK": f"ADMIN#{body.user.sub}"}
    now = datetime.now(timezone.utc)
    item: dict[str, Any] = {
        **key,
        "email": str(body.user.email),
        "assigned_by": actor.sub,
        "assigned_at": now.isoformat(),
        "role": "session_admin",
    }
    already_assigned = False
    try:
        await sessions.put_item(item, condition_expression="attribute_not_exists(PK)")
    except ClientError as exc:
        if not _is_conditional_failure(exc):
            raise
        existing = await sessions.get_item(key)
        if existing is None:
            raise
        already_assigned = True
        item = existing

    response.status_code = (
        status.HTTP_200_OK if already_assigned else status.HTTP_201_CREATED
    )
    result = AdminAssignResponse(
        session_code=session_code,
        user_sub=body.user.sub,
        email=str(item.get("email", body.user.email)),
        assigned_by_sub=str(item.get("assigned_by", actor.sub)),
        assigned_at=item.get("assigned_at", now),
        already_assigned=already_assigned,
    )
    await audit.log(
        event_type=EVENT_SESSION_ADMIN_ASSIGN,
        actor_sub=actor.sub,
        session_code=session_code,
        details={"target_sub": body.user.sub, "result": "success"},
        request=request,
    )
    return result


__all__ = ["router"]
