# ADR-0011: RBAC IntEnum + `require_role` Factory with Deny-Default

## Status
Accepted

## Date
2026-06-25

## Context
Phase 2 Task 2.4 requires implementing role-based access control (RBAC) per the Phase 1
`docs/rbac_matrix.md`. The RBAC system must:

1. Support 5 roles with precedence: Superuser > Manager > Session Admin > Driver > Passenger.
2. Enforce **deny-default** — every protected route must explicitly declare required roles.
3. Support **session-scoped** roles (Session Admin, Driver, Passenger) that apply only within
   a specific session, plus **global** roles (Superuser, Manager) that apply everywhere.
4. Be type-safe — FastAPI's dependency injection should enforce role requirements at the
   function signature level.
5. Return 403 with a machine-readable error code (`FORBIDDEN`) on insufficient permissions.

Forces at play:
- ADR-0005 mandates RBAC runs 4th in the middleware chain (after rate_limit → audit → auth).
- ADR-0002 stores `global_role` as a single string inside the JWT (not a list).
- The ERD supports session-scoped roles via `ADMIN#<sub>` and `REG#<sub>` items under
  `SESSION#<code>` partitions.
- Future phases (3–5) add more endpoints with varying permission requirements.

## Decision

### `Role` IntEnum with Precedence

```python
class Role(IntEnum):
    PASSENGER = 0
    DRIVER = 20
    SESSION_ADMIN = 40
    MANAGER = 60
    SUPERUSER = 80

    def satisfies(self, required: "Role") -> bool:
        return self >= required
```

Precedence is encoded in the integer values, spaced 20 apart to allow inserting intermediate
roles later. `satisfies()` uses numeric comparison — a Superuser (80) automatically passes a
Manager (60) check.

### `require_role` Factory

```python
def require_role(*allowed: Role) -> Callable[..., TokenPayload]:
    """FastAPI dependency that enforces deny-default RBAC.

    Returns 403 if the current user's effective role set does not
    contain any of the allowed roles.
    """
    async def check_role(
        request: Request,
        payload: TokenPayload = Depends(get_current_user),
        session_code: str | None = None,  # from path param
    ) -> TokenPayload:
        effective = await compute_effective_roles(payload, session_code, request)
        if not any(role.satisfies(req) for role in effective for req in allowed):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Insufficient permissions",
                        "details": {
                            "required_roles": [r.name for r in allowed],
                            "user_roles": [r.name for r in effective],
                        },
                    }
                },
            )
        return payload

    return check_role
```

### Session-Scoped Role Resolution

`compute_effective_roles()` resolves roles as:

1. **Global role** from JWT's `global_role` claim (Superuser or Manager or Passenger —
   defaults to Passenger).
2. **Session-scoped roles** from DynamoDB: checks for `ADMIN#<sub>` (Session Admin) and
   `REG#<sub>` (Driver or Passenger) under the `SESSION#<code>` partition.
3. Returns the **union** of all resolved roles.

If no `session_code` is provided (e.g., global endpoints like `GET /sessions`), only the
JWT's `global_role` applies. The `session_code` parameter is extracted from FastAPI path
parameters via `request.path_params`. Session-scoped lookups are synchronous (boto3) inside
an `async def` — acceptable for MVP where each lookup is a single DynamoDB call <10ms.

### `current_user` Dependency

```python
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
```

Route handlers use concise signatures:

```python
@router.get("/admin/dashboard")
async def admin_dashboard(
    user: CurrentUser,
    _: Depends(require_role(Role.SUPERUSER)),
) -> dict: ...
```

## Alternatives Considered

### Alternative A: String-based roles with manual checks (rejected)
Store roles as strings in a `set[str]` and compare with `if "superuser" in user.roles`.

- Pros: Simple; no enum needed.
- Cons: No precedence (a Superuser wouldn't automatically satisfy a Manager check unless
  the check explicitly included both); no type safety; easy to mistype role names; no
  IDE autocomplete. Rejected: the RBAC matrix has clear precedence semantics.

### Alternative B: Bitmask roles (rejected)
`PASSENGER=1, DRIVER=2, SESSION_ADMIN=4, MANAGER=8, SUPERUSER=16`, check with `&`.

- Pros: Compact; fast bitwise checks.
- Cons: Precedence requires either redundant bits (Manager must include all lower bits)
  or a second precedence table; 5 roles fits within an IntEnum; bitmask is overkill
  for this scale. Rejected: the IntEnum approach is simpler and equally fast.

### Alternative C: Decorator-based RBAC (rejected)
`@require_role(Role.MANAGER)` as a function decorator outside FastAPI's dependency system.

- Pros: Could apply to non-FastAPI functions.
- Cons: Doesn't integrate with FastAPI's dependency injection and OpenAPI auto-documentation;
  requires a custom middleware or AOP framework. Rejected: the FastAPI `Depends` pattern is
  the framework-native approach and produces automatic OpenAPI `security` documentation.

## Consequences
- **Positive:** Deny-default enforced by construction — a route without `require_role()`
  has no permission check. Precedence is transparent via `IntEnum >=` comparison.
  Session-scoping is resolved at request time from DynamoDB.
- **Negative:** Session-scoped role resolution adds a DynamoDB read per protected endpoint
  that uses a `session_code` path parameter. Acceptable at MVP scale; can add caching
  (in-memory dict with TTL) in Phase 6 if latency becomes an issue.
- **Negative:** `compute_effective_roles` is called synchronously (blocking boto3) inside
  an `async def`. Acceptable because DynamoDB reads are <10ms and Lambda invocations are
  isolated.

## Links
- `docs/rbac_matrix.md` — RBAC permission matrix
- ADR-0005 (middleware ordering)
- ADR-0002 (JWT auth + `global_role`)
- `app/middleware/rbac.py` — implementation
- `app/models/roles.py` — `Role` enum
- `tests/middleware/test_rbac.py` — 22 tests (16 e2e + 6 unit)
