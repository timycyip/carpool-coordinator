# Phase 2 — Foundation Plan

Builds on Phase 1 artifacts (`doc/requirements_baseline.md`, `doc/api_contracts.md`, `doc/data_model_erd.md`). Goal: working Google login + session setup deployed to AWS, with the Next.js frontend bootstrapped on Cloudflare Pages.

## Open Questions (to refine)
- [ ] Google OAuth client: shared single client or per-environment (dev/stage/prod)?
- [ ] Lambda packaging: SAM, Serverless Framework, AWS CDK, or plain zip via GitHub Actions? (Affects CI/CD tasks.)
- [x] DynamoDB: single table `app_data` (resolved — rate-limit + cache items use TTL in `app_data`; no separate tables).
- [ ] Cloudflare Pages: single project with preview deploys per branch, or manual promotion?
- [ ] Secrets: AWS Parameter Store (per doc) vs Secrets Manager? Parameter Store is cheaper; confirm acceptable.

## Goal
Deployable FastAPI skeleton on Lambda ARM64 with Google OIDC auth, session-code validation, RBAC middleware, rate limiting, and DynamoDB schema. Next.js app on Cloudflare Pages with login + session-code entry + role-based routing scaffold.

## Decisions (locked)
- Backend: FastAPI + Mangum on Lambda ARM64 (Python 3.12, 256 MB, 5–10s timeout).
- Backend layout per Section 11: `app/{main,auth,api,models,services,repositories,middleware}`.
- Reuse existing `src/main.py` matching logic, relocated into `app/services/matching.py` (adapted in Phase 4).
- Single DynamoDB table `app_data` (rate-limit + cache items use TTL attributes; no separate cache tables).
- Google OIDC for identity; session code = registration invite only.
- Multi-session per user: one global identity, many registrations.
- Rate limits: 60 req/min per IP, 120 req/min per user (Section 14).
- Next.js (App Router) on Cloudflare Pages via `next-on-pages`.

## Tasks (ordered)

### Backend
1. **Project scaffold**: create `app/` structure (Section 11). `app/main.py` = FastAPI app + Mangum handler. Add `pyproject.toml`, `requirements.txt`, `tests/`.
2. **CI/CD**: GitHub Actions (repo already uses `.github/workflows`). Workflows: lint (ruff/pylint), typecheck, unit tests, Lambda package + deploy on merge to main. Separate deploy for Cloudflare Pages.
3. **DynamoDB schema**: provision single table `app_data` via IaC (CDK or SAM). Implement `app/repositories/` with the PK/SK patterns + GSIs from Phase 1 ERD. Rate-limit counters + geocode cache stored as TTL items in `app_data`.
4. **Google OIDC auth**: `app/auth/oidc.py` — verify Google JWT, extract `sub`/`email`/`name`, enforce `USER#<sub>` upsert. Reject invalid/expired tokens. Issue app session (signed cookie or JWT).
5. **Session code validation**: `app/services/session.py` — validate code, check session expiration, registration window, status. Session code may be prepopulated via URL (`/register?session=ABC123`).
6. **RBAC middleware**: `app/middleware/rbac.py` — deny-default, role precedence (`Superuser > Manager > Session Admin > Driver > Passenger`), session-scoped role resolution.
7. **Rate limiting middleware**: `app/middleware/rate_limit.py` — token bucket (per IP + per user) stored as TTL items in `app_data`. *(Abuse detection deferred — post-MVP.)*
8. **Session management APIs**: `POST /sessions`, `GET /sessions/{code}`, `PATCH /sessions/{code}`, `DELETE /sessions/{code}` (Manager/Superuser). Enforce Session status enum transitions.
9. **Admin assignment API**: `POST /sessions/{code}/admin` — Manager assigns a user as Session Admin. (New endpoint added per Phase 1 decision.)
10. **Audit logging**: `app/middleware/audit.py` — record logins, auth failures, session changes, admin overrides to `AUDIT#DATE`.

