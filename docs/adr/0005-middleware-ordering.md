# ADR-0005: Middleware Order — rate_limit → audit → auth → rbac

## Status
Accepted

## Date
2026-06-23

## Context
FastAPI processes incoming requests through a dependency chain (not global middleware). The order
in which these dependencies execute affects security, observability, and performance. Four concerns
must be ordered: rate limiting, audit logging, authentication, and authorization (RBAC).

Forces at play:
- Rate limiting should reject abusive traffic as cheaply as possible (no downstream work).
- Audit logging must capture **all** attempts — including rate-limited and auth-failed requests —
  with enough context (actor, action, IP, result).
- Authentication must resolve the user's identity before RBAC can check permissions.
- RBAC must run last because it needs both the identity (from auth) and the requested resource
  (from the route handler).
- Audit writes to DynamoDB must not add latency to the response (non-blocking).

## Decision
Implement the chain as **FastAPI dependencies** (not Starlette global middleware) so each route
explicitly declares its dependencies. The execution order for protected routes is:

1. **rate_limit** — Token-bucket check (per IP, per user). Returns `429` immediately if exhausted.
   Cheapest operation (one DynamoDB read on a TTL item).
2. **audit** — Records the attempt with IP, path, method, timestamp. Actor and result are resolved
   **after** auth/RBAC, so audit writes are **async** (fire-and-forget via `asyncio.create_task`)
   and fill in actor/result once known.
3. **auth** — Verifies the JWT (ADR-0002) and resolves the user `sub`, `email`, `global_role`.
   Returns `401` on failure.
4. **rbac** — Deny-default. Resolves effective role (global + session-scoped). Returns `403` on
   insufficient permissions.

For unprotected routes (e.g., `GET /health`), only rate_limit and audit are applied.

## Alternatives Considered

### Alternative A: Global Starlette middleware
Register rate_limit/audit/auth as global middleware on the FastAPI app.

- Pros: applies to all routes automatically.
- Cons: no per-route control; RBAC is hard to do globally (different routes need different roles);
  auth runs on `GET /health` unnecessarily; debugging middleware ordering is harder.

### Alternative B: Different order (auth → rbac → rate_limit → audit)
- Pros: authenticated user is known before rate-limiting (per-user limits are cheaper).
- Cons: rate-limiting should reject **before** doing any expensive work (JWT verification,
  JWKS fetch on cold start). A burst of unauthenticated requests would all verify JWTs before
  being rejected. **Rejected.**

### Alternative C: Dependency chain (chosen)
- Pros: per-route control; explicit; each dependency can be tested in isolation; RBAC is type-safe
  (`Depends(require_role(Role.MANAGER))`); ordering is clear in code.
- Cons: every protected route must chain all four dependencies (mitigated by a
  `get_protected_deps()` helper or a router-level dependency override).

## Consequences
- **Positive:** Cheapest rejection first (rate limit); audit captures all events including denials;
  RBAC is type-safe and per-route; each layer is independently testable.
- **Negative:** Every protected route must chain four dependencies (mitigated by helper).
- **Audit must be non-blocking** — `asyncio.create_task` or background dependency; a slow DynamoDB
  write must never increase response latency.

## Links
- Phase 2 plan Tasks 2.4, 2.8, 2.9: `plans/phase-2-foundation.md`
- ADR-0002 (JWT auth): `docs/adr/0002-app-session-jwt.md`
- ARCHITECTURE.md §Backend layering: `ARCHITECTURE.md`
