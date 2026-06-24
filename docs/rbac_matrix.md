# RBAC Permission Matrix

**Version:** 1.0
**Date:** 2026-06-23
**Author:** Solution Architect
**Status:** Draft
**Related artifacts:**
- Master spec: `docs/functional_requirements_and_architecture.md` (§3 Stakeholders, §4 Authorization Model, FR-1, FR-7, FR-8, FR-9, §9 REST API)
- Auth/session design: `docs/adr/0002-app-session-jwt.md`
- Middleware ordering (where RBAC is enforced): `docs/adr/0005-middleware-ordering.md`
- Phase plan: `plans/phase-1-discovery.md` Task 2

---

## 1. Role Inventory

| Role | Scope | Description |
| --- | --- | --- |
| **Superuser** | Global | Platform-wide administrator. Holds every permission across every session. Used for break-glass operations, abuse response, and initial bootstrap. |
| **Manager** | Global | Creates carpool sessions. By the precedence rule (`Manager > Session Admin`) a Manager can act as Session Admin for any session in the platform. Used to bootstrap sessions and provide a second pair of eyes during approval. |
| **Session Admin** | Session-scoped | Manages one specific carpool session end-to-end: configuration, registration window, matching, override, approval, and notification. A user is granted Session Admin per session; the same user may be admin of multiple sessions. |
| **Driver** | Session-scoped | A participant who offers seats. Their driver-role grants are valid only inside sessions where they hold an active Driver registration. The same person may be a Driver in one session and a Passenger in another. |
| **Passenger** | Session-scoped | A participant who requests a ride. Their passenger-role grants are valid only inside sessions where they hold an active Passenger registration. |
| **System** | Non-human | The automated matching engine, notification service, and audit logger. Invoked by async jobs (Lambda, SQS/Step Functions, Fargate for large sessions). Cannot authenticate as a user; uses IAM/service credentials. |

