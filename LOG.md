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
