# Phase 6 — Hardening Plan

> **3-WEEK MVP NOTE:** Most of Phase 6 is DEFERRED to post-MVP. For the 3-week MVP, only the observability pipeline (CloudWatch → S3 → Athena) and a basic production-readiness checklist are in scope. The observability pipeline should be set up during Phase 2 (foundation), not deferred to a hardening sprint. Load testing, security review, abuse detection, frontend polish, and restore drills are post-MVP.

Builds on Phases 2–5 (fully functional platform). Goal: production readiness — load testing, security review, observability, rate-limit tuning, and abuse detection, plus frontend resilience.

## Open Questions (to refine)
- [ ] Load test targets: confirm expected peak (5000 req/min per NFR) and session sizes for matching stress (100/300/500 users)?
- [ ] Security review: internal review only, or external penetration test? If external, what scope/budget?
- [ ] Observability dashboards: CloudWatch dashboards + Athena, or add a third-party APM (Datadog/Grafana)? Recommend CloudWatch + Athena only to keep idle cost $0.
- [ ] Backup/restore for DynamoDB: PITR on, plus on-demand backups — confirm recovery RPO/RTO targets.
- [ ] On-call: who receives CloudWatch alarms? Define an alarm routing target (Slack/email/SNS).
- [ ] Cost ceiling: monthly budget alert threshold per environment?

## Goal
A hardened, observable, production-ready system meeting the NFRs (p95 < 800ms, matching <30s for 500 users, 99.5% availability, burst to 5000 req/min, security controls).

## Decisions (locked)
- Observability: CloudWatch Logs → S3 (30-day lifecycle) → Athena (Section 10). Avoid verbose success logging. **Note:** the observability pipeline is set up during Phase 2 (foundational infra), not deferred to Phase 6.
- Monitoring: CloudWatch alarms + dashboards; routing via SNS.
- Security: JWT validation, rate limiting, anti-bot, encrypted storage, no password storage (Section 6). Cloudflare Free WAF at edge.
- Rate limits: 60 req/min IP, 120 req/min user (tuned in this phase).
- Abuse detection: failed logins, invalid session codes, suspicious access patterns → temp bans + exponential backoff + alerting.

## Tasks (ordered)

### Backend / Infra
1. **Load testing**: scripts (k6 or Locust) for: API burst (5000 req/min sustained), registration surge, matching run at 300 and 500 users. Capture p95/p99 latency, error rate, Lambda concurrency/throttling, DynamoDB consumed capacity.
2. **Concurrency tuning**: set Lambda reserved concurrency to bound cost spikes (Risk table) while meeting burst demand. Right-size memory (256 MB baseline, raise for matching if needed).
3. **DynamoDB capacity**: switch tables from default on-demand to provisioned if load is predictable, or keep on-demand with autoscaling. Enable PITR on `app_data`; define on-demand backup cadence + restore drill.
4. **Rate-limit tuning**: validate 60/min IP and 120/min user under load; adjust buckets to protect auth + matching endpoints without blocking legit burst registration.
5. **Abuse detection hardening**: brute-force thresholds for login + session-code attempts; exponential backoff schedule; temporary ban enforcement; CloudWatch alarm on ban-rate spikes.
6. **Security review**: JWT verification paths, session-code brute-force, IDOR on `GET /sessions/{code}/me` and admin endpoints, SSRF on geocode/ORS client, secrets not logged, DynamoDB encryption at rest, least-privilege IAM roles per Lambda.
7. **Observability pipeline**: CloudWatch Logs → subscription → S3 (30-day lifecycle). Athena tables/glue catalog for: errors, auth failures, latency summaries, notification outcomes, matching runs.
8. **Alarms + dashboards**: CloudWatch dashboards for API latency/error rate, matching duration, email send failures, DynamoDB throttling, ORS quota usage. Alarms → SNS → on-call.
9. **Audit completeness**: verify FR-11 events are all captured and queryable; add alert on audit-write failures.
10. **Production readiness checklist**: runbooks for: matching timeout, email send failure + retry, DynamoDB restore, session cancellation rollback, ORS quota exhaustion (monitor quota usage; alert at 80% of daily limit).

### Frontend (Next.js)
1. **Error handling**: global error boundary, API error toast/inline messaging, retry-on-network-failure for idempotent reads.
2. **Loading + skeleton states**: for registration, matching review, assignment views.
3. **Monitoring hooks**: client-side error reporting to CloudWatch (via Lambda endpoint) for uncaught exceptions; RUM-lite (optional).
4. **Security headers + CSP**: configure via Cloudflare Pages / `next.config.js`; enforce HTTPS, HSTS, secure cookies for the app session.
5. **Accessibility**: keyboard nav, ARIA on forms/maps, color-contrast pass for the core flows.
6. **Performance**: Lighthouse pass on key routes (login, registration, assignment view); bundle size budget; image/font optimization.

