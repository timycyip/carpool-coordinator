> **Amendment pointer (Phase 2 housekeeping):** This spec is v3.0 and already incorporates
> the resolutions below. This banner is an at-a-glance overlay, not a content fix.
> Superseding ADRs: ADR-0001 (multi-table DynamoDB, supersedes single-table assumption),
> ADR-0008 (deferred notification delivery, supersedes synchronous email). See `docs/adr/`.

# Carpool Matching Application — Functional Requirements & Solution Architecture (v3)

## Version
v3.0 (Updated with Phase 1 Discovery resolutions)

## Revision Log

| Version | Date | Changes |
|---------|------|---------|
| v2.0 | 2026-06-23 | Initial stakeholder-reviewed spec |
| v3.0 | 2026-06-23 | Phase 1 Discovery resolutions: canonical registration schema replaces FR-3/FR-4; NFRs expanded with testable acceptance criteria; FR-5 routing provider changed to ORS; FR-10 notifications changed to deferred delivery (ADR-0008); §8 data model updated to multi-table (ADR-0001); §10 AWS components updated to 5 tables; session status enum changed to snake_case; frontend locked to Next.js; idle cost NFR corrected |

> **Note:** This spec is now the single source of truth for all functional and non-functional requirements. The `docs/requirements_baseline.md` is a thin delta document tracking review status and sign-off only.

## Authors
- Business Analyst
- Solution Architect

## Tech Stack Constraints
- Backend: Python + FastAPI
- Hosting: AWS Lambda ARM64
- Authentication: Google OIDC + Session Code
- Mapping: OpenStreetMap ecosystem (OSRM / Nominatim)
- Database: DynamoDB
- Logging: CloudWatch → S3 → Athena
- CDN / Edge Protection: Cloudflare Free

---

# 1. Project Overview
This application is a **carpool coordination platform** for events such as church gatherings, conferences, volunteering, school activities, and group trips.

## 1.1 Problem Statement

Organizations such as churches, schools, conferences, volunteer groups, and event organizers often coordinate carpools manually through spreadsheets or chat groups.

This introduces:

* inefficient ride assignment
* poor seat utilization
* privacy leakage
* high admin workload
* poor handling of last-minute changes

The proposed application automates:

* ride registration
* passenger-driver matching
* route optimization
* admin approval workflow
* assignment publishing

Unlike ride-hailing apps, this platform assumes:
- each session has a shared **destination** OR shared **origin**
- participants are grouped into carpools
- matching is optimized for route efficiency and schedule compatibility

---

# 2. Business Goals

Primary goals:

1. Reduce manual coordination effort by 80%
2. Increase vehicle seat utilization
3. Minimize detour distance/time
4. Preserve user privacy
5. Support burst traffic with low infrastructure cost

---

# 3. Stakeholders

| Role          | Responsibility                |
| ------------- | ----------------------------- |
| Superuser     | Global platform administrator |
| Manager       | Creates sessions              |
| Session Admin | Manage a carpool session      |
| Driver        | Provides ride                 |
| Passenger     | Requests ride                 |
| System        | Matching and routing engine   |

---

# 4. Authorization Model (RBAC)

Default policy: **DENY ALL**

Roles grant permissions.

## 4.1 System Roles
- Superuser
- Manager

### 4.1.1 Superuser

Global authority.

Permissions:

* create sessions
* delete sessions
* assign admins
* view all sessions
* override all matches
* audit logs
* force rematch

---

## 4.2 Session Roles
- Admin
- Driver
- Passenger

Session roles are scoped per session.

### 4.2.1 Session Admin

Scoped to one carpool session.

Permissions:

* configure session
* open registration
* close registration
* run matching algorithm
* manually adjust matching
* approve matching
* notify participants

---

## 4.2.2 Driver

Permissions:

* register as driver
* define seats
* define route preferences
* see assigned passengers
* see approved route

Can view:

* assigned passengers
* own route

Cannot view:

* passengers of other drivers

---

## 4.2.3 Passenger

Permissions:

* register trip request
* update pickup/dropoff
* view assigned driver

Cannot view:

* other passengers
* unassigned drivers
* other driver routes

## 4.3 Role Precedence
Permission resolution:

`Superuser > Manager > Session Admin > Driver > Passenger`

Higher roles override lower roles.

---

# 5. Functional Requirements

