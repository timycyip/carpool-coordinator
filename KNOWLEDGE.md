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