**Scope key:**
- *Global* — permission applies to every session in the platform.
- *Session-scoped* — permission applies only within a specific session (the one identified by `{code}` in the URL or by the user's session-scoped role assignment).
- *Non-human* — invoked by backend services, not by end users.

---

## 2. Permission Resolution Rules

### 2.1 Default-deny
The policy is **DENY ALL**. A permission must be explicitly granted by at least one role held by the authenticated principal. Any request for which the principal has no matching permission is rejected with `403 Forbidden`.

### 2.2 Precedence (from §4.3 of the master spec)
`Superuser > Manager > Session Admin > Driver > Passenger`

A higher-ranked role satisfies any permission check that a lower-ranked role satisfies. Concretely:
- A **Superuser** satisfies every permission check in the matrix (including session-scoped ones), without needing an explicit session-scoped assignment.
- A **Manager** satisfies every Session Admin permission in **any** session (they do not need an explicit `SESSION#<code>#ADMIN` assignment).
- A **Session Admin** satisfies Driver- and Passenger-scoped checks **within their assigned session only**.
- A **Driver** satisfies Passenger-scoped checks **within the session they are registered as a driver** (a Driver is a Participant; they have the rights of a participant in their own session).

### 2.3 Session-scoping rules
1. **Superuser and Manager** are *not* session-scoped; their grants apply platform-wide.
2. **Session Admin** rights are bound to the session listed in their `SESSION#<code>#ADMIN` role assignment. A user who is Session Admin for session `ABC` has **no** Session Admin rights in session `DEF`.
3. **Driver** rights are bound to the session(s) where the user holds an active Driver registration (`SESSION#<code>#REG#<sub>` with role=driver). The same `sub` can simultaneously be a Driver in `ABC` and a Passenger in `DEF`.
4. **Passenger** rights are bound to the session(s) where the user holds an active Passenger registration.
5. A user with **no matching scope** for a given session receives `403` for any session-scoped request, even if they hold the role in a different session.

### 2.4 Multi-role users
A user may hold several roles simultaneously across the system. The effective permission set is the **union** of permissions granted by each role they hold, intersected with the scope of each role. Example:

- A user who is Session Admin of session `ABC` **and** Driver in session `DEF` can:
  - Configure `ABC`, approve matches in `ABC`, notify participants in `ABC` (via Session Admin role, scoped to `ABC`).
  - View their own driver route in `DEF`, edit their own registration in `DEF`, see assigned passengers in `DEF` (via Driver role, scoped to `DEF`).
  - **Cannot** configure `DEF` (no Session Admin role there).

When two roles **conflict** for the same resource (rare; e.g., Superuser overriding a Session Admin's edit), the higher-precedence role wins (see §2.2).

### 2.5 Unauthenticated callers
Endpoints that require authentication reject unauthenticated callers with `401 Unauthorized` (see §6). RBAC is enforced **after** authentication (ADR-0005).

---

## 3. Permission Matrix

**Legend:**
- ✓ — permission granted unconditionally within the role's scope
- ◐ — permission granted **session-scoped** (see footnote ‡)
- ✗ — permission denied
- n/a — not applicable (System is not a human role and does not hold user-facing permissions)

**Footnotes:**
- ‡ For **Driver**, **Passenger**, and **Session Admin**, ◐ means: granted **only** within the session(s) where the principal holds the corresponding role assignment. Outside that scope, the permission is denied.
- For **Manager**, ◐ on session-scoped rows means: granted in **any** session (Manager is global, not bound to a specific `SESSION#<code>#ADMIN` record).
- **Superuser** is global and grants apply to every session without an explicit assignment.

### 3.1 Session management

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-01 | Create session | ✓ | ✓ | ✗ | ✗ | ✗ | n/a |
| P-02 | View session detail | ✓ | ✓ | ◐ ‡ | ◐ ‡ | ◐ ‡ | n/a |
| P-03 | List all sessions | ✓ | ✓ | ◐ ‡ (only sessions they admin) | ◐ ‡ (only sessions where registered) | ◐ ‡ (only sessions where registered) | n/a |
| P-04 | Edit session config (title, dates, anchor, capacity, etc.) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | n/a |
| P-05 | Delete session | ✓ | ✗ | ✗ | ✗ | ✗ | n/a |
| P-06 | Assign Session Admin to a session | ✓ | ✓ | ✗ | ✗ | ✗ | n/a |

### 3.2 Registration

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-07 | Register as Driver (self) | ✓ | ✓ | ✓ | ✓ | ✓ | n/a |
| P-08 | Register as Passenger (self) | ✓ | ✓ | ✓ | ✓ | ✓ | n/a |
| P-09 | View own registration | ✓ | ✓ | ✓ | ◐ ‡ | ◐ ‡ | n/a |
| P-10 | Edit own registration (incl. seats, route preferences, pickup/dropoff) | ✓ | ✓ | ✓ | ◐ ‡ | ◐ ‡ | n/a |
| P-11 | Withdraw own registration | ✓ | ✓ | ✓ | ◐ ‡ | ◐ ‡ | n/a |

> **Notes:**
> - P-07 / P-08 are only meaningful when the session's registration window is open; RBAC enforces "may register"; session state enforces "may register now". A separate status check is layered on top.
> - "Define seats" and "define route preferences" (spec §4.2.2) are realized via P-10.

### 3.3 Registration window

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-12 | Open registration (`draft` → `registration_open`) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | n/a |
| P-13 | Close registration (`registration_open` → `matching_pending`) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | n/a |

### 3.4 Matching

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-14 | Run matching algorithm (kicks off the optimizer) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| P-15 | View proposed match (pre-approval) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| P-16 | Edit proposed match (move/unassign/lock adjustments, pre-approval) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✗ |
| P-17 | Approve matching (`matching_proposed` → `approved`) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✗ |
| P-18 | Publish assignments to participants (post-approval) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| P-19 | Force rematch (re-run regardless of status) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| P-20 | Manual override — move passenger to another driver | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✗ |
| P-21 | Manual override — unassign passenger | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✗ |
| P-22 | Manual override — mark passenger unmatched | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✗ |
| P-23 | Manual override — lock assignment (prevents auto re-match overwrite) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✗ |

> **Note on P-18:** Manual override after approval triggers a notification (FR-8); the publish action is therefore performed by the same override path AND by the initial approve action.

### 3.5 Visibility (FR-9)

> This block encodes the FR-9 visibility table. "Assigned only" means: a Driver sees a specific Passenger record only when the latest **approved** match (or a post-approval override) places that passenger in their vehicle; a Passenger sees a specific Driver record only when they themselves are assigned to that driver.

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V-01 | View own profile | ✓ | ✓ | ✓ | ◐ ‡ | ◐ ‡ | n/a |
| V-02 | View other passengers in the session (full list / search) | ✓ | ✓ | ◐ ‡ | ◐ ‡ (assigned only) | ✗ | n/a |
| V-03 | View other drivers in the session (full list / search) | ✓ | ✓ | ◐ ‡ | ◐ ‡ (yes — see note) | ◐ ‡ (assigned only) | n/a |
| V-04 | View matching score (objective value, cost-matrix entries) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| V-05 | View full session data (all registrations, all match details, raw itinerary) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| V-06 | View assigned passengers (Driver's roster — names, pickup order, contact) | ✓ | ✓ | ◐ ‡ | ◐ ‡ (only own roster) | ✗ | n/a |
| V-07 | View own approved route (Driver) | ✓ | ✓ | ◐ ‡ | ◐ ‡ | ✗ | n/a |
| V-08 | View assigned driver (Passenger) | ✓ | ✓ | ◐ ‡ | ✗ | ◐ ‡ (only own driver) | n/a |

> **Driver on V-03:** A Driver *can* see the existence of other drivers in the same session (otherwise carpool coordination would be impossible). Spec §FR-9 explicitly grants "Yes" for "Other drivers / Driver" — all drivers in the session are visible to a Driver, but driver-to-driver personal data (phone, address, route) is not exposed unless that driver is the passenger's own driver.

### 3.6 Admin operations

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A-01 | Notify participants (manual ad-hoc message; FR-10) | ✓ | ✓ | ◐ ‡ | ✗ | ✗ | ✓ |
| A-02 | View audit logs (FR-11) | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |

> **Note on A-02:** The spec explicitly grants "audit logs" to Superuser (§4.1.1). Manager is added by precedence — a Manager is authorized for operational visibility equivalent to Superuser for the audit log surface. Session Admins have **not** been granted audit-log read access in this version (deferred; revisit if admins need to debug their own session without Superuser involvement).

### 3.7 System (non-human) capabilities

| # | Permission | Superuser | Manager | Session Admin | Driver | Passenger | System |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | Execute matching engine (compute proposed match) | n/a | n/a | n/a | n/a | n/a | ✓ |
| S-02 | Emit notifications (registration success / match approved / match changed / session cancelled) | n/a | n/a | n/a | n/a | n/a | ✓ |
| S-03 | Write audit log entries (login attempts, auth failures, session changes, matching approvals, admin overrides) | n/a | n/a | n/a | n/a | n/a | ✓ |

**Total permissions in matrix: 33** (P-01..P-23 = 23; V-01..V-08 = 8; A-01..A-02 = 2; S-01..S-03 = 3).

### 3.8 Orphan checks

- **Roles with at least one ✓ / ◐ / n/a entry:** Superuser, Manager, Session Admin, Driver, Passenger, System — **all six roles covered.**
- **Permissions granted to at least one role:** every permission P-01..P-23, V-01..V-08, A-01..A-02, S-01..S-03 has at least one non-✗ cell. **No orphan permissions.**

---

## 4. Session Admin Assignment Flow

A Session Admin is **not** a global role; it is a per-session assignment stored as a DynamoDB item (`SESSION#<code>#ADMIN#<sub>` — see `docs/data_model_erd.md`). The flow to grant a user Session Admin rights for a given session is:

### 4.1 Endpoint (NEW — extends §9 of the master spec)

```http
POST /sessions/{code}/admin
Authorization: Bearer <app session JWT>
Content-Type: application/json
```

### 4.2 Request body

```json
{
  "user": {
    "sub":  "google-oauth2|1234567890",
    "email": "alex@example.com"
  }
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `user.sub` | string | Yes | Google subject identifier (stable, opaque, never changes for the lifetime of the Google account). Used as the canonical user key. |
| `user.email` | string | Yes | Google account email at the time of assignment. Recorded for human-readable audit; the source of truth is `sub`. |

`{code}` in the path is the session code.

### 4.3 Authorization

The caller must hold **Superuser** or **Manager** (global role). Session Admins **cannot** self-promote or promote others. `401` if unauthenticated, `403` if the caller lacks the required global role, `404` if the session does not exist or is not in an assignable state.

### 4.4 Effect

A new item is written to `app_data`:

```
PK = SESSION#<code>
SK = ADMIN#<google_sub>
attributes = { email, assigned_by_sub, assigned_at, role = "session_admin" }
```

The target user gains the **Session Admin** role for the session `{code}` only. The assignment is **idempotent** — re-posting the same payload is a no-op success. If the target user is already a Driver or Passenger in this session, the new role is **additive** (multi-role user; see §2.4).

### 4.5 Preconditions

1. The caller has authenticated (app session JWT present and valid; ADR-0002).
2. The caller is Superuser or Manager (global role from the JWT `global_role` claim).
3. The session `{code}` exists and is not in `closed` status.
4. The target user has authenticated at least once and therefore has a `USER#<sub>` record on file. (Otherwise there is no Google account to bind the role to and we reject with `404 Not Found` plus a `target_user_unknown` error code.)

### 4.6 Audit

Every successful assignment writes an audit log entry (S-03) with:
- actor = caller's `sub`
- action = `session_admin.assign`
- target = `{code} + target sub`
- result = `success` / `failure`
- reason (on failure)

### 4.7 Revocation (companion endpoint — out of scope for v1 of this matrix)

A symmetric `DELETE /sessions/{code}/admin/{sub}` is **not** in §9 of the master spec. It is logged here as a follow-up ADR candidate; do not implement without a separate ADR.

---

## 5. Endpoint-to-Permission Mapping

Every REST endpoint in `docs/functional_requirements_and_architecture.md` §9 plus the new admin-assignment endpoint from §4. Required roles are evaluated **after** authentication (ADR-0005). All authenticated callers must satisfy the rate-limit dependency first.

| # | Endpoint | Method | Required Role | Notes |
| --- | --- | --- | --- | --- |
| E-01 | `/auth/google` | POST | **Unauthenticated** | Issues the app session JWT (ADR-0002). Rate-limit + audit apply; RBAC skipped. |
| E-02 | `/sessions` | POST | **Superuser or Manager** | P-01. |
| E-03 | `/sessions` | GET | **Any authenticated user** | P-03 — the response is filtered by the caller's effective scope (a Driver only sees sessions they're registered in, a Session Admin only sees their sessions, etc.). Superuser sees all. |
| E-04 | `/sessions/{code}` | GET | **Any authenticated user** | P-02 — same scope-filtering rules as E-03. |
| E-05 | `/sessions/{code}` | PATCH | **Superuser, Manager, or Session Admin of `{code}`** | P-04. |
| E-06 | `/sessions/{code}` | DELETE | **Superuser** | P-05. |
| E-07 | `/sessions/{code}/register` | POST | **Any authenticated user (with registration open)** | P-07 / P-08 depending on body.role. RBAC enforces "may register"; session status enforces "may register now". |
| E-08 | `/sessions/{code}/me` | GET | **Any authenticated user** | P-09 — returns 404 if caller is not registered in `{code}`. |
| E-09 | `/sessions/{code}/me` | PATCH | **Any authenticated user** | P-10 — same 404 rule as E-08. |
| E-10 | `/sessions/{code}/me` | DELETE | **Any authenticated user** | P-11 — same 404 rule. |
| E-11 | `/sessions/{code}/match/run` | POST | **Superuser, Manager, or Session Admin of `{code}`** | P-14 / P-19 (force rematch). |
| E-12 | `/sessions/{code}/match` | GET | **Superuser, Manager, Session Admin of `{code}`** | P-15. Returns `404` until a proposed match exists. Drivers and passengers receive `403`. |
| E-13 | `/sessions/{code}/match/approve` | POST | **Superuser, Manager, or Session Admin of `{code}`** | P-17. Triggers P-18 (publish). |
| E-14 | `/sessions/{code}/match/manual` | PATCH | **Superuser, Manager, or Session Admin of `{code}`** | P-20, P-21, P-22, P-23 — discriminated union in the request body selects the operation. |
| E-15 | `/sessions/{code}/registration/open` | POST | **Superuser, Manager, or Session Admin of `{code}`** | P-12. (Implicit — Section 9 of the master spec does not list this endpoint explicitly; it is required by §4.2.1. Documented here; raise as a follow-up ADR if the API contract team disagrees.) |
| E-16 | `/sessions/{code}/registration/close` | POST | **Superuser, Manager, or Session Admin of `{code}`** | P-13. (Same note as E-15.) |
| E-17 | `/sessions/{code}/admin` | POST | **Superuser or Manager** | **NEW endpoint** defined in §4. P-06. |
| E-18 | `/sessions/{code}/admin/notify` | POST | **Superuser, Manager, or Session Admin of `{code}`** | A-01. |
| E-19 | `/audit` | GET | **Superuser or Manager** | A-02. |
| E-20 | `/sessions/{code}/assignment` | GET | **Any authenticated user** | V-06 / V-07 / V-08 — the response is filtered by the caller's scope (Driver sees their roster, Passenger sees their driver, Session Admin sees everything in their session). |
| E-21 | `/sessions/{code}/registrations` | GET | **Superuser, Manager, or Session Admin of `{code}`** | V-02 / V-03 / V-05 — admin roster view. |
| E-22 | `/health` | GET | **Unauthenticated** | Operational probe. No RBAC; rate-limit + audit apply. |

### 5.1 Endpoint-to-permission cross-check

- Every endpoint above maps to one or more permissions in §3.
- Every permission in §3 is reachable by at least one endpoint above **or** by an internal system action (System column).
- No endpoint is unprotected (except E-01 and E-22, which are explicitly unauthenticated by design).
- No endpoint is "all-authenticated-users-can-do-anything" — the loosest authenticated rule (E-03 / E-04 / E-08 / E-09 / E-10 / E-20) still filters responses by scope.

---

## 6. RBAC Enforcement Point (Design Note)

RBAC is enforced as the **fourth** dependency in the FastAPI request chain, per **ADR-0005 (Middleware Order): `rate_limit → audit → auth → rbac`**. Implementation notes (not code):

- Each protected route declares `Depends(require_role(...))` in its handler signature; the dependency reads the resolved principal from the `auth` dependency and the route-scoped resource from the path/body.
- Resolution order inside `rbac`:
  1. Compute the **effective role set** for the principal at the requested resource scope (global role + session-scoped roles; see §2.4).
  2. Evaluate the **permission predicate** for the route against that role set (deny-default).
  3. On `False`, return `403 Forbidden` with an `insufficient_permissions` error code; the `audit` dependency records the denial (S-03).
- `audit` runs **before** RBAC and writes asynchronously (`asyncio.create_task`) so a denied request never adds DynamoDB latency to the response (ADR-0005 §Consequences).
- Scope-filtering for read endpoints (E-03, E-04, E-20, E-21) is applied **inside** the route handler **after** RBAC passes — RBAC confirms the caller may see *some* data from this session; the handler then strips fields the caller's effective scope disallows (per §3.5).
- The `POST /sessions/{code}/admin` endpoint (E-17) is the **only** endpoint that mutates role assignments. All other write paths modify session/registration/match records and inherit the caller's existing roles.

---

## 7. Open Questions / Follow-ups

- **E-15 / E-16**: Should `POST /sessions/{code}/registration/open` and `…/close` be added explicitly to §9 of the master spec, or folded into `PATCH /sessions/{code}` (changing `status`)? Recommend separate endpoints for audit clarity.
- **A-02**: Session Admin audit-log access is currently ✗ — consider granting read-only access to logs scoped to their session in v2.
- **§4.7**: A `DELETE /sessions/{code}/admin/{sub}` revocation endpoint is not yet speced.
- **Superuser-assigns-Superuser**: out of scope; bootstrapped via Parameter Store / Terraform, not via the API.
