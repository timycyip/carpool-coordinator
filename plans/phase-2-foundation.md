# Phase 2 — Foundation Plan

Builds on Phase 1 artifacts (`docs/requirements_baseline.md`, `docs/api_contracts.md`,
`docs/data_model_erd.md`, `docs/rbac_matrix.md`). Goal: working Google login + session setup
deployed to AWS, with the Next.js frontend bootstrapped on Cloudflare Pages.

---

## Phase 1 Review Advisories (carried forward)

These advisories from the Phase 1 consolidated review must be addressed during Phase 2.

| Priority | ID | Advisory | Owner |
|----------|----|----------|-------|
| **Week 1** | A1 | `plans/phase-1-discovery.md` Decisions section still references stale pre-ADR decisions (single consolidated table, synchronous email). Add an ADR supersession banner at the top of the plan. | Task 2.1 |
| **Week 1** | A3 | `KNOWLEDGE.md` not created at repo root. AGENTS.md §17 requires it after first task wrap-up. Capture: ADR-0001 multi-table rationale, ADR-0008 deferred-delivery reversal, canonical schema supremacy principle. | Task 2.1 |
| **Week 1** | A5 | `docs/functional_requirements_and_architecture.md` (master spec) §10 lists 4 tables (now 5 per ADR-0001) and §13/§14 describe synchronous email (now deferred per ADR-0008). Add an amendment banner at the top of the spec listing superseding ADRs. | Task 2.1 |
| **Phase 2** | A7 | `gsi_latest_match_by_session` in the ERD is architecturally redundant — the main-table Query on `SESSION#<code>` + `SK begins_with MATCH#` returns the same data at identical cost. During Task 2.2, evaluate: drop the GSI or document the cost-benefit rationale. | Task 2.2 |
| **Phase 2** | A9 | NFR-SCALE-2 states "idle cost = $0" — literally false (CloudWatch Logs ingestion is never zero). Reword to "≤ $1/month idle" or define a measurement window in `docs/requirements_baseline.md` §5.3. | Task 2.10 |

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

> Tasks are **vertically sliced** — each task delivers working, testable functionality spanning
> backend and frontend where appropriate. Tasks are sized S (1–2 files) or M (3–5 files). No task
> is XL. Each task has acceptance criteria, verification steps, dependencies, files likely touched,
> and a scope estimate.

> Phase 1 (Discovery) produces design artifacts, not code. It runs in parallel and is tracked in
> `plans/phase-1-discovery.md`. Phase 1 is **complete as of 2026-06-23** — `docs/api_contracts.md`,
> `docs/data_model_erd.md`, `docs/rbac_matrix.md`, and `docs/requirements_baseline.md` are all
> present. Wireframes exist in `docs/wireframes/`. No blockers remain.

---

### Dependency Graph

```
                         ┌──────────────────────┐
                         │   Phase 1 Artifacts   │  (COMPLETE — unblocks everything)
                         └──────────┬───────────┘
                  ┌─────────────────┼───────────────────┐
                  │                 │                   │
                  ▼                 ▼                   ▼
         ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐
         │  Task 2.1    │   │  Task 2.11   │   │ Advisory Fixes     │
         │  Backend     │   │  Frontend    │   │ A1, A3, A5, A9    │
         │  scaffold    │   │  bootstrap   │   │ (housekeeping)     │
         └──────┬───────┘   └──────┬──────┘   └──────────────────┘
                │                  │
                ▼                  │
         ┌─────────────┐           │
         │  Task 2.2    │◄──────────┼── Terraform refs Frontend bucket
         │  DynamoDB +  │           │
         │  repos       │           │
         └──────┬───────┘           │
                │                  │
                ▼                  │
         ┌─────────────┐           │
         │  Task 2.3    │◄──────────┼── Auth API ↔ Frontend login page
         │  Google OIDC │           │
         │  (vertical)  │           │
         └──────┬───────┘           │
                │                  │
       ┌────────┼──────────┐       │
       │        ▼          │       │
       │  ┌──────────┐     │       │
       │  │ Task 2.4 │     │       │
       │  │  RBAC    │     │       │
       │  └────┬─────┘     │       │
       │       │           │       │
       │  ┌────┴──────────────────┐
       │  │   Parallel after 2.4  │
       │  │                       │
       │  │  Task 2.5  Session    │
       │  │  CRUD (vertical)      │
       │  │  Task 2.7  Admin      │
       │  │  assign API           │
       │  │  Task 2.8  Rate limit │
       │  │  Task 2.6  Code       │── depends on 2.5
       │  │  validation           │
       │  │  Task 2.9  Audit      │── depends on 2.2
       │  └───────────┬───────────┘
       │              │
       │              ▼
       │  ┌──────────────────────┐
       │  │  Task 2.10           │◄── Depends on 2.1, 2.11, 2.3
       │  │  CI/CD pipelines     │    (needs frontend built + backend auth)
       │  └──────────────────────┘
       │
       └──► (2.8, 2.9 run any time after their deps)

   Legend:
   →  = must complete first (strict)
   ◄── = references but runs in parallel  (loose)
```

**Strictly sequential chain:** 2.1 → 2.2 → 2.3 → 2.4 → 2.5
**Parallelizable after 2.4 lands:** 2.5 (backend), 2.7, 2.8
**Gated on 2.5:** 2.6
**Gated on 2.2:** 2.9
**Independent of backend:** 2.11 (frontend bootstrap)
**Final assembly:** 2.10 (CI/CD) — gated on 2.1 + 2.3 + 2.11

---

### Phase 1 Review Advisories — Mapping to Phase 2 Tasks