### Frontend (Next.js on Cloudflare Pages)
1. **Bootstrap**: `npx create-next-app@latest` (App Router, TypeScript, Tailwind). Configure `next-on-pages`. Cloudflare Pages project with preview deploys per branch.
2. **API client**: typed fetch wrapper targeting the Lambda Function URL; auth cookie/JWT passthrough.
3. **Login screen**: Google Identity Services button → `POST /auth/google` → store session.
4. **Session-code entry**: `/register?session=ABC123` deep link + manual entry form → validates against backend.
5. **Role-based routing scaffold**: route guards (Superuser/Manager/Admin/Driver/Passenger) and a shared layout with role-aware nav.
6. **Session dashboard (Manager)**: list/create sessions; status badges.
7. **Config + secrets**: Google OAuth client id, Lambda Function URL via env at build time.

## Deliverables
- Deployable FastAPI Lambda (login + session CRUD + admin assignment working).
- Provisioned DynamoDB table `app_data` + GSIs.
- Next.js app on Cloudflare Pages (login + session-code entry + dashboard scaffold).
- CI/CD pipelines (GitHub Actions) for both backend and frontend.
- Smoke test: a user can Google-login, create a session (Manager), and assign an admin.

## Validation
- `POST /auth/google` rejects forged/expired JWTs.
- Session code validation rejects expired/closed sessions and unknown codes.
- Rate limiter returns 429 past 60/min IP and 120/min user.
- RBAC: a Passenger calling `DELETE /sessions/{code}` → 403.
- Audit log captures every login attempt and admin assignment.
- p95 API latency < 800ms on a smoke route.

## Dependencies
- Phase 1: `doc/api_contracts.md`, `doc/data_model_erd.md`, `doc/rbac_matrix.md`.
- Google OAuth client credentials provisioned.
- AWS account + Cloudflare account access.

## Out of Scope
- Registration forms (Phase 3).
- Maps integration (Phase 3).
- Matching engine (Phase 4).
- Email notifications (Phase 5).

---

## Task Breakdown

> Tasks are **vertically sliced** — each task delivers working, testable functionality spanning backend and frontend where appropriate. Tasks are sized S (1–2 files) or M (3–5 files). No task is XL. Each task has acceptance criteria, verification steps, dependencies, files likely touched, and a scope estimate.

> Phase 1 (Discovery) produces design artifacts, not code. It runs in parallel and is tracked in `plans/phase-1-discovery.md`. Foundation tasks can start once Phase 1 delivers `doc/api_contracts.md` and `doc/data_model_erd.md`. Remaining Phase 1 artifacts (wireframes, RBAC matrix) inform later tasks but don't block the scaffold.

### Task 2.1: Backend project scaffold + health endpoint [MVP]

**Description:** Create the FastAPI project structure per Section 11, with a Mangum handler, a `/health` endpoint, `pyproject.toml`, `requirements.txt`, and a test harness. This is the deployable skeleton that all subsequent backend tasks build on.

**Acceptance criteria:**
- [ ] `app/main.py` creates a FastAPI app with Mangum handler export
- [ ] `GET /health` returns `{"status": "ok"}` with 200
- [ ] `pyproject.toml` and `requirements.txt` pin FastAPI, Mangum, and test deps
- [ ] `pytest` runs and passes with at least one smoke test for `/health`

**Verification:**
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Local serve works: `uvicorn app.main:app` and `curl localhost:8000/health`
- [ ] Lambda handler importable: `python -c "from app.main import handler; print(handler)"`

**Dependencies:** None

**Files likely touched:**
- `app/main.py`
- `app/__init__.py`
- `pyproject.toml`
- `requirements.txt`
- `tests/test_health.py`

**Estimated scope:** S

### Task 2.2: DynamoDB schema + repository layer [MVP]

**Description:** Provision the single DynamoDB table `app_data` via IaC, and implement the repository layer with the PK/SK patterns and GSIs from the Phase 1 ERD. Rate-limit counters and geocode-cache items are stored as TTL items within `app_data` (no separate cache tables).

**Acceptance criteria:**
- [ ] IaC (CDK or SAM) provisions a single table `app_data` with correct key schemas
- [ ] `app/repositories/` implements base repository + User, Session, Registration, Match, Audit repos
- [ ] GSI `sessions-by-user` created on `app_data`
- [ ] TTL attributes configured on rate-limit + geocode-cache item types in `app_data`
- [ ] PITR enabled on `app_data`
- [ ] Repository unit tests pass against a local DynamoDB (docker) or moto mock