## FR-1 Authentication & Session Registration
Users can sign in using Google without session code.

Session code required only for registration.

Flow:

```text
Open App
1. Google login
2. Browse app
3. Register to session with session code
```

Session code may be:
- manually entered
- prepopulated via URL

Example:
`/register?session=ABC123`

Managers and Superusers may create sessions without session code.
For other users, it would return session code not found. 

Validation:

* verify Google JWT token
* verify session code
* check session expiration
* ensure user role is permitted

---

## FR-2 Session Management

A session represents a carpool event.
Manager creates session.

Examples:

* church service
* hiking trip
* conference
* airport pickup

Session attributes:

| Field                 | Type         |
| --------------------- | ------------ |
| session_code          | string       |
| title                 | string       |
| description           | string       |
- trip mode:
  - TO_DESTINATION
  - FROM_ORIGIN
- anchor location (destination or origin)
| earliest_pickup       | datetime     |
| latest_arrival        | datetime     |
| registration_deadline | datetime     |
| status                | enum         |

Session status (snake_case enum values):

* `draft`
* `registration_open`
* `matching_pending`
* `matching_proposed`
* `approved`
* `closed`

---

## FR-3 / FR-4 Registration (Canonical Schema)

> **This schema supersedes the original v2 FR-3 and FR-4 field lists.** It is the single source of truth for Phase 3 registration implementation. Any future change requires a new ADR.

Users register into a session as either a **Driver** or a **Passenger**. The role is selected at registration time and cannot be changed (users must delete and re-create to switch roles).

### Common Fields (required for every registrant)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string (1–120 chars) | Yes | Display name shown to admins and (post-publish) to assigned peers. |
| `email` | string (RFC 5322) | Yes | Must match the authenticated Google OIDC email; otherwise registration fails. |
| `role` | enum (`driver` \| `passenger`) | Yes | Selected at registration time; changing role requires deleting and re-creating the registration. |
| `postal_code` | string | Yes | Approximate postal code (or ZIP) geocoded server-side via FR-5; raw lat/lon is never collected from the user. |
| `earliest_departure_time` | ISO-8601 datetime | Yes | The earliest the user can leave their pickup point; used by the matching engine's time-window logic. |
| `latest_departure_time` | ISO-8601 datetime | Yes | The latest the user can leave their pickup point; must be ≥ `earliest_departure_time` and ≤ session's `registration_deadline`. |
| `session_code` | string | Yes | FK to the session; provided in the registration URL or entered manually. |

### Driver-Specific Fields (required only when `role = driver`)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `seat_capacity` | integer (1+) | Yes | Number of passenger seats the driver offers in addition to themselves. No hard cap. |
| `earliest_pickup_time` | ISO-8601 datetime | Yes | Earliest time the driver can start picking up passengers. |
| `latest_pickup_time` | ISO-8601 datetime | Yes | Latest time the driver will start their route. Must satisfy `earliest_pickup_time ≤ latest_pickup_time` and the session's `latest_arrival` constraint. |

### Passenger-Specific Fields (required only when `role = passenger`)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `accessibility_requirements` | string (0–500 chars) | Optional | Free-text accessibility needs. Used as a soft constraint by the matching engine; never auto-overrides a hard constraint. |
| `special_notes` | string (0–500 chars) | Optional | Free-text notes for the driver (e.g., "traveling with small child"). Visible to the assigned driver only after publish. |

### Server-Derived Fields (never accepted from the client)

| Field | Type | Source |
| --- | --- | --- |
| `registration_id` | ULID | Generated on create. |
| `user_sub` | string (Google `sub`) | From the verified JWT. |
| `geocoded_location` | `{lat: float, lon: float, source: "nominatim", cached_at: ISO-8601}` | From FR-5 geocode cache or live Nominatim call. |
| `created_at` / `updated_at` | ISO-8601 datetime | Server clock. |
| `status` | enum (`active` \| `withdrawn`) | Defaults to `active`; set to `withdrawn` on user-initiated delete. |

### Validation Rules (enforced server-side, 422 on failure)

1. `earliest_departure_time ≤ latest_departure_time`.
2. `earliest_departure_time ≥ now()` (no back-dated registrations).
3. Both departure times fall within `[session.earliest_pickup, session.latest_arrival]`.
4. `seat_capacity ≥ 1` if `role = driver`.
5. If `role = driver`: `earliest_pickup_time ≤ latest_pickup_time` and both fall within the session window.
6. A user may register once per session; a second `POST /sessions/{code}/register` for the same `user_sub` returns 409.
7. Postal code must geocode successfully (FR-5); failure returns 422.

