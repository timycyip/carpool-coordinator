# LOG.md — Task Log

Running log of completed tasks with dates, scope, and verification status.

---

## Task 2.1: Backend Project Scaffold + Health Endpoint

| Field | Value |
|-------|-------|
| **Date** | 2026-06-24 |
| **Phase** | 2 (Foundation) |
| **Scope** | S (skeleton, no business logic) |
| **Status** | DONE |

### What Was Done

1. **Backend scaffold** — FastAPI app with Mangum handler (`app/main.py`), health endpoint
   (`GET /health` → `{"status": "ok"}`), Pydantic response model (`HealthResponse`),
   shared error envelope (`ErrorResponse`/`ErrorBody` from API contracts §2).

2. **Project structure** — `app/` package tree with placeholders for auth, models, services,
   repositories, middleware. `tests/` with conftest fixture and 7 tests.

3. **Build config** — `pyproject.toml` with hatchling, uv, ruff, mypy --strict, pytest,
   pytest-cov. Legacy `src/`/`test/` excluded from quality gates.

4. **API design patterns** — Contract-first (Pydantic `response_model` on every endpoint),
   consistent error envelope, input/output model separation. ADR-0009 records the decision.

5. **Housekeeping** — A1 banner on `plans/phase-1-discovery.md`, A5 banner on master spec,
   `KNOWLEDGE.md` created with ADR summaries and resolved OQs.

6. **Documentation** — README rewritten (Quick Start, Commands, Architecture, ADR table),
   docstrings on all public modules/functions/models, ADR-0009 written.

### Verification

| Check | Result |
|-------|--------|
| `pytest --cov=app` | 7/7 passed, 100% coverage |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 15 files formatted |
| `mypy .` | No issues (15 files, strict) |
| `from app.main import handler` | `<class 'mangum.adapter.Mangum'>` |
| `uvicorn` + `curl /health` | `{"status":"ok"}` |
| OpenAPI `/docs`, `/redoc` | 200 |

---

## Task 2.2: DynamoDB Schema + Repository Layer

| Field | Value |
|-------|-------|
| **Date** | 2026-06-24 |
| **Phase** | 2 (Foundation) |
| **Scope** | M (infra + data layer, no API endpoints yet) |
| **Status** | DONE |

### What Was Done

1. **Terraform IaC (`infra/`)** — 5 DynamoDB tables provisioned per Phase 1 ERD
   (`docs/data_model_erd.md`) and ADR-0001 (tables named per data model):
   - `app_data` — PK/SK single-table pattern, GSI `gsi_sessions_by_user` and
     `gsi_admins_by_user`, PITR enabled, SSE, no TTL (durable business data).
   - `session_cache`, `rate_limit_cache`, `brute_force_counter`, `geocode_cache` —
     PK/SK, TTL on `ttl` attribute, SSE. Billing mode PAY_PER_REQUEST (ADR-0007).
   - `infra/variables.tf` with `region` (default `us-east-2`) and `environment`.
   - `infra/terraform.tf` with `hashicorp/aws ~> 5.0` provider constraint.

2. **Repository layer (`app/repositories/`)** — 6 classes implementing all ERD §2
   entity access patterns:
   - `DynamoRepository` (base) — typed helpers for `put_item`, `get_item`, `query`,
     `update_item`, `delete_item` with transparent DynamoDB JSON serialization via
     `TypeSerializer`/`TypeDeserializer` and `Decimal`→`int`/`float` conversion.
   - `UserRepository` — `get_by_sub`, `upsert`
   - `SessionRepository` — `create`, `get_by_code`, `update`, `delete`
   - `RegistrationRepository` — `create` (populates `gsi1_pk`/`gsi1_sk` for GSI1),
     `get`, `list_by_session`, `update`, `delete`
   - `MatchRepository` — `create` (zero-padded `MATCH#V<n>`), `get_latest` (main-table
     Query per Advisory A7 — GSI NOT provisioned), `list_versions`, `update_status`
   - `AuditRepository` — `write`, `query_audit` (date range + filter)

3. **Tests (`tests/repositories/`)** — 24 tests across 5 files using moto `mock_aws`
   DynamoDB mock. Extended `tests/conftest.py` with `ddb_client` fixture that creates
   all 5 tables with correct key schemas and GSI definitions.

4. **Dependencies** — Added `boto3` (runtime), `moto[dynamodb]` and
   `boto3-stubs[dynamodb]` (dev) to `pyproject.toml`.

### Advisory A7 Resolution

The ERD §3.3 defines `gsi_latest_match_by_session` as a GSI on `app_data`. Analysis
(Phase 1 review advisory A7) shows this GSI is architecturally redundant: a main-table
Query on `PK = SESSION#<code>` with `SK begins_with MATCH#`, `ScanIndexForward=False`,
`Limit=1` returns the same highest-version match at identical cost. The GSI is **not**
provisioned in Terraform. The comment in `MatchRepository.get_latest()` documents this
decision.

### Verification

| Check | Result |
|-------|--------|
| `pytest -v` | 31/31 passed (24 new + 7 existing from Task 2.1) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 27 files formatted |
| `mypy .` | No issues (27 files, strict) |
| `terraform validate` | HCL valid (CLI not installed locally; verified on deploy) |

---

## Task 2.11 — Next.js Frontend Bootstrap

| Field | Value |
|-------|-------|
| **Phase** | 2 (Foundation) |
| **Task** | 2.11 |
| **Status** | DONE |
| **Date** | 2026-06-24 |
| **Plan ref** | `plans/phase-2-foundation.md` Task 2.11 |
| **Branch** | `phase-2-task-2-11-frontend-bootstrap` |

### What was implemented

Bootstrapped `frontend/` with Next.js 16 (App Router) + TypeScript + Tailwind v4, including:
- Same-origin API client with JWT injection and nested error parsing
- In-memory auth context (login/logout/isAuthenticated) with 401 subscriber bridge
- Role-aware accessible Nav (superuser/manager/default links, mobile disclosure)
- Route guard component (ProtectedRoute with loading state)
- Landing page with auth-aware states
- Vitest test suite for api-client (13 tests, 100% coverage on api-client.ts)

### ADRs written

- ADR-0009: 401 Unauthorized Subscriber Pattern (`docs/adr/0009-unauthorized-subscriber-pattern.md`)

### Key decisions

1. Used `--legacy-peer-deps` for `@cloudflare/next-on-pages` (peer dep caps at Next 15; only `next build` is the hard gate).
2. Added `onUnauthorized` subscriber pattern after code review found the 401→redirect chain was broken.
3. Design tokens: emerald-600 primary, slate-neutral base via Tailwind v4 `@theme inline` CSS variables.

### Verification results

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | Clean |
| `npm test` (vitest) | 13/13 passed |
| `npm run build` | Compiled successfully |
| `npm run lint` (eslint) | Clean |
| Coverage (api-client.ts) | 100% stmts / 100% branches / 100% funcs / 100% lines |

### Deferred to later tasks

| Item | Task |
|------|------|
| Google GIS sign-in button | 2.3 |
| Silent re-auth on page reload | 2.3 |
| `/login`, `/dashboard`, `/sessions/*` pages | Later tasks |
| Component tests (Nav, auth-context) | 2.5+ |
| Cloudflare Pages deploy CI | 2.10 |

### Lessons learned

See `KNOWLEDGE.md` § Task 2.11.