| Advisory | Action | Assigned To |
|----------|--------|-------------|
| **A1** — Add ADR supersession banner to `plans/phase-1-discovery.md` | Edit the Decisions section to note that ADR-0001 (multi-table) and ADR-0008 (deferred email) supersede the original plan's assumptions. | Task 2.1 (housekeeping) |
| **A3** — Create `KNOWLEDGE.md` at repo root | Capture: ADR-0001 multi-table rationale, ADR-0008 deferred-delivery reversal, canonical schema supremacy principle, Phase 1 lessons learned. | Task 2.1 (housekeeping) |
| **A5** — Add amendment banner to master spec | Add a banner at the top of `docs/functional_requirements_and_architecture.md` listing superseding ADRs (0001, 0008). | Task 2.1 (housekeeping) |
| **A7** — Evaluate `gsi_latest_match_by_session` redundancy | During repository implementation, assess whether the main-table `Query` on `SESSION#<code>` + `SK begins_with MATCH#` with `ScanIndexForward=false, Limit=1` is sufficient to replace the GSI. Document rationale in a code comment on the Match repository. | Task 2.2 |
| **A9** — Fix NFR-SCALE-2 wording | Change "idle cost = $0" to "≤ $1/month idle" in `docs/requirements_baseline.md` §5.3. The master spec v3.0 already has the correction; baseline needs sync. | Task 2.10 |

---

### Phase A: Scaffold & Foundation (Tasks 2.1, 2.11, 2.2)

#### Task 2.1: Backend project scaffold + health endpoint [S]

**Description:** Create the FastAPI project structure per Section 11, with a Mangum handler,
`GET /health`, `pyproject.toml`, and a pytest harness. Also resolves Phase 1 review advisories
A1, A3, A5 (housekeeping edits to existing docs).

**Acceptance criteria:**
- [ ] `app/main.py` creates a FastAPI app (`app = FastAPI(...)`) with a `handler = Mangum(app)` export
- [ ] `GET /health` returns `{"status": "ok"}` with 200; registered under `app.include_router(health.router)`
- [ ] `pyproject.toml` declares `[project]` with Python 3.12, `[project.optional-dependencies]` dev extras (pytest, pytest-asyncio, ruff, mypy), and `[tool.pytest.ini_options]` for `testpaths = ["tests"]`
- [ ] `requirements.txt` pins `fastapi`, `mangum`, `uvicorn[standard]`
- [ ] `tests/test_health.py` uses `TestClient` from `fastapi.testclient`; one smoke test for `/health`
- [ ] `tests/conftest.py` defines `@pytest.fixture` for the FastAPI `TestClient`
- [ ] **A1 resolved:** `plans/phase-1-discovery.md` Decisions section has a banner noting ADR-0001/0008 supersession
- [ ] **A3 resolved:** `KNOWLEDGE.md` exists at repo root with Phase 1 lessons (see `docs/requirements_baseline.md` §4 for resolved OQs)
- [ ] **A5 resolved:** `docs/functional_requirements_and_architecture.md` has an amendment banner at line 1 listing superseding ADRs

**Verification:**
- [ ] `uv run pytest tests/ -v` — all pass
- [ ] `uv run uvicorn app.main:app --port 8000` and `curl localhost:8000/health` → `{"status": "ok"}`
- [ ] `python -c "from app.main import handler; print(type(handler))"` — imports without error
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy .` — all clean

**Dependencies:** None (Phase 1 artifacts complete — no blockers)

**Files created/modified:**
- `app/__init__.py` (empty)
- `app/main.py` (FastAPI app + Mangum handler + health router include)
- `app/api/__init__.py` (empty)
- `app/api/health.py` (health router with `GET /health`)
- `app/auth/__init__.py` (empty)
- `app/models/__init__.py` (empty)
- `app/services/__init__.py` (empty)
- `app/repositories/__init__.py` (empty)
- `app/middleware/__init__.py` (empty)
- `tests/__init__.py` (empty)
- `tests/conftest.py` (TestClient fixture)
- `tests/test_health.py` (smoke test)
- `pyproject.toml`
- `requirements.txt`
- `plans/phase-1-discovery.md` (edit — add A1 banner)
- `KNOWLEDGE.md` (create — A3)
- `docs/functional_requirements_and_architecture.md` (edit — add A5 banner)

**Estimated scope:** S (2 new Python modules, 4 doc edits, pyproject.toml)

**ADR references:** ADR-0002 (JWT session mechanism — imported later but `pyproject.toml` pins PyJWT), ADR-0003 (Python 3.12 / ARM64 target)

---

#### Task 2.11: Next.js frontend bootstrap [M]

**Description:** Bootstrap the Next.js app with App Router, TypeScript, Tailwind, and
`@cloudflare/next-on-pages` adapter. Set up the typed API client, auth context provider, and
role-based routing scaffold. This is the frontend foundation that all UI tasks build on.

**Acceptance criteria:**
- [x] `npx create-next-app@latest frontend --typescript --tailwind --app --src-dir` creates the project
- [x] `@cloudflare/next-on-pages` installed and configured (`next.config.ts` with `setupDevPlatform()`)
- [x] `wrangler.toml` created with `compatibility_date`, `name = "carpool-coordinator"`, and a `pages_build_output_dir` pointing to `.vercel/output/static`
- [x] `frontend/src/lib/api-client.ts` exports a typed `apiClient` with `get<T>`, `post<T>`, `patch<T>`, `del` methods that inject `Authorization: Bearer ${token}` from the auth context
- [x] `frontend/src/lib/auth-context.tsx` exports `AuthProvider` (React Context) wrapping the app; stores JWT in-memory (never `localStorage` — ADR-0002); exposes `{ user, token, isAuthenticated, login, logout }`
- [x] `frontend/src/lib/route-guard.tsx` exports `ProtectedRoute` component that redirects to `/login` if `!isAuthenticated`
- [x] `frontend/src/app/layout.tsx` wraps children in `AuthProvider` + includes a role-aware `<Nav />` component
- [x] `frontend/src/components/Nav.tsx` shows different links per `user.global_role` (Superuser: all links; Manager: sessions, audit; otherwise: register, dashboard)
- [x] `npm run build` succeeds without errors
- [x] `npm run dev` serves the app at `localhost:3000`

**Verification:**
- [x] `cd frontend && npm run build` — succeeds
- [x] `cd frontend && npm run lint` — clean
- [x] `cd frontend && npx tsc --noEmit` — clean
- [x] Manual: `npm run dev` → landing page renders at `localhost:3000`
- [x] Manual: Cloudflare Pages preview deploy URL accessible (requires Cloudflare API token; may be deferred to Task 2.10)

**Dependencies:** None (can start in parallel with all backend tasks)

**Files created:**
- `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.ts`, `frontend/tailwind.config.ts`, `frontend/postcss.config.mjs`
- `frontend/wrangler.toml`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx` (landing)
- `frontend/src/app/globals.css`
- `frontend/src/lib/api-client.ts`
- `frontend/src/lib/auth-context.tsx`
- `frontend/src/lib/route-guard.tsx`
- `frontend/src/components/Nav.tsx`
- `frontend/.gitignore` (extends root `.gitignore` for `node_modules/`, `.next/`, `.vercel/`)

