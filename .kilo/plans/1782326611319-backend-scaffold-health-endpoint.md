# Plan — Task 2.1: Backend Project Scaffold + Health Endpoint [DONE]

**Phase:** 2 (Foundation) · **Task:** 2.1 · **Scope:** S (skeleton, no business logic)
**Source plan:** `plans/phase-2-foundation.md` Task 2.1 · **Spec:** `docs/functional_requirements_and_architecture.md` v3 §11
**Status:** DONE (2026-06-24) — see LOG.md for verification results

## Goal
Create the deployable FastAPI + Mangum backend skeleton (Python 3.12) that every
subsequent backend task builds on, plus resolve Phase 1 review housekeeping advisories
A1, A3, A5. No auth/RBAC/DB/middleware logic in this task — pure scaffold + health route.

## Resolved Decision
- **`requirements.txt` remains the legacy CLI pin file** (pandas/geopy/scipy) — untouched,
  per AGENTS.md (legacy `src/main.py` stays runnable). Backend runtime + dev deps live
  **solely in `pyproject.toml`**. Acceptance criterion #4 ("requirements.txt pins
  fastapi/mangum/uvicorn[standard]") is satisfied by `pyproject.toml`'s
  `[project.dependencies]`; this deviation is documented in the PR description and below.
  `uv` is the package manager; `pip install -r requirements.txt` still serves the legacy CLI.

## Files to Create / Edit

### Create (backend scaffold)
- `app/__init__.py` (empty)
- `app/main.py` — FastAPI app, `include_router(health.router)`, `handler = Mangum(app)`
- `app/api/__init__.py` (empty)
- `app/api/health.py` — `APIRouter` with `@router.get("/health", response_model=HealthResponse)` → `HealthResponse(status="ok")` (200)
- `app/models/health.py` — `HealthResponse(BaseModel)` Pydantic contract for the health endpoint
- `app/models/error.py` — `ErrorBody` + `ErrorResponse` Pydantic models from API contracts §5 (shared error envelope)
- `app/auth/__init__.py`, `app/models/__init__.py`, `app/services/__init__.py`,
  `app/repositories/__init__.py`, `app/middleware/__init__.py` (all empty — placeholders
  for Tasks 2.2–2.9)
- `tests/__init__.py` (empty)
- `tests/conftest.py` — `client` fixture: `TestClient(app)` (import from `app.main`)
- `tests/test_health.py` — smoke tests: 200, json match, Pydantic `model_validate` schema conformance
- `pyproject.toml` — backend + dev deps, tool config (see below)

### Edit (housekeeping)
- `plans/phase-1-discovery.md` (A1) — prepend a supersession banner to the **Decisions
  (locked)** section noting ADR-0001 (multi-table, supersedes single-table assumption) and
  ADR-0008 (deferred delivery, supersedes synchronous-email assumption). Note: lines 16 & 20
  already cite the ADRs; the banner is an explicit at-a-glance pointer per advisory A1.
- `KNOWLEDGE.md` (A3, new, repo root) — capture: ADR-0001 multi-table rationale, ADR-0008
  deferred-delivery reversal, canonical registration schema supremacy (master spec v3 §5
  FR-3/FR-4 supersedes v2 field lists), and the 13 resolved OQs from
  `docs/requirements_baseline.md` §4 (summary table, not full reproduction).
- `docs/functional_requirements_and_architecture.md` (A5) — prepend an amendment banner
  above line 1 listing superseding ADRs (ADR-0001 multi-table; ADR-0008 deferred delivery;
  pointer to `docs/adr/`). Spec is already v3.0 incorporating these; banner is a pointer only.

## pyproject.toml Contents
- `[build-system]` → `hatchling` (build backend) with `uv` as resolver
- `[project]`: `name = "carpool-coordinator-backend"`, `version = "0.1.0"`,
  `requires-python = ">=3.12"`
- `[project.dependencies]`: `fastapi`, `mangum`, `uvicorn[standard]`
  (Mangum is a runtime dep — the handler import-smoke test requires it; not dev-only.)