---

## FR-5 Geolocation

System must use OpenStreetMap ecosystem. Users provide approximate postal code.

Required services:

### Geocoding

Convert postal code → coordinates (centroid lat/lon)

Suggested:

* Nominatim

### Routing

Calculate:

* route
* duration
* distance
* detour

Provider:

* OpenRouteService (ORS) free-tier API (`/v2/directions`, `/v2/matrix`)
* Free tier: 2000 req/day, 40 req/min, ~50 locations per matrix call
* Matrix calls must be chunked for sessions with >50 locations
* OSRM self-hosting is deferred to post-MVP

Required endpoints:

```text
/geocode
/route
/matrix
```

Matrix API is required for efficient matching.

---

## FR-6 Matching Engine

System generates optimized ride assignment.

Objectives:

* minimize total distance
* minimize detour
* avoid lateness
* maximize seat utilization

---

### Hard Constraints

Must satisfy:

- seat capacity
- geographic feasibility
- schedule compatibility
- arrival/departure constraints

---

### Soft Constraints

Optimize:

- fairness
- shortest total distance
- balanced driver load

The engine must consider time windows:
- driver earliest departure
- passenger earliest availability
- session cutoff

Problem formulation:
**Capacitated Vehicle Routing Problem with Time Windows (CVRPTW)**

Input:

```text
drivers
passengers
locations
constraints
```

Output:

```json
{
  "driver_1": ["passenger_3", "passenger_8"]
}
```

---

## FR-7 Matching Approval Workflow

Matching result is not immediately visible.

Workflow:

```text
Admin runs algorithm
→ Proposed match generated
→ Admin reviews
→ Admin edits
→ Admin approves
→ Publish to users
```

Before approval:
- hidden from drivers/passengers

After approval:
- visible to assigned users only

---

## FR-8 Manual Override

Admin can manually:

* move passenger to another driver
* unassign passenger
* mark passenger unmatched
* lock assignment

Admin changes are allowed:

* before approval
* after approval

Changes after approval trigger notification.

---

## FR-9 Visibility Rules

| Data              | Passenger     | Driver        | Admin/Manager | Superuser |
| ----------------- | ------------- | ------------- | ------------- | --------- |
| Own profile       | Yes           | Yes           | Yes           | Yes       |
| Other passengers  | No            | Assigned only | Yes           | Yes       |
| Other drivers     | Assigned only | Yes           | Yes           | Yes       |
| Matching score    | No            | No            | Yes           | Yes       |
| Full session data | No            | No            | Yes           | Yes       |

Session Admin can only see passengers and drivers registered in sessions being admin for.

---

## FR-10 Notifications

Notifications via email.

Events:

* registration success
* matching approved
* match changed
* session cancelled

### Delivery Model (per ADR-0008)

Email delivery is **deferred**, not synchronous:

1. API Lambda writes `notification_pending` items to DynamoDB and returns 200 immediately.
2. An SQS → email Lambda consumer reads pending items and sends via Microsoft Graph `sendMail` to M365 Exchange.
3. Failed sends retry with exponential backoff (3 attempts); permanently failed items are marked `failed` for admin review.
4. The API request path never blocks on email delivery.

Email templates: HTML with org logo placeholder.

Future:

* SMS
* WhatsApp
* push notifications

---

## FR-11 Audit Logging

System logs:

* login attempts
* failed authentication
* session changes
* matching approvals
* admin overrides

Required for:

* security
* troubleshooting
* auditing

---

# 6. Non-Functional Requirements

Each NFR must be verifiable by an automated test, a CloudWatch metric + alarm, or a documented operational runbook step.

## 6.1 Performance