**Estimated scope:** M (entire scaffold — 10+ generated files, 5 hand-written modules)

**ADR references:** ADR-0002 (JWT in-memory storage), ADR-0004 (same-origin via rewrites — implemented in Task 2.10 CI)

---

#### Task 2.2: DynamoDB schema + repository layer [M]

**Description:** Provision all 5 DynamoDB tables from `docs/data_model_erd.md` §1 via **Terraform**,
and implement the repository layer with the PK/SK patterns, GSIs, and TTL attributes defined there.
Tables are **named per data model** (ADR-0001). Also resolves advisory A7.

**Acceptance criteria:**
- [ ] Terraform `infra/main.tf` provisions all 5 tables: `app_data`, `session_cache`, `rate_limit_cache`, `brute_force_counter`, `geocode_cache` — with `billing_mode = "PAY_PER_REQUEST"` (ADR-0007) and `server_side_encryption { enabled = true }` (AWS-owned KMS key, $0 cost — NFR-SEC-4)
- [ ] `app_data` GSIs: `gsi_sessions_by_user` (PK=`USER#<sub>`, SK=`SESSION#<code>`), `gsi_admins_by_user` (PK=`USER#<sub>`, SK=`SESSION#<code>`)
- [ ] TTL attributes: `ttl` on `rate_limit_cache`, `brute_force_counter`, `geocode_cache`; `session_cache` TTL TBD
- [ ] PITR enabled on `app_data` only (not on ephemeral cache/counter tables)
- [ ] `app/repositories/base.py` exports `DynamoRepository` base class with `_table`, `_client` (boto3), typed `put_item`/`get_item`/`query`/`update_item`/`delete_item`
- [ ] `app/repositories/user.py` — `UserRepository`: `get_by_sub(sub)`, `upsert(sub, email, name)`, `update_roles(sub, roles)`
- [ ] `app/repositories/session.py` — `SessionRepository`: `create(code, attrs)`, `get_by_code(code)`, `update(code, attrs)`, `delete(code)`, `list_by_user(sub)` via GSI
- [ ] `app/repositories/registration.py` — `RegistrationRepository`: `create(session_code, sub, attrs)`, `get(session_code, sub)`, `list_by_session(session_code)`, `update(...)`, `delete(...)`
- [ ] `app/repositories/match.py` — `MatchRepository`: `create(session_code, version, attrs)`, `get_latest(session_code)`, `get_approved(session_code)`, `list_versions(session_code)`
- [ ] `app/repositories/audit.py` — `AuditRepository`: `write(date, event_id, attrs)`, `query(date, from_ts, to_ts, filters)`
- [ ] Repository tests use `moto` (unit) via `tests/conftest.py` fixture that creates mock DynamoDB tables; no live AWS calls in unit tests
- [ ] **A7 resolved:** A comment on `MatchRepository.get_latest()` documents the GSI-vs-Query evaluation — if the main-table `Query` suffices, `gsi_latest_match_by_session` is dropped from Terraform and ERD is annotated

**Verification:**
- [ ] `uv run pytest tests/repositories/ -v` — all pass
- [ ] `cd infra && terraform plan` — shows planned tables
- [ ] `cd infra && terraform apply -auto-approve` (dev account) — creates tables
- [ ] `cd infra && terraform plan` (second run) — shows no changes (idempotent)
- [ ] Manual: `aws dynamodb put-item --table-name app_data --item '{"PK":{"S":"USER#test123"},"SK":{"S":"METADATA"}}'` succeeds
- [ ] NFR-SEC-4 verified: `cd infra && terraform plan` output shows `server_side_encryption` block on all 5 DynamoDB tables (AWS-owned KMS key, $0 cost)

**Dependencies:** Task 2.1 (needs `app/` layout), Phase 1 ERD (`docs/data_model_erd.md` — complete)

**Files created/modified:**
- `infra/main.tf` (5 DynamoDB tables + 3 GSIs + `server_side_encryption { enabled = true }` on all tables)
- `infra/variables.tf` (region, env)
- `infra/terraform.tf` (backend config — S3 + DynamoDB lock, deferred to Task 2.10)
- `app/repositories/__init__.py` (re-exports)
- `app/repositories/base.py`
- `app/repositories/user.py`
- `app/repositories/session.py`
- `app/repositories/registration.py`
- `app/repositories/match.py`
- `app/repositories/audit.py`
- `tests/__init__.py` (already created in 2.1)
- `tests/conftest.py` (extend with moto fixtures)
- `tests/repositories/__init__.py`
- `tests/repositories/test_user.py`
- `tests/repositories/test_session.py`
- `tests/repositories/test_registration.py`
- `tests/repositories/test_match.py`
- `tests/repositories/test_audit.py`

**Estimated scope:** M (6 repository modules, 1 Terraform file, 5+ test files)

**ADR references:** ADR-0001 (multi-table), ADR-0007 (on-demand billing), NFR-SEC-4 (encryption at rest — AWS-owned KMS key, $0 cost), ERD §1–§5 (PK/SK/GSI/TTL design)

---

