# KNOWLEDGE.md — Lessons Learned & Decisions Log

Running log of lessons learned, gotchas, and decisions. Updated in the DOCUMENTATION phase of
every task (AGENTS.md §17).

---

## Task 2.1 — Backend Project Scaffold + Health Endpoint (2026-06-24)

### ADR Resolutions Captured

- **ADR-0001 (multi-table DynamoDB):** The earlier Phase 2 plan draft proposed consolidating
  all DynamoDB tables into a single `app_data` table. This was rejected by human review.
  Tables are now named per the Phase 1 ERD (`docs/data_model_erd.md`) — each logical entity
  group gets its own table with independent TTL, capacity, and backup policies. Hot rate-limit
  traffic is isolated from durable application data. See `docs/adr/0001-table-naming-by-data-model.md`.

- **ADR-0008 (deferred notification delivery):** The Phase 1 plan originally locked
  synchronous email delivery from the API Lambda via Microsoft Graph `sendMail`. This was
  reversed: the API Lambda now writes `notification_pending` items to DynamoDB; a separate
  SQS → Lambda consumer handles delivery with exponential backoff. This avoids blocking
  the API response on Graph availability and removes the 10-second Lambda timeout risk for
  large-session fan-out. See `docs/adr/0008-deferred-notification-delivery.md`.

- **Canonical registration schema:** Master spec v3.0 §5 (FR-3/FR-4) supersedes the v2
  field lists. The separate driver/passenger registration schemas are merged into one
  canonical schema. The `docs/requirements_baseline.md` §2 FR-3/FR-4 entries note this.

### Resolved Open Questions (all 13 — summary)

All OQs from `docs/requirements_baseline.md` §4 are **Resolved**. Highest-signal:

| OQ | Resolution |
|----|------------|
| OQ-6 | Deferred email per ADR-0008 (reverses synchronous assumption) |
| OQ-9 | AWS region = `us-east-2` (Ohio), confirmed by ADR-0003 |
| OQ-5 | ORS free-tier matrix chunk = 50 locations; sessions >100 need batching |
| OQ-7 | `TO_DESTINATION` only for MVP; `FROM_ORIGIN` deferred post-MVP |
| OQ-8 | Solo dev + AI agents fill all spec §17 roles |
| OQ-3 | Compliance (GDPR/PIPEDA) deferred to post-MVP |

Full table: `docs/requirements_baseline.md` §4.

### Technical Notes

- **hatchling package discovery:** When the project name (`carpool-coordinator-backend`)
  doesn't match a directory name, hatchling requires explicit
  `[tool.hatch.build.targets.wheel] packages = ["app"]` in `pyproject.toml`.

- **httpx requirement:** FastAPI's `TestClient` (Starlette 0.36+) requires `httpx` at
  runtime, even for sync test usage. Forgetting it in dev deps causes `ImportError` at
  test collection. Listed in `[project.optional-dependencies] dev`.

- **Legacy code exclusion:** `src/`, `test/`, `mock/` are excluded from ruff
  (`extend-exclude`) and mypy (`exclude`) to prevent legacy Python 3.8 code from
  failing strict quality gates. Do not modify legacy files to make gates pass.

- **`requirements.txt` deviation:** The file retains legacy CLI pins (pandas/geopy/scipy)
  per AGENTS.md. Backend pins live in `pyproject.toml` only. Human-approved.

- **API design patterns (established):** Every endpoint uses a Pydantic `response_model`
  (contract-first). Shared error envelope (`ErrorResponse`/`ErrorBody` in
  `app/models/error.py`) matches API contracts §2. Input/output model separation
  (Create/Update/Response per resource). FastAPI auto-generates OpenAPI 3.1.0 schema
  from Pydantic models — the types ARE the documentation. Apply these patterns to all
  subsequent endpoints.

- **pytest-cov needed for coverage:** `pytest --cov` requires `pytest-cov` in dev deps;
  forgetting it causes `unrecognized arguments: --cov`. Added to `pyproject.toml`.

- **Model-only code needs import tests:** Pydantic models that aren't used by any endpoint
  yet (e.g., `ErrorResponse`) still count toward coverage. Add unit tests that construct
  and validate the models directly (see `tests/test_models.py`).

---

## Task 2.2 — DynamoDB Schema + Repository Layer (2026-06-24)

### Design Decisions

- **Sync boto3, async interface:** Repositories use sync `boto3` client internally but
  expose `async def` methods. This keeps the interface compatible with FastAPI's async
  endpoints while avoiding `aioboto3` complexity. The brief blocking is acceptable at MVP
  scale (Lambda invocations are isolated; each call is <1ms).