| ID | Requirement | Acceptance Criteria (testable) |
| --- | --- | --- |
| NFR-PERF-1 | API latency p95 < 800ms | Measured at the Lambda Function URL via CloudWatch EMF metrics. p95 of all 2xx + 4xx API responses, sampled over a rolling 24h window, is < 800ms. Matching endpoints (`POST /match/run`) are excluded from this SLO. |
| NFR-PERF-2 | Matching completes < 30s for 500 users | End-to-end `POST /sessions/{code}/match/run` (request → 200 with proposed match) completes in < 30s wall-clock for a session with 500 registrants in a memory-isolated Lambda benchmark. Validated in Phase 4 spike and re-verified in Phase 6 load test. (MVP greedy solver caps at <300 users; 500-user target is a Phase 6 post-MVP goal.) |
| NFR-PERF-3 | Cold-start p95 < 1500ms | First-request latency after a 10-minute idle window is p95 < 1500ms. Tracked via CloudWatch `init_duration`. Provisioned concurrency is evaluated in Phase 6 if not met. |
| NFR-PERF-4 | Frontend LCP < 2.5s on 4G | Largest Contentful Paint on the registration dashboard is < 2.5s. Verified in Phase 2 bootstrap and re-verified in Phase 6. |

## 6.2 Availability

| ID | Requirement | Acceptance Criteria |
| --- | --- | --- |
| NFR-AVAIL-1 | 99.5% monthly availability | Monthly uptime (successful responses / total requests, excluding client errors) ≥ 99.5%. Measured at the Lambda Function URL. |
| NFR-AVAIL-2 | Zero-data-loss for session, registration, match, and audit writes | Every write returns success only after DynamoDB confirms the item is durably stored. No fire-and-forget writes on these tables. |

## 6.3 Scalability

| ID | Requirement | Acceptance Criteria |
| --- | --- | --- |
| NFR-SCALE-1 | Handle bursts up to 5000 req/min | Sustained 5000 req/min for 5 minutes produces zero 5xx responses and no DynamoDB throttling (per ADR-0007 on-demand capacity). Validated via Phase 6 load test. |
| NFR-SCALE-2 | Idle cost ≤ $1/month | Monthly AWS bill for an idle deployment (no traffic for 30 days) is ≤ $1.00 (CloudWatch Logs ingestion may incur minimal cost). Verified by a monthly cost-anomaly review. |
| NFR-SCALE-3 | Multi-session per user | A single authenticated user can hold active registrations in ≥10 sessions concurrently without quota error. |

## 6.4 Security

| ID | Requirement | Acceptance Criteria |
| --- | --- | --- |
| NFR-SEC-1 | JWT validation on every API request | All API endpoints reject requests without a valid, unexpired, signature-verified JWT (except `POST /auth/google`). Verified by an automated test suite in Phase 2. |
| NFR-SEC-2 | Rate limiting — 60 req/min/IP and 120 req/min/user | Requests exceeding either limit return 429 with a `Retry-After` header. Counters live in the `rate_limit_cache` table with TTL. Verified by Phase 2 tests and Phase 6 load test. |
| NFR-SEC-3 | Anti-bot protection | Cloudflare Free WAF + Turnstile (or equivalent) protects registration and authentication endpoints. Verified by manual abuse test in Phase 6. |
| NFR-SEC-4 | Encrypted at rest | All DynamoDB tables use AWS-managed KMS encryption. All S3 buckets use SSE-KMS. Verified by Terraform plan + AWS Config rule. |
| NFR-SEC-5 | No passwords stored | The codebase and DynamoDB schema contain no password fields. Verified by grep test in Phase 2 CI. |
| NFR-SEC-6 | Per-session RBAC enforcement | A passenger cannot read another session's registration data via any endpoint; a non-admin Session Admin cannot read sessions they do not admin. Verified by automated IDOR test suite in Phase 5. |
| NFR-SEC-7 | PII minimization in audit logs | Audit log `payload_summary` fields never contain email, name, postal code, or geocoded coordinates in plaintext. Verified by a Phase 5 audit-log inspection test. |

## 6.5 Operability & Observability

| ID | Requirement | Acceptance Criteria |
| --- | --- | --- |
| NFR-OPS-1 | Structured JSON logs to CloudWatch | Every Lambda invocation emits a structured JSON log line with `request_id`, `route`, `user_sub` (or `anon`), `status`, `latency_ms`. Verified by log-format test in Phase 2. |
| NFR-OPS-2 | 30-day log retention via S3 lifecycle | CloudWatch → S3 subscription with a 30-day lifecycle policy deletes old logs automatically. Verified by Terraform plan + AWS Config rule. |
| NFR-OPS-3 | Athena-queryable logs | Logs in S3 are queryable via Athena for incident analysis and abuse investigation. Verified in Phase 2 bootstrap. |
| NFR-OPS-4 | CloudWatch alarms on 5xx rate and p95 latency | Alarms page (or notify) on >1% 5xx rate over 5 min or p95 latency > 2× SLO for 10 min. Verified in Phase 6. |

