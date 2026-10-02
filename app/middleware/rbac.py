"""RBAC dependency injection (ADR-0005, ``docs/rbac_matrix.md``).

Exports the ``require_role(*allowed)`` FastAPI dependency and the
``compute_effective_roles`` helper it uses to resolve the caller's
effective role set for a given request.

Design notes:

- **Deny-default.** Every protected route must explicitly declare its
  required role(s) via ``Depends(require_role(Role.MANAGER))``. Routes
  that do not declare a required role have no RBAC dependency wired
  in — adding new protection is a positive opt-in.
- **Role precedence.** A higher-precedence role satisfies any check a
  lower-precedence role satisfies (``Role.satisfies``). A Superuser
  passes every check without any session-scoped assignment; a Manager
  passes Session Admin checks on any session.
- **Session-scoping.** ``SESSION_ADMIN``, ``DRIVER``, and ``PASSENGER``
  rights are bound to a specific session. The dependency extracts the
  ``{code}`` path parameter (if any) and resolves session-scoped roles
  via DynamoDB lookups on ``app_data`` (``ADMIN#<sub>`` and ``REG#<sub>``
  items under ``SESSION#<code>``).
- **Resolution order.** Global role from the JWT is resolved first.
  If the caller is Superuser or Manager the global role alone
  determines the effective set (no DynamoDB lookup). Otherwise the
  session-scoped assignments are queried.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Callable

from fastapi import Depends, HTTPException, Request, status

from app.config import app_data_table_name
from app.db import get_ddb_client
from app.middleware.auth import get_current_user
from app.models.auth import TokenPayload
from app.models.error import ErrorBody, ErrorResponse
from app.models.roles import Role

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


_PK_SESSION = "SESSION"
_PK_USER = "USER"
_SK_ADMIN = "ADMIN"
_SK_REG = "REG"
_SK_METADATA = "METADATA"


def _forbidden(required: list[str], session_code: str | None) -> HTTPException:
    """Build the canonical 403 envelope for an RBAC denial."""
    details: dict[str, object] = {"required_role": "|".join(required)}
    if session_code is not None:
        details["session_code"] = session_code
    body = ErrorResponse(
        error=ErrorBody(
            code="FORBIDDEN",
            message="Insufficient permissions.",
            details=details,
        )
    )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=body.model_dump(),
    )


async def _lookup_session_roles(
    user: TokenPayload,
    session_code: str,
    ddb_client: "DynamoDBClient",
) -> set[Role]:
    """Read ``ADMIN#<sub>`` and ``REG#<sub>`` items for a session.

    Returns the set of session-scoped roles the caller holds. Empty set
    if neither item exists. Called only when the caller's global role
    is neither ``superuser`` nor ``manager`` (those roles bypass the
    DynamoDB lookup per the resolution rules).
    """
    scoped: set[Role] = set()
    admin_resp = ddb_client.get_item(
        TableName=app_data_table_name(),
        Key={
            "PK": {"S": f"{_PK_SESSION}#{session_code}"},
            "SK": {"S": f"{_SK_ADMIN}#{user.sub}"},
        },
    )
    if admin_resp.get("Item") is not None:
        scoped.add(Role.SESSION_ADMIN)

    reg_resp = ddb_client.get_item(
        TableName=app_data_table_name(),
        Key={
            "PK": {"S": f"{_PK_SESSION}#{session_code}"},
            "SK": {"S": f"{_SK_REG}#{user.sub}"},
        },
    )
    reg_item = reg_resp.get("Item")
    if reg_item is not None:
        role_attr = reg_item.get("role", {}).get("S")
        if role_attr == "driver":
            scoped.add(Role.DRIVER)
        elif role_attr == "passenger":
            scoped.add(Role.PASSENGER)

    return scoped


async def compute_effective_roles(
    user: TokenPayload,
    session_code: str | None,
    ddb_client: "DynamoDBClient",
) -> set[Role]:
    """Return the union of global + session-scoped roles for the caller.

    Steps (per ``docs/rbac_matrix.md`` §2):

    1. Seed from the JWT ``global_role`` claim (``superuser`` /
       ``manager`` / everything else → empty).
    2. If a ``session_code`` is supplied AND the global role is not
       ``superuser``/``manager``, look up the ``ADMIN#<sub>`` and
       ``REG#<sub>`` items under ``SESSION#<code>`` in ``app_data`` and
       add the corresponding session-scoped roles.
    3. Expand for the precedence rule: ``SESSION_ADMIN`` implies
       ``DRIVER`` and ``PASSENGER``; ``DRIVER`` implies ``PASSENGER``.
       The actual permission check via ``Role.satisfies()`` would
       already handle this; the expansion keeps the returned set
       semantically complete.
    """
    effective: set[Role] = set()

    if user.global_role == "superuser":
        effective.add(Role.SUPERUSER)
    elif user.global_role == "manager":
        effective.add(Role.MANAGER)

    if session_code is not None and not effective:
        effective |= await _lookup_session_roles(user, session_code, ddb_client)

    if Role.SESSION_ADMIN in effective:
        effective.add(Role.DRIVER)
        effective.add(Role.PASSENGER)
    if Role.DRIVER in effective:
        effective.add(Role.PASSENGER)

    return effective


def require_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[TokenPayload]]:
    """Build a FastAPI dependency that enforces any of ``allowed_roles``.

    Resolves the caller's effective role set against the requested
    session (if any) and returns the ``TokenPayload`` so downstream
    handlers can use it. Raises ``403 FORBIDDEN`` with the canonical
    error envelope when none of the caller's effective roles satisfies
    any of ``allowed_roles``.

    Run order: ``Depends(get_current_user)`` runs first (401 on bad
    token); then DynamoDB lookups for session-scoped roles; then the
    precedence check.
    """

    async def _dependency(
        request: Request,
        user: TokenPayload = Depends(get_current_user),
        ddb_client: "DynamoDBClient" = Depends(get_ddb_client),
    ) -> TokenPayload:
        session_code = request.path_params.get("code")
        effective = await compute_effective_roles(user, session_code, ddb_client)

        required_names = [r.name.lower() for r in allowed_roles]
        for role in effective:
            for allowed in allowed_roles:
                if role.satisfies(allowed):
                    return user

        raise _forbidden(required_names, session_code)

    return _dependency


__all__ = ["compute_effective_roles", "require_role"]