- **`TypeSerializer`/`TypeDeserializer` for DynamoDB JSON:** The base repository
  auto-serializes plain Python dicts to DynamoDB JSON format and deserializes responses
  back. This gives callers a clean Python-dict API without manual type-descriptor
  boilerplate (`{"S": "value"}`).

- **`Decimal`→`int`/`float` conversion:** DynamoDB's `TypeDeserializer` returns
  `Decimal` for numbers. The base repository converts these to `int` (if no fractional
  part) or `float` so callers don't need to handle `Decimal` serialization in JSON
  responses.

- **Advisory A7 — `gsi_latest_match_by_session` not provisioned:** The ERD §3.3 GSI is
  redundant. A main-table Query with `ScanIndexForward=False, Limit=1` on the same
  partition returns identical results at the same cost. The GSI is omitted from Terraform;
  the comment in `MatchRepository.get_latest()` records the rationale.

- **Zero-padded match version SKs:** `MATCH#V0001`, `MATCH#V0002`, etc. (4-digit padding)
  ensures lexicographic sort order matches numeric order for DynamoDB's `ScanIndexForward`
  behavior. Breaks at V10000+ (5 digits) — acceptable for MVP.

### Technical Notes

- **moto 5.x uses `mock_aws`:** The older `mock_dynamodb` context manager was consolidated
  into `mock_aws` in moto 5.0. All test fixtures use `@mock_aws` (or `with mock_aws()`).

- **moto table creation requires all GSI key attributes:** When creating a table with GSIs
  in moto, all attributes used as GSI hash/range keys must be listed in the table's
  `AttributeDefinitions`, even though DynamoDB itself only requires definitions for key
  attributes. Moto enforces this at create time.

- **pytest-asyncio `mode = "auto"`:** All async test functions are collected and run
  automatically without explicit `@pytest.mark.asyncio` decorators, but we include them
  for clarity and compatibility with stricter pytest-asyncio versions.

- **Task 2.1 branch merge required:** This worktree was based on `master` which lacked
  the Task 2.1 scaffold. The `phase-2-task-2-1-backend-scaffold` branch was merged in
  first (fast-forward). Future task branches should be created from the latest merged
  state of their dependencies.

- **Audit `query_audit` naming:** The audit repository method is named `query_audit`
  (not `query`) to avoid shadowing the base class `query` method in the `super().query()`
  call. Python's MRO would otherwise cause infinite recursion if the method were named
  `query`.

---

## Task 2.11 — Next.js Frontend Bootstrap (2026-06-24)

### Next.js 16 + Tailwind v4 specifics

- `create-next-app@latest` (v16.2.9) generates Tailwind v4 with `@theme inline` CSS variables
  in `globals.css` — NOT a `tailwind.config.ts` color-object structure. Edit the `:root` CSS
  variables and `@theme inline` block to set design tokens.
- The scaffold uses `Geist` and `Geist_Mono` fonts from `next/font/google`.
- `next build` uses Turbopack by default in Next 16 (not webpack). The build output is still
  compatible with `@cloudflare/next-on-pages`.

### @cloudflare/next-on-pages peer dependency cap

- `@cloudflare/next-on-pages@1.13.16` has `peerDependencies` capped at `next@<=15.5.2`.
  Installing with Next 16 requires `--legacy-peer-deps`. The package is also deprecated in
  favor of the OpenNext adapter (`https://opennext.js.org/cloudflare`).
- Only `next build` (`npm run build`) is the hard acceptance gate for this task. The
  `pages:build` Cloudflare output is verified end-to-end in Task 2.10.

### 401 → redirect chain gap

- **Gotcha:** If the api-client clears its module-scoped token on `401` but the React
  auth context holds a separate `useState` copy, `isAuthenticated` stays `true` and the
  route guard never redirects. Both layers must be notified.
- **Fix:** Subscriber pattern (`onUnauthorized` in api-client, `useEffect` subscription in
  AuthProvider). Documented in ADR-0009.

### `.gitignore` and `.env.example`

- `create-next-app` generates `.env*` in `.gitignore` which also matches `.env.example`.
  Changed to `.env` + `.env.*` + `!.env.example` so the template is committed.
- Added `.wrangler/` to `.gitignore` for Wrangler dev artifacts.

### API base URL