**Verification:**
- [ ] Tests pass: `pytest tests/repositories/ -v`
- [ ] IaC deploy succeeds to a dev account: `cdk deploy` (or equivalent)
- [ ] Manual check: put/get a User item and a Session item via repository

**Dependencies:** Task 2.1

**Files likely touched:**
- `infra/` (CDK or SAM stack — single `app_data` table)
- `app/repositories/base.py`
- `app/repositories/user.py`
- `app/repositories/session.py`
- `app/repositories/registration.py`
- `app/repositories/match.py`
- `app/repositories/audit.py`
- `tests/repositories/test_*.py`

**Estimated scope:** M

### Task 2.3: Google OIDC authentication (backend + frontend) [MVP]

**Description:** Implement Google OIDC login end-to-end. Backend verifies Google JWT, extracts `sub`/`email`/`name`, upserts a `USER#<sub>` record, and issues an app session (signed cookie or JWT). Frontend renders a Google login button, calls `POST /auth/google`, and stores the session. This is the first full vertical slice: a user can log in.

**Acceptance criteria:**
- [ ] `POST /auth/google` accepts a Google ID token, verifies signature + audience + expiry
- [ ] On success: upserts `USER#<sub>` in DynamoDB, returns app session token
- [ ] On invalid/expired token: returns 401 with clear error
- [ ] Frontend login page renders Google Identity Services button
- [ ] After login, frontend stores session and redirects to dashboard
- [ ] Unauthenticated requests to protected routes return 401

**Verification:**
- [ ] Tests pass: `pytest tests/auth/ -v`
- [ ] Manual check: complete Google login flow in browser, verify session cookie set
- [ ] Manual check: tampered JWT → 401

**Dependencies:** Task 2.2

**Files likely touched:**
- `app/auth/oidc.py`
- `app/api/auth.py`
- `app/middleware/auth.py`
- `frontend/src/app/login/page.tsx`
- `frontend/src/lib/api-client.ts`
- `tests/auth/test_oidc.py`

**Estimated scope:** M

### Task 2.4: RBAC middleware [MVP]

**Description:** Implement deny-default RBAC middleware with role precedence (`Superuser > Manager > Session Admin > Driver > Passenger`) and session-scoped role resolution. Endpoint decorators or dependency injection enforce permissions per Section 4.

**Acceptance criteria:**
- [ ] Middleware resolves user's global role + session-scoped role from DynamoDB
- [ ] Deny-default: any endpoint without explicit permission grants returns 403
- [ ] Role precedence enforced (Superuser overrides Session Admin, etc.)
- [ ] Session-scoped: a Session Admin for session A gets no admin rights on session B
- [ ] Unit tests cover all 5 roles × representative permissions

**Verification:**
- [ ] Tests pass: `pytest tests/middleware/test_rbac.py -v`
- [ ] Manual check: Passenger calling `DELETE /sessions/{code}` → 403
- [ ] Manual check: Manager calling `POST /sessions` → 201

**Dependencies:** Task 2.3

**Files likely touched:**
- `app/middleware/rbac.py`
- `app/models/roles.py`
- `tests/middleware/test_rbac.py`

**Estimated scope:** S

### Task 2.5: Session CRUD (backend + frontend) [MVP]

**Description:** Implement session management end-to-end. Manager/Superuser can create, read, update, delete sessions. Frontend renders a session dashboard with create form and status badges. Session status enum transitions enforced (Draft → Registration Open → … → Closed).

