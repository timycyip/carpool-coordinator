# REST API Contract

| | |
| --- | --- |
| **Title** | Carpool Coordinator — REST API Contract |
| **Version** | 1.0 (Draft) |
| **Date** | 2026-06-23 |
| **Author Role** | Solution Architect |
| **Status** | **Draft** — pending review by Tech Lead and Backend Engineers |
| **Phase** | 1 — Discovery, Task 5 (per `plans/phase-1-discovery.md`) |
| **Related artifacts** | Master spec `docs/functional_requirements_and_architecture.md` §9 (REST API), §14 (Security Controls); RBAC `docs/rbac_matrix.md`; Auth model `docs/adr/0002-app-session-jwt.md`; Middleware ordering `docs/adr/0005-middleware-ordering.md`; Requirements baseline `docs/requirements_baseline.md` §3 (canonical registration schema) |

---

## 1. Conventions

### 1.1 Base URL

The API is exposed behind **AWS Lambda Function URL** with **Cloudflare** as the edge. The exact base URL is **TBD in Phase 2** (Foundation). All paths below are relative to the base URL.

```
{base_url}/<endpoint>
```

Cloudflare Pages rewrites (per `docs/adr/0004-same-origin-rewrites.md`) front the Lambda URL so that the public-facing origin is the same as the frontend.

### 1.2 Authentication

All endpoints except `POST /auth/google` (and the operational `GET /health`) require a valid **app session JWT** in the `Authorization` header:

```http
Authorization: Bearer <app_session_jwt>
```

The JWT model, claims, and storage are defined in **ADR-0002 (`docs/adr/0002-app-session-jwt.md`)**. Required claims for downstream RBAC:

- `sub` — Google subject identifier (canonical user key).
- `email` — Google account email.
- `name` — display name.
- `global_role` — one of `superuser` | `manager` | `none`.
- `iat`, `exp` — issued-at and expiry (1-hour TTL).

Endpoints that operate on a specific carpool session also include the session code in the path (`{code}`). Session-scoped role resolution (Session Admin, Driver, Passenger) is **not** encoded in the JWT — it is looked up per request against the DynamoDB `app_data` table (see RBAC matrix §2.3, §2.4).

### 1.3 Content Type

```http
Content-Type: application/json
```

All request and response bodies use JSON. Request bodies are validated against Pydantic models (§5); malformed bodies return `400` or `422` (see §3 Error Taxonomy).

### 1.4 Rate Limiting

Per `docs/functional_requirements_and_architecture.md` §14 and `docs/rbac_matrix.md` §6:

- **60 requests / minute / IP** (anonymous bucket).
- **120 requests / minute / authenticated user** (user bucket — applied after JWT verification).

Every response (success or error) **must** include the following headers (per `docs/adr/0005-middleware-ordering.md` — rate_limit is the first dependency):

| Header | Meaning |
| --- | --- |
| `X-RateLimit-Limit` | The active limit (per-IP or per-user) in the current window. |
| `X-RateLimit-Remaining` | Requests remaining in the current window for the active limit. |
| `X-RateLimit-Reset` | Unix epoch seconds at which the current window resets. |
| `Retry-After` | **(429 only)** Seconds until the client may retry. |

When either limit is exceeded the API returns `429 RATE_LIMITED` (see §3). Rate-limit counters live in the `rate_limit_cache` DynamoDB table (TTL-bounded) per the data model ERD.

### 1.5 Pagination

**Cursor-based pagination** for every endpoint that returns a list. There are no offset/limit endpoints in this API.

**Query parameters:**

| Param | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `cursor` | string (opaque token) | No | — | Opaque cursor returned from the previous page's `next_cursor`. Omit on the first page. |
| `limit` | integer | No | `50` | Page size. Clamped to `[1, 100]`; values outside the range return `400`. |

**Response envelope** for paginated list endpoints (matches `PaginatedResponse[T]` in §5):

```json
{
  "items": [ ... ],
  "next_cursor": "opaque_string_or_null",
  "limit": 50
}
```

`next_cursor` is `null` when there are no further pages. Clients must treat the cursor as opaque — encoding/decoding is server-internal.

### 1.6 Idempotency

`POST /sessions/{code}/match/run` accepts an optional `Idempotency-Key` header:

```http
Idempotency-Key: <client-generated-string>
```

- Max length 128 chars; recommended to be a UUID v4.
- When supplied, a second invocation with the **same key** for the **same caller (`sub`)** and **same session (`{code}`)** within a 24-hour window returns the **original response body and status code** without re-running the matching engine.
- Keys are scoped per `(sub, {code})`; reuse across callers or sessions is permitted (no cross-account contamination) but never inverts to a different result.
- Idempotency keys are stored in the `idempotency` DynamoDB table with a 24-hour TTL.

Other write endpoints (`POST /sessions`, `POST /sessions/{code}/register`, `POST /sessions/{code}/admin`, `POST /sessions/{code}/admin/notify`) do **not** accept idempotency keys in v1; clients should retry safely at the transport layer. `POST /sessions/{code}/admin` is **idempotent by design** — re-posting the same payload is a no-op success (RBAC matrix §4.4).

### 1.7 Timestamps

All datetimes are **ISO-8601 strings** with explicit timezone offset (UTC preferred). Example:

```json
"created_at": "2026-06-23T17:09:22Z"
"earliest_pickup": "2026-07-04T08:00:00-04:00"
```

### 1.8 Naming and Field Conventions