- `[project.optional-dependencies.dev]` (or `[dependency-groups.dev]`): `pytest`,
  `pytest-asyncio`, `ruff`, `mypy` (and `httpx` — FastAPI's TestClient runtime dep)
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `asyncio_mode = "auto"`
- `[tool.ruff]`: `line-length = 88`, `target-version = "py312"`
- `[tool.mypy]`: `strict = true`, `python_version = "3.12"`
- Note: `httpx` is required by `fastapi.testclient.TestClient` (Starlette 0.36+) even for
  sync usage; include it in dev deps so tests import cleanly.

## Implementation Order (TDD)
1. Create empty `__init__.py` package files + directory tree.
2. Write `tests/test_health.py` + `tests/conftest.py` **first** (failing — no app yet).
3. Write `pyproject.toml`; run `uv sync` to install; confirm `uv run pytest` fails (import error).
4. Implement `app/api/health.py` (router) → `app/main.py` (app + Mangum handler).
5. `uv run pytest tests/ -v` → green.
6. Housekeeping edits A1, A3, A5 (documentation only — do not touch logic).
7. Run full verification block below.

## Conventions (from phase-2 plan §Code Style)
- `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE` enums.
- `mypy --strict` (no `Any` without justification). `async` route handlers. ruff format
  (line-length 88). No comments unless asked.

## API Design Patterns (from api-and-interface-design skill)

Established in this task, applied to all subsequent endpoints:

1. **Contract First** — every endpoint has a Pydantic `response_model` that defines the
   response schema. The types ARE the documentation; FastAPI auto-generates OpenAPI from them.
   Health returns `HealthResponse`, not a raw dict.
2. **Consistent Error Envelope** — `ErrorResponse`/`ErrorBody` (in `app/models/error.py`)
   follows API contracts §2: `{"error": {"code": "...", "message": "...", "details": {...}}}`.
   Every future endpoint uses this same error shape. Status code mapping per §2.1.
3. **Validate at Boundaries** — Pydantic models at the API layer; internal code trusts types.
4. **Input/Output Separation** — separate Create/Update/Response models per resource
   (see API contracts §5 stubs: `SessionCreate`, `SessionUpdate`, `SessionResponse`).
5. **Predictable Naming** — plural nouns for REST resources, camelCase response fields,
   UPPER_SNAKE enum values, `is/has/can` prefix for booleans.

## Verification (all must pass — run from worktree root)
```bash
uv sync                                       # install deps
uv run pytest tests/ -v                       # smoke test passes
uv run ruff check . && uv run ruff format --check . && uv run mypy .
python -c "from app.main import handler; print(type(handler))"   # <class 'mangum.Mangum'>
uv run uvicorn app.main:app --port 8000 &     # server starts
curl -s localhost:8000/health                  # {"status":"ok"}
```
- mypy strict must pass with zero errors on the new `app/` + `tests/`.
- ruff must not flag the legacy `src/` (it is pre-existing; scope checks to `app/`+`tests/`,
  but `ruff check .` runs repo-wide — verify legacy doesn't newly fail; if it does, restrict
  ruff `src`/`exclude` rather than editing legacy code).

## Risks / Edge Cases
- **Mangum import at module load** — `from app.main import handler` runs `Mangum(app)`; ensure
  no side effects (no DB/network) in module scope. Health route must not touch any resource.
- **ruff/mypy over legacy `src/`** — legacy code targets py3.8 + pylint and likely fails strict
  mypy/ruff. Mitigation: configure `[tool.mypy] exclude = ["src/", "test/"]` and
  `[tool.ruff]` `extend-exclude = ["src/", "test/", "mock/"]` so gates apply to `app/`+`tests/`
  only, without editing legacy. Document this exclusion in the PR.
- **`requires-python` vs `python_requires`** — use `requires-python` (PEP 621) for uv/hatch.
- **httpx missing** — FastAPI `TestClient` (Starlette 0.36+) needs `httpx`; forgetting it
  causes `ImportError` at test collection. Listed in dev deps above.
- **No secrets** — JWT signing secret, Google client, OSRM endpoint are NOT in this task.

## Acceptance Criteria Mapping
1. ✅ `app/main.py` FastAPI app + `handler = Mangum(app)` export
2. ✅ `GET /health` → `{"status":"ok"}` 200
3. ✅ `pyproject.toml` declares py3.12, dev extras (pytest, pytest-asyncio, ruff, mypy),
   `testpaths = ["tests"]`
4. ⚠️ `requirements.txt` → **deviation**: legacy CLI pins retained; backend pins in
   pyproject. Documented in PR. (Human-approved resolution.)
5. ✅ `tests/test_health.py` TestClient smoke test passes
6. ✅ `tests/conftest.py` defines `client` TestClient fixture
7. ✅ Housekeeping A1, A3, A5 complete

## Out of Scope
- Auth (Task 2.3), RBAC (2.4), DynamoDB/repos (2.2), middleware, rate limiting, CI/CD (2.10),
  frontend. `app/{auth,models,services,repositories,middleware}/__init__.py` exist as empty
  placeholders only.
