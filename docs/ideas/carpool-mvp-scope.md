# Carpool Coordinator — Sharpened MVP Scope

## Problem Statement
How might we deliver a working carpool-coordination web app for a specific NGO group in 3 weeks with a 4–6 person team — without the infrastructure of a venture-backed SaaS?

## Recommended Direction
Build a single-tenant web app (FastAPI on Lambda + Next.js on Cloudflare Pages, one DynamoDB table) that covers the full vertical slice: Google login → session → driver/passenger registration with geocoded locations → matching engine → admin approval → email notification. Use free-tier OpenRouteService for routing instead of self-hosting OSRM. Send email synchronously via Microsoft Graph from the API Lambda — no queue, no separate email worker. Keep the 5-role RBAC and the CloudWatch → S3 → Athena observability pipeline as specified.

The original v2 architecture over-engineered three areas that are now cut: self-hosted OSRM (replaced by ORS free tier), a 4-table DynamoDB layout (collapsed to one table with TTL items), and an async SQS → email-Lambda notification pipeline (replaced by synchronous Graph `sendMail`). These three cuts remove roughly one full week of infra work and an ongoing operational burden (OSRM host, queue monitoring, DLQ drains) that a single NGO deployment does not need.

What makes this fit in 3 weeks is deferring everything that isn't on the critical path to participant-value: manual override UI, version compare, load testing, abuse-detection hardening, frontend accessibility/polish, and the security review are all post-MVP. The admin can re-run matching instead of manually dragging passengers between drivers; the NGO's internal traffic doesn't need brute-force protection on day one.

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
- Email notifications: 4 types (registration success, matching approved, match changed, session cancelled), sent synchronously via Microsoft Graph
- Participant assignment views (driver sees own passengers + route; passenger sees own driver + pickup)
- Basic audit logging (login, session changes, approvals, overrides)
- CloudWatch Logs → S3 (30-day lifecycle) → Athena pipeline + basic dashboards/alarms
- Basic rate limiting (60/min IP, 120/min user, TTL items in app_data)

**Deferred (post-MVP):**
- Manual override UI (admin re-runs matching instead)
- Match version compare
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
- **SQS queue + separate email Lambda + DLQ** — async pipeline is overkill for low-volume transactional email. Synchronous Graph `sendMail` from the API Lambda, with admin-retry on failure, is simpler and sufficient. Removes queue monitoring, DLQ drains, and a second Lambda to maintain.
- **4 DynamoDB tables** — `session_cache`, `rate_limit_cache`, `brute_force_counter` collapse into TTL items on `app_data`. One table, one billing model, one PITR target.
- **Manual override UI** — drag/drop reassignment with live constraint validation is a meaningful frontend effort. For MVP, the admin re-runs matching (deterministic, seeded) or edits registrations and re-runs. Override service + UI deferred.
- **Hardening sprint (Phase 6)** — load testing, security review, accessibility, Lighthouse are real work but not day-one value for a single internal NGO deployment. Basic JWT validation + IDOR checks stay; the rest is post-MVP.

## Open Questions
- ORS matrix batching: what's the max locations-per-call on the free tier, and does the cost-matrix stage need chunking for 200+ participant sessions?
- Email fan-out on approval: send all emails in-loop within Lambda timeout, or write a "pending notifications" list and let the admin trigger sends in batches?
- Does the NGO need return-trip support for their first event, or is `TO_DESTINATION` sufficient for MVP?
- Who on the 4–6 person team owns frontend vs. backend vs. infra? The 3-week timeline assumes ≥2 backend, ≥1 frontend, ≥1 infra/full-stack, working in parallel from week 1.
