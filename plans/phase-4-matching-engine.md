# Phase 4 — Matching Engine Plan

Builds on Phase 3 (registrations with geocoded locations). Most complex phase. Goal: a CVRPTW-based greedy matching engine producing versioned proposed matches, with admin review/edit UI.

---

## Phase 1 Review Advisories (carried forward)

These advisories from the Phase 1 consolidated review must be addressed during Phase 4.

| Priority | ID | Advisory | Owner |
|----------|----|----------|-------|
| **Phase 4** | A8 | NFR-PERF-2 targets "Matching < 30s for 500 users" but the MVP greedy solver caps at <300 users per the spec. The 500-user NFR is untestable on the MVP solver. Resolution: lower the NFR to 300 users for MVP and add a post-MVP NFR for 500 users in Phase 6. Update `docs/requirements_baseline.md` NFR-PERF-2. | Planning |
| **Anytime** | A6 | Broken link in `docs/requirements_baseline.md` Appendix A: `plans/phase-4-matching.md` should be `plans/phase-4-matching-engine.md`. Fix the link. | Planning |

### Cross-phase blockers from Phase 2 review (2026-06-24)

| Priority | ID | Item | Owner |
|----------|----|------|-------|
| **Phase 4** | B4-P2 | Override operation literal mismatch — API contract `OverrideOperation` enum uses `unassign_passenger`, `lock_assignment` but request bodies use `unassign`, `lock`. Reconcile before implementation. Choose one convention and align. | Backend |
| **Phase 4** | B5-P2 | Match entity shape mismatch — ERD uses `assignments: map {driver → [passengers]}` with `__unmatched__` sentinel; API Contract uses `assignments: list[{driver_sub, passenger_subs, pickup_order, locked}]` with separate `unassigned: list[str]`. `pickup_order`, `locked`, `match_score` (ERD) vs `objective_score` (API) also diverge. Reconcile before implementation. | Backend + Planning |
| **Phase 4** | H1-P2 | Match versioning ERD §4.2 "exactly one approved per session" contradicts §4.5 scenario producing two approved versions. Clarify: "currently approved = highest-version-number `MATCH#V<n>` with `status=approved`; historical approved versions retained." | Backend |

---

## Open Questions (to refine)
- [ ] Cost-function weights (distance/time/load): default values? Make configurable per session or global?
- [ ] Detour feasibility threshold: absolute (km) or relative (× direct distance)?
- [ ] When capacity is insufficient for all passengers, what's the policy — leave unmatched and flag, or overfill with warning? Recommend: leave unmatched + flag in admin UI.
- [x] ~~Should the engine support return trips (`FROM_ORIGIN`) in MVP or only `TO_DESTINATION`?~~ → **RESOLVED (OQ-7):** `TO_DESTINATION` only for MVP. `FROM_ORIGIN` deferred post-MVP.
- [ ] Determinism: should the same input always produce the same proposed match (seeded)? Recommend yes for auditability.

## Goal
A matching engine that takes a session's drivers + passengers + constraints and outputs an optimized assignment, scored and versioned. Runs synchronously in Lambda for sessions <300 users. Admins review, edit, and prepare for approval (publish is Phase 5).

## Decisions (locked)
- Greedy heuristic MVP (Section 12 Stage 4 MVP), sync in Lambda.
- Algorithm adapted from existing `src/main.py` distance-matrix approach, relocated to `app/services/matching.py` and enhanced for CVRPTW.
- Four-stage pipeline (Section 12): geographic clustering → candidate filtering → cost matrix → optimization.
- Cost function: `score = distance_weight*detour + time_weight*lateness + load_weight*imbalance`.
- Matrix API (OpenRouteService free-tier `/v2/matrix`) required for efficient candidate scoring. Batched for sessions >50 participants.
- Match versioning: each `POST /match/run` writes `MATCH#V{n+1}`; only one version approved per session.
- Proposed matches hidden from drivers/passengers until approval (Phase 5).
- Async + OR-Tools production solver deferred (noted as future enhancement).

## Tasks (ordered)