## Deliverables
- Load test reports with NFR pass/fail per metric.
- Tuned Lambda concurrency + DynamoDB capacity config.
- Security review report with remediations applied.
- CloudWatch dashboards + alarms wired to on-call.
- Athena queryable log archive (30-day lifecycle).
- Production readiness checklist + runbooks.
- Frontend error handling + observability hooks.

## Validation

> **3-week MVP scope:** Most NFR validation (load tests, Lighthouse, restore drill) is **DEFERRED** to post-MVP. Only the items marked [MVP] below are validated during the MVP timeline.

**MVP (validated during Phases 2–5 / Phase 2 setup):**
- [MVP] CloudWatch → S3 → Athena pipeline queryable (errors/log summaries retrievable via Athena)
- [MVP] Basic JWT validation rejects forged/expired tokens (no alg=none bypass)
- [MVP] IDOR check: user A cannot access user B's registration via `GET /sessions/{code}/me` (→ 403)

**Deferred (post-MVP):**
- NFRs met: p95 API latency < 800ms; matching <30s for 500 users; 5000 req/min burst sustained without 5xx spike; 99.5% availability over a test window (load tests — 6.1)
- Security review: no critical/high findings open at sign-off (6.5)
- Rate limiter blocks abuse patterns without impacting legit users (6.4)
- Email Lambda DLQ drains cleanly; no duplicate emails on replay
- Restore drill: DynamoDB PITR restore to a point in time succeeds in a staging table (6.3)
- Lighthouse: key routes ≥ target scores (6.8)

## Dependencies
- Phases 2–5: the full platform.
- On-call routing target provisioned (SNS → Slack/email).
- AWS cost budget + alerts configured.

## Out of Scope
- Third-party APM (Datadog/Grafana) unless approved.
- External penetration test (unless scoped/budgeted).
- Migration to async matching / OR-Tools (future enhancement).
- New product features (return trips, recurring sessions, live GPS, etc. — Section 19 future enhancements).
- Most of Phase 6 (load testing, security review, abuse detection, frontend polish, restore drill) is deferred to post-MVP for the 3-week timeline.

---

## Task Breakdown

> Tasks are sized S or M. Each task has acceptance criteria, verification steps, dependencies, files likely touched, and a scope estimate.

### Task 6.1: Load testing scripts [DEFERRED]

**Description:** Write load test scripts (k6 or Locust) for: API burst (5000 req/min sustained), registration surge, matching run at 100/300/500 users. Capture p95/p99 latency, error rate, Lambda concurrency, DynamoDB consumed capacity.

**Acceptance criteria:**
- [ ] k6 (or Locust) scripts for API burst, registration surge, matching stress
- [ ] Scripts parameterized for user count and request rate
- [ ] Reports: p95/p99 latency, error rate, Lambda throttling, DynamoDB consumed/throttled
- [ ] Synthetic test data generator for 500-user sessions
- [ ] Results documented in `docs/load_test_results.md`

**Verification:**
- [ ] Manual check: run burst test against staging → NFRs evaluated
- [ ] NFR check: p95 API latency < 800ms
- [ ] NFR check: matching < 30s for 500 users
- [ ] NFR check: 5000 req/min sustained without 5xx spike

**Dependencies:** Phases 2–5 complete

**Files likely touched:**
- `tests/load/api_burst.js`
- `tests/load/registration_surge.js`
- `tests/load/matching_stress.js`
- `tests/load/data_generator.py`
- `docs/load_test_results.md`

**Estimated scope:** M

### Task 6.2: Lambda concurrency + memory tuning [DEFERRED] (basic sizing done in Phase 2)

**Description:** Based on load test results, tune Lambda reserved concurrency to bound cost spikes (Risk table) while meeting burst demand. Right-size memory (256 MB baseline; raise for matching if needed). Verify timeout settings.

**Acceptance criteria:**
- [ ] Reserved concurrency set to bound cost without throttling legit burst
- [ ] Memory right-sized: matching Lambda raised if 256 MB is insufficient
- [ ] Timeout: 5–10s for API, longer for matching if needed (but < 15s Lambda limit)
- [ ] Configuration via IaC (not console)
- [ ] Documented rationale in `docs/lambda_tuning.md`

**Verification:**
- [ ] Manual check: re-run burst test → no throttling with reserved concurrency
- [ ] Manual check: matching at 500 users completes within timeout

**Dependencies:** Task 6.1

**Files likely touched:**
- `infra/lambda-config.ts`
- `docs/lambda_tuning.md`

**Estimated scope:** S

### Task 6.3: DynamoDB capacity + PITR + backup drill [DEFERRED] (PITR enabled in Phase 2; restore drill post-MVP)

