# Phase 3 — Registration Plan

Builds on Phase 2 (working auth + session CRUD + RBAC). Goal: users can register as drivers/passengers into a session, with location lookup via OSM services.

## Open Questions (to refine)
- [ ] ORS free-tier matrix limit (~50 locations/call) — what batching strategy for sessions with 200+ participants?
- [ ] Geocode cache TTL: permanent (postal code centroids rarely change) or 90-day refresh?
- [ ] Postal code validation: which countries/regexes for MVP? Recommend restricting to one country per first-deployment region.
- [ ] Accessibility requirements field: free text or controlled vocabulary (wheelchair, service animal, etc.)?

## Goal
Registration workflow with maps integration. Drivers and passengers can register into an open session, submit location (postal code → geocoded), and view their own registration. Admin can see all registrations for their session.

## Decisions (locked)
- Geocoding: public Nominatim, rate-limited to 1 req/s, results cached as TTL items in `app_data` (key = postal code).
- Routing/matrix: OpenRouteService (ORS) free-tier API (`/v2/directions`, `/v2/matrix`). Free tier: 2000 req/day, 40 req/min, ~50 locations per matrix call — batching required for large sessions.
- Registration APIs: `POST /sessions/{code}/register`, `GET /sessions/{code}/me`, `PATCH /sessions/{code}/me`.
- Canonical registration schema (resolving FR-3 vs FR-4 duplication) from Phase 1 baseline.
- Driver/passenger visibility per FR-9: users see only their own registration pre-match.

## Tasks (ordered)

### Backend
1. **Registration API**: `POST /sessions/{code}/register` — accept role (driver/passenger) + canonical fields. Validate session is `Registration Open` and not past `registration_deadline`. Enforce one registration per user per session (role locked at registration).
2. **Geocode service**: `app/services/geocode.py` — postal code → centroid lat/lon via Nominatim (1 req/s RateLimiter adapted from existing `src/main.py`). Check `app_data` TTL cache first; on miss, geocode + cache with TTL. Handle `CustomGeocodingError` → return 400 with actionable message.
3. **Routing service**: `app/services/routing.py` — thin client over ORS `/v2/directions` and `/v2/matrix`. Used now for distance validation (detour feasibility pre-check); primary consumer is Phase 4 matching.
4. **Registration read/update**: `GET /sessions/{code}/me` (self), `PATCH /sessions/{code}/me` (self, only while `Registration Open`). Enforce FR-9 visibility.
5. **Admin registration view**: `GET /sessions/{code}/registrations` (Session Admin/Manager/Superuser) — list all drivers/passengers with locations + time windows.
6. **Registration field validation**: postal code format, time window sanity (earliest < latest, within session window), seat capacity > 0 for drivers.
7. **Audit**: log registration create/update events.

### Frontend (Next.js)
1. **Driver registration form**: canonical driver fields, postal code with autocomplete + map preview pin, seat capacity, time windows, route preferences.
2. **Passenger registration form**: canonical passenger fields, postal code + map pin, time windows, accessibility notes.
3. **Session join flow**: deep-link `/register?session=ABC123` → session summary → choose role → form → confirmation.
4. **"My registration" view**: `GET /sessions/{code}/me` render; edit while registration open.
5. **Admin registrations table**: paginated, filterable by role, with location map markers.
6. **Map components**: use a lightweight OSM-tile map (e.g., `react-leaflet`) for pin preview and admin overview.

## Deliverables
- Registration APIs live and validated.
- ORS routing client integrated (directions + matrix) with free-tier throttling.
- Geocode cache populated and respecting 1 req/s.
- Driver + passenger registration forms in Next.js.
- Admin registrations view with map.

## Validation
- Registering into a `Draft` or `Closed` session → 403/409.
- Duplicate registration (same user, same session) → 409 with clear message.
- Postal code not resolvable by Nominatim → 400 with "location not found".
- Geocode cache hit rate > 90% after first load of a session's registrations.
- Nominatim never called more than once per second.
- Driver cannot see other drivers' passengers (FR-9 enforced).
- p95 registration latency < 800ms (excluding first-geocode cold path).
- ORS matrix call for 50 locations completes < 2s.

## Dependencies
- Phase 2: auth, session lifecycle, RBAC middleware.
- Phase 1: canonical registration schema, ERD, API contracts.
- ORS API key provisioned (free tier: 2000 req/day, 40 req/min).

## Out of Scope
- Matching engine (Phase 4).
- Approval workflow (Phase 5).
- Notifications (Phase 5).
- Return-trip registration (future enhancement).

---

## Task Breakdown

> Tasks are **vertically sliced** and sized S or M. Each task has acceptance criteria, verification steps, dependencies, files likely touched, and a scope estimate. No task is XL.

### Task 3.1: Geocode service (Nominatim + cache) [MVP]