### Checkpoint A: Foundation Complete
- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy .` — all clean
- [ ] `cd frontend && npm run build && npm run lint && npx tsc --noEmit` — all clean
- [ ] `python -c "from app.main import handler"` — imports cleanly
- [ ] Terraform plan shows no drift
- [ ] Housekeeping: A1, A3, A5 resolved; KNOWLEDGE.md exists; master spec has ADR banner
- [ ] **Review with human before proceeding**

---

### Phase B: Authentication & Authorization (Tasks 2.3, 2.4)

#### Task 2.3: Google OIDC authentication (backend + frontend) [M — VERTICAL SLICE]

**Description:** Implement Google OIDC login end-to-end — the first full vertical slice. Backend:
verify Google ID token against cached JWKS (ADR-0006), extract `sub`/`email`/`name`, upsert
`USER#<sub>` in DynamoDB, issue a signed app session **JWT** (ADR-0002, 1h TTL). Frontend:
render a Google Identity Services button, call `POST /auth/google`, store JWT in memory, and
redirect to dashboard. Auth middleware rejects requests with invalid/missing JWTs.

**Acceptance criteria:**
- [ ] `app/auth/oidc.py` — `verify_google_token(id_token: str) -> GoogleUser`:
  - Fetches Google JWKS from `https://www.googleapis.com/oauth2/v3/certs` (first call only; cached 1h per ADR-0006)
  - Verifies JWT signature, `aud` matches the configured client ID (from env/SSM), `exp` is in the future
  - Returns `GoogleUser(sub=str, email=str, name=str)` on success; raises `InvalidTokenError` on failure
- [ ] `app/auth/jwt.py` — `create_app_token(user: User) -> str`:
  - Signs with HS256 using a secret from `os.environ["JWT_SECRET"]` (Parameter Store at deploy time; local dev uses `.env`)
  - Claims: `sub`, `email`, `name`, `global_role` (one of `superuser`/`manager`/`none`), `iat`, `exp` (now + 3600s)
  - `decode_app_token(token: str) -> TokenPayload` — verifies signature, checks expiry; raises on invalid
- [ ] `app/api/auth.py` — `POST /auth/google`:
  - Accepts `{"id_token": "..."}` → verifies with `oidc.verify_google_token()` → upserts `USER#<sub>` → issues JWT via `jwt.create_app_token()` → returns `GoogleAuthResponse`
  - On invalid Google token: returns `401 UNAUTHORIZED` with `{"error": {"code": "UNAUTHORIZED", "message": "...", "details": {"reason": "invalid_google_token"}}}`
  - On expired: `details.reason = "token_expired"`
- [ ] `app/middleware/auth.py` — `get_current_user(request: Request) -> TokenPayload`:
  - Reads `Authorization: Bearer <token>` header; returns 401 if missing
  - Decodes JWT with `jwt.decode_app_token()`; returns 401 if invalid/expired
  - Returns `TokenPayload` for downstream dependencies
- [ ] Frontend `login/page.tsx`: renders Google Identity Services `Sign In With Google` button; on credential response, `POST /api/auth/google` with the `credential` (ID token); on success, calls `auth.login(token, user)` from context and redirects to `/dashboard`
- [ ] Frontend `api-client.ts`: injected with the auth context's `token`; every request includes `Authorization: Bearer <token>`
- [ ] `frontend/.env.local` contains `NEXT_PUBLIC_GOOGLE_CLIENT_ID` and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

**Verification:**
- [ ] `uv run pytest tests/auth/ -v` — test_oidc.py + test_jwt.py:
  - Mocked Google JWKS endpoint returns known keys; verify a self-signed test token; verify rejection of expired/audience-mismatched/tampered tokens
  - JWT creation/decode round-trip; tampered JWT → decode raises
- [ ] `uv run pytest tests/api/test_auth.py -v` — test_auth.py: `POST /auth/google` with valid mock → 200 + JWT; invalid token → 401; missing body → 422
- [ ] Manual: `uv run uvicorn app.main:app` + `npm run dev` in frontend/ → complete Google login in browser → redirected to `/dashboard` with user info
- [ ] Manual: `curl -H "Authorization: Bearer garbage" localhost:8000/health` → 401 (after auth middleware is wired; health may be exempt initially)

**Dependencies:** Task 2.2 (needs UserRepository + DynamoDB tables)

**Files created/modified:**
- `app/auth/__init__.py`
- `app/auth/oidc.py` (Google token verification + JWKS caching per ADR-0006)
- `app/auth/jwt.py` (app session JWT create/decode)
- `app/api/auth.py` (`POST /auth/google`)
- `app/middleware/auth.py` (Bearer token dependency)
- `app/main.py` (edit — include auth router, mount auth middleware as FastAPI dependency)
- `frontend/src/app/login/page.tsx`
- `frontend/src/lib/api-client.ts` (extend with token injection)
- `frontend/src/lib/auth-context.tsx` (update `login`/`logout` with real API calls)
- `frontend/.env.local`
- `tests/auth/__init__.py`
- `tests/auth/test_oidc.py`
- `tests/auth/test_jwt.py`
- `tests/api/__init__.py`
- `tests/api/test_auth.py`

**Estimated scope:** M (6 backend modules, 2 frontend modules, 3 test files)

**ADR references:** ADR-0002 (JWT issuance/storage), ADR-0006 (JWKS caching), ADR-0005 (middleware order — auth runs after rate_limit + audit)

---

#### Task 2.4: RBAC middleware [S]

**Description:** Implement deny-default RBAC dependency injection with role precedence
(`Superuser > Manager > Session Admin > Driver > Passenger`) and session-scoped role
resolution per `docs/rbac_matrix.md`. Every protected route declares required role via
`Depends(require_role(Role.MANAGER))`. ADR-0005 §3: RBAC is the 4th dependency in the chain.

**Acceptance criteria:**
- [ ] `app/models/roles.py` defines `Role` enum with 5 values + `int` precedence weights
- [ ] `app/middleware/rbac.py` exports:
  - `require_role(*allowed: Role) -> Callable` — FastAPI dependency that reads `TokenPayload` from `get_current_user`, resolves effective role set for the requested session (if session-scoped), and returns `403 FORBIDDEN` if none of `allowed` roles match
  - `compute_effective_roles(payload, session_code) -> set[Role]` — union of global role + session-scoped roles (Session Admin via DynamoDB `ADMIN#<sub>` item; Driver/Passenger via `REG#<sub>` item)