- The api-client uses the literal string `"/api"` as its base (same-origin, relative).
  `NEXT_PUBLIC_API_BASE_URL` is read ONLY inside `next.config.ts` `rewrites()` — never
  imported in client code. This keeps the backend URL hidden from the browser bundle
  (mild tension: `NEXT_PUBLIC_` vars are inlined at build time, so the URL is technically
  in the JS bundle, but it's not on the critical path for security).

### GlobalRole values

- Confirmed lowercase strings: `"superuser" | "manager" | "none"`. Nav role branching
  compares against lowercase. Source: `docs/api_contracts.md` §5 `GlobalRole` enum and
  §1.2 JWT claims.

---

## Task 2.3 — Google OIDC Authentication (Backend + Frontend Vertical Slice) (2026-06-24)

### HTTPException envelope unwrapping

- FastAPI's `HTTPException(detail=...)` renders the response as
  `{"detail": <detail>}`. To match the API contract envelope `{"error": {...}}`,
  register an exception handler in `app/main.py` that unwraps
  `HTTPException(detail={"error": {...}})` and returns the inner dict directly.
  All auth-related errors now use the canonical envelope without per-route
  boilerplate.

### JWKS caching

- `app/auth/oidc.py` keeps the JWKS payload in a module-level `_cache` dict +
  `_fetched_at` timestamp. `time.monotonic()` would be more correct (immune
  to wall-clock jumps), but ADR-0006 specifies elapsed-time semantics that work
  either way. A stale-key fallback test (`tests/auth/test_oidc.py`) exercises
  the "fetch fails → serve from cache" branch by mutating `_cache.fetched_at`
  and patching `_fetch_jwks` to raise `OSError`.
- Fetch uses `urllib.request` instead of `httpx`/`aiohttp` to keep runtime deps
  minimal. JWKS fetch is rare (once per ~hour per Lambda instance) so the
  blocking call inside an `async def` is acceptable. If JWKS fetch latency
  becomes a cold-start concern, swap to `httpx.AsyncClient`.

### PyJWT + cryptography

- `jwt.algorithms.RSAAlgorithm.from_jwk(...)` returns an `RSAPublicKey`
  directly (not a private key). Use `.public_bytes(Encoding.PEM,
  PublicFormat.SubjectPublicKeyInfo)` to serialize for `jwt.decode(...)`.
- Earlier mistake: `.public_key().export_to_pem()` — `.public_key()` does not
  exist on a public key, only on a private key.

### PyJWT HS256 key length warning

- PyJWT emits `InsecureKeyLengthWarning` for HMAC keys < 32 bytes. The
  `test_wrong_secret_raises` fixture uses a 12-byte "wrong-secret" to
  intentionally trigger the failure mode; the warning is suppressed by
  test ordering, not silenced. Production secrets from Parameter Store are
  always ≥ 32 bytes.

### `@react-oauth/google` + `GoogleOAuthProvider`

- The provider must wrap the entire app (not just the login page) — placed in
  `frontend/src/app/layout.tsx`. If `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is unset,
  the page renders a friendly "not configured" alert instead of crashing the
  GIS button.
- `frontend` package install requires `--legacy-peer-deps` because
  `@cloudflare/next-on-pages@1.13.16` only declares peer support for Next ≤15,
  while the project pins `next@16.2.9`. The Next 16 build works fine via
  turbopack; only the legacy Pages adapter is incompatible (Phase 2 deploy
  will pin Next 15.x for `pages:build`).

### Test fixture sharing

- Tests that need both a moto-mocked DynamoDB **and** the FastAPI app's
  `app.dependency_overrides[get_ddb_client] = lambda: ddb_client` must depend
  on the conftest's `ddb_client` fixture (not create a new `mock_aws()`
  context). Otherwise the mocked tables aren't shared, and writes from one
  side are invisible to the other. Pattern documented in
  `tests/api/test_auth.py::auth_client`.

### Field name alignment

- Backend `GoogleAuthResponse` uses `access_token` (matching API contract §3.1
  and the existing `frontend/src/lib/types.ts`). The Task 2.3 spec mentioned
  `token` but that would have broken the established contract — kept the
  contract-aligned name.

---

## Task 2.4 — RBAC Middleware (2026-06-24)

### Role IntEnum design (ADR-0011)

- `Role` is an `IntEnum` with precedence weights spaced 20 apart:
  `PASSENGER=0, DRIVER=20, SESSION_ADMIN=40, MANAGER=60, SUPERUSER=80`.
- `satisfies(required: Role) -> bool` checks `self >= required` — higher roles
  automatically pass lower-role checks (Superuser passes everything).
- `require_role(*allowed: Role)` is a FastAPI dependency factory that returns
  `Depends(...)`. It reads the resolved `TokenPayload` from `get_current_user`,
  computes the effective role set (global + session-scoped), and returns 403 if
  none match.

### Session-scoped RBAC

- Session-scoped roles (Session Admin, Driver, Passenger) require a DynamoDB
  lookup: `ADMIN#<sub>` or `REG#<sub>` under `SESSION#<code>` partition.
- `compute_effective_roles(payload, session_code)` unions global role with any
  session-scoped roles. If no `session_code`, only global role applies.
- **Deny-default:** every protected route must explicitly declare the required
  role via `Depends(require_role(...))`. No implicit allowances.

### `CurrentUser` type alias

- Defined in `app/middleware/auth.py` as
  `Annotated[TokenPayload, Depends(get_current_user)]`.
- Enables concise dependency injection in route signatures:
  `async def route(user: CurrentUser, rbac: Depends(require_role(Role.MANAGER)))`.

---

## Task 2.8 — Rate Limiting Middleware (2026-06-24)

### DynamoDB token-bucket design (ADR-0012)

- Atomic `UpdateItem` with `ADD count :inc` and `ConditionExpression:
  attribute_not_exists(#ts) OR (#ts = :window_start AND #count <= :limit)`.
- Per-IP bucket: PK=`RATELIMIT#IP#<ip>`, SK=`<window_start>`.
- Per-user bucket: PK=`RATELIMIT#USER#<sub>`, SK=`<window_start>`.
- TTL on `rate_limit_cache` table auto-expires old window records.

### Hot-path optimization

- **Removed unnecessary `GetItem`:** The initial implementation did a `GetItem`
  to check the current count before the `UpdateItem`. This was unnecessary —
  DynamoDB's `UpdateItem` with `ConditionExpression` handles the check
  atomically. Removed in commit `5a11522`.
- `ReturnValues="UPDATED_NEW"` returns post-increment count for the response.

### `Retry-After` and rate-limit headers

- 429 response includes `Retry-After`, `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, `X-RateLimit-Reset` per API contracts §1.4.
- Window size is configurable: `RATE_LIMIT_WINDOW_IP` (default 60s),
  `RATE_LIMIT_WINDOW_USER` (default 60s).

### Abuse detection deferred

- `brute_force_counter` table is provisioned but no code writes to it yet.
  Post-MVP: track consecutive auth failures, escalate to IP ban.

---

## Task 2.9 — Audit Logging Middleware (2026-06-24)

### Fire-and-forget writes (ADR-0013)

- `AuditLogger.log()` dispatches DynamoDB writes via `asyncio.create_task` —
  the API response never waits on audit persistence.
- Failed audit writes are caught and logged to stderr; they never propagate
  to the caller.
- PK=`AUDIT#<YYYY-MM-DD>`, SK=`<event_id>` (UUIDv4). Daily partition for
  bounded scans.

### `_SyncAuditLogger` test pattern

- The fire-and-forget pattern is inherently non-deterministic in tests.
  `_SyncAuditLogger` subclass overrides `_dispatch_write()` to run the
  coroutine synchronously in the main event loop.
- Tests override `audit_dependency` via FastAPI's `dependency_overrides`
  to inject the synchronous logger. `request.state.audit_logger` is then
  accessible for test assertions.

### `next_cursor` pagination bug (code review fix)

- **Bug:** `next_cursor` used `raw_items[-1]["SK"]` — the last item of
  the entire query (all events for the day), not the last *returned* item
  after slicing. This caused pagination to skip rows when `limit < total`.
- **Fix:** `next_cursor` now uses `last_sk` — the SK of the last item
  actually returned in the current page.

### RBAC on `GET /audit` (code review fix)

- **Bug:** `GET /audit` was public (no `Depends(require_role(...))`).
- **Fix:** Added `Depends(require_role(Role.MANAGER, Role.SUPERUSER))`.
  Unauthenticated → 401, Passenger → 403.

### Auth audit logging (code review fix)

- **Missing:** `POST /auth/google` had no audit logging.
- **Fix:** Writes `auth.login.success` (with `actor_sub`) on successful login
  and `auth.login.failure` (with `reason` in details) on invalid token.

---

## Task 2.10 — CI/CD Pipelines (2026-06-25)

### Three GitHub Actions workflows

- **`backend-ci.yml`:** ruff check + ruff format check + mypy (strict) +
  pytest with coverage. Build + deploy to Lambda on push to main.
- **`frontend-ci.yml`:** eslint + tsc --noEmit + vitest. Build + deploy to
  Cloudflare Pages on push to main.
- **`terraform.yml`:** Plan on PR to main, plan + apply on push to main.
  Uses `hashicorp/setup-terraform@v3`.

### Terraform workflow fixes (code review)

- **Bug:** PR plan job echoed "Terraform plan would run here" instead of
  actually running `terraform plan`. Cloudflare OIDC provider + backend
  config caused real plan to fail.
- **Fix:** PR plan job now runs `terraform plan -input=false` with full
  AWS credentials.
- **Bug:** Apply job used `-var-file=dev.tfvars` which doesn't exist.
- **Fix:** Removed `-var-file`. `variables.tf` defaults `environment` to
  `"dev"` so no external var file is needed.

### A9 advisory: NFR-SCALE-2 wording

- Changed "idle cost = $0" to "≤ $1/month idle" in
  `docs/requirements_baseline.md` §5.3 to account for CloudWatch Logs ingestion
  (which is never zero).