**Description:** Implement the geocode service that converts postal codes to centroid lat/lon via public Nominatim (rate-limited to 1 req/s), with results cached as TTL items in `app_data` (key = postal code). Adapt the existing `custom_geocode` and `RateLimiter` patterns from `src/main.py`.

**Acceptance criteria:**
- [ ] `app/services/geocode.py` accepts a postal code, checks cache first, then Nominatim
- [ ] Rate limiter enforces max 1 request/second to Nominatim
- [ ] Cache hits return cached lat/lon without calling Nominatim
- [ ] Cache TTL configurable (default: permanent for postal code centroids)
- [ ] Unresolvable postal code → raises `CustomGeocodingError` → API returns 400
- [ ] Unit tests with mocked Nominatim responses

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_geocode.py -v`
- [ ] Manual check: geocode a postal code, verify cache populated, second call is instant
- [ ] Manual check: invalid postal code → 400 with actionable message

**Dependencies:** Task 2.2

**Files likely touched:**
- `app/services/geocode.py`
- `tests/services/test_geocode.py`

**Estimated scope:** S

### Task 3.3: Routing service client [MVP]

**Description:** Implement a thin client over the OpenRouteService (ORS) free-tier API — `/v2/directions/{profile}` for routes with geometry and `/v2/matrix` for distance+duration matrices. Used now for distance validation (detour feasibility pre-check during registration) and as the primary consumer by the Phase 4 matching engine.

**Acceptance criteria:**
- [ ] `app/services/routing.py` provides `get_route(origin, destination)` and `get_matrix(locations)`
- [ ] `get_route` calls ORS `/v2/directions/{profile}` and returns distance (m), duration (s), polyline geometry
- [ ] `get_matrix` calls ORS `/v2/matrix` and returns structured distance + duration matrices
- [ ] Handles ORS free-tier rate limits (40 req/min) with client-side throttling
- [ ] Batches matrix requests for >50 locations (chunked calls + merge)
- [ ] Handles ORS errors gracefully with retries (exponential backoff)
- [ ] Configurable ORS base URL + API key (env vars)
- [ ] Unit tests with mocked ORS responses

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_routing.py -v`
- [ ] Manual check: `curl` ORS `/v2/directions/driving` between two known points returns an expected distance range
- [ ] Manual check: `curl` ORS `/v2/matrix` for a small location set returns an NxN matrix

**Dependencies:** Task 3.1

**Files likely touched:**
- `app/services/routing.py`
- `tests/services/test_routing.py`

**Estimated scope:** S

### Task 3.4: Registration API (driver + passenger) [MVP]

**Description:** Implement `POST /sessions/{code}/register`, `GET /sessions/{code}/me`, `PATCH /sessions/{code}/me`. Accepts role (driver/passenger) + canonical fields (resolving FR-3 vs FR-4 duplication). Validates session is open, geocodes postal code, enforces one registration per user per session.

