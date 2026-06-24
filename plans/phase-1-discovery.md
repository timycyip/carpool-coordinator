# Phase 1 — Discovery Plan

Plan series derived from `docs/functional_requirements_and_architecture.md`. This phase produces design artifacts and contracts; no production code is shipped.

## Open Questions (to refine)
- [ ] Who owns sign-off on finalized requirements (Product Owner, BA, or both)?
- [ ] Branding/design system: existing design language or wireframes define one?
- [ ] Compliance constraints (PII residency, data retention law) beyond 30-day S3 lifecycle?
- [ ] Localization/i18n required for MVP or future?

## Goal
Convert the v2 requirements doc into implementation-ready artifacts: signed-off requirements baseline, role matrix, workflow diagrams, data model ERD, API contracts, and low-fi wireframes. Full-stack scope (Next.js frontend + FastAPI backend).

## Decisions (locked)
- Full-stack plans: Next.js (App Router) on Cloudflare Pages + FastAPI on Lambda ARM64.
- Multi-table DynamoDB per data model: `app_data` (single-table PK/SK pattern internally for business entities) + separate `session_cache`, `rate_limit_cache`, `brute_force_counter`, `geocode_cache` tables (see [ADR-0001](docs/adr/0001-table-naming-by-data-model.md)). Rate-limit + cache items use TTL.
- Google OIDC global identity; session code = registration invite; multi-session per user.
- Public Nominatim (geocode, cached in app_data) + OpenRouteService free-tier API (matrix/route).
- Greedy matching MVP, sync in Lambda (`TO_DESTINATION` only; `FROM_ORIGIN` deferred post-MVP).
- Email delivery **deferred**: API Lambda writes `notification_pending` items to DynamoDB; a separate processor (SQS → email Lambda or admin-triggered batch) sends emails via Microsoft Graph `sendMail` → M365 Exchange. This avoids blocking the API response on email delivery. See ADR-0008.

## Tasks (ordered)

### 1. Requirements baseline sign-off
- Review `docs/functional_requirements_and_architecture.md` against stakeholder feedback.
- Produce `docs/requirements_baseline.md`: FR-1..FR-11 with status (Accepted / Clarified / Deferred) and inline clarifications.
- Resolve the FR-3 vs FR-4 field duplication into one canonical registration schema.

### 2. RBAC matrix formalization
- Tabulate every Section 4 permission against each role (Superuser, Manager, Session Admin, Driver, Passenger, System).
- Define Session Admin assignment flow (Manager → user) and the new `POST /sessions/{code}/admin` endpoint contract.
- Specify permission resolution rules (precedence, deny-default, session-scoping).

### 3. Workflow diagrams (Mermaid, `docs/diagrams/`)
- Auth + registration flow (Google login → session code → role assignment).
- Session lifecycle (Draft → Registration Open → Matching Pending → Proposed → Approved → Closed).
- Matching approval workflow (run → propose → review → edit → approve → publish).
- Notification fan-out (API event → synchronous email send via Microsoft Graph → M365 Exchange).

### 4. Data model ERD
- Single-table DynamoDB (`app_data`) entity map: Users, Sessions, Registrations, Matches (versioned), Audit Logs, plus rate-limit counters and geocode-cache items stored with TTL attributes (no separate cache tables).
- Partition/sort key patterns (Section 8) + required GSIs:
  - `registrations-by-session` (PK SESSION#code, SK REG#user).
  - `sessions-by-user` (GSI on user sub).
  - `latest-match-by-session` (PK SESSION#code, SK begins_with MATCH#).
- Match versioning rule: each `POST /match/run` writes `MATCH#V{n+1}`; admin approves exactly one version.

### 5. API contract draft
- Lock REST endpoints from Section 9 plus the admin-assignment endpoint.
- Define request/response JSON schemas (Pydantic model stubs) for every endpoint.
- Specify auth header requirements, error taxonomy, pagination convention.

### 6. Low-fi wireframes (frontend, Next.js screens)
- Login + session-code entry.
- Session list / dashboard.
- Driver registration form.
- Passenger registration form.
- Admin session config + matching review/edit.
- Admin approval + publish.
- Participant "my assignment" view.

## Deliverables
- `docs/requirements_baseline.md`
- `docs/rbac_matrix.md`
- `docs/diagrams/*.mmd`
- `docs/data_model_erd.md`
- `docs/api_contracts.md`
- `docs/wireframes/*.md`

## Validation
- Every FR-1..FR-11 maps to ≥1 task in a later phase plan.
- RBAC matrix covers all Section 4 permissions with no orphan roles.
- API contracts cover all Section 9 endpoints plus admin assignment.
- Stakeholder sign-off recorded in `docs/requirements_baseline.md`.

## Dependencies
- Stakeholder availability for sign-off.
- First-deployment target region for OSM extract planning.

## Out of Scope
- Production code or infrastructure provisioning (Phase 2).
- Final visual design / high-fidelity mockups (later design sprint).
- SMS/WhatsApp/push notifications (future per FR-10).