---

# 7. Session Geometry Model
```json
{
  "session_code": "ABC123",
  "trip_mode": "TO_DESTINATION",
  "anchor_location": {
    "lat": 43.81,
    "lon": -79.39
  }
}
```

Used for:
- geographic clustering
- pruning impossible matches
- reducing computational cost


---

# 8. Data Model

Recommended:
Multi-table DynamoDB design — tables named per data model (per ADR-0001). The `app_data` table uses the single-table PK/SK-overloading pattern internally for business entities. Cache and counter stores are in separate named tables with TTL. See `docs/data_model_erd.md` for the full ERD.

---

## Users

Partition key:

```text
USER#<google_sub>
```

Example:

```json
{
  "email": "user@example.com",
  "name": "John",
  "role": "driver"
}
```

---

## Sessions

```text
SESSION#ABC123
```

---

## Registrations

```text
PK: SESSION#ABC123
SK: REG#USER123
```

---

## Matches

```text
PK: SESSION#ABC123
SK: MATCH#V1
```

---

## Audit Logs

```text
AUDIT#DATE
```

---

# 9. REST API Specification

## Authentication

```http
POST /auth/google
```

---

## Session APIs

```http
POST /sessions
GET /sessions/{code}
PATCH /sessions/{code}
DELETE /sessions/{code}
```

---

## Registration APIs

```http
POST /sessions/{code}/register
GET /sessions/{code}/me
PATCH /sessions/{code}/me
```

---

## Matching APIs

```http
POST /sessions/{code}/match/run
GET /sessions/{code}/match
POST /sessions/{code}/match/approve
PATCH /sessions/{code}/match/manual
```

---

## Admin APIs

```http
POST /sessions/{code}/admin/notify
GET /audit
```

---

# 9. Solution Architecture

```text
Users
 ↓
Cloudflare Free
 ↓
AWS Lambda Function URL
 ↓
FastAPI + Mangum
 ├─ Google OIDC Auth
 ├─ Session Validation
 ├─ Rate Limiting
 ├─ Matching Engine
 ↓
DynamoDB
 ↓
CloudWatch Logs
 ↓
S3
 ↓
Athena
```

---

# 10. AWS Components

## Compute

AWS Lambda ARM64

Recommended:

* Python 3.12
* ARM64 runtime
* 256 MB memory
* 5–10 sec timeout

---

## Database

DynamoDB

Tables (per ADR-0001 — named per data model):

* `app_data` (business entities: users, sessions, registrations, matches, audit logs)
* `session_cache` (session-scoped ephemeral state, TTL)
* `rate_limit_cache` (per-IP/per-user request counters, TTL)
* `brute_force_counter` (failed-auth tracking, TTL)
* `geocode_cache` (postal-code → lat/lon cache, 30-day TTL)

All tables use on-demand capacity (ADR-0007). See `docs/data_model_erd.md` for the full schema.

---

## Secrets

AWS Parameter Store

Store:

* Google OIDC config
* API keys
* session secrets

---

## Monitoring

CloudWatch Logs

Log:

* errors
* auth failures
* latency summaries

Avoid verbose success logging.

---

## Storage

Amazon S3

Retention:
30-day lifecycle deletion

---

## Analytics

Athena

Use for:

* incident analysis
* abuse investigation
* debugging

Idle cost:
≤ $1/month (CloudWatch Logs ingestion may incur minimal cost)

---

# 11. Backend Design

Recommended structure:

```bash
app/
 ├─ main.py
 ├─ auth/
 ├─ api/
 ├─ models/
 ├─ services/
 │   ├─ matching.py
 │   ├─ routing.py
 │   └─ session.py
 ├─ repositories/
 └─ middleware/
```

---

# 12. Matching Algorithm Design

Algorithm derived from reference repo.

---

## Stage 1: Geographic Clustering
Cluster by postal-code proximity.

Reduces complexity.

## Stage 2: Candidate Filtering
Remove infeasible matches:
- too far
- no schedule overlap
- no seat

Remove impossible matches.

Example:

```text
detour > driver.max_detour
```

Discard candidate.

---

## Stage 3 Cost Matrix

