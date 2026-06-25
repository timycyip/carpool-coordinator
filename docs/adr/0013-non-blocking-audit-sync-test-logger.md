# ADR-0013: Non-Blocking Audit Writes + `_SyncAuditLogger` Test Pattern

## Status
Accepted

## Date
2026-06-25

## Context
Phase 2 Task 2.9 requires audit logging for login attempts, session changes, admin assignments,
and RBAC denials. ADR-0005 mandates that audit writes are **non-blocking** — a slow or failing
DynamoDB write must never delay or fail the API response.

Forces at play:
- Audit writes to DynamoDB add ~5–10ms latency (write + eventual consistency). On cold starts
  or under load, this can spike to 50ms+.
- The NFR target is p95 < 800ms on smoke routes. Every millisecond counts.
- Audit data must not be lost if DynamoDB is temporarily unavailable — but the API response
  must not be affected.
- The frontend and caller should never wait on audit persistence.
- In tests, fire-and-forget writes are non-deterministic — assertions may pass or fail based
  on event-loop timing, making TDD unreliable.

## Decision

### Fire-and-Forget via `asyncio.create_task`

`AuditLogger.log()` dispatches DynamoDB writes by scheduling a coroutine in the background
via `asyncio.create_task()`. The method returns immediately; the caller never awaits the
result:

```python
class AuditLogger:
    def log(self, event_type: str, actor_sub: str | None, ...) -> None:
        """Record an audit event. Non-blocking — returns immediately."""
        try:
            asyncio.create_task(self._dispatch_write(event))
        except Exception:
            logger.exception("Failed to schedule audit write")

    async def _dispatch_write(self, event: AuditEvent) -> None:
        """Actual DynamoDB write, runs in background task."""
        try:
            await self.repo.put_item(event.dict())
        except Exception:
            logger.exception("Audit write failed")
```

**Key behaviors:**
- `log()` catches scheduling failures (e.g., event loop not available) and logs them.
- `_dispatch_write()` catches DynamoDB errors and logs them — they never propagate.
- The API response is returned to the caller before the audit write completes.

### `audit_dependency` as FastAPI Dependency

`app/middleware/audit.py` exports an `audit_dependency` function that creates an
`AuditLogger` and stores it on `request.state.audit_logger`. This makes the logger
accessible to route handlers and other middleware without passing it through every function
signature:

```python
async def audit_dependency(request: Request) -> None:
    request.state.audit_logger = AuditLogger(repo)
```

Routes can access it via `request.state.audit_logger.log(...)`.

### `_SyncAuditLogger` Test Pattern

For deterministic test assertions, `_SyncAuditLogger` overrides `_dispatch_write()` to run
the coroutine **synchronously** in the current event loop:

```python
class _SyncAuditLogger(AuditLogger):
    """Audit logger that writes synchronously for test determinism."""

    def log(self, event_type, actor_sub, ...):
        """Synchronously dispatch the write — await inside the current loop."""
        loop = asyncio.get_running_loop()
        coro = self._dispatch_write(event)
        task = loop.create_task(coro)
        loop.run_until_complete(task)
```

Tests inject `_SyncAuditLogger` via FastAPI's `dependency_overrides`:

```python
@pytest.fixture
def auth_client_with_audit(ddb_client, app):
    repo = AuditRepository(ddb_client)
    sync_logger = _SyncAuditLogger(repo)

    async def override_audit(request: Request):
        request.state.audit_logger = sync_logger

    app.dependency_overrides[audit_dependency] = override_audit
    with TestClient(app) as client:
        yield client, sync_logger
    app.dependency_overrides.pop(audit_dependency)
```

Tests then assert on audit events immediately after the API call:

```python
def test_login_audits_success(auth_client_with_audit):
    client, logger = auth_client_with_audit
    response = client.post("/auth/google", json={"id_token": valid_token})
    assert response.status_code == 200
    events = logger.get_events()  # drain the in-memory list
    assert events[0]["event_type"] == "auth.login.success"
```

### Audit Events on Login (code review fix 2026-06-25)

During code review, it was identified that `POST /auth/google` had no audit logging.
The fix wires audit into both the success and failure paths:

- **Success:** `auth.login.success` — logged after JWT issuance, with `actor_sub` set to
  the authenticated user's `sub`.
- **Failure:** `auth.login.failure` — logged when `verify_google_token` raises, with
  `details.reason` set to `invalid_google_token` or `token_expired`.

## Alternatives Considered

### Alternative A: Synchronous writes (rejected)
Await the DynamoDB `put_item` directly in the response path.

- Pros: No data loss; deterministic; simplest code.
- Cons: Adds 5–50ms to every API response; makes audit availability a hard dependency
  of the API (DynamoDB degradation = API degradation). Rejected: violates ADR-0005's
  non-blocking requirement.

### Alternative B: Queue-based (rejected)
Write audit events to an SQS queue; a separate Lambda consumer writes to DynamoDB.

- Pros: Maximum isolation; zero API latency impact; queue buffers bursts.
- Cons: Adds operational complexity (SQS queue, consumer Lambda, DLQ); cold-start
  latency for the consumer; eventual consistency means audit events may not appear for
  seconds; overkill for MVP audit volume. Rejected: the fire-and-forget pattern provides
  sufficient isolation at MVP scale. Revisit if audit volume exceeds DynamoDB write
  capacity.

### Alternative C: BackgroundTask (rejected)
Use FastAPI's `BackgroundTasks.add_task()`.

- Pros: Framework-native; no manual event-loop management.
- Cons: `BackgroundTasks` requires the `Response` object, which may not be available in
  all middleware contexts; the task runs after the response is sent, not concurrently;
  tests can't easily drain background tasks. Rejected: `asyncio.create_task` is simpler
  and works uniformly across all middleware layers.

### Alternative D: Fire-and-forget create_task (chosen)
- Pros: Zero API latency impact; audit failures are self-contained (logged to CloudWatch);
  works in any async context (middleware, route handlers, dependency functions).
- Cons: Data loss if the Lambda is terminated mid-write (acceptable — audit is
  non-critical for MVP); non-deterministic in tests (mitigated by `_SyncAuditLogger`).

## Consequences
- **Positive:** Audit writes add ~0ms to API response latency. Audit system failure is
  fully isolated from API availability. `_SyncAuditLogger` makes TDD feasible.
- **Negative:** Audit data is best-effort — writes during Lambda shutdown are lost.
  Acceptable for MVP; for production, switch to SQS (Alternative B) to guarantee delivery.
- **Negative:** The `_SyncAuditLogger` pattern requires test authors to understand the
  override chain (`dependency_overrides[audit_dependency]`). Documentation in
  `tests/api/test_auth.py` and `tests/api/test_audit.py` serves as reference.

## Links
- ADR-0005 (middleware ordering — audit is 2nd dependency)
- FR-11 (audit logging requirements)
- `app/middleware/audit.py` — `AuditLogger` + `_SyncAuditLogger`
- `app/api/auth.py` — audit logging on login success/failure
- `tests/api/test_auth.py` — audit test patterns
- `tests/api/test_audit.py` — paginated audit query tests
- `tests/middleware/test_audit.py` — fire-and-forget write tests