**Acceptance criteria:**
- [ ] `POST /sessions` (Manager+) creates a session with code, title, trip mode, anchor location, time windows, registration deadline, status=Draft
- [ ] `GET /sessions/{code}` returns session details (visible to registered users + admins)
- [ ] `PATCH /sessions/{code}` (Manager/Admin) updates fields; enforces valid status transitions
- [ ] `DELETE /sessions/{code}` (Manager+) soft-deletes/cancels a session
- [ ] Frontend dashboard lists sessions for the user; create form validates all fields
- [ ] Session code auto-generated or Manager-specified; unique

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_sessions.py -v`
- [ ] Manual check: create a session via UI, verify it appears in dashboard
- [ ] Manual check: invalid status transition (Draft → Approved) → 409

**Dependencies:** Task 2.4

**Files likely touched:**
- `app/api/sessions.py`
- `app/models/session.py`
- `app/services/session.py`
- `frontend/src/app/sessions/page.tsx`
- `frontend/src/app/sessions/create/page.tsx`
- `tests/api/test_sessions.py`

**Estimated scope:** M

### Task 2.6: Session code validation + registration entry (backend + frontend) [MVP]

**Description:** Implement the session-code entry flow. A user authenticates via Google, then enters (or follows a deep link with) a session code to register. Backend validates the code, checks session is open for registration and not expired. Frontend supports both manual entry and `/register?session=ABC123` deep links.

**Acceptance criteria:**
- [ ] `GET /sessions/{code}/eligibility` (or equivalent) validates code: exists, status=Registration Open, not past deadline
- [ ] Unknown code → 404; expired/closed → 409 with reason
- [ ] Deep link `/register?session=ABC123` pre-fills code and shows session summary
- [ ] Manager/Superuser can bypass session code requirement for registration
- [ ] Frontend shows session title/description/times before prompting role selection

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_session_code.py -v`
- [ ] Manual check: deep link with valid code → session summary page
- [ ] Manual check: invalid code → "session not found" message

**Dependencies:** Task 2.5

**Files likely touched:**
- `app/api/registration.py`
- `app/services/session.py` (extend)
- `frontend/src/app/register/page.tsx`
- `tests/api/test_session_code.py`

**Estimated scope:** S

### Task 2.7: Admin assignment API [MVP]

**Description:** Implement the new `POST /sessions/{code}/admin` endpoint. A Manager assigns a registered user as Session Admin for a specific session. Records the assignment in DynamoDB and fires an audit event.

**Acceptance criteria:**
- [ ] `POST /sessions/{code}/admin` (Manager+) accepts a user sub/email, assigns Session Admin role scoped to that session
- [ ] Only a user already registered in the session can be assigned as admin
- [ ] Assignment is idempotent (re-assigning same user is a no-op)
- [ ] Audit log entry written with actor, target, session code
- [ ] Non-Manager calling → 403

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_admin_assignment.py -v`
- [ ] Manual check: assign admin via API, verify RBAC grants admin permissions on that session only

**Dependencies:** Task 2.4, Task 2.5

**Files likely touched:**
- `app/api/admin.py`
- `app/services/session.py` (extend)
- `tests/api/test_admin_assignment.py`

**Estimated scope:** S

### Task 2.8: Rate limiting middleware (basic) [MVP]

> Abuse detection / brute-force escalation is **[DEFERRED]** (post-MVP). Single-tenant internal deployment = low abuse risk for first user.

**Description:** Implement basic token-bucket rate limiting (60 req/min per IP, 120 req/min per user) stored as TTL items in `app_data`. No abuse detection, brute-force escalation, or ban enforcement for MVP.

**Acceptance criteria:**
- [ ] Rate limiter returns 429 with `Retry-After` header when limit exceeded
- [ ] Per-IP and per-user buckets tracked as TTL items in `app_data`
- [ ] Configurable limits (env vars or config file)
- [ ] *(DEFERRED) Abuse detection / brute-force counter / exponential backoff / temporary bans — not in MVP scope*

**Verification:**
- [ ] Tests pass: `pytest tests/middleware/test_rate_limit.py -v`
- [ ] Manual check: burst 70 requests/min from one IP → 429 after 60th

**Dependencies:** Task 2.3

**Files likely touched:**
- `app/middleware/rate_limit.py`
- `tests/middleware/test_rate_limit.py`

**Estimated scope:** S

### Task 2.9: Audit logging middleware [MVP]

**Description:** Implement audit logging that captures login attempts, auth failures, session changes, admin overrides, and matching approvals (matching events come in Phase 4/5). Writes to `AUDIT#DATE` partition in DynamoDB.