**Acceptance criteria:**
- [ ] `POST /sessions/{code}/register` accepts role + fields; validates session status=Registration Open, deadline not passed
- [ ] Geocodes postal code on write; stores lat/lon with registration
- [ ] One registration per user per session (role locked at registration); duplicate → 409
- [ ] `GET /sessions/{code}/me` returns own registration only
- [ ] `PATCH /sessions/{code}/me` allows updates only while Registration Open
- [ ] Driver: seat capacity > 0 required; passenger: accessibility notes optional
- [ ] Admin/Manager can `GET /sessions/{code}/registrations` to list all

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_registration.py -v`
- [ ] Manual check: register as driver, verify geocoded location stored
- [ ] Manual check: duplicate registration → 409
- [ ] Manual check: PATCH after matching started → 409

**Dependencies:** Task 3.1, Task 2.6

**Files likely touched:**
- `app/api/registration.py`
- `app/models/registration.py`
- `app/services/registration.py`
- `tests/api/test_registration.py`

**Estimated scope:** M

### Task 3.5: Driver registration UI [MVP]

**Description:** Build the driver registration form in Next.js. Collects canonical driver fields, postal code with geocode preview (map pin), seat capacity, time windows. Shows confirmation on success.

**Acceptance criteria:**
- [ ] Form collects: name (pre-filled from Google), email (pre-filled), postal code, seat capacity, earliest/latest pickup times, route preferences
- [ ] Postal code entry triggers geocode preview with map pin (react-leaflet + OSM tiles)
- [ ] Form validation: seat capacity > 0, time windows sane (earliest < latest, within session window)
- [ ] On submit: calls `POST /sessions/{code}/register`, shows confirmation with assignment pending
- [ ] Error states: session closed, duplicate registration, geocode failure

**Verification:**
- [ ] Manual check: fill form, submit, see confirmation
- [ ] Manual check: invalid postal code → inline error with map pin missing
- [ ] Manual check: seat capacity 0 → validation error

**Dependencies:** Task 3.4, Task 2.11

**Files likely touched:**
- `frontend/src/app/sessions/[code]/register/driver/page.tsx`
- `frontend/src/components/LocationPicker.tsx`
- `frontend/src/components/RegistrationForm.tsx`

**Estimated scope:** M

### Task 3.6: Passenger registration UI [MVP]

**Description:** Build the passenger registration form. Collects canonical passenger fields, postal code with map preview, time windows, accessibility notes. Shows confirmation on success.

**Acceptance criteria:**
- [ ] Form collects: name (pre-filled), email (pre-filled), postal code, earliest/latest available times, accessibility requirements, special notes
- [ ] Postal code geocode preview with map pin (reuses `LocationPicker` component)
- [ ] Form validation: time windows within session bounds
- [ ] On submit: calls `POST /sessions/{code}/register`, shows confirmation
- [ ] Error states: session closed, duplicate registration, geocode failure

**Verification:**
- [ ] Manual check: fill form, submit, see confirmation
- [ ] Manual check: accessibility notes persisted and visible to admin

**Dependencies:** Task 3.4, Task 3.5 (reuses LocationPicker)

**Files likely touched:**
- `frontend/src/app/sessions/[code]/register/passenger/page.tsx`
- `frontend/src/components/RegistrationForm.tsx` (extend with passenger variant)

**Estimated scope:** S

### Task 3.7: "My registration" view + edit [MVP]

**Description:** Build the participant's view of their own registration (`GET /sessions/{code}/me`), with edit capability while registration is open. Shows role, location on map, time windows, and status.

**Acceptance criteria:**
- [ ] Page renders own registration with all fields + map pin
- [ ] Edit button visible only while session status=Registration Open
- [ ] Edit form reuses the driver/passenger form (read-only mode → edit mode)
- [ ] "Waiting for matching" indicator shown after registration closes
- [ ] No visibility into other participants' data (FR-9)

**Verification:**
- [ ] Manual check: view own registration, edit postal code, save
- [ ] Manual check: after registration closes, edit button hidden

**Dependencies:** Task 3.4, Task 3.5

**Files likely touched:**
- `frontend/src/app/sessions/[code]/me/page.tsx`
- `frontend/src/components/RegistrationView.tsx`

**Estimated scope:** S

### Task 3.8: Admin registrations view with map [MVP — lean]

**Description:** Build the Session Admin's view of all registrations for their session. Paginated, filterable by role, with location markers on a map. **Lean MVP:** basic table + simple map; defer clustering/pagination polish.

**Acceptance criteria:**
- [ ] `GET /sessions/{code}/registrations` (Admin/Manager) lists all drivers + passengers
- [ ] Frontend table: name, role, postal code, time windows, seat capacity (drivers), accessibility notes (passengers)
- [ ] Map view with all participant location markers (clustered if many)
- [ ] Filter by role (all / drivers / passengers)
- [ ] Session Admin for session A cannot see session B's registrations
- [ ] Pagination for sessions with many registrations

**Verification:**
- [ ] Manual check: admin views all registrations, map shows markers
- [ ] Manual check: admin for session A queries session B → 403
- [ ] Performance: 100 registrations loads < 2s

**Dependencies:** Task 3.4, Task 2.4 (RBAC)

**Files likely touched:**
- `frontend/src/app/sessions/[code]/admin/registrations/page.tsx`
- `frontend/src/components/RegistrationsMap.tsx`

**Estimated scope:** M

### Checkpoint: End of Phase 3
- [ ] All tests pass
- [ ] A driver and passenger can register into a session with geocoded locations
- [ ] Admin can view all registrations on a map
- [ ] Geocode cache hit rate > 90% after initial load
- [ ] **Review with human before proceeding to Phase 4**

### Parallelization notes
- Task 3.2 (OSRM setup) is removed — no self-hosted routing infrastructure this phase.
- Task 3.3 (routing client) now depends on 3.1 only; can start once the geocode service exists.
- Tasks 3.5, 3.6, 3.7, 3.8 all depend on 3.4 and can partially overlap (form components share `LocationPicker`).

### Risks (Phase 3 specific)
| Risk | Impact | Mitigation |
|------|--------|------------|
| Nominatim 1 req/s rate limit blocks registration | High | Aggressive cache, 1 req/s RateLimiter; permanent TTL for postal code centroids |
| ORS free-tier rate limit (40 req/min, 2000/day) too low for large-session matrix calls | Medium | Batch matrix requests; cache results per session; fall back to haversine distance for clustering pre-filter |
| Duplicate registrations due to retry | Medium | Idempotency key on registration POST; unique constraint on (session, user) |
| Map tiles blocked by CSP | Medium | Configure CSP allowlist for tile.openstreetmap.org in Cloudflare |
| `LocationPicker` component drift between driver/passenger forms | Low | Single shared component with role-specific prop schema |
