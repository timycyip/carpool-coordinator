# Phase 2 — Foundation Plan

Builds on Phase 1 artifacts (`docs/requirements_baseline.md`, `docs/api_contracts.md`,
`docs/data_model_erd.md`, `docs/rbac_matrix.md`). Goal: working Google login + session setup
deployed to AWS, with the Next.js frontend bootstrapped on Cloudflare Pages.

---

## Progress & Decision Log

> **Status as of 2026-06-23:** SPECIFY gate complete. All blocking open questions resolved
> by human review. Phase 2 implementation is **gated on Phase 1 Discovery completing**
> `docs/api_contracts.md`, `docs/data_model_erd.md`, and `docs/rbac_matrix.md`. No Phase 2
> implementation task (2.1+) may start until those artifacts land.

| # | Decision (resolved 2026-06-23) | Resolution | ADR / Notes |
|---|---|---|---|
| 1 | Phase 1 artifacts missing | **Complete Phase 1 first.** Phase 1 Discovery produces `docs/api_contracts.md`, `docs/data_model_erd.md`, `docs/rbac_matrix.md`, wireframes before any Phase 2 code. | Hard prerequisite; gates Task 2.2+ |
| 2 | DynamoDB table strategy | **Tables named per data model** (NOT single-table consolidation). | ADR-0001 `docs/adr/0001-table-naming-by-data-model.md` |
| 3 | App session mechanism | **JWT.** Backend issues a signed JWT after Google OIDC verification. Frontend stores in memory (not localStorage). | ADR-0002; human-confirmed 2026-06-23 |
| 4 | IaC choice | **Terraform** (provisioned via GitHub Actions on merge to main). | ADR-0003; human-confirmed 2026-06-23 |
| 5 | AWS region | **`us-east-2`** (Ohio). | ADR-0003; human-confirmed 2026-06-23 |
| 6 | Secrets store | **AWS Parameter Store** (per requirements doc §10). | Tasks 2.3, 2.10 |
| 7 | Docs dir naming (`docs/` vs `doc/`) | **Open — to be settled in Phase 1.** AGENTS.md and this plan reference `doc/`; repo currently uses `docs/`. | Low risk; resolves with Phase 1 artifacts |

**Remaining open (lower risk, decide inline during implementation):**
- ~~Google OAuth client: single shared vs per-environment~~ → **RESOLVED (2026-06-23): single shared client.** One client ID/secret; injected via Parameter Store / env at deploy time.
- ~~Cloudflare Pages: single project + preview-per-branch vs manual promotion~~ → **RESOLVED (2026-06-23): preview-per-branch.** Every branch push → preview URL; merge to main → production.

---

## Spec

> This section is the **Phase 1 (Specify)** gate of spec-driven development. The Plan
> (Decisions/Goal) and Tasks below correspond to phases 2 and 3. The spec must be reviewed and
> the assumptions/​open questions resolved or accepted **before** implementation (Task 2.1) starts.
> Per the gated workflow, do not advance to IMPLEMENT until the human has reviewed this spec.

### Assumptions I'm making

> These are the most dangerous form of misunderstanding. Correct any that are wrong before I
> proceed to implementation.

1. **Phase 1 artifacts are a hard dependency and are NOT yet complete.** The repo currently
   contains only `docs/functional_requirements_and_architecture.md` and `docs/ideas/`.
   `docs/api_contracts.md`, `docs/data_model_erd.md`, `docs/rbac_matrix.md`, and wireframes are
   referenced by Tasks 2.2/2.4/2.5 but do **not exist yet**. → **RESOLVED (2026-06-23):**
   Phase 1 Discovery completes these first. No Phase 2 implementation (Task 2.1+) starts until
   they land.
2. The target layout adds an `app/` Python backend and a separate `frontend/` Next.js project;
   the legacy `src/main.py` and `test/` remain untouched (matching logic is *adapted*, not moved,
   until Phase 4).