- All field names are `snake_case`.
- All enum values are `snake_case` lowercase strings (e.g., `to_destination`, `registration_open`).
- IDs are opaque strings (ULIDs preferred); never expose internal DynamoDB keys to clients.
- `null` is used only when the field is genuinely nullable; optional-but-absent fields are omitted.

---

## 2. Error Taxonomy

Every error response — regardless of endpoint — uses the same JSON envelope:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable, safe to display to end users.",
    "details": { /* optional, structured */ }
  }
}
```

- `code` is a stable, machine-readable identifier (one of the constants in §2.1).
- `message` is a short, sanitized human description. **No PII, no internal stack traces, no secrets.**
- `details` is optional. When present it carries structured, non-sensitive information (e.g., a list of field-level validation errors).

### 2.1 Error Codes

| Code | HTTP Status | When Returned |
| --- | --- | --- |
| `UNAUTHORIZED` | `401` | No `Authorization` header, malformed bearer token, JWT signature invalid, JWT expired, or Google OIDC verification failed on `/auth/google`. |
| `FORBIDDEN` | `403` | Authenticated but the caller's effective role lacks the required permission (RBAC denial). See `docs/rbac_matrix.md` §3. |
| `NOT_FOUND` | `404` | The addressed resource does not exist **and** the caller is permitted to know it does (e.g., a session they admin, a registration they own). Used for generic misses where the existence of the resource is not security-sensitive. |
| `SESSION_CODE_NOT_FOUND` | `404` | The `{code}` in the path does not match any session. Distinct from generic `NOT_FOUND` so clients can render a "session code invalid" UX. |
| `TARGET_USER_UNKNOWN` | `404` | `POST /sessions/{code}/admin` was called with a `user.sub` that has never authenticated against the platform. |
| `VALIDATION_ERROR` | `422` | Request body fails schema or rule validation. `details` carries per-field error messages (`{"fields": [{"path": "email", "issue": "must be a valid email"}]}`). |
| `REGISTRATION_CLOSED` | `409` | `POST /sessions/{code}/register` attempted when the session's `status` is not `registration_open`. |
| `SESSION_NOT_OPEN` | `409` | `POST /sessions/{code}/match/run` or `…/match/approve` attempted when the session is in a state that disallows the action (e.g., still `Draft`). |
| `SESSION_ALREADY_EXISTS` | `409` | `POST /sessions` rejected because the generated `session_code` collides with an existing session. |
| `ALREADY_REGISTERED` | `409` | `POST /sessions/{code}/register` attempted by a user who already holds an active registration in `{code}`. |
| `MATCH_VERSION_LOCKED` | `409` | `POST /sessions/{code}/match/approve` attempted with a `version` that is already approved, already superseded, or locked. |
| `RATE_LIMITED` | `429` | Per-IP or per-user rate limit exceeded. `Retry-After` header included. |
| `INTERNAL_ERROR` | `500` | Unhandled server error. The `request_id` is included in `details` for support correlation; no stack trace is exposed. |
| `SERVICE_UNAVAILABLE` | `503` | Downstream dependency (DynamoDB, Nominatim, ORS, Microsoft Graph) is unreachable or timing out. Transient; clients should retry with backoff. |

### 2.2 Error Response Examples

**`401 UNAUTHORIZED`** — missing or invalid JWT:

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required.",
    "details": { "reason": "token_expired" }
  }
}
```

**`403 FORBIDDEN`** — RBAC denial:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to perform this action.",
    "details": { "required_role": "session_admin", "session_code": "ABC123" }
  }
}
```

**`404 SESSION_CODE_NOT_FOUND`**:

```json
{
  "error": {
    "code": "SESSION_CODE_NOT_FOUND",
    "message": "No session matches this code.",
    "details": { "session_code": "ZZZZZZ" }
  }
}
```

**`422 VALIDATION_ERROR`**:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields failed validation.",
    "details": {
      "fields": [
        { "path": "email", "issue": "must be a valid email address" },
        { "path": "earliest_departure_time", "issue": "must be after now" }
      ]
    }
  }
}
```

**`429 RATE_LIMITED`** (with `Retry-After: 30`):

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Try again shortly.",
    "details": { "scope": "per_user", "retry_after_seconds": 30 }
  }
}
```

**`500 INTERNAL_ERROR`**:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again.",
    "details": { "request_id": "01J3XQ7Z9F2K7YBW8V0P5N6M4R" }
  }
}
```

---

## 3. Endpoint Definitions

Conventions used in each subsection:

- **Path params** appear in `{curly_braces}` in the URL.
- **Query params** are listed with type, default, and required.
- **Request body** schema is given as JSON with field types and `required` / `optional` markers.
- **Response body** schema is given for the success case; error responses follow §2 universally.
- **Status codes** list the success status plus the applicable error statuses.
- **Required role** is mapped to the RBAC matrix (`docs/rbac_matrix.md` §5).

### 3.1 `POST /auth/google`

Exchange a Google ID token for an app session JWT.

| Aspect | Value |
| --- | --- |
| **Description** | Verifies the supplied Google ID token, upserts a `USER#<sub>` record, issues a short-lived (1h) signed JWT for subsequent requests. |
| **Auth** | **Unauthenticated.** This endpoint **issues** the credential. Rate-limit + audit apply. |
| **Required role** | None. |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | None. |
| **Request body** | `{ "id_token": string (Google ID token, required) }` |
| **Success response** | `200 OK` — `{ "access_token": string, "token_type": "Bearer", "expires_in": int (seconds, default 3600), "user": { "sub": string, "email": string, "name": string, "global_role": "superuser"\|"manager"\|"none" } }` |
| **Status codes** | `200` success; `400` malformed body; `401 UNAUTHORIZED` (invalid Google token); `422 VALIDATION_ERROR` (missing `id_token`); `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE` (JWKS / Google unreachable). |