Cost Matrix
Score = weighted sum of:
- detour
- lateness
- imbalance

```text
driver × passenger
```

Cost function:

```text
score =
distance_weight * detour
+ time_weight * lateness
+ load_weight * imbalance
```

Lower score = better.

---

## Stage 4 Optimization

### MVP

Greedy heuristic

Suitable:
<300 users

---

### Production

Optimization solver

Suggested:

* OR-Tools
* linear programming
* integer programming

For return trips:
solve separately:

* outbound
* return

---

# 13. Lambda Constraints

Lambda is not ideal for long-running optimization.

Reasons:

* execution timeout
* CPU limits
* memory limits

Recommendation:

## Small Sessions (<300)

Run inside Lambda.

## Large Sessions (>300)

Use async processing:

* SQS
* Step Functions
* Fargate

---

# 14. Security Controls

Cloudflare Free offers limited WAF.

Application should enforce:

---

## Rate Limits

Per IP:

```text
60 requests/min
```

Per user:

```text
120 requests/min
```

---

## Abuse Detection

Track:

* failed login attempts
* invalid session code attempts
* suspicious access patterns

Apply:

* temporary bans
* exponential backoff
* alerting

---

# 15. Frontend Recommendation

Framework:
Next.js (App Router) — locked decision

Deployment:
Cloudflare Pages via `next-on-pages` (preview per branch, production on merge to main)

Benefits:

* static hosting
* CDN
* low cost

---

# 16. Implementation Plan

---

## Phase 1 — Discovery (1–2 weeks)

Deliverables:

* finalized requirements
* wireframes
* role matrix
* workflow diagrams

---

## Phase 2 — Foundation (2 weeks)

Build:

* FastAPI skeleton
* CI/CD
* Lambda deployment
* DynamoDB schema
* authentication

Deliverable:
working login + session setup

---

## Phase 3 — Registration (2 weeks)

Build:

* registration workflow
* maps integration
* location lookup
* driver/passenger UI

---

## Phase 4 — Matching Engine (3–5 weeks)

Build:

* route matrix
* scoring engine
* optimization
* admin override UI

Most complex phase.

---

## Phase 5 — Approval & Notification (2 weeks)

Build:

* approval workflow
* email notification
* audit logging

---

## Phase 6 — Hardening (2 weeks)

Build:

* load testing
* security review
* observability
* production readiness

---

# 17. Team Composition

Recommended team:

Business:

* 1 Business Analyst
* 1 Product Owner

Engineering:

* 1 Solution Architect
* 2 Backend Engineers
* 1 Frontend Engineer
* 1 QA Engineer

Total:
4–6 people minimum

---

> **Project Note (2026-06-23):** The actual project is a solo-dev deployment with AI agents
> filling the roles above (Team Lead agent, Product Owner agent, Business Analyst agent,
> Solution Architect agent, etc.). The role definitions above describe the *responsibilities*
> each agent covers, not separate human team members. See `docs/requirements_baseline.md` §5
> for the sign-off process.

---

# 18. Risks & Mitigation

| Risk              | Severity | Mitigation           |
| ----------------- | -------- | -------------------- |
| OSM rate limits   | High     | Self-host OSRM       |
| Matching too slow | High     | Async jobs           |
| Privacy leakage   | High     | Strict RBAC          |
| Cost spikes       | Medium   | Reserved concurrency |
| Poor routing      | Medium   | Admin override       |

---

# 19. Future Enhancements

Potential v2 features:

* Return trip support
* recurring sessions
* live GPS tracking
* ETA updates
* ride check-in
* AI-assisted matching
* park-and-pool model
* carbon savings dashboard
* in-app chat

---

# Final Recommendation

This architecture is suitable for:

* low traffic systems
* bursty event-based workloads
* low operational overhead
* cost-sensitive deployment

Recommended improvement:

Use asynchronous matching workflow:

```text
Admin clicks match
→ Lambda validates request
→ SQS / Step Functions starts async job
→ Store result in DynamoDB
→ Admin reviews result
```

This improves reliability for large sessions (200+ participants).

---

# Appendix A: Research Repositories
- https://github.com/ayushb77891/carpool
- https://github.com/Melody-Meng/Car-pool-algorithm
- https://github.com/LivingCat/MSSI1819
- https://github.com/Sn00pyW00dst0ck/Carpool-Creator
- https://github.com/thefriedbee/CarpoolSim