3. Backend runs on **Python 3.12** (Lambda ARM64 target); all new Python code uses `uv`,
   `ruff`, `mypy --strict`, `pytest` — replacing the legacy `pylint`/`unittest`/Python 3.8 toolchain.
4. The frontend is a **single** Next.js (App Router) app deployed to **Cloudflare Pages** via
   `next-on-pages`; it talks to the backend over the Lambda Function URL.
5. ~~There is exactly **one** DynamoDB table (`app_data`)~~ → **SUPERSEDED (2026-06-23):**
   Tables are **named per data model**, per ADR-0001. The single-table consolidation was
   rejected. Rate-limit/cache/brute-force tables remain separate (per requirements doc §10),
   with TTL attributes where appropriate. Exact table names finalized by Phase 1 ERD.
6. App session issuance uses a **signed cookie OR JWT** — ~~the mechanism is not yet decided~~ →
   **RESOLVED (2026-06-23): JWT.**
7. Local dev uses DynamoDB via **docker (dynamo-local) for repository integration tests** and
   **moto** for fast unit tests, with real tables provisioned via **Terraform** (was: "CDK or
   SAM") for deployed envs.
8. Rate limiting is MVP-only (token bucket); **abuse detection / brute-force escalation / bans are
   deferred** to post-MVP (per Task 2.8). Cloudflare WAF (Free) is the edge layer.
9. Single-tenant / first-user internal deployment for MVP — low abuse risk justifies deferring
   abuse controls.

→ ~~Correct me now or I'll proceed with these.~~ → **All corrected/resolved; see Progress &
Decision Log above.**

### Objective

Phase 2 delivers the **deployable foundation** of the carpool platform: an authenticated,
authorized, observable API skeleton plus a bootstrapped frontend, so that a real user can
Google-log-in, have a Manager create a carpool session, assign a Session Admin, and enter a
session code to register — end to end, deployed, not just locally.

It is the substrate every later phase builds on (registration in Phase 3, matching in Phase 4,
approval/notification in Phase 5). Nothing in Phases 3–6 can ship until Phase 2's foundation
(auth, RBAC, persistence, CI/CD) is green and deployed.

**User stories (Phase 2 scope):**
- As a **Manager**, I can log in with Google, create a session, and assign a Session Admin.
- As a **Passenger**, I can log in with Google and enter (or deep-link) a session code to reach a
  session summary before registration (full registration forms are Phase 3).
- As a **Superuser**, I can view the audit log of logins, session changes, and admin assignments.

**Out of scope (explicitly deferred):** registration forms, maps/geocoding/routing, the matching
engine, email notifications, load testing, and production hardening (Phases 3–6).

### Tech Stack

**Backend**
- Python 3.12, FastAPI, Mangum (Lambda adapter)
- AWS Lambda (ARM64, 256 MB, 5–10s timeout), DynamoDB (tables per data model — see ADR-0001)
- `uv` (package manager), `ruff` (lint+format), `mypy --strict` (types), `pytest` (tests)
- Google OIDC (identity) + app-issued **JWT** session (resolved 2026-06-23)
- IaC: **Terraform** (provisioned via GitHub Actions) — region **`us-east-2`**

**Frontend**
- Node.js LTS, Next.js (App Router), TypeScript, Tailwind CSS
- `@cloudflare/next-on-pages` adapter; Cloudflare Pages hosting (preview per branch)
- `eslint`, `prettier`, `tsc --noEmit`, Vitest (unit), Playwright (e2e — TBD)

**Infra / Edge**
- AWS (Lambda Function URL, DynamoDB, CloudWatch, S3 logs→Athena, Parameter Store)
- Cloudflare Pages + Cloudflare Free edge/WAF
- GitHub Actions for CI/CD (replaces the legacy `pylint.yml`/`unittest.yml` workflows for new code)

### Commands

Backend (run from repo root once `app/` exists):
```bash
uv sync                                    # install deps
uv run pytest                              # all tests
uv run pytest tests/repositories/ -v       # filtered
uv run pytest --cov=app --cov-report=term-missing   # coverage
uv run ruff check .                        # lint
uv run ruff format --check .              # format check
uv run mypy .                              # types (strict)
uv run uvicorn app.main:app --reload       # local dev server
python -c "from app.main import handler"   # Lambda handler import smoke
```

Legacy CLI (still runnable, not modified in Phase 2):
```bash
pip install -r requirements.txt
python3 src/main.py <input_csv> <output_csv>
```

Frontend (run from `frontend/`):
```bash
npm install
npm run dev                                # local Next.js
npm run lint                               # eslint
npx tsc --noEmit                           # type check
npm run build                              # production build (next-on-pages)
```

### Project Structure

```
app/                        → Backend source (FastAPI + Mangum)
  main.py                   → FastAPI app + Mangum handler export
  auth/                     → Google OIDC verification, session issuance
  api/                      → Route modules (auth, sessions, registration, admin, audit)
  models/                   → Pydantic models + enums (roles, session status)
  services/                 → Business logic (session validation, etc.); matching.py added in Phase 4
  repositories/             → DynamoDB data access (base, user, session, registration, match, audit)
  middleware/               → auth, rbac, rate_limit, audit
infra/                      → IaC (Terraform) — provisions DynamoDB tables per Phase 1 ERD + GSIs
tests/                      → pytest tests, mirrored to app/ layout (auth/, api/, repositories/, middleware/)
frontend/                   → Next.js app (App Router, TS, Tailwind)
  src/app/                  → routes (login, register, sessions, dashboard)
  src/lib/                  → api-client, auth-context
  wrangler.toml             → Cloudflare Pages / next-on-pages config
src/                        → Legacy CLI (untouched in Phase 2; matching logic adapted in Phase 4)
test/                       → Legacy unittest tests (untouched)
mock/                       → Legacy CSV fixtures
docs/                       → Requirements + architecture + Phase 1 design artifacts
plans/                      → Phase plans (this file + phase-1, phase-3..6)
docs/adr/           → Architecture Decision Records
.github/workflows/          → CI/CD (backend-ci.yml, frontend-ci.yml added; legacy pylint/unittest remain for src/)
```

> Note: the repo uses `docs/` (with an `s`) today; the AGENTS.md and requirements doc reference
> `docs/` is canonical (renamed 2026-06-23).

### Code Style

One real snippet illustrates the backend conventions (ruff-formatted, strict-typed, dependency
injection for RBAC, deny-default):

```python
"""Session management API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.middleware.rbac import CurrentUser, require_role
from app.models.roles import Role
from app.models.session import SessionStatus
from app.services.session import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    trip_mode: str
    anchor_location: dict[str, float]
    earliest_pickup: str  # ISO datetime
    latest_arrival: str
    registration_deadline: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    user: Annotated[CurrentUser, Depends(require_role(Role.MANAGER))],
    service: Annotated[SessionService, Depends()],
) -> dict[str, str]:
    """Create a new carpool session (Manager+)."""
    session = await service.create(body, actor=user)
    return {"session_code": session.code}
```

Conventions: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE` for enums;
modules typed with `mypy --strict` (no `Any` without `# type: ignore[reason]`); RBAC via FastAPI
`Depends` (deny-default — every protected route explicitly declares required role); Pydantic
models for all request/response bodies; `async` route handlers; ruff `format` (line length 88).

### Testing Strategy

- **Backend framework:** `pytest` + `pytest-asyncio`. Locations mirror `app/` under `tests/`
  (`tests/auth/`, `tests/api/`, `tests/repositories/`, `tests/middleware/`).
- **DynamoDB in tests:** `moto` for unit tests (fast, in-memory); docker `dynamo-local` for
  repository integration tests. No live AWS calls in CI unit tests.
- **Coverage:** ≥ 80% on changed code (`pytest --cov=app --cov-report=term-missing`).
- **Test levels:**
  - Unit — pure functions, services with mocked repos, middleware logic.
  - Integration — repository ↔ dynamo-local; API route ↔ service ↔ mocked repo.
  - Contract — auth/JWT verification against known-good/known-bad Google tokens.
- **Frontend:** Vitest for unit (api-client, auth-context), Playwright for e2e (login → dashboard
  flow) — bootstrapped in Phase 2, expanded in Phase 3.
- **No silent skips:** if a frontend test runner isn't set up for a task, note it in the PR with
  justification; do not silently omit.

### Boundaries

- **Always do:**
  - Run `pytest`, `ruff check`, `ruff format --check`, `mypy .` before every commit (backend);
    `npm run lint`, `tsc --noEmit`, `npm run build` before every frontend commit.
  - Follow TDD: failing test first for any logic change.
  - Validate all inputs with Pydantic models; deny-default RBAC on every protected route.
  - Reference the spec/FR number in commit messages and PR descriptions.
  - Keep `src/main.py` and `test/` (legacy) untouched unless a task explicitly adapts matching logic.
- **Ask first (human approval required per AGENTS.md §12):**
  - Any **DynamoDB schema change** (table/GSI/TTL) — table boundaries are decided by the Phase 1
    ERD; deviations need an ADR. *(See ADR-0001: tables are named per data model; single-table
    consolidation was rejected.)*
  - **AWS region** changes (currently locked to `us-east-2`) — affects OSRM geography later.
  - Changing the **secrets store** choice (currently AWS Parameter Store).
  - Changing CI config, adding dependencies, or modifying the Google OAuth client configuration.
  - Any architectural decision needing an ADR (e.g., further deviation from requirements doc
    Section 10's table list beyond what Phase 1 ERD finalizes).
- **Never do:**
  - Commit secrets (Google OAuth client secret, AWS keys, OSRM endpoints) — use Parameter Store / env.
  - Edit vendor/node_modules or generated `next-on-pages` output.
  - Remove a failing test to make CI green without approval.
  - Implement features outside the Phase 2 scope (registration forms, maps, matching, email).
  - Skip the spec — update this spec first if scope/decisions change.

### Success Criteria

Reframed from the vague goal "working login + session setup deployed to AWS":

- [ ] A user can complete a **Google OIDC login** in the deployed frontend and receive an app
  session (cookie or JWT) — tampered/expired Google tokens return **401**.
- [ ] A **Manager** can `POST /sessions` to create a session; it appears in the frontend dashboard
  with the correct status badge. A **Passenger** calling `POST /sessions` returns **403**.
- [ ] A **Manager** can `POST /sessions/{code}/admin` to assign a Session Admin; the assignment is
  idempotent and scoped (admin rights for session A grant nothing on session B).
- [ ] A user can enter a session code (manual or `/register?session=ABC123` deep link) and, for an
  open session, see the session summary; **unknown code → 404**, **expired/closed → 409**.
- [ ] **Session status transitions** are enforced: an invalid transition (e.g., Draft → Approved)
  returns **409**.
- [ ] **Rate limiting** returns **429** with `Retry-After` past 60 req/min (IP) or 120 req/min (user).
- [ ] **Audit log** captures every login attempt (success + failure), session CRUD, and admin
  assignment; `GET /audit` (Superuser) returns paginated entries.
- [ ] **p95 API latency < 800ms** on the smoke route (login → create session) in the deployed env.
- [ ] Both **backend (Lambda)** and **frontend (Cloudflare Pages)** are deployed on merge to main;
  the deployed `/health` endpoint responds 200.
- [ ] All quality gates green: `pytest` (≥80% on changed code), `ruff check`, `ruff format --check`,
  `mypy .` (backend); `npm run lint`, `tsc --noEmit`, `npm run build` (frontend).

### Open Questions

*(Resolved 2026-06-23 — see Progress & Decision Log at top of this file. Summary below.)*

1. ~~**[BLOCKER] Phase 1 artifacts missing.~~ → **RESOLVED:** Complete Phase 1 first. Phase 1
   Discovery delivers `docs/api_contracts.md`, `docs/data_model_erd.md`, `docs/rbac_matrix.md`
   before any Phase 2 implementation task starts.
2. ~~**IaC choice**~~ → **RESOLVED:** Terraform (provisioned via GitHub Actions).
3. ~~**Google OAuth client**~~ → **RESOLVED (2026-06-23):** single shared client. Injected via Parameter Store / env.
   
4. ~~**Cloudflare Pages**~~ → **RESOLVED (2026-06-23):** preview-per-branch. Every branch push → preview URL; merge to main → production.
   
5. ~~**Secrets store**~~ → **RESOLVED:** AWS Parameter Store.
6. ~~**App session mechanism**~~ → **RESOLVED:** JWT.
7. ~~**AWS region**~~ → **RESOLVED:** `us-east-2`.
8. ~~**Docs dir naming**~~ → **RESOLVED (2026-06-23):** `docs/` is canonical. All references updated.
   To be settled in Phase 1 when artifacts are created.
9. ~~**Single-table ADR**~~ → **RESOLVED via ADR-0001:** single-table consolidation **rejected**;
   tables named per data model per the Phase 1 ERD.

---

## Open Questions (to refine)
- [x] ~~Google OAuth client: shared single client or per-environment?~~ → **RESOLVED:** single shared client (2026-06-23).
- [ ] ~~Lambda packaging: SAM, Serverless Framework, AWS CDK, or plain zip via GitHub Actions?~~ → **RESOLVED:** Terraform via GitHub Actions.
- [x] ~~DynamoDB: single table `app_data`~~ → **RESOLVED via ADR-0001:** tables named per data model (single-table consolidation rejected).
- [x] ~~Cloudflare Pages: preview-per-branch vs manual promotion?~~ → **RESOLVED:** preview-per-branch (2026-06-23).
- [x] ~~Secrets: AWS Parameter Store vs Secrets Manager?~~ → **RESOLVED:** AWS Parameter Store.

## Goal
Deployable FastAPI skeleton on Lambda ARM64 with Google OIDC auth, session-code validation, RBAC middleware, rate limiting, and DynamoDB schema. Next.js app on Cloudflare Pages with login + session-code entry + role-based routing scaffold.

## Architecture

> Full design lives in [`ARCHITECTURE.md`](../ARCHITECTURE.md) (reconciled with the Decision Log
> and ADR-0001, 2026-06-23). This section summarizes the architecture-relevant decisions and ADRs
> that constrain the tasks below.

**Deployment topology (us-east-2):**
```
Browser ──HTTPS──► Cloudflare (Pages + edge/WAF)
                       │  next.config rewrites() proxies /api/* (same-origin, no CORS)
                       ▼
                 Lambda ARM64 (FastAPI + Mangum)
                       │  middleware: rate_limit → audit → auth → rbac
                       ▼
                 Service → Repository → DynamoDB (tables per data model, ADR-0001)
                            │  audit write (async)
                 Parameter Store (secrets) ─► CloudWatch ─► S3(30d) ─► Athena
```

**Architectural constraints for implementation:**
- **Same-origin via Pages `rewrites()`** (ADR-004, recommended) — wire `/api/*` → Lambda URL before
  auth (Task 2.11 / 2.3). Avoids CORS preflight; hides the Lambda URL.
- **JWT stored in memory** in the browser (ADR-002, LOCKED) — not `localStorage` (XSS resistance).
  Authorization: Bearer header on every `/api/*` call.
- **Middleware order:** `rate_limit → audit → auth → rbac` (ADR-005) — cheapest reject first;
  audit captures denials with the resolved actor; audit writes are non-blocking.
- **Implement RBAC as FastAPI `Depends`** (per-route), not global middleware — enforces deny-default
  at the type system (`Depends(require_role(...))`).
- **Google JWKS cached** in Lambda (ADR-006, TTL ~1h) — avoids a network call per login to keep
  p95 < 800ms; fall back to cached keys on fetch failure.
- **Terraform state:** S3 + DynamoDB lock backend configured in Task 2.10 (ADR-003).

**ADRs (status):**
| # | Decision | Status | File |
|---|----------|--------|------|
| ADR-0001 | Tables named per data model (reject single-table) | **LOCKED** | `docs/adr/0001-table-naming-by-data-model.md` (exists) |
| ADR-0002 | App session = JWT (in-memory browser storage) | Accepted | `docs/adr/0002-app-session-jwt.md` (exists) |
| ADR-0003 | IaC = Terraform; region = us-east-2 | Accepted | `docs/adr/0003-terraform-iac-us-east-2.md` (exists) |
| ADR-0004 | Same-origin via CF Pages `rewrites()` | Accepted | `docs/adr/0004-same-origin-rewrites.md` (exists) |
| ADR-0005 | Middleware order `rate_limit→audit→auth→rbac` | Accepted | `docs/adr/0005-middleware-ordering.md` (exists) |
| ADR-0006 | Google JWKS cached in Lambda | Accepted | `docs/adr/0006-jwks-caching.md` (exists) |
| ADR-0007 | DynamoDB on-demand capacity | Accepted | `docs/adr/0007-dynamodb-on-demand.md` (exists) |

> ADR-0002 (auth posture) and ADR-0003 (IaC) require human-approval status recorded when written,
> per AGENTS.md §12. ADR-0004..0007 are within existing patterns but must be recorded for
> traceability. All ADR files should be created in the DOCUMENTATION phase of their owning task
> (Task 2.2 → ADR-0001; Task 2.3 → ADR-0002/0006; Task 2.10 → ADR-0003/0007; Task 2.11 → ADR-0004).

## Decisions (locked)
- Backend: FastAPI + Mangum on Lambda ARM64 (Python 3.12, 256 MB, 5–10s timeout).
- Backend layout per Section 11: `app/{main,auth,api,models,services,repositories,middleware}`.
- Reuse existing `src/main.py` matching logic, relocated into `app/services/matching.py` (adapted in Phase 4).
- DynamoDB tables **named per data model** per Phase 1 ERD — **NOT** single-table consolidation
  (ADR-0001, resolved 2026-06-23). Rate-limit/cache/brute-force tables remain separate with TTL
  where appropriate; exact names finalized in `docs/data_model_erd.md`.
- Google OIDC for identity; **app session = JWT** (resolved 2026-06-23); session code = registration invite only.
- Multi-session per user: one global identity, many registrations.
- Rate limits: 60 req/min per IP, 120 req/min per user (Section 14).
- Next.js (App Router) on Cloudflare Pages via `next-on-pages`.
- IaC: **Terraform** via GitHub Actions; region **`us-east-2`** (resolved 2026-06-23).
- Secrets: **AWS Parameter Store** (resolved 2026-06-23).
- **Phase 1 is a hard prerequisite** — no Phase 2 implementation (Task 2.1+) until Phase 1
  delivers `docs/api_contracts.md`, `docs/data_model_erd.md`, `docs/rbac_matrix.md`.

## Tasks (ordered)

### Backend
1. **Project scaffold**: create `app/` structure (Section 11). `app/main.py` = FastAPI app + Mangum handler. Add `pyproject.toml`, `requirements.txt`, `tests/`.
2. **CI/CD**: GitHub Actions (repo already uses `.github/workflows`). Workflows: lint (ruff/pylint), typecheck, unit tests, Lambda package + deploy on merge to main. Terraform apply on merge to main (provisions/updates infra). Separate deploy for Cloudflare Pages.
3. **DynamoDB schema**: provision DynamoDB tables **per the Phase 1 ERD** (`docs/data_model_erd.md`) via **Terraform** (ADR-0001 — tables named by data model, not consolidated). Implement `app/repositories/` with the PK/SK patterns + GSIs from Phase 1. Rate-limit counters + geocode cache stored as TTL items in their own cache/counter tables.
4. **Google OIDC auth**: `app/auth/oidc.py` — verify Google JWT, extract `sub`/`email`/`name`, enforce `USER#<sub>` upsert. Reject invalid/expired tokens. Issue app session **JWT** (resolved 2026-06-23).
5. **Session code validation**: `app/services/session.py` — validate code, check session expiration, registration window, status. Session code may be prepopulated via URL (`/register?session=ABC123`).
6. **RBAC middleware**: `app/middleware/rbac.py` — deny-default, role precedence (`Superuser > Manager > Session Admin > Driver > Passenger`), session-scoped role resolution.
7. **Rate limiting middleware**: `app/middleware/rate_limit.py` — token bucket (per IP + per user) stored as TTL items in the rate-limit table per Phase 1 ERD. *(Abuse detection deferred — post-MVP.)*
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
- Provisioned DynamoDB tables (per Phase 1 ERD) + GSIs, via Terraform.
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
- **Phase 1 (hard prerequisite):** `docs/api_contracts.md`, `docs/data_model_erd.md`,
  `docs/rbac_matrix.md` must be complete before any Phase 2 implementation task (2.1+) starts.
- Google OAuth client credentials provisioned.
- AWS account (`us-east-2`) + Cloudflare account access.

## Out of Scope
- Registration forms (Phase 3).
- Maps integration (Phase 3).
- Matching engine (Phase 4).
- Email notifications (Phase 5).

---

## Task Breakdown

> Tasks are **vertically sliced** — each task delivers working, testable functionality spanning backend and frontend where appropriate. Tasks are sized S (1–2 files) or M (3–5 files). No task is XL. Each task has acceptance criteria, verification steps, dependencies, files likely touched, and a scope estimate.

> Phase 1 (Discovery) produces design artifacts, not code. It runs in parallel and is tracked in `plans/phase-1-discovery.md`. Foundation tasks can start once Phase 1 delivers `docs/api_contracts.md` and `docs/data_model_erd.md`. Remaining Phase 1 artifacts (wireframes, RBAC matrix) inform later tasks but don't block the scaffold.

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

**Description:** Provision DynamoDB tables **per the Phase 1 ERD** (`docs/data_model_erd.md`) via
**Terraform**, and implement the repository layer with the PK/SK patterns and GSIs defined there.
Tables are **named per data model** (ADR-0001) — the single-table consolidation was rejected.
Rate-limit counters and geocode-cache items live in their own cache/counter tables with TTL
attributes, not inside the application data table.

**Acceptance criteria:**
- [ ] Terraform provisions all DynamoDB tables defined in the Phase 1 ERD with correct key schemas
- [ ] `app/repositories/` implements base repository + User, Session, Registration, Match, Audit repos
- [ ] GSIs from the ERD created (e.g., `sessions-by-user`, `registrations-by-session`, `latest-match-by-session`)
- [ ] TTL attributes configured on rate-limit + geocode-cache + brute-force counter tables per ERD
- [ ] PITR enabled on durable application-data tables per ERD
- [ ] Repository unit tests pass against a local DynamoDB (docker) or moto mock

**Verification:**
- [ ] Tests pass: `pytest tests/repositories/ -v`
- [ ] Terraform apply succeeds to a dev account: `cd infra && terraform plan && terraform apply`
- [ ] Manual check: put/get a User item and a Session item via repository

**Dependencies:** Task 2.1, **Phase 1 ERD (`docs/data_model_erd.md`)**

**Files likely touched:**
- `infra/` (Terraform — DynamoDB tables per ERD)
- `app/repositories/base.py`
- `app/repositories/user.py`
- `app/repositories/session.py`
- `app/repositories/registration.py`
- `app/repositories/match.py`
- `app/repositories/audit.py`
- `tests/repositories/test_*.py`

**Estimated scope:** M

### Task 2.3: Google OIDC authentication (backend + frontend) [MVP]

**Description:** Implement Google OIDC login end-to-end. Backend verifies Google JWT, extracts `sub`/`email`/`name`, upserts a `USER#<sub>` record, and issues an **app session JWT** (resolved 2026-06-23). Frontend renders a Google login button, calls `POST /auth/google`, and stores the JWT. This is the first full vertical slice: a user can log in.

**Acceptance criteria:**
- [ ] `POST /auth/google` accepts a Google ID token, verifies signature + audience + expiry
- [ ] On success: upserts `USER#<sub>` in DynamoDB, returns app session **JWT** (signed with a secret from Parameter Store)
- [ ] On invalid/expired token: returns 401 with clear error
- [ ] Frontend login page renders Google Identity Services button
- [ ] After login, frontend stores the JWT and redirects to dashboard
- [ ] Unauthenticated requests to protected routes return 401

**Verification:**
- [ ] Tests pass: `pytest tests/auth/ -v`
- [ ] Manual check: complete Google login flow in browser, verify JWT issued and stored
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

**Description:** Implement basic token-bucket rate limiting (60 req/min per IP, 120 req/min per user) stored as TTL items in the rate-limit table per Phase 1 ERD (ADR-0001). No abuse detection, brute-force escalation, or ban enforcement for MVP.

**Acceptance criteria:**
- [ ] Rate limiter returns 429 with `Retry-After` header when limit exceeded
- [ ] Per-IP and per-user buckets tracked as TTL items in the rate-limit table (per ERD)
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

**Description:** Set up GitHub Actions workflows for both backend and frontend. Backend: lint (ruff), type-check, unit tests, Lambda package + deploy on merge to main, plus **Terraform plan/apply** for infra (`us-east-2`). Frontend: build, type-check, deploy to Cloudflare Pages with preview per branch.

**Acceptance criteria:**
- [ ] Backend workflow runs on PR + push: ruff check, mypy, pytest, then Lambda zip + deploy on main
- [ ] Terraform workflow runs on PR (plan) + on merge to main (apply) against `us-east-2`
- [ ] Frontend workflow runs on PR + push: tsc, build, then `wrangler pages deploy` on main
- [ ] Preview deploys created per branch on Cloudflare Pages
- [ ] Secrets (Google OAuth client, AWS creds, Cloudflare API token, JWT signing secret) stored as GitHub Actions secrets → Parameter Store in deployed env
- [ ] Workflow status badges added to README

**Verification:**
- [ ] Push to a feature branch → CI runs green
- [ ] Merge to main → deploy succeeds; Lambda Function URL + Cloudflare Pages URL both serve
- [ ] Terraform apply is idempotent (`terraform plan` shows no changes after apply)
- [ ] Manual check: deployed `/health` endpoint responds

**Dependencies:** Task 2.1, Task 2.3 (frontend bootstrap needed)

**Files likely touched:**
- `.github/workflows/backend-ci.yml`
- `.github/workflows/terraform.yml`
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
- **Phase 1 Discovery must complete `docs/api_contracts.md`, `docs/data_model_erd.md`, and
  `docs/rbac_matrix.md` before any Phase 2 implementation task starts.**
- Task 2.1 → 2.2 → 2.3 are strictly sequential.
- Task 2.4 depends on 2.3; Task 2.5 depends on 2.4.
- Task 2.7 (admin assignment) can be built in parallel with 2.5/2.6 once 2.4 lands.
- Task 2.11 (frontend bootstrap) is independent of all backend tasks and can start immediately
  once Phase 1 lands (no backend dependency for the scaffold itself).

### Risks (Phase 2 specific)
| Risk | Impact | Mitigation |
|------|--------|------------|
| OAuth client misconfig blocks all auth | High | Test with Google Identity Services dev keys first; document client ID/secret rotation |
| IaC drift between local and prod | Medium | Tables provisioned via Terraform (single source of truth, `us-east-2`); deploy dev first, then prod; never edit via console; `terraform plan` must be clean post-apply |
| Lambda cold start on first deploy | Low | Provisioned concurrency off in dev; tune in Phase 6 |