### 3.2 `POST /sessions`

Create a new carpool session.

| Aspect | Value |
| --- | --- |
| **Description** | Creates a session with the supplied configuration. The server generates `session_code` and returns it. |
| **Auth** | Required. |
| **Required role** | **Superuser or Manager** (RBAC P-01). |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | None. |
| **Request body** | `SessionCreate` (see §5). Fields: `title` (string, 1–120 chars, required), `description` (string, 0–2000 chars, optional), `trip_mode` (`"to_destination"` \| `"from_origin"`, required), `anchor_postal_code` (string, required — geocoded server-side per FR-5), `earliest_pickup` (ISO-8601 datetime, required), `latest_arrival` (ISO-8601 datetime, required, must be ≥ `earliest_pickup`), `registration_deadline` (ISO-8601 datetime, required, must be ≤ `earliest_pickup`). Optional: `capacity_hint` (integer, ≥1, optional — suggested default seat count; no upper cap per OQ-11). |
| **Success response** | `201 Created` — `SessionResponse` (see §5). `Location` header contains the canonical session URL. |
| **Status codes** | `201` created; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `409 SESSION_ALREADY_EXISTS` (server-generated code collision — extraordinarily rare); `422 VALIDATION_ERROR`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE` (geocoding dependency). |

### 3.3 `GET /sessions/{code}`

Retrieve session details. Visibility is filtered by the caller's effective role (RBAC P-02).

| Aspect | Value |
| --- | --- |
| **Description** | Returns the full `SessionResponse` for callers with read access. For Drivers and Passengers, sensitive admin fields are stripped. |
| **Auth** | Required. |
| **Required role** | Any authenticated user; response is scope-filtered (RBAC E-04). |
| **Request headers** | None required. |
| **Path / Query params** | `{code}` — session code (string, required). |
| **Request body** | None. |
| **Success response** | `200 OK` — `SessionResponse` (see §5). |
| **Status codes** | `200`; `401 UNAUTHORIZED`; `403 FORBIDDEN` (caller authenticated but has no role in this session); `404 SESSION_CODE_NOT_FOUND`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

### 3.4 `PATCH /sessions/{code}`

Update session configuration.

| Aspect | Value |
| --- | --- |
| **Description** | Partial update of session fields. Used both for content edits (title, description) and status transitions (Draft → Registration Open → Matching Pending → Matching Proposed → Approved → Closed). |
| **Auth** | Required. |
| **Required role** | **Superuser, Manager, or Session Admin of `{code}`** (RBAC P-04). |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `SessionUpdate` (see §5). All fields optional (partial update). Same field set as `SessionCreate` plus `status` (enum). Allowed status transitions are enforced server-side per the state machine in §3 of `docs/requirements_baseline.md`. |
| **Success response** | `200 OK` — updated `SessionResponse`. |
| **Status codes** | `200`; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `409 SESSION_NOT_OPEN` (illegal status transition); `422 VALIDATION_ERROR`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE`. |

### 3.5 `DELETE /sessions/{code}`

Delete a session and all of its dependent records (registrations, matches, admin assignments).

| Aspect | Value |
| --- | --- |
| **Description** | Hard delete. Cascades to all registrations and matches under the session. Audit-logged but the audit record itself is retained. |
| **Auth** | Required. |
| **Required role** | **Superuser** only (RBAC P-05). |
| **Request headers** | None required. |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | None. |
| **Success response** | `204 No Content`. |
| **Status codes** | `204`; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

### 3.6 `POST /sessions/{code}/register`

Register as a driver or passenger for the session.