**Acceptance criteria:**
- [ ] Middleware/decorator captures: login attempts (success+fail), session CRUD, admin assignment, RBAC denials
- [ ] Each entry has: timestamp, actor sub, action, resource, IP, result
- [ ] Audit writes are non-blocking (don't slow API responses)
- [ ] `GET /audit` (Superuser) returns paginated, filterable audit log

**Verification:**
- [ ] Tests pass: `pytest tests/middleware/test_audit.py -v`
- [ ] Manual check: perform a login + session create → verify audit entries in DynamoDB

**Dependencies:** Task 2.2

**Files likely touched:**
- `app/middleware/audit.py`
- `app/api/audit.py`
- `tests/middleware/test_audit.py`

**Estimated scope:** S

### Task 2.10: CI/CD pipelines (backend + frontend) [MVP]

**Description:** Set up GitHub Actions workflows for both backend and frontend. Backend: lint (ruff), type-check, unit tests, Lambda package + deploy on merge to main. Frontend: build, type-check, deploy to Cloudflare Pages with preview per branch.

**Acceptance criteria:**
- [ ] Backend workflow runs on PR + push: ruff check, mypy, pytest, then Lambda zip + deploy on main
- [ ] Frontend workflow runs on PR + push: tsc, build, then `wrangler pages deploy` on main
- [ ] Preview deploys created per branch on Cloudflare Pages
- [ ] Secrets (Google OAuth client, AWS creds, Cloudflare API token) stored as GitHub Actions secrets
- [ ] Workflow status badges added to README

**Verification:**
- [ ] Push to a feature branch → CI runs green
- [ ] Merge to main → deploy succeeds; Lambda Function URL + Cloudflare Pages URL both serve
- [ ] Manual check: deployed `/health` endpoint responds

**Dependencies:** Task 2.1, Task 2.3 (frontend bootstrap needed)

**Files likely touched:**
- `.github/workflows/backend-ci.yml`
- `.github/workflows/frontend-ci.yml`
- `README.md` (badges)

**Estimated scope:** M

### Task 2.11: Next.js frontend bootstrap [MVP]

**Description:** Bootstrap the Next.js app with App Router, TypeScript, Tailwind, and `next-on-pages` adapter. Set up the API client, auth context, and role-based routing scaffold. This is the frontend foundation that all UI tasks build on.

**Acceptance criteria:**
- [ ] `npx create-next-app` with App Router + TypeScript + Tailwind
- [ ] `@cloudflare/next-on-pages` configured; `wrangler.toml` set up
- [ ] API client (`lib/api-client.ts`) with typed fetch wrapper, auth token passthrough
- [ ] Auth context provider wrapping the app; protected route guard component
- [ ] Role-aware layout with nav showing different links per role
- [ ] Deploys to Cloudflare Pages successfully

**Verification:**
- [ ] Build succeeds: `npm run build`
- [ ] Local dev works: `npm run dev` → renders landing page
- [ ] Cloudflare preview deploy URL accessible

**Dependencies:** None (can start in parallel with backend tasks)

**Files likely touched:**
- `frontend/` (entire scaffold)
- `frontend/src/app/layout.tsx`
- `frontend/src/lib/api-client.ts`
- `frontend/src/lib/auth-context.tsx`
- `frontend/wrangler.toml`

**Estimated scope:** M

### Checkpoint: End of Phase 2
- [ ] All tests pass (backend + frontend)
- [ ] A user can Google-login, create a session (Manager), assign an admin, and enter a session code
- [ ] Rate limiter and audit logging active
- [ ] Both backend and frontend deployed (Lambda + Cloudflare Pages)
- [ ] **Review with human before proceeding to Phase 3**

### Parallelization notes
- Task 2.1 → 2.2 → 2.3 are strictly sequential.
- Task 2.4 depends on 2.3; Task 2.5 depends on 2.4.
- Task 2.7 (admin assignment) can be built in parallel with 2.5/2.6 once 2.4 lands.
- Task 2.11 (frontend bootstrap) is independent of all backend tasks and can start immediately.

### Risks (Phase 2 specific)
| Risk | Impact | Mitigation |
|------|--------|------------|
| OAuth client misconfig blocks all auth | High | Test with Google Identity Services dev keys first; document client ID/secret rotation |
| IaC drift between local and prod | Medium | Single `app_data` table in one IaC stack; deploy dev first, then prod; never edit via console |
| Lambda cold start on first deploy | Low | Provisioned concurrency off in dev; tune in Phase 6 |