**Description:** Finalize DynamoDB capacity mode (on-demand vs provisioned with autoscaling). Confirm PITR on `app_data`. Conduct a restore drill to a staging table to validate RPO/RTO.

**Acceptance criteria:**
- [ ] Capacity mode decision documented (on-demand for bursty, provisioned for predictable)
- [ ] PITR enabled on `app_data`
- [ ] Restore drill: restore `app_data` to a point in time → staging table → verify data integrity
- [ ] On-demand backup cadence defined (if applicable)
- [ ] RPO/RTO targets documented

**Verification:**
- [ ] Manual check: restore to 5 minutes ago → staging table has expected records
- [ ] Manual check: PITR status = ENABLED on `app_data`

**Dependencies:** Task 2.2

**Files likely touched:**
- `infra/dynamodb-config.ts`
- `docs/dynamodb_backup.md`

**Estimated scope:** S

### Task 6.4: Rate-limit tuning + abuse detection hardening [DEFERRED] (basic rate limiting active from Phase 2; abuse detection deferred)

**Description:** Validate rate limits (60/min IP, 120/min user) under load. Tune brute-force thresholds for login + session-code attempts. Configure CloudWatch alarms on ban-rate spikes. Verify exponential backoff schedule.

**Acceptance criteria:**
- [ ] Rate limits validated under load; adjusted if blocking legit burst
- [ ] Brute-force thresholds tuned: login (e.g., 5 failures → 15-min ban), session code (e.g., 10 → 30-min ban)
- [ ] Exponential backoff schedule documented
- [ ] CloudWatch alarm on ban-rate spike (e.g., > 50 bans/hour)
- [ ] Abuse patterns tested: credential stuffing, code brute-force

**Verification:**
- [ ] Manual check: sustained abuse → bans enforced + alarm fires
- [ ] Manual check: legit burst registration not blocked

**Dependencies:** Task 2.8, Task 6.1

**Files likely touched:**
- `app/middleware/rate_limit.py` (tune)
- `app/middleware/abuse_detection.py` (tune)
- `infra/alarms.ts`
- `docs/rate_limit_tuning.md`

**Estimated scope:** S

### Task 6.5: Security review [DEFERRED] (basic JWT/IDOR checks done during Phases 2–5; full review post-MVP)

**Description:** Conduct a security review covering: JWT verification, session-code brute-force resistance, IDOR on `GET /sessions/{code}/me` and admin endpoints, SSRF on geocode/ORS client, secrets not logged, DynamoDB encryption at rest, least-privilege IAM roles per Lambda, CSP headers on frontend.

**Acceptance criteria:**
- [ ] JWT verification: rejects forged/expired tokens (no alg=none bypass)
- [ ] IDOR: user A cannot access user B's registration via `GET /sessions/{code}/me`
- [ ] SSRF: geocode/ORS client cannot be redirected to internal endpoints
- [ ] Secrets: no secrets in code, logs, or error messages
- [ ] DynamoDB encryption at rest enabled
- [ ] IAM: each Lambda has minimal permissions (no wildcard)
- [ ] Frontend: CSP, HSTS, secure cookies enforced
- [ ] Findings documented in `docs/security_review.md` with remediations

**Verification:**
- [ ] Manual check: attempt IDOR → 403
- [ ] Manual check: scan logs for secrets → none found
- [ ] Manual check: IAM policy analyzer → no overly permissive roles

**Dependencies:** Phases 2–5 complete

**Files likely touched:**
- `docs/security_review.md`
- `frontend/next.config.js` (CSP headers)
- `infra/iam-policies.ts` (tighten if needed)

**Estimated scope:** M

### Task 6.6: Observability pipeline (CloudWatch → S3 → Athena) [MVP] — set up during Phase 2, not a hardening sprint

**Description:** Finalize the observability pipeline: CloudWatch Logs subscription → S3 (30-day lifecycle). Athena tables/glue catalog for: errors, auth failures, latency summaries, notification outcomes, matching runs. CloudWatch dashboards + alarms wired to SNS → on-call.

**Acceptance criteria:**
- [ ] CloudWatch Logs subscription filter → S3 bucket with 30-day lifecycle
- [ ] Athena/Glue tables queryable for: errors, auth failures, latency, notifications, matching
- [ ] CloudWatch dashboards: API latency/error rate, matching duration, email send failures, DynamoDB throttling, ORS quota usage
- [ ] Alarms → SNS → on-call routing (Slack/email)
- [ ] Avoid verbose success logging (errors + summaries only per Section 10)

**Verification:**
- [ ] Manual check: query Athena for errors in the last 24h → results returned
- [ ] Manual check: trigger an error → appears in dashboard + alarm fires
- [ ] Manual check: DLQ depth alarm fires when messages accumulate

