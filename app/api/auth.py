"""``POST /auth/google`` — exchange Google ID token for app session JWT.

Verifies the Google ID token against Google's cached JWKS (ADR-0006),
upserts the corresponding USER#<sub> record in DynamoDB, then issues
an HS256-signed app session JWT (ADR-0002) for subsequent requests.

On success or failure, a fire-and-forget audit event is written to the
audit log (``app_data``, ``AUDIT#<date>`` partition) per FR-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.jwt import create_app_token
from app.auth.oidc import InvalidTokenError, verify_google_token
from app.db import get_ddb_client
from app.middleware.audit import (
    EVENT_AUTH_LOGIN_FAILURE,
    EVENT_AUTH_LOGIN_SUCCESS,
    AuditLogger,
    audit_dependency,
)
from app.models.auth import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    UserInfo,
)
from app.models.error import ErrorBody, ErrorResponse
from app.repositories.user import UserRepository

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

router = APIRouter(tags=["auth"])

_TABLE_NAME = "app_data"
_TTL_SECONDS = 3600


def _pick_global_role(record: dict[str, Any] | None) -> str:
    """Map the stored ``global_roles`` list to the single-valued JWT claim.

    Returns the first role if one exists, otherwise ``"none"``. Stored
    values may be ``"superuser"`` or ``"manager"``; anything else is
    treated as no role.
    """
    if not record:
        return "none"
    raw_roles = record.get("global_roles")
    if not isinstance(raw_roles, list) or not raw_roles:
        return "none"
    first = raw_roles[0]
    return first if first in ("superuser", "manager") else "none"


@router.post("/auth/google", response_model=GoogleAuthResponse)
async def login_with_google(
    payload: GoogleAuthRequest,
    request: Request,
    audit: AuditLogger = Depends(audit_dependency),
    client: "DynamoDBClient" = Depends(get_ddb_client),
) -> GoogleAuthResponse:
    """Verify a Google ID token and issue an app session JWT."""
    try:
        google_user = verify_google_token(payload.id_token)
    except InvalidTokenError as exc:
        await audit.log(
            event_type=EVENT_AUTH_LOGIN_FAILURE,
            actor_sub=None,
            session_code=None,
            details={"reason": "invalid_google_token"},
            request=request,
        )
        body = ErrorResponse(
            error=ErrorBody(
                code="UNAUTHORIZED",
                message="Google ID token verification failed.",
                details={"reason": "invalid_google_token"},
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=body.model_dump(),
        ) from exc

    repo = UserRepository(table_name=_TABLE_NAME, client=client)
    record = await repo.upsert(
        sub=google_user.sub,
        email=google_user.email,
        name=google_user.name,
    )

    global_role = _pick_global_role(record)
    token = create_app_token(google_user, global_role=global_role)

    await audit.log(
        event_type=EVENT_AUTH_LOGIN_SUCCESS,
        actor_sub=google_user.sub,
        session_code=None,
        details={"method": "google"},
        request=request,
    )

    return GoogleAuthResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=_TTL_SECONDS,
        user=UserInfo(
            sub=google_user.sub,
            email=google_user.email,
            name=google_user.name,
            global_role=global_role,  # type: ignore[arg-type]
        ),
    )


__all__ = ["router"]