- [ ] Permission matrix tests cover:
  - Superuser → can do anything (any role check passes, even without session-scoped assignment)
  - Manager → passes `Role.MANAGER`, `Role.SESSION_ADMIN`, `Role.DRIVER`, `Role.PASSENGER` checks
  - Session Admin for session A → passes admin checks on A, **fails** on session B
  - Driver in session A → passes driver checks on A, fails admin checks on A
  - Passenger → passes passenger checks only; all others fail
  - Unauthenticated → 401 (from auth middleware, before RBAC)
- [ ] `require_role()` returns user-friendly `403` JSON: `{"error": {"code": "FORBIDDEN", "message": "...", "details": {"required_role": "manager", "session_code": "..."}}}`
- [ ] FastAPI `Depends` chain tested: `Depends(get_current_user)` then `Depends(require_role(Role.MANAGER))` — end-to-end

**Verification:**
- [ ] `uv run pytest tests/middleware/test_rbac.py -v` — 10+ parametrized test cases covering all 5 roles × 4 permission levels
- [ ] Manual: wire a dummy protected route with `Depends(require_role(Role.MANAGER))`; call with JWT for a Passenger → 403
- [ ] Manual: call same route with JWT for a Manager → 200

**Dependencies:** Task 2.3 (needs `get_current_user` dependency + `TokenPayload`)

**Files created/modified:**
- `app/models/roles.py` (Role enum + precedence)
- `app/middleware/rbac.py` (require_role, compute_effective_roles)
- `app/middleware/auth.py` (extend — export `CurrentUser` type alias for Annotated injection)
- `tests/middleware/__init__.py`
- `tests/middleware/test_rbac.py`

**Estimated scope:** S (2 backend modules, 1 test file)

**ADR references:** ADR-0005 (middleware ordering — rbac runs 4th), RBAC matrix §2–§3, FR-9 visibility rules

---

### Checkpoint B: Auth + RBAC Working
- [ ] `uv run pytest tests/auth/ tests/middleware/test_rbac.py -v` — all pass
- [ ] Manual: Google login → JWT in memory → protected route with Manager role → 200
- [ ] Manual: Passenger JWT → Manager-only route → 403
- [ ] **Review with human before building feature endpoints**

---

### Phase C: Core Backend Features (Tasks 2.5, 2.7, 2.6, 2.8, 2.9)

Tasks 2.5, 2.7, and 2.8 can run **in parallel** once 2.4 lands. Task 2.6 depends on 2.5.
Task 2.9 depends on 2.2.

#### Task 2.5: Session CRUD (backend + frontend) [M — VERTICAL SLICE]

**Description:** Implement session management end-to-end. Manager/Superuser can create, read,
update, delete sessions. Frontend renders a session dashboard with create form and status badges.
Session status enum transitions enforced per the state machine in §3 of the requirements baseline.

**Acceptance criteria:**
- [ ] `app/models/session.py` defines `SessionStatus` enum (6 values), `SessionCreate` Pydantic model, `SessionResponse`, `SessionUpdate` (per `docs/api_contracts.md` §4)
- [ ] `app/services/session.py` — `SessionService`:
  - `async create(body: SessionCreate, actor: TokenPayload) -> SessionResponse` — generates 6-char alphanumeric `session_code` (collision retry up to 3 times), geocodes `anchor_postal_code` (stub for Phase 3 — returns mock lat/lon), writes `SESSION#<code>` / `METADATA` item, returns response
  - `async get(code: str, actor: TokenPayload) -> SessionResponse` — reads session; scope-filters per RBAC (strips capacity_hint for non-admin roles)
  - `async update(code: str, body: SessionUpdate, actor: TokenPayload) -> SessionResponse` — validates status transition is legal (see state machine below), partial update
  - `async delete(code: str, actor: TokenPayload) -> NoContent` — hard delete (Superuser only per RBAC P-05)
- [ ] State machine enforcement in `SessionService._validate_transition(current, new)`:
  ```
  draft → registration_open; registration_open → matching_pending;
  matching_pending → matching_proposed; matching_proposed → approved;
  approved → closed; any → closed (force-close).
  Invalid transitions → 409 SESSION_NOT_OPEN.
  ```
- [ ] `app/api/sessions.py` — `POST /sessions` (Manager+), `GET /sessions/{code}` (any authenticated, scope-filtered), `PATCH /sessions/{code}` (Manager/Admin), `DELETE /sessions/{code}` (Superuser only)
- [ ] Frontend `sessions/page.tsx`: lists sessions for the current user (fetches via GSI); "Create" button links to `/sessions/create`
- [ ] Frontend `sessions/create/page.tsx`: form with all `SessionCreate` fields; `onSubmit` calls `POST /api/sessions`; on success redirects to dashboard
- [ ] Frontend component `SessionCard.tsx` renders `title`, `status` badge (color-coded), `registration_deadline`

**Verification:**
- [ ] `uv run pytest tests/api/test_sessions.py -v` — create, get, patch, delete; status transition enforcement; RBAC checks (Manager=OK, Passenger=403 on create)
- [ ] `uv run pytest tests/services/test_session.py -v` — status transition logic unit tests
- [ ] Manual: Manager creates session via UI → appears in dashboard with status badge "Draft"
- [ ] Manual: `PATCH /sessions/ABC123` with `{"status": "approved"}` from Draft → 409

**Dependencies:** Task 2.4 (needs RBAC `require_role`)

**Files created/modified:**
- `app/models/session.py`
- `app/services/session.py`
- `app/api/sessions.py`
- `app/main.py` (edit — include sessions router)
- `frontend/src/app/sessions/page.tsx`
- `frontend/src/app/sessions/create/page.tsx`
- `frontend/src/components/SessionCard.tsx`
- `tests/api/test_sessions.py`
- `tests/services/__init__.py`
- `tests/services/test_session.py`