| Aspect | Value |
| --- | --- |
| **Description** | Creates a registration record keyed by `SESSION#{code}` and `REG#<user_sub>`. The server geocodes `postal_code` via Nominatim (FR-5). |
| **Auth** | Required. |
| **Required role** | Any authenticated user (RBAC P-07 / P-08); session status must be `registration_open`. |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `RegistrationCreate` (see §5; canonical schema per `docs/requirements_baseline.md` §3). Fields: `role` (`"driver"` \| `"passenger"`, required), `name` (string, 1–120, required), `email` (string, RFC 5322, required — must match the authenticated user's Google email), `postal_code` (string, required), `earliest_departure_time` (ISO-8601, required), `latest_departure_time` (ISO-8601, required, ≥ `earliest_departure_time`), and **role-specific fields**: for `driver`, `seat_capacity` (int ≥1, no upper cap per OQ-11), `earliest_pickup_time` (ISO-8601), `latest_pickup_time` (ISO-8601); for `passenger`, `accessibility_requirements` (string ≤500 chars, optional), `special_notes` (string ≤500 chars, optional). |
| **Success response** | `201 Created` — `RegistrationResponse`. |
| **Status codes** | `201`; `400` malformed body; `401 UNAUTHORIZED`; `409 ALREADY_REGISTERED`; `409 REGISTRATION_CLOSED`; `422 VALIDATION_ERROR` (incl. geocoding failure per §3.5 of requirements baseline); `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE`. |

### 3.7 `GET /sessions/{code}/me`

Retrieve the caller's own registration in the session.

| Aspect | Value |
| --- | --- |
| **Description** | Returns the registration record owned by the authenticated `sub`. Returns `404` (not `403`) when the caller is authenticated but not registered, to avoid leaking session-roster membership. |
| **Auth** | Required. |
| **Required role** | Any authenticated user (RBAC P-09). |
| **Request headers** | None required. |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | None. |
| **Success response** | `200 OK` — `RegistrationResponse`. |
| **Status codes** | `200`; `401 UNAUTHORIZED`; `404 NOT_FOUND` (caller not registered in `{code}`); `404 SESSION_CODE_NOT_FOUND`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

### 3.8 `PATCH /sessions/{code}/me`

Update the caller's own registration.

| Aspect | Value |
| --- | --- |
| **Description** | Partial update of the registration owned by the authenticated `sub`. Editing is restricted to driver- or passenger-specific fields plus the common fields that are mutable after creation (e.g., `latest_departure_time`, `accessibility_requirements`). Changing `role` is **not** permitted — callers must delete and re-register. |
| **Auth** | Required. |
| **Required role** | Any authenticated user (RBAC P-10). |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `RegistrationUpdate` (see §5) — partial subset of `RegistrationCreate`, minus `role`. |
| **Success response** | `200 OK` — updated `RegistrationResponse`. |
| **Status codes** | `200`; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN` (registration locked because the session has an approved match); `404 NOT_FOUND` (caller not registered); `404 SESSION_CODE_NOT_FOUND`; `409 REGISTRATION_CLOSED` (session no longer accepts edits); `422 VALIDATION_ERROR`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

> **Companion endpoint:** `DELETE /sessions/{code}/me` (RBAC P-11) withdraws the registration. Not explicitly listed in §9 of the master spec; included for completeness. Same RBAC as PATCH. Returns `204`.

### 3.9 `POST /sessions/{code}/match/run`

Run the matching engine and produce a new proposed match version.

| Aspect | Value |
| --- | --- |
| **Description** | Triggers a new CVRPTW solve (FR-6). Each call writes `MATCH#V{n+1}` to DynamoDB. For sessions < 300 users, runs synchronously in the API Lambda; for ≥ 300 users the call returns `202 Accepted` with a job reference and the solve runs async (Phase 4 detail). |
| **Auth** | Required. |
| **Required role** | **Superuser, Manager, or Session Admin of `{code}`** (RBAC P-14 / P-19). |
| **Request headers** | `Content-Type: application/json` (optional); `Idempotency-Key` (optional, see §1.6). |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | None (or empty `{}`). |
| **Success response** | `200 OK` (sync, < 300 users) — `MatchRunResponse` (see §5) summarizing the proposed version (`version`, `objective_score`, `assigned_count`, `unassigned_count`, `compute_time_ms`, `created_at`). `202 Accepted` (async, ≥ 300 users) — `{ "job_id": string, "status": "queued", "estimated_seconds": int }`. |
| **Status codes** | `200` / `202`; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `409 SESSION_NOT_OPEN`; `422 VALIDATION_ERROR` (no registrations); `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE`. |

### 3.10 `GET /sessions/{code}/match`

Retrieve the latest match for the session. Visibility is role-filtered.

| Aspect | Value |
| --- | --- |
| **Description** | For admins, returns the **latest proposed** match (pre-approval). For Drivers and Passengers, returns the **approved** match, filtered to the caller's assignment only (FR-9 visibility). |
| **Auth** | Required. |
| **Required role** | **Superuser, Manager, or Session Admin of `{code}`** for the proposed match (RBAC P-15); **any authenticated user with a registration** for the approved match filtered view. |
| **Request headers** | None required. |
| **Path / Query params** | `{code}` — session code (required). Query: `version` (integer, optional — when omitted, returns the latest version; when omitted and caller is Driver/Passenger, returns the approved version). |
| **Request body** | None. |
| **Success response** | `200 OK` — `MatchResult` (see §5). The response is filtered: admins see all `MatchAssignment`s; drivers see only their own; passengers see only their own `driver_sub` and pickup order. |
| **Status codes** | `200`; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `404 NOT_FOUND` (no proposed/approved match exists yet); `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

### 3.11 `POST /sessions/{code}/match/approve`

Approve a specific match version.

| Aspect | Value |
| --- | --- |
| **Description** | Marks the supplied `version` as the approved version of the session's match and **queues** the publish-to-users email fan-out (FR-10). One or more `notification_pending` items are written to DynamoDB; a separate processor (SQS → Lambda or admin-triggered) sends emails via Microsoft Graph `sendMail`. Only one version per session may be approved. See ADR-0008. |
| **Auth** | Required. |
| **Required role** | **Superuser, Manager, or Session Admin of `{code}`** (RBAC P-17). |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `MatchApproveRequest` (see §5) — `{ "version": int (required, ≥ 1), "publish": bool (default true — if true, the approved match is immediately visible to assigned participants and FR-10 "match approved" emails are queued for deferred delivery per ADR-0008) }`. |
| **Success response** | `200 OK` — approved `MatchResult`. `details.publish: bool` and `details.notifications_queued: int` (count of `notification_pending` items written for deferred delivery per ADR-0008 / OQ-6). The API never blocks on email delivery. |
| **Status codes** | `200`; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `409 MATCH_VERSION_LOCKED` (already approved, superseded, or invalid `version`); `422 VALIDATION_ERROR`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE`. |

### 3.12 `PATCH /sessions/{code}/match/manual`

Manual override of the approved or proposed match (FR-8). Discriminated union on `operation`.

| Aspect | Value |
| --- | --- |
| **Description** | Admin moves a passenger to another driver, unassigns a passenger, marks them unmatched, or locks an assignment. Allowed both before and after approval; post-approval overrides trigger a `match.changed` notification. |
| **Auth** | Required. |
| **Required role** | **Superuser, Manager, or Session Admin of `{code}`** (RBAC P-20, P-21, P-22, P-23). |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `ManualOverrideRequest` (see §5) — discriminated union with `Literal[...]` discriminator on `operation`. Three operation variants: `{ "operation": "move_passenger", "passenger_sub": string, "to_driver_sub": string, "reason": string \| null }`; `{ "operation": "unassign", "passenger_sub": string, "reason": string \| null }`; `{ "operation": "lock", "driver_sub": string, "lock": bool, "reason": string \| null }`. The `reason` field is optional free-text written to the FR-11 audit log. |
| **Success response** | `200 OK` — updated `MatchResult`. |
| **Status codes** | `200`; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `409 MATCH_VERSION_LOCKED` (the target assignment is locked by an earlier override); `422 VALIDATION_ERROR` (hard-constraint violation, e.g., target driver's seat capacity exceeded); `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE`. |

### 3.13 `POST /sessions/{code}/admin/notify`

Send an ad-hoc notification to participants.

| Aspect | Value |
| --- | --- |
| **Description** | Admin-initiated notification. Queues the FR-10 fan-out by writing `notification_pending` items to DynamoDB; a separate processor (SQS → Lambda or admin-triggered batch with `action: "send"`) sends emails via Microsoft Graph `sendMail`. The API response does not block on email delivery. See ADR-0008. |
| **Auth** | Required. |
| **Required role** | **Superuser, Manager, or Session Admin of `{code}`** (RBAC A-01). |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `{ "event": string (one of `"registration_open"`, `"registration_closing_reminder"`, `"session_cancelled"`, `"custom"`; required), "subject": string (required when `event = "custom"`), "body": string (required when `event = "custom"`), "recipient_filter": object \| null (optional — restricts the fan-out; null/omitted means all registrants). `recipient_filter` shape: `{ "roles": ["driver"\|"passenger"] \| null, "assigned_only": bool \| null, "registration_status": ["active"\|"withdrawn"] | null }`. |
| **Success response** | `200 OK` — `{ "notification_id": string, "event": string, "recipient_count": int, "queued_count": int, "failed_count": int, "notifications_pending": bool }`. `queued_count` reflects the number of `notification_pending` items written to DynamoDB; `failed_count` reflects items that could not be queued (rare; SQS / DynamoDB write failure). |
| **Status codes** | `200`; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `422 VALIDATION_ERROR`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`; `503 SERVICE_UNAVAILABLE` (Microsoft Graph unreachable). |

### 3.14 `GET /audit`

Query audit logs (FR-11).

| Aspect | Value |
| --- | --- |
| **Description** | Paginated read of audit log items. Filters: date range, event type, session code. |
| **Auth** | Required. |
| **Required role** | **Superuser or Manager** (RBAC A-02). |
| **Request headers** | None required. |
| **Path / Query params** | `{code}` — not used. Query: `from` (ISO-8601 datetime, optional), `to` (ISO-8601 datetime, optional, ≥ `from`), `event_type` (string, optional — one of `auth.login.success`, `auth.login.failure`, `session.created`, `session.updated`, `session.deleted`, `registration.created`, `registration.updated`, `match.run.started`, `match.run.completed`, `match.approved`, `match.override`, `notification.sent`, `notification.failed`, `session_admin.assign`), `session_code` (string, optional), `cursor` (opaque, optional), `limit` (int, default 50, max 100). |
| **Request body** | None. |
| **Success response** | `200 OK` — `PaginatedResponse[AuditEvent]`. `AuditEvent` shape: `{ "event_id": string, "timestamp": ISO-8601, "actor_sub": string | null, "actor_role": string | null, "session_code": string | null, "event": string, "payload_summary": object (no PII), "request_id": string, "source_ip": string }`. |
| **Status codes** | `200`; `400` malformed query; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `422 VALIDATION_ERROR` (invalid filter); `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

### 3.15 `POST /sessions/{code}/admin` **(new endpoint)**

Assign a user as Session Admin for the session. Defined in `docs/rbac_matrix.md` §4 and `plans/phase-1-discovery.md` Task 2.

| Aspect | Value |
| --- | --- |
| **Description** | Grants the target user the **Session Admin** role for the specified session. Idempotent — re-posting the same payload is a no-op success. |
| **Auth** | Required. |
| **Required role** | **Superuser or Manager** (global role; RBAC P-06). Session Admins cannot self-promote or promote others. |
| **Request headers** | `Content-Type: application/json` |
| **Path / Query params** | `{code}` — session code (required). |
| **Request body** | `{ "user": { "sub": string (Google subject; required), "email": string (RFC 5322; required — recorded for audit) } }`. Exactly one of `user.sub` or `user.email` is required as a key — `sub` is preferred; `email` may be supplied for convenience but the server resolves the canonical `sub` before writing. |
| **Success response** | `200 OK` — `{ "session_code": string, "user_sub": string, "email": string, "role": "session_admin", "assigned_by_sub": string, "assigned_at": ISO-8601, "already_assigned": bool }`. `201 Created` when the assignment is new; `200 OK` when `already_assigned: true`. |
| **Status codes** | `200` / `201`; `400` malformed body; `401 UNAUTHORIZED`; `403 FORBIDDEN`; `404 SESSION_CODE_NOT_FOUND`; `404 TARGET_USER_UNKNOWN` (no `USER#<sub>` record exists); `422 VALIDATION_ERROR`; `429 RATE_LIMITED`; `500 INTERNAL_ERROR`. |

---

## 4. Pydantic Model Stubs

These are **type stubs only** — type annotations with no business logic. They define the contract for Phase 2 implementation. Imports are listed once for the whole block.

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, EmailStr, Field


# ---------- Enums ----------

class TripMode(str, Enum):
    TO_DESTINATION = "to_destination"
    FROM_ORIGIN = "from_origin"


class SessionStatus(str, Enum):
    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    MATCHING_PENDING = "matching_pending"
    MATCHING_PROPOSED = "matching_proposed"
    APPROVED = "approved"
    CLOSED = "closed"


class GlobalRole(str, Enum):
    SUPERUSER = "superuser"
    MANAGER = "manager"
    NONE = "none"


class RegistrationRole(str, Enum):
    DRIVER = "driver"
    PASSENGER = "passenger"


class RegistrationStatus(str, Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class OverrideOperation(str, Enum):
    MOVE_PASSENGER = "move_passenger"
    UNASSIGN_PASSENGER = "unassign_passenger"
    MARK_UNMATCHED = "mark_unmatched"
    LOCK_ASSIGNMENT = "lock_assignment"


class NotificationEvent(str, Enum):
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSING_REMINDER = "registration_closing_reminder"
    SESSION_CANCELLED = "session_cancelled"
    CUSTOM = "custom"


# ---------- Common / Shared ----------

class AnchorLocation(BaseModel):
    lat: float
    lon: float
    source: Literal["nominatim"]
    cached_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------- Auth ----------

class GoogleAuthRequest(BaseModel):
    id_token: str


class UserInfo(BaseModel):
    sub: str
    email: EmailStr
    name: str
    global_role: GlobalRole


class GoogleAuthResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    user: UserInfo


# ---------- Sessions ----------

class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    trip_mode: TripMode
    anchor_postal_code: str = Field(min_length=1, max_length=20)
    earliest_pickup: datetime
    latest_arrival: datetime
    registration_deadline: datetime
    capacity_hint: int | None = Field(default=None, ge=1)


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    trip_mode: TripMode | None = None
    anchor_postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    earliest_pickup: datetime | None = None
    latest_arrival: datetime | None = None
    registration_deadline: datetime | None = None
    capacity_hint: int | None = Field(default=None, ge=1)
    status: SessionStatus | None = None


class SessionResponse(BaseModel):
    session_code: str
    title: str
    description: str | None
    trip_mode: TripMode
    anchor_location: AnchorLocation
    earliest_pickup: datetime
    latest_arrival: datetime
    registration_deadline: datetime
    status: SessionStatus
    created_by_sub: str
    created_at: datetime
    updated_at: datetime
    capacity_hint: int | None = None


# ---------- Registrations ----------

class RegistrationDriverFields(BaseModel):
    seat_capacity: int = Field(ge=1)
    earliest_pickup_time: datetime
    latest_pickup_time: datetime


class RegistrationPassengerFields(BaseModel):
    accessibility_requirements: str | None = Field(default=None, max_length=500)
    special_notes: str | None = Field(default=None, max_length=500)


class RegistrationCreate(BaseModel):
    """Canonical registration create body. Discriminator: ``role``."""

    role: RegistrationRole
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    postal_code: str = Field(min_length=1, max_length=20)
    earliest_departure_time: datetime
    latest_departure_time: datetime

    # Driver-only (required when role == driver)
    seat_capacity: int | None = Field(default=None, ge=1)
    earliest_pickup_time: datetime | None = None
    latest_pickup_time: datetime | None = None

    # Passenger-only (optional when role == passenger)
    accessibility_requirements: str | None = Field(default=None, max_length=500)
    special_notes: str | None = Field(default=None, max_length=500)


class RegistrationUpdate(BaseModel):
    """Partial registration update. ``role`` is intentionally not updatable."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    earliest_departure_time: datetime | None = None
    latest_departure_time: datetime | None = None
    seat_capacity: int | None = Field(default=None, ge=1)
    earliest_pickup_time: datetime | None = None
    latest_pickup_time: datetime | None = None
    accessibility_requirements: str | None = Field(default=None, max_length=500)
    special_notes: str | None = Field(default=None, max_length=500)


class RegistrationResponse(BaseModel):
    registration_id: str
    session_code: str
    user_sub: str
    role: RegistrationRole
    name: str
    email: EmailStr
    postal_code: str
    geocoded_location: AnchorLocation
    earliest_departure_time: datetime
    latest_departure_time: datetime
    status: RegistrationStatus
    created_at: datetime
    updated_at: datetime
    # Driver-only
    seat_capacity: int | None = None
    earliest_pickup_time: datetime | None = None
    latest_pickup_time: datetime | None = None
    # Passenger-only
    accessibility_requirements: str | None = None
    special_notes: str | None = None


# ---------- Matching ----------

class MatchAssignment(BaseModel):
    driver_sub: str
    passenger_subs: list[str]
    pickup_order: list[str]
    locked: bool = False


class MatchResult(BaseModel):
    session_code: str
    version: int
    status: Literal["proposed", "approved"]
    assignments: list[MatchAssignment]
    unassigned: list[str]
    objective_score: float
    compute_time_ms: int
    created_at: datetime
    approved_at: datetime | None = None
    approved_by_sub: str | None = None
    notifications_pending: bool = False


class MatchRunResponse(BaseModel):
    session_code: str
    version: int
    objective_score: float
    assigned_count: int
    unassigned_count: int
    compute_time_ms: int
    created_at: datetime


class MatchRunQueuedResponse(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"
    estimated_seconds: int


class MatchApproveRequest(BaseModel):
    version: int = Field(ge=1)
    publish: bool = True


class MovePassengerOp(BaseModel):
    """`PATCH /sessions/{code}/match/manual` — move a passenger to another driver."""

    operation: Literal["move_passenger"]
    passenger_sub: str
    to_driver_sub: str
    reason: str | None = None


class UnassignOp(BaseModel):
    """`PATCH /sessions/{code}/match/manual` — unassign a passenger from their driver."""

    operation: Literal["unassign"]
    passenger_sub: str
    reason: str | None = None


class LockAssignmentOp(BaseModel):
    """`PATCH /sessions/{code}/match/manual` — lock or unlock a driver's assignment.

    ``lock=True`` prevents subsequent re-runs / overrides from overwriting the driver's
    roster; ``lock=False`` clears an existing lock. Each call writes a ``match.lock`` or
    ``match.unlock`` audit event (FR-11).
    """

    operation: Literal["lock"]
    driver_sub: str
    lock: bool  # True to lock, False to unlock
    reason: str | None = None


ManualOverrideRequest = MovePassengerOp | UnassignOp | LockAssignmentOp

# Note: each operation's ``reason`` field is free-text and is written to the FR-11
# audit log (event_type ``match.override`` / ``match.lock`` / ``match.unlock``) so
# admins can audit why a manual change was made after the fact. ``reason`` is
# optional and may be null when the change is purely operational.


# ---------- Notifications ----------

class RecipientFilter(BaseModel):
    roles: list[RegistrationRole] | None = None
    assigned_only: bool | None = None
    registration_status: list[RegistrationStatus] | None = None


class NotifyRequest(BaseModel):
    event: NotificationEvent
    subject: str | None = None
    body: str | None = None
    recipient_filter: RecipientFilter | None = None


class NotifyResponse(BaseModel):
    notification_id: str
    event: NotificationEvent
    recipient_count: int
    queued_count: int
    failed_count: int
    notifications_pending: bool


# ---------- Admin assignment ----------

class AdminAssignUser(BaseModel):
    sub: str | None = None
    email: EmailStr | None = None


class AdminAssignRequest(BaseModel):
    user: AdminAssignUser


class AdminAssignResponse(BaseModel):
    session_code: str
    user_sub: str
    email: EmailStr
    role: Literal["session_admin"] = "session_admin"
    assigned_by_sub: str
    assigned_at: datetime
    already_assigned: bool = False


# ---------- Audit ----------

class AuditEvent(BaseModel):
    event_id: str
    timestamp: datetime
    actor_sub: str | None
    actor_role: str | None
    session_code: str | None
    event: str
    payload_summary: dict
    request_id: str
    source_ip: str


# ---------- Pagination envelope ----------

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
    limit: int
```

> **Implementation notes for Phase 2:**
> - Use `from __future__ import annotations` and `pydantic` v2 (`BaseModel` with `model_config = ConfigDict(from_attributes=True)`).
> - `EmailStr` requires the `pydantic[email]` extra; use `str` with a regex if extra deps are unacceptable.
> - `paginated_response(...)` factory helper to be implemented in `app/api/pagination.py`.
> - All datetime fields use `datetime` with timezone-aware values at runtime; Pydantic serializes to ISO-8601.
> - Discriminated unions (`RegistrationCreate`, `ManualOverrideRequest`) should use `Literal[...]` discriminators with a `@field_validator` to enforce role/operation-specific required-field rules (e.g., `seat_capacity` required when `role == driver`).

---

## 5. Role Requirements Summary

Endpoint-to-role mapping, derived from `docs/rbac_matrix.md` §5 and the endpoint definitions in §3. "Scope-filtered" means the response is filtered by the caller's effective role per FR-9.

| # | Method | Endpoint | Required Role | RBAC Ref | Visibility Scope |
| --- | --- | --- | --- | --- | --- |
| 1 | `POST` | `/auth/google` | **Unauthenticated** (issues JWT) | E-01 | n/a |
| 2 | `POST` | `/sessions` | Superuser or Manager | P-01 | n/a |
| 3 | `GET` | `/sessions/{code}` | Any authenticated user (scope-filtered) | P-02 | Scope-filtered |
| 4 | `PATCH` | `/sessions/{code}` | Superuser, Manager, or Session Admin of `{code}` | P-04 | n/a |
| 5 | `DELETE` | `/sessions/{code}` | **Superuser** | P-05 | n/a |
| 6 | `POST` | `/sessions/{code}/register` | Any authenticated user (registration must be open) | P-07 / P-08 | Self only |
| 7 | `GET` | `/sessions/{code}/me` | Any authenticated user | P-09 | Self only |
| 8 | `PATCH` | `/sessions/{code}/me` | Any authenticated user | P-10 | Self only |
| 9 | `DELETE` | `/sessions/{code}/me` | Any authenticated user | P-11 | Self only |
| 10 | `POST` | `/sessions/{code}/match/run` | Superuser, Manager, or Session Admin of `{code}` | P-14 / P-19 | n/a |
| 11 | `GET` | `/sessions/{code}/match` | Superuser, Manager, Session Admin of `{code}` (proposed) / Any authenticated registrant (approved) | P-15 + FR-9 | Role-filtered |
| 12 | `POST` | `/sessions/{code}/match/approve` | Superuser, Manager, or Session Admin of `{code}` | P-17 | n/a |
| 13 | `PATCH` | `/sessions/{code}/match/manual` | Superuser, Manager, or Session Admin of `{code}` | P-20..P-23 | n/a |
| 14 | `POST` | `/sessions/{code}/admin/notify` | Superuser, Manager, or Session Admin of `{code}` | A-01 | n/a |
| 15 | `POST` | `/sessions/{code}/admin` | **Superuser or Manager** | P-06 | n/a |
| 16 | `GET` | `/audit` | Superuser or Manager | A-02 | Global |

### 5.1 Companion Endpoints Documented But Not in §9

The following endpoints are **required by the RBAC matrix** but are not explicitly listed in §9 of the master spec. They are documented here for completeness and must be ratified by an ADR before Phase 2 implementation:

| Method | Endpoint | Required Role | RBAC Ref | Notes |
| --- | --- | --- | --- | --- |
| `GET` | `/sessions` | Any authenticated user (scope-filtered) | P-03 | List view; scope-filtered. |
| `DELETE` | `/sessions/{code}/me` | Any authenticated user | P-11 | Withdraw own registration. |
| `POST` | `/sessions/{code}/registration/open` | Superuser, Manager, or Session Admin of `{code}` | P-12 | Status transition `Draft` → `Registration Open`. |
| `POST` | `/sessions/{code}/registration/close` | Superuser, Manager, or Session Admin of `{code}` | P-13 | Status transition `Registration Open` → `Matching Pending`. |
| `GET` | `/sessions/{code}/assignment` | Any authenticated user (scope-filtered) | V-06 / V-07 / V-08 | "My assignment" view (driver sees roster, passenger sees driver). |
| `GET` | `/sessions/{code}/registrations` | Superuser, Manager, or Session Admin of `{code}` | V-02 / V-03 / V-05 | Admin roster view. |
| `GET` | `/health` | Unauthenticated | n/a | Operational probe. Rate-limit + audit apply. |

> **Action item:** raise an ADR proposing the addition of the endpoints above to §9 of the master spec, or document the rationale for folding them into `PATCH /sessions/{code}` (status field).

---

## 6. Open Questions

These open questions affect this contract and must be resolved before Phase 2 (Foundation) completes:

| ID | Question | Affects |
| --- | --- | --- |
| AC-OQ-1 | Confirm the list of error codes — is `TARGET_USER_UNKNOWN` (404) a desired distinct code, or fold into `NOT_FOUND`? | §2.1, §3.15 |
| AC-OQ-2 | Confirm cursor-pagination envelope field names (`items`, `next_cursor`, `limit`) and that no client-side `total`/`has_more` will be exposed. | §1.5, §4 |
| AC-OQ-3 | Confirm the async boundary for `POST /sessions/{code}/match/run` at ≥ 300 users (`202 Accepted` + job reference). | §3.9 |
| AC-OQ-4 | Confirm idempotency scope is `(sub, {code})` and TTL is 24h. | §1.6 |
| AC-OQ-5 | Confirm rate-limit headers are mandatory on **every** response (including 4xx / 5xx). | §1.4 |
| AC-OQ-6 | Confirm the canonical companion endpoints in §5.1 (list, registration open/close, my assignment, registrations, health) should be ratified via ADR and added to §9. | §5.1 |
| AC-OQ-7 | Confirm the `email` field in `RegistrationCreate` must match the authenticated Google email exactly, not merely the domain. | §3.6 |
| AC-OQ-8 | Confirm `DELETE /sessions/{code}/admin/{sub}` (revocation, RBAC matrix §4.7) is out of scope for v1 of this contract. | §4.7 |

---

## 7. Versioning and Change Control

- This contract is **versioned semver**: breaking changes (new required field, removed field, semantic change to an existing field, new error code with new HTTP status) increment the major version; additive changes (new optional field, new endpoint, new error code consistent with existing HTTP status) increment the minor version.
- The `/auth/google` and `/sessions/{code}/admin` endpoints are versioned within the contract but never receive URL-level versioning (`/v1/...`); the frontend reads `expires_in` from `GoogleAuthResponse` and refreshes.
- Any change to this document **requires** an ADR for material changes and a PR review by the Tech Lead + a Backend Engineer.

---

## Appendix A — Endpoint Index (master list)

For convenience, every endpoint defined in this contract:

| # | Method | Path | Defined in |
| --- | --- | --- | --- |
| 1 | `POST` | `/auth/google` | §3.1 |
| 2 | `POST` | `/sessions` | §3.2 |
| 3 | `GET` | `/sessions/{code}` | §3.3 |
| 4 | `PATCH` | `/sessions/{code}` | §3.4 |
| 5 | `DELETE` | `/sessions/{code}` | §3.5 |
| 6 | `POST` | `/sessions/{code}/register` | §3.6 |
| 7 | `GET` | `/sessions/{code}/me` | §3.7 |
| 8 | `PATCH` | `/sessions/{code}/me` | §3.8 |
| 9 | `POST` | `/sessions/{code}/match/run` | §3.9 |
| 10 | `GET` | `/sessions/{code}/match` | §3.10 |
| 11 | `POST` | `/sessions/{code}/match/approve` | §3.11 |
| 12 | `PATCH` | `/sessions/{code}/match/manual` | §3.12 |
| 13 | `POST` | `/sessions/{code}/admin/notify` | §3.13 |
| 14 | `GET` | `/audit` | §3.14 |
| 15 | `POST` | `/sessions/{code}/admin` | §3.15 |

**Total endpoints defined: 15** (matches the required scope of Phase 1 Discovery Task 5).