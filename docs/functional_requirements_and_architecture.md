# Carpool Matching Application — Functional Requirements & Solution Architecture (v2)

## Version
v2.0 (Updated with stakeholder feedback)

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

Session status:

* Draft
* Registration Open
* Matching Pending
* Matching Proposed
* Approved
* Closed

---

## FR-3 Registration

### Driver fields
- name
- Google email
- approximate postal code
- seats available for additional passengers
- earliest time to offer ride

### Passenger fields
- name
- Google email
- approximate postal code
- earliest available time

---

## FR-4 User Registration

Users register into session as:

* Driver
* Passenger

Common fields:

| Field            | Required |
| ---------------- | -------- |
| Name             | Yes      |
| Google Email     | Yes      |
| Location         | Yes      |
(approximate postal code)
| Earliest Departure Time      |
| Latest Departure Time        |

---

### Driver Additional Fields

| Field                     |
| ------------------------- |
| Seat Capacity             |
| Earliest Pickup Time      |
| Latest Pickup Time        |

---

### Passenger Additional Fields

| Field                      |
| -------------------------- |
| Accessibility Requirements |
| Special Notes              |

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

Suggested:

* OSRM

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

## Performance

* API latency p95 < 800ms
* Matching < 30 sec for 500 users

---

## Availability

Target:
99.5%

---

## Scalability

System must support:

* idle traffic
* sudden bursts up to 5000 requests/min

---

## Security

Requirements:

* JWT validation
* rate limiting
* anti-bot protection
* encrypted storage
* no password storage

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
Single-table DynamoDB design

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

Tables:

* app_data
* session_cache
* rate_limit_cache
* brute_force_counter

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
$0

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

Suggested:

* React
  or
* Next.js

Deployment:
Cloudflare Pages

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