**Estimated scope:** M (3 backend modules, 3 frontend modules, 2 test files)

**ADR references:** FR-2 (session attributes), API contracts §3.2–§3.5, RBAC P-01/P-02/P-04/P-05

---

#### Task 2.7: Admin assignment API [S]

**Description:** Implement `POST /sessions/{code}/admin` per `docs/api_contracts.md` §3.15 and
`docs/rbac_matrix.md` §4. Manager/Superuser assigns a user as Session Admin for a session.
Idempotent; audit-logged.

**Acceptance criteria:**
- [ ] `app/api/admin.py` — `POST /sessions/{code}/admin` (requires `Role.MANAGER` or `Role.SUPERUSER`):
  - Accepts `{"user": {"sub": "...", "email": "..."}}` (per `AdminAssignRequest`)
  - Resolves target user exists in `USER#<sub>`; 404 `TARGET_USER_UNKNOWN` if not
  - Writes `SESSION#<code>` / `ADMIN#<sub>` item (idempotent — re-posting same payload returns `already_assigned: true`)
  - Returns `AdminAssignResponse` with `201` (new) or `200` (already assigned)
  - Writes audit event `session_admin.assign`
- [ ] `app/models/admin.py` defines `AdminAssignRequest`, `AdminAssignResponse`, `AdminAssignUser`
- [ ] Session Admin assignment is **not** gated on the target user already being registered — per RBAC matrix §4.4 preconditions, only `USER#<sub>` existence is required

**Verification:**
- [ ] `uv run pytest tests/api/test_admin_assignment.py -v` — assign new admin (201), re-assign (200 idempotent), non-existent user (404), Passenger caller (403), audit event written
- [ ] Manual: Manager assigns admin → verify RBAC grants admin permissions on that session only

**Dependencies:** Task 2.4, Task 2.5 (needs session to exist)

**Files created/modified:**
- `app/models/admin.py`
- `app/api/admin.py`
- `app/main.py` (edit — include admin router)
- `tests/api/test_admin_assignment.py`

**Estimated scope:** S (2 backend modules, 1 test file)

**ADR references:** RBAC matrix §4 (admin assignment flow), API contracts §3.15, P-06

---

> **Task 2.6 depends on Task 2.5 completing first** (needs session endpoints + service).
> **Tasks 2.8 and 2.9 can run in parallel with 2.5/2.7.**

#### Task 2.8: Rate limiting middleware (basic) [S]

**Description:** Implement token-bucket rate limiting (60 req/min per IP, 120 req/min per user)
stored as TTL items in `rate_limit_cache` per ERD §2.8. Abuse detection / brute-force escalation
is **deferred** (post-MVP). Single-tenant deployment = low abuse risk.

**Acceptance criteria:**
- [ ] `app/middleware/rate_limit.py` exports `rate_limit_middleware` — a FastAPI dependency that:
  - Reads client IP from `X-Forwarded-For` header (Cloudflare edge) or `request.client.host`
  - For authenticated requests: checks both per-IP bucket AND per-user bucket
  - Uses atomic DynamoDB `UpdateItem` with `ADD count :inc` and `ConditionExpression: count < :limit` (or similar optimistic concurrency pattern on the TTL item)
  - On limit exceeded: returns `429` with `Retry-After` header + `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers (per API contracts §1.4)
  - Configurable via `os.environ`: `RATE_LIMIT_PER_IP=60`, `RATE_LIMIT_PER_USER=120`, `RATE_LIMIT_WINDOW_IP=60`, `RATE_LIMIT_WINDOW_USER=60`
- [ ] *(DEFERRED) `brute_force_counter` table is provisioned but no code writes to it.*

**Verification:**
- [ ] `uv run pytest tests/middleware/test_rate_limit.py -v` — mock DynamoDB, verify 429 returned after exceeding limit, `Retry-After` header present
- [ ] Manual: burst 70 requests in 60s from same IP → 429 after 60th

**Dependencies:** Task 2.2 (needs `rate_limit_cache` table provisioned)

**Files created/modified:**
- `app/middleware/rate_limit.py`
- `app/main.py` (edit — mount rate limiter as first dependency on protected routes)
- `tests/middleware/test_rate_limit.py`

**Estimated scope:** S (1 backend module, 1 test file)

**ADR references:** ADR-0005 (rate_limit is 1st dependency), API contracts §1.4, ERD §2.8

---

#### Task 2.9: Audit logging middleware [S]

**Description:** Implement audit logging as the 2nd dependency in the middleware chain (per
ADR-0005). Captures login attempts, auth failures, session CRUD, admin assignments, RBAC
denials. Writes to `AUDIT#<YYYY-MM-DD>` partition in `app_data`. Writes are **non-blocking**
(`asyncio.create_task`).

**Acceptance criteria:**
- [ ] `app/middleware/audit.py` exports `AuditLogger` class:
  - `log(event_type: str, actor_sub: str | None, session_code: str | None, details: dict, request: Request)` — generates event_id (UUIDv4), builds AuditEvent dict, writes to DynamoDB via `asyncio.create_task`
  - `event_type` constants defined: `auth.login.success`, `auth.login.failure`, `session.created`, `session.updated`, `session.deleted`, `session_admin.assign`, `rbac.denied`
  - All fields stored without PII in `details` (actor_sub is the only user identifier; no email/name in audit payload per NFR-SEC-7)
- [ ] `app/api/audit.py` — `GET /audit` (Superuser or Manager):
  - Query params: `from`, `to` (ISO-8601), `event_type`, `session_code`, `cursor`, `limit`
  - Returns `PaginatedResponse[AuditEvent]` per API contracts §3.14
- [ ] Audit writes are fire-and-forget — a failed audit write must not impact the API response (log the failure to CloudWatch but return 200/201/403 to caller)
- [ ] `app/models/audit.py` defines `AuditEvent` Pydantic model

