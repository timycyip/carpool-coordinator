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
