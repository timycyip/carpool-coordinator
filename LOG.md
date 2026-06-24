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