**Verification:**
- [ ] `uv run pytest tests/middleware/test_audit.py -v` — verify audit event written after login success, login failure, session create, RBAC denial
- [ ] `uv run pytest tests/api/test_audit.py -v` — paginated query, filter by event_type/session_code
- [ ] Manual: perform login + session create → query `GET /audit?from=...&to=...` → returns events

**Dependencies:** Task 2.2 (needs AuditRepository + `app_data` table)

**Files created/modified:**
- `app/middleware/audit.py`
- `app/models/audit.py`
- `app/api/audit.py`
- `app/main.py` (edit — include audit router)
- `tests/middleware/test_audit.py`
- `tests/api/test_audit.py`

**Estimated scope:** S (2 backend modules, 1 model, 2 test files)

**ADR references:** ADR-0005 (audit is 2nd dependency — non-blocking writes), FR-11, API contracts §3.14

---

### Checkpoint C: Core Backend Feature Complete
- [ ] `uv run pytest tests/ -v` — all backend tests pass
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy .` — clean
- [ ] Manual smoke test (all via curl or Swagger UI at `localhost:8000/docs`):
  - POST /auth/google (with test token) → JWT
  - POST /sessions (with Manager JWT) → session_code
  - POST /sessions/{code}/admin (with Manager JWT) → admin assigned
  - GET /sessions/{code} (with Passenger JWT) → session detail (scope-filtered)
  - GET /audit (with Superuser JWT) → paginated events
  - Burst 70 requests → 429
- [ ] **Review with human before proceeding to Phase D (CI/CD)**

---

### Phase D: CI/CD & Deployment (Tasks 2.6, 2.10)

#### Task 2.6: Session code validation + registration entry [S — VERTICAL SLICE]

**Description:** Implement the session-code entry flow. Backend validates codes and returns
session summaries. Frontend supports manual entry and `/register?session=ABC123` deep links.
This task completes the Phase 2 user story: "Passenger can enter a session code and see the
session summary before registration."

**Acceptance criteria:**
- [ ] `GET /sessions/{code}/eligibility` (or reuse `GET /sessions/{code}` with an `eligibility` query param):
  - Exists → returns session summary (title, description, trip_mode, times, status)
  - Status != `registration_open` → 409 `REGISTRATION_CLOSED`
  - Past `registration_deadline` → 409 `REGISTRATION_CLOSED`
  - Unknown code → 404 `SESSION_CODE_NOT_FOUND`
- [ ] Frontend `register/page.tsx`:
  - Reads `?session=` from `useSearchParams()`; if present, auto-fetches eligibility and shows session summary card
  - Manual entry: text input + "Join" button; on submit, fetches eligibility
  - On success: shows session summary with title, description, times, and a placeholder "Register as Driver / Passenger" section (full registration form deferred to Phase 3)
  - On error: shows appropriate message ("Session not found", "Registration closed", etc.)
- [ ] Manager/Superuser bypass: `GET /sessions/{code}` already works for these roles (no code-gating)

**Verification:**
- [ ] `uv run pytest tests/api/test_session_code.py -v` — valid code (200), unknown (404), closed session (409), past deadline (409)
- [ ] `uv run pytest tests/api/test_registration.py -v` — if endpoint extends to `GET /sessions/{code}/eligibility`
- [ ] Manual: navigate to `/register?session=ABC123` in browser → session summary shown
- [ ] Manual: navigate to `/register?session=ZZZZZZ` → "session not found"

**Dependencies:** Task 2.5 (needs session endpoints + SessionService)

**Files created/modified:**
- `app/api/registration.py` (extend with eligibility endpoint — or add to sessions.py)
- `app/services/session.py` (extend with `check_eligibility` method)
- `frontend/src/app/register/page.tsx`
- `tests/api/test_session_code.py`

**Estimated scope:** S (1 backend extension, 1 frontend page, 1 test file)

**ADR references:** FR-1 (session code validation flow), API contracts §3.3 (GET /sessions/{code})

---

#### Task 2.10: CI/CD pipelines (backend + frontend) [M]

**Description:** Set up GitHub Actions workflows for backend (lint, type-check, test, Lambda
package + deploy, Terraform plan/apply) and frontend (build, type-check, deploy to Cloudflare
Pages with preview per branch). Also resolves advisory A9.

**Acceptance criteria:**
- [ ] `.github/workflows/backend-ci.yml`:
  - **Triggers:** `push` to any branch, `pull_request` to `main`
  - **Jobs:** `lint` (ruff check + format check), `typecheck` (mypy .), `test` (pytest --cov=app --cov-report=term-missing), `build-and-deploy` (on `push` to `main` only — zip app/ + requirements.txt, upload to S3 with SSE-KMS per NFR-SEC-4, update Lambda with `aws lambda update-function-code`)
  - Uses `uv` for Python dependency management (cache `~/.cache/uv`)
- [ ] `.github/workflows/terraform.yml`:
  - **Triggers:** `pull_request` to `main` (plan only), `push` to `main` (plan + apply)
  - Uses `hashicorp/setup-terraform@v3`; configures AWS credentials via `aws-actions/configure-aws-credentials`
  - Terraform backend: S3 bucket + DynamoDB lock table (create via one-time `terraform init` bootstrap)
- [ ] `.github/workflows/frontend-ci.yml`:
  - **Triggers:** `push` to any branch, `pull_request` to `main`
  - **Jobs:** `lint` (npm run lint), `typecheck` (npx tsc --noEmit), `build` (npm run build), `deploy-preview` (on push to non-main branches — `npx wrangler pages deploy`), `deploy-production` (on push to `main` — `npx wrangler pages deploy --branch main`)
- [ ] GitHub Actions secrets configured: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GOOGLE_CLIENT_ID`
- [ ] JWT signing secret (`JWT_SECRET`) provisioned into AWS Parameter Store by Terraform (`infra/lambda.tf`), NOT stored as a GitHub Actions secret — the Lambda reads it at cold-start (per ADR-0002). GitHub Actions OIDC role grants Lambda the `ssm:GetParameter` permission.
- [ ] `README.md` updated with CI status badges for all 3 workflows
- [ ] **A9 resolved:** `docs/requirements_baseline.md` §5.3 NFR-SCALE-2 wording changed to "≤ $1/month idle"
- [ ] NFR-SEC-4: S3 buckets (Terraform state backend, CloudWatch log archive, Lambda deployment artifact) have SSE-KMS configured via `aws_s3_bucket_server_side_encryption_configuration` with `sse_algorithm = "aws:kms"` (AWS-managed `aws/s3` key, $0 monthly key cost)