**Dependencies:** Phases 2–5 complete

**Files likely touched:**
- `infra/observability-stack.ts`
- `infra/dashboards/`
- `docs/observability.md`

**Estimated scope:** M

### Task 6.8: Frontend error handling + monitoring + accessibility [DEFERRED] (basic error boundary [MVP]; accessibility/Lighthouse/bundle deferred)

**Description:** Harden the Next.js frontend: global error boundary, API error toast/inline messaging, retry on network failure for idempotent reads. Client-side error reporting to CloudWatch (via Lambda endpoint). Accessibility pass: keyboard nav, ARIA, color-contrast. Lighthouse performance pass.

**Acceptance criteria:**
- [ ] Global error boundary catches uncaught exceptions → reports to CloudWatch
- [ ] API errors show user-friendly toast/inline messages
- [ ] Idempotent GET requests retry on network failure (max 3)
- [ ] Keyboard navigation works for all core flows (login, registration, matching review)
- [ ] ARIA labels on forms, maps, buttons
- [ ] Color-contrast meets WCAG AA on core flows
- [ ] Lighthouse: key routes ≥ defined thresholds (performance > 90, accessibility > 95)
- [ ] Bundle size budget enforced

**Verification:**
- [ ] Manual check: trigger a frontend error → error boundary + CloudWatch entry
- [ ] Manual check: tab through registration form without mouse
- [ ] Lighthouse audit on login + registration + assignment pages

**Dependencies:** Phases 2–5 complete

**Files likely touched:**
- `frontend/src/app/error.tsx`
- `frontend/src/components/ErrorToast.tsx`
- `frontend/src/lib/error-reporting.ts`
- `frontend/src/app/globals.css` (accessibility)
- `frontend/next.config.js` (bundle budget)

**Estimated scope:** M

### Task 6.9: Production readiness checklist + runbooks [DEFERRED] (minimal checklist [MVP]; full runbooks post-MVP)

**Description:** Compile a production readiness checklist and runbooks for common operational scenarios: matching timeout, email send failure + retry, DynamoDB restore, session cancellation rollback, ORS quota exhaustion.

**Acceptance criteria:**
- [ ] `docs/production_readiness.md` with sign-off checklist (NFRs, security, observability)
- [ ] Runbooks: matching timeout, DLQ drain, DynamoDB restore, ORS quota exhaustion, mass notification failure
- [ ] Each runbook: symptoms, diagnosis steps, resolution, escalation contact
- [ ] NFR sign-off: p95 < 800ms, matching < 30s, 99.5% availability, 5000 req/min burst

**Verification:**
- [ ] Manual check: walk through DLQ drain runbook → messages reprocessed
- [ ] Manual check: all NFR checkboxes signed off

**Dependencies:** All Phase 6 tasks

**Files likely touched:**
- `docs/production_readiness.md`
- `docs/runbooks/*.md`

**Estimated scope:** M

### Checkpoint: End of Phase 6
- [ ] All NFRs met and signed off
- [ ] No critical/high security findings open
- [ ] Observability dashboards live with alarms wired
- [ ] Runbooks tested and accessible
- [ ] ORS free-tier quota monitoring + alarm at 80% verified
- [ ] Lighthouse targets met on key routes
- [ ] **Final review with human before production launch**

### Parallelization notes

> **3-week MVP:** Phase 6 reduces to observability pipeline (done in Phase 2) + basic security checks (inline during Phases 2–5) + minimal readiness checklist. Most tasks below are [DEFERRED] to post-MVP.

- **6.6 (observability)** is set up during Phase 2 (foundational infra), not as a separate hardening sprint.
- Tasks 6.5 (security review), 6.8 (frontend hardening) are [DEFERRED]; basic JWT/IDOR and error-boundary work happen inline during Phases 2–5.
- Task 6.1 (load tests) must precede 6.2, 6.3, 6.4 (tuning tasks) — all [DEFERRED] to post-MVP.
- Task 6.9 (runbooks) depends on all other Phase 6 tasks; only a minimal readiness checklist is [MVP].

### Risks (Phase 6 specific)
| Risk | Impact | Mitigation |
|------|--------|------------|
| Load tests reveal NFR not met | High | Document gap; either fix in this phase or defer to known-limitation; do not launch |
| Security finding discovered late | High | Triage within 48h; critical/high blocks launch |
| ORS free-tier quota exhausted (2000 req/day) during large-session matching | Medium | Monitor daily quota usage via CloudWatch alarm at 80%; cache matrix results per session; haversine pre-filter reduces ORS calls |
| Observability blind spot (missing alarm) | Medium | Failure-mode review per resource; dry-run alarms |
| DynamoDB restore drill corrupts production | Medium | Restore to separate staging table; never overwrite prod |
