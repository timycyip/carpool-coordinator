# Carpool Coordinator — Sharpened MVP Scope

## Problem Statement
How might we deliver a working carpool-coordination web app for a specific NGO group in 3 weeks with a 4–6 person team — without the infrastructure of a venture-backed SaaS?

## Recommended Direction
Build a single-tenant web app (FastAPI on Lambda + Next.js on Cloudflare Pages, one DynamoDB table) that covers the full vertical slice: Google login → session → driver/passenger registration with geocoded locations → matching engine → admin approval → email notification. Use free-tier OpenRouteService for routing instead of self-hosting OSRM. Notifications are deferred per ADR-0008: the API queues `notification_pending` items and a separate SQS → Lambda consumer sends via Microsoft Graph. Keep the 5-role RBAC and the CloudWatch → S3 → Athena observability pipeline as specified.

The original v2 architecture over-engineered three areas that are now cut: self-hosted OSRM (replaced by ORS free tier), a 4-table DynamoDB layout (collapsed to one table with TTL items), and a synchronous email fan-out (replaced by a deferred queue — see ADR-0008 and §notification-deferral below). These three cuts remove roughly one full week of infra work and an ongoing operational burden (OSRM host, queue monitoring, DLQ drains) that a single NGO deployment does not need.

What makes this fit in 3 weeks is deferring everything that isn't on the critical path to participant-value: load testing, abuse-detection hardening, frontend accessibility/polish, and the security review are all post-MVP. The NGO's internal traffic doesn't need brute-force protection on day one.

## Key Assumptions to Validate
- [ ] ORS free tier (2,000 req/day, 40 req/min) is sufficient for the NGO's session sizes — test with a 200-participant matrix call (200×200 = 40,000 entries; ORS matrix takes up to ~50 locations per call, so batching is required). Validate the batching approach early in Phase 3.
- [ ] Synchronous email send from Lambda stays under the 10s timeout — M365 Graph `sendMail` is typically <2s; a batch of 200 emails sent in a loop may exceed it. Validate the per-approval fan-out approach (loop with early-exit on timeout, log unsent, admin retry).
- [ ] Single DynamoDB table with TTL items for rate-limiting holds up under the NGO's burst (a registration deadline surge). Validate with a 50-concurrent-registration smoke test.
- [ ] The NGO group has a Google Workspace or consumer Google accounts for OIDC, and an M365 mailbox for the sender address. Confirm both before Phase 2.
- [ ] 3 weeks is calendar weeks with the full team available — no partial availability. If any team member is part-time, the deferred list grows.

## MVP Scope (3 weeks)
**In:**
- Google OIDC authentication + 5-role RBAC (Superuser, Manager, Session Admin, Driver, Passenger)
- Session CRUD with status lifecycle
- Driver + passenger registration with postal-code geocoding (Nominatim, cached)
- Matching engine: 4 stages (geographic clustering → candidate filtering → cost matrix via ORS → greedy optimization), versioned, deterministic
- Admin matching review UI (run, view proposed match, per-driver cards with route)
- Approval + publish with FR-9 visibility rules (pre-approval hidden; post-approval assigned-only)
- Email notifications: 4 types (registration success, matching approved, match changed, session cancelled), delivered via a deferred SQS → Lambda consumer that sends via Microsoft Graph `sendMail`. Notifications are deferred: API queues notification_pending items; a separate SQS → Lambda consumer sends emails via Microsoft Graph. See ADR-0008.
- Participant assignment views (driver sees own passengers + route; passenger sees own driver + pickup)
- Basic audit logging (login, session changes, approvals, overrides)
- CloudWatch Logs → S3 (30-day lifecycle) → Athena pipeline + basic dashboards/alarms
- Basic rate limiting (60/min IP, 120/min user, TTL items in app_data)

**Deferred (post-MVP):**
- Manual override UI is IN SCOPE for MVP. Admins can drag-to-reorder passengers, lock assignments, switch match versions, and export CSV from the admin matching review screen.
- Match version compare is IN SCOPE for MVP.
- Load testing, concurrency tuning, DynamoDB restore drill
- Abuse detection / brute-force escalation
- External security review (keep basic JWT/IDOR checks only)
- Frontend accessibility pass, Lighthouse, bundle budgets
- Admin free-text notify composer
- Email content preview UI
- SMS / WhatsApp / push notifications
- Return-trip (`FROM_ORIGIN`) matching
- OR-Tools production solver / async matching for >300 users

## Not Doing (and Why)
- **Self-hosted OSRM** — operational burden (host, OSM extract, health checks, fallback matrix) is unjustified for one NGO. ORS free tier covers routing + matrix. The entire OSRM IaC stack, resilience task, and fallback cache are removed.
- **Deferred notification pipeline (replaces synchronous Graph `sendMail`)** — Notifications are queued, not sent synchronously. The API writes `notification_pending` items to DynamoDB and returns immediately; a separate SQS → Lambda consumer drains the queue and calls Microsoft Graph `sendMail` with exponential-backoff retries. Failed items are marked for admin review. This stays within the 10s Lambda timeout for the API path (which never blocks on email) and removes the synchronous fan-out risk. See ADR-0008.
- **4 DynamoDB tables** — `session_cache`, `rate_limit_cache`, `brute_force_counter` collapse into TTL items on `app_data`. One table, one billing model, one PITR target.
- **Manual override UI** — drag/drop reassignment with live constraint validation. IN SCOPE for MVP: move passenger (drag-to-reorder), unassign, lock, match version switching. Service-layer contract (`PATCH /match/manual`) and admin UI are both in scope for Phase 5.
- **Hardening sprint (Phase 6)** — load testing, security review, accessibility, Lighthouse are real work but not day-one value for a single internal NGO deployment. Basic JWT validation + IDOR checks stay; the rest is post-MVP.

## Open Questions
- ORS matrix batching: what's the max locations-per-call on the free tier, and does the cost-matrix stage need chunking for 200+ participant sessions?
- Email fan-out on approval: send all emails in-loop within Lambda timeout, or write a "pending notifications" list and let the admin trigger sends in batches?
- Does the NGO need return-trip support for their first event, or is `TO_DESTINATION` sufficient for MVP?
- Who on the 4–6 person team owns frontend vs. backend vs. infra? The 3-week timeline assumes ≥2 backend, ≥1 frontend, ≥1 infra/full-stack, working in parallel from week 1.