**Verification:**
- [ ] Push to a feature branch → all CI jobs run green
- [ ] Merge to main → Lambda deployed, Terraform applied, Cloudflare Pages production deploy succeeded
- [ ] `terraform plan` on main shows no changes after apply (idempotent)
- [ ] Manual: `curl https://<lambda-url>/health` → `{"status": "ok"}`
- [ ] Manual: Cloudflare Pages production URL serves the frontend
- [ ] NFR-SEC-4 verified: `cd infra && terraform plan` output shows SSE-KMS (`sse_algorithm = "aws:kms"`) on all S3 bucket resources

**Dependencies:** Task 2.1 (backend scaffold), Task 2.3 (auth needs to work for meaningful deploy), Task 2.11 (frontend must build)

**Files created/modified:**
- `.github/workflows/backend-ci.yml`
- `.github/workflows/terraform.yml`
- `.github/workflows/frontend-ci.yml`
- `infra/terraform.tf` (backend config — S3 + DynamoDB lock + SSE-KMS on S3 buckets per NFR-SEC-4)
- `infra/lambda.tf` (Lambda function resource + Function URL + IAM role)
- `README.md` (CI badges)
- `docs/requirements_baseline.md` (edit — A9)

**Estimated scope:** M (3 workflow files, 2 Terraform files, 1 doc edit)

**ADR references:** ADR-0003 (Terraform, us-east-2), ADR-0004 (Cloudflare Pages same-origin rewrites), NFR-SEC-4 (S3 SSE-KMS), NFR-OPS-2 (30-day log retention via S3 lifecycle)

---

### Checkpoint D: Deployed & Complete
- [ ] `uv run pytest tests/ -v` — 100% pass
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy .` — clean
- [ ] `cd frontend && npm run lint && npx tsc --noEmit && npm run build` — clean
- [ ] End-to-end smoke test (deployed):
  1. Navigate to Cloudflare Pages URL → see landing page
  2. Google login → JWT stored; redirected to dashboard
  3. Create session (Manager) → session appears in dashboard
  4. Assign Session Admin → admin can manage session
  5. Enter session code as Passenger → see session summary
  6. Rate limit: burst >60/min → 429
  7. `GET /audit` (Superuser) → events visible
- [ ] All 9 success criteria (from Spec section §Success Criteria) met
- [ ] **Review with human before proceeding to Phase 3**

---

## Parallelization Summary

| Can run in parallel | Tasks | Reason |
|---------------------|-------|--------|
| **Immediately (no blockers)** | 2.1 + 2.11 | Backend scaffold and frontend bootstrap share no code |
| **After 2.2 (DynamoDB ready)** | 2.9 (audit) | Only needs DynamoDB tables provisioned |
| **After 2.3 (auth ready)** | 2.8 (rate limit) | Only needs auth dependency |
| **After 2.4 (RBAC ready)** | 2.5 + 2.7 + 2.8 + 2.9 | All need RBAC resolution for permission checks |
| **Cannot parallelize** | 2.1→2.2→2.3→2.4→2.5→2.6 | Strict dependency chain (each builds on the prior) |
| **Last** | 2.10 | Needs all backend features + frontend to exist |

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| OAuth client misconfig blocks all auth | **High** | Medium | Test with Google Identity Services dev keys first; `app/auth/oidc.py` logs JWKS fetch errors clearly; document client ID/secret rotation in `KNOWLEDGE.md` |
| DynamoDB table provisioning takes longer than expected (GSI backfill, PITR enable) | Medium | Low | Terraform handles creation; on-demand billing means no capacity tuning; GSI creation is async but fast for empty tables |
| IaC drift between local moto mocks and real DynamoDB | Medium | Medium | All repository tests run against moto (exact API surface); integration tests against docker `dynamodb-local` in CI (Task 2.10); Terraform is single source of truth |
| `next-on-pages` incompatibility with a Next.js feature used in scaffold | Medium | Low | Stick to supported patterns (no `middleware.ts`, no ISR at edge); validate with `npx @cloudflare/next-on-pages` before merging |
| Lambda cold start on first deploy | Low | Low | Provisioned concurrency off for dev; cold starts are < 1500ms per NFR-PERF-3; tune in Phase 6 |
| `gsi_latest_match_by_session` adds unnecessary write cost | Low | Low | Evaluated in Task 2.2 (advisory A7); likely dropped — main-table Query suffices per ERD §3.3 analysis |

---

## Task Completion Tracker

| Task | Status | Scope | Deps | Verification |
|------|--------|-------|------|-------------|
| 2.1 | ⬜ Pending | S | — | pytest, ruff, mypy, uvicorn smoke |
| 2.11 | ⬜ Pending | M | — | npm build, lint, tsc |
| 2.2 | ⬜ Pending | M | 2.1 | pytest repos, terraform plan |
| 2.3 | ⬜ Pending | M | 2.2 | pytest auth, manual Google login |
| 2.4 | ⬜ Pending | S | 2.3 | pytest rbac, manual 403 check |
| 2.5 | ⬜ Pending | M | 2.4 | pytest sessions, manual CRUD |
| 2.7 | ⬜ Pending | S | 2.4, 2.5 | pytest admin, manual assign |
| 2.6 | ⬜ Pending | S | 2.5 | pytest code validation, manual deep link |
| 2.8 | ⬜ Pending | S | 2.2 | pytest rate limit, manual burst |
| 2.9 | ⬜ Pending | S | 2.2 | pytest audit, manual query |
| 2.10 | ⬜ Pending | M | 2.1, 2.3, 2.11 | CI green, manual deploy smoke |