### Backend
1. **Relocate + refactor existing matcher**: move `src/main.py` distance-matrix + geocode helpers into `app/services/matching.py` and `app/services/geocode.py`. Remove CLI/pandas-CSV I/O; operate on registration data from DynamoDB. Keep `test/` suite ported to operate on repository data.
2. **Stage 1 — Geographic clustering**: cluster drivers/passengers by postal-code proximity to prune the search space (Section 12 Stage 1).
3. **Stage 2 — Candidate filtering**: discard infeasible driver↔passenger pairs (detour > driver max, no schedule overlap, no remaining seat, arrival/departure constraint violation).
4. **Stage 3 — Cost matrix**: build driver× passenger cost matrix using ORS `/v2/matrix` for actual road distances/durations. Compute per-pair score via the cost function (detour, lateness, imbalance). Batched for sessions >50 participants.
5. **Stage 4 — Greedy optimization**: assign passengers greedily by ascending score subject to seat capacity + time-window feasibility. Track unmatched passengers and over-capacity/under-capacity drivers.
6. **Matching APIs**: `POST /sessions/{code}/match/run` (Session Admin) — runs engine, writes `MATCH#V{n+1}` as `Matching Pending → Matching Proposed`. `GET /sessions/{code}/match` — latest proposed match (admin only). `PATCH /sessions/{code}/match/manual` — admin override (move/unassign/lock).
7. **Idempotency table + `match/run` idempotency** (deferred from Phase 2): add `idempotency` table to `docs/data_model_erd.md` §1 with PK=`IDEMPOTENCY#<sub>#<session>#<key>`, SK=`METADATA`, TTL=24h. Provision the table in Terraform (`infra/idempotency.tf`). Implement idempotency-key logic in `POST /sessions/{code}/match/run` per `docs/api_contracts.md` §1.6: on repeat key within 24h, return original response without re-running the engine. Scope: `(sub, {code})`.
8. **Manual override service**: `app/services/override.py` — implement FR-8 (move passenger, unassign, mark unmatched, lock assignment). Validate overrides keep hard constraints satisfied; warn (don't block) on soft-constraint regressions.
9. **Session status transitions**: enforce `Registration Open → (close) → Matching Pending → Matching Proposed` and block registration changes once matching has run.
10. **Per-passenger matching score**: store per-pair score for admin transparency (FR-9: admin/manager/superuser only).
11. **Performance guardrail**: for sessions >300 users, refuse synchronous run with a clear message directing to the (future) async path; document the limit.

### Frontend (Next.js)
1. **Admin matching dashboard**: "Run matching" action, status indicator, run history (versions).
2. **Proposed-match review**: per-driver cards listing assigned passengers with route map (ORS `/v2/directions` polyline), detour/distance/lateness, and per-pair scores.
3. **Manual override UI**: drag/drop or pick passenger → reassign to another driver; unassign; lock toggle. Live validation feedback on hard-constraint violations.
4. **Unmatched panel**: list of unmatched passengers + reason (no seat, no feasible driver, schedule).
5. **Version compare**: diff between two proposed match versions (optional, time-permitting).

## Deliverables
- `app/services/matching.py` with the 4-stage pipeline, adapted from existing logic.
- Matching APIs (`run`, `get`, `manual`) with versioning.
- **`infra/idempotency.tf`** — `idempotency` DynamoDB table (deferred from Phase 2) for `POST /match/run` idempotency-key support per §1.6.
- Admin matching review/edit UI with route maps and scores.
- Performance: <30s for 500 users (NFR), synchronous in Lambda.

## Validation
- Hard constraints always satisfied in output (seat capacity, schedule, geographic feasibility).
- Re-running with identical input produces identical output (deterministic, seeded).
- Unmatched passengers explicitly listed, not silently dropped.
- Drivers/passengers cannot see proposed matches (FR-9 + FR-7 pre-approval).
- Manual override that violates a hard constraint is rejected with a clear reason.
- Performance test: 500-user synthetic session completes <30s in Lambda.
- Existing `test/test_match_riders_*.py` ported and passing on new data path.

## Dependencies
- Phase 3: registrations + geocoded locations + ORS free-tier `/v2/matrix` + `/v2/directions`.
- Phase 2: session lifecycle + RBAC.
- Phase 1: ERD match versioning, API contracts for matching endpoints.

## Out of Scope
- OR-Tools / integer-programming production solver (future).
- Async matching via SQS/Step Functions/Fargate for >300 users (future enhancement).
- Return-trip (`FROM_ORIGIN`) solving (future).
- Approval + publish + notifications (Phase 5).

---

## Task Breakdown

> Most complex phase. The existing `src/main.py` logic (distance matrix + greedy closest-pairs + geopy geocoding) is relocated and enhanced for CVRPTW. Ported tests from `test/test_match_riders_*.py` must pass on the new data path. Tasks are sized S or M.

### Task 4.1: Relocate + refactor existing matcher [MVP]

**Description:** Move the existing `src/main.py` distance-matrix + geocode helpers into `app/services/matching.py` and `app/services/geocode.py`. Remove CLI/pandas-CSV I/O; operate on registration data from DynamoDB repositories. Port existing test suite to operate on repository data.

**Acceptance criteria:**
- [ ] `app/services/matching.py` contains the relocated distance-matrix + greedy assignment logic
- [ ] CLI argparse and pandas CSV I/O removed; operates on `Registration` model objects
- [ ] `find_closest_x_locations` and `reduce_matrix` helpers preserved and unit-tested
- [ ] Ported `tests/services/test_matching_basic.py` passes (adapted from `test/test_match_riders_*.py`)
- [ ] `src/main.py` and old `test/` retained but deprecated (or archived to `legacy/`)

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_matching_basic.py -v`
- [ ] Manual check: feed mock registrations, get assignment output

**Dependencies:** Task 3.4

**Files likely touched:**
- `app/services/matching.py`
- `tests/services/test_matching_basic.py`
- `app/services/__init__.py`

**Estimated scope:** M

### Task 4.2: Stage 1 — Geographic clustering [MVP]

**Description:** Implement Stage 1 of the matching pipeline (Section 12): cluster drivers/passengers by postal-code proximity to reduce the search space. Prune participants too far from the anchor location.

**Acceptance criteria:**
- [ ] Clustering groups participants by postal-code proximity (configurable radius)
- [ ] Participants beyond max distance from anchor (destination/origin) pruned as unmatched
- [ ] Each cluster is a self-contained candidate set for Stages 2–4
- [ ] Unit tests with known geographic distributions

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_clustering.py -v`
- [ ] Manual check: 50 registrations across 3 postal codes → 3 clusters

**Dependencies:** Task 4.1

**Files likely touched:**
- `app/services/clustering.py`
- `tests/services/test_clustering.py`

**Estimated scope:** S

### Task 4.3: Stage 2 — Candidate filtering [MVP]

**Description:** Implement Stage 2: for each cluster, discard infeasible driver↔passenger pairs based on detour > driver max, no schedule overlap, no remaining seat, arrival/departure constraint violations.

**Acceptance criteria:**
- [ ] Filters pairs where detour exceeds driver's max detour (configurable)
- [ ] Filters pairs with no time-window overlap (driver departure vs passenger availability)
- [ ] Filters pairs where arrival would be after session cutoff
- [ ] Returns a candidate list per driver with feasible passengers
- [ ] Unit tests with edge cases (all filtered, none filtered, boundary conditions)

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_candidate_filter.py -v`
- [ ] Manual check: a passenger too far from all drivers → marked unmatched

**Dependencies:** Task 4.2

**Files likely touched:**
- `app/services/candidate_filter.py`
- `tests/services/test_candidate_filter.py`

**Estimated scope:** S

### Task 4.4: Stage 3 — Cost matrix via ORS [MVP]

**Description:** Build the driver×passenger cost matrix using ORS `/v2/matrix` for actual road distances/durations. Compute per-pair score: `score = distance_weight*detour + time_weight*lateness + load_weight*imbalance`. Lower score = better.

**Acceptance criteria:**
- [ ] Fetches road distance/duration matrix from ORS `/v2/matrix` for all candidate pairs
- [ ] Batches matrix calls for >50 locations (chunked ORS calls + merge into single cost matrix)
- [ ] Client-side throttling respects ORS free-tier 40 req/min limit
- [ ] Computes detour (extra distance vs direct driver→destination)
- [ ] Computes lateness (arrival time vs session cutoff)
- [ ] Computes imbalance (driver load vs average)
- [ ] Weights configurable (env vars or session config)
- [ ] Returns structured cost matrix with per-pair scores
- [ ] Unit tests with mocked ORS matrix

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_cost_matrix.py -v`
- [ ] Manual check: 5 drivers × 10 passengers → 50-element cost matrix via ORS with sensible scores

**Dependencies:** Task 3.3 (routing client, ORS-based), Task 4.3

**Files likely touched:**
- `app/services/cost_matrix.py`
- `tests/services/test_cost_matrix.py`

**Estimated scope:** M

### Task 4.5: Stage 4 — Greedy optimization [MVP]

**Description:** Implement the greedy assignment: assign passengers to drivers by ascending cost score, subject to seat capacity + time-window feasibility. Track unmatched passengers and capacity utilization. Deterministic (seeded) for auditability.

**Acceptance criteria:**
- [ ] Greedy assignment: sort candidate pairs by ascending score, assign greedily
- [ ] Respects seat capacity per driver
- [ ] Respects time-window feasibility (no passenger assigned to a driver whose departure is too late)
- [ ] Unmatched passengers explicitly listed (not silently dropped)
- [ ] Same input always produces same output (deterministic seed)
- [ ] Returns structured output: `{driver_id: [passenger_ids], unmatched: [passenger_ids]}`

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_greedy_optimization.py -v`
- [ ] Manual check: 10 drivers, 20 passengers → all assigned within capacity
- [ ] Manual check: insufficient capacity → unmatched list populated

**Dependencies:** Task 4.4

**Files likely touched:**
- `app/services/matching.py` (extend with greedy optimizer)
- `tests/services/test_greedy_optimization.py`

**Estimated scope:** M

### Task 4.6: Matching run API + versioning [MVP]

**Description:** Implement `POST /sessions/{code}/match/run` (Session Admin) and `GET /sessions/{code}/match` (Admin). Each run writes `MATCH#V{n+1}` to DynamoDB. Transitions session status `Matching Pending → Matching Proposed`. Proposed matches hidden from drivers/passengers (FR-7/FR-9).

**Acceptance criteria:**
- [ ] `POST /sessions/{code}/match/run` executes the 4-stage pipeline, stores result as `MATCH#V{n+1}`
- [ ] Session status transitions: Registration Open → (close) → Matching Pending → Matching Proposed
- [ ] Registration changes blocked once matching has run
- [ ] `GET /sessions/{code}/match` returns latest proposed match (admin/manager/superuser only)
- [ ] Driver/passenger calling `GET /sessions/{code}/match` → 403 (pre-approval)
- [ ] Performance guardrail: sessions >300 users → 400 with "async matching not yet available"
- [ ] Per-pair matching scores stored for admin transparency

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_matching.py -v`
- [ ] Manual check: run matching on a test session, verify versioned output in DynamoDB
- [ ] Performance test: 500-user synthetic session completes < 30s in Lambda

**Dependencies:** Task 4.5, Task 2.2

**Files likely touched:**
- `app/api/matching.py`
- `app/services/matching.py` (extend)
- `app/repositories/match.py` (extend)
- `tests/api/test_matching.py`

**Estimated scope:** M

### Task 4.7: Manual override service [MVP]

**Description:** Implement `PATCH /sessions/{code}/match/manual` (Admin) supporting FR-8: move passenger to another driver, unassign passenger, mark passenger unmatched, lock assignment. Validates hard constraints; warns on soft-constraint regressions.

**Acceptance criteria:**
- [ ] Move passenger: validates target driver has capacity + feasibility
- [ ] Unassign passenger: removes from driver, adds to unmatched list
- [ ] Mark unmatched: explicit flag for participants with no feasible driver
- [ ] Lock assignment: prevents future algorithm reassignment for that passenger
- [ ] Hard-constraint violation (over-capacity, schedule) → rejected with 400 + reason
- [ ] Soft-constraint regression (worse score) → warning returned but change applied
- [ ] Allowed both before and after approval
- [ ] Each override writes a new match version delta

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_manual_override.py -v`
- [ ] Manual check: move passenger to full driver → 400
- [ ] Manual check: move passenger to feasible driver → success + new version

**Dependencies:** Task 4.6

**Files likely touched:**
- `app/api/matching.py` (extend)
- `app/services/override.py`
- `tests/api/test_manual_override.py`

**Estimated scope:** M

### Task 4.8: Admin matching review UI [MVP]

**Description:** Build the admin matching dashboard: "Run matching" action, status indicator, version history. Proposed-match review with per-driver cards showing assigned passengers, route map (ORS polyline), detour/distance/lateness, and per-pair scores.

> **Note (lean MVP):** run button, per-driver cards with passenger list + route map + scores, unmatched panel. Defer version compare.

**Acceptance criteria:**
- [ ] Dashboard shows session status + "Run Matching" button (disabled if status ≠ Registration Open closed)
- [ ] After run: per-driver cards with assigned passengers, route map, metrics
- [ ] Route map renders ORS `/v2/directions` polyline via react-leaflet
- [ ] Per-pair scores visible (color-coded: green=good, yellow=warning)
- [ ] Unmatched panel lists unmatched passengers + reason
- [ ] Version history shows prior runs with timestamps

**Verification:**
- [ ] Manual check: run matching, see driver cards with route maps
- [ ] Manual check: unmatched passengers listed with reasons
- [ ] Manual check: version history navigable

**Dependencies:** Task 4.6, Task 3.3

**Files likely touched:**
- `frontend/src/app/sessions/[code]/admin/matching/page.tsx`
- `frontend/src/components/MatchingDashboard.tsx`
- `frontend/src/components/DriverRouteCard.tsx`
- `frontend/src/components/RouteMap.tsx`

**Estimated scope:** M

### Task 4.9: Manual override UI [DEFERRED]

**Description:** Build the manual override interface within the matching review: drag/drop or pick passenger → reassign, unassign, lock toggle. Live validation feedback on hard-constraint violations.

> **Note (DEFERRED):** Deferred for 3-week MVP. Admin re-runs matching (deterministic, seeded) or edits registrations + re-runs. The override backend service (Task 4.7) remains [MVP] for post-approval edits in Phase 5.

**Acceptance criteria:**
- [ ] Each passenger in a driver card has actions: "Reassign", "Unassign", "Lock"
- [ ] Reassign opens a driver picker (filtered to feasible drivers with capacity)
- [ ] Hard-constraint violation → action blocked with red error message
- [ ] Soft-constraint regression → confirmation dialog with warning
- [ ] Changes immediately reflected in the review view
- [ ] Unmatched passengers can be manually assigned to a driver

**Verification:**
- [ ] Manual check: reassign passenger to feasible driver → success
- [ ] Manual check: reassign to full driver → blocked with error
- [ ] Manual check: unassign passenger → moves to unmatched panel

**Dependencies:** Task 4.8, Task 4.7

**Files likely touched:**
- `frontend/src/components/MatchingDashboard.tsx` (extend)
- `frontend/src/components/OverridePanel.tsx`

**Estimated scope:** S

### Checkpoint: End of Phase 4
- [ ] All tests pass (including ported tests from original `src/main.py`)
- [ ] Matching runs on a test session and produces sensible assignments
- [ ] Admin can review, override, and re-run matching
- [ ] Performance: <30s for 500 users (ORS batched matrix calls may extend runtime; validate with a 200-user session)
- [ ] Proposed matches hidden from drivers/passengers
- [ ] **Review with human before proceeding to Phase 5**

### Parallelization notes
- Stages 1–4 (4.2, 4.3, 4.4, 4.5) are strictly sequential — each depends on the previous.
- Task 4.6 (run API) depends on all stages. Task 4.7 (override) depends on 4.6.
- Tasks 4.8 and 4.9 are UI tasks; 4.8 can begin once the API contract from 4.6 is defined (even before 4.6 lands).

### Risks (Phase 4 specific)
| Risk | Impact | Mitigation |
|------|--------|------------|
| Matching exceeds Lambda timeout (>15 min) | High | Sync only for <300; refuse >300 with clear message; async path is future |
| Existing `src/main.py` tests break on refactor | Medium | Port incrementally (4.1); keep `src/` as reference until ported tests pass |
| Greedy algorithm produces poor assignments | Medium | Surface per-pair scores to admin; manual override always available |
| ORS free-tier rate limit (40 req/min) throttles large-session matrix calls | Medium | Batch + cache matrix per session; haversine pre-filter reduces candidate set before ORS call |
| Non-deterministic output blocks audit | Low | Seeded random; same input → same output tested in 4.5 |
| Visibility leak in proposed match (driver sees other drivers) | High | Server-side filter in `GET /match`; never return other drivers' data pre-approval |
