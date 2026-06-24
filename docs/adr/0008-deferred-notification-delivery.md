# ADR-0008: Deferred Notification Delivery (SQS → Lambda)

## Status
Accepted

## Date
2026-06-23

## Context
The Phase 1 plan (`plans/phase-1-discovery.md`, "Decisions (locked)") recorded that email
notifications would be sent **synchronously** from the API Lambda via Microsoft Graph
`sendMail` → M365 Exchange. The v2 master spec (§10, §13) describes a fuller SQS →
dedicated email Lambda → DLQ pipeline, but explicitly defers it post-MVP per
`docs/ideas/carpool-mvp-scope.md`.

During Phase 1 open-questions review (OQ-6) the synchronous pattern was rejected because:
- Lambda's 10-second timeout risks being exceeded for sessions with many participants
  when the Graph `sendMail` call fan-out is performed in the request handler.
- The API response is blocked on email delivery, so a transient Microsoft 365 / Graph
  outage degrades the user-visible latency of the approval endpoint and risks
  returning `5xx` even when the approval itself succeeded at the database.
- The admin UX is poor: a partially-completed email fan-out (some sent, some failed)
  cannot be retried without re-running the approval logic.

A new pattern is required that keeps the email pipeline within MVP scope but removes
the synchronous dependency from the API request path.

## Decision
Email delivery is **deferred**. The API Lambda writes `notification_pending` items
to the `app_data` DynamoDB table, keyed by `PK = NOTIF#<date>`, `SK = <timestamp>#<event_id>`.
A separate processor — either an SQS → Lambda consumer or an admin-triggered batch
(`POST /sessions/{code}/admin/notify` with `action: "send"`) — reads pending items
and sends emails via Microsoft Graph `sendMail`. Failed sends are retried with
exponential backoff; after 3 failures, the item is marked `failed` for admin review.

The `POST /sessions/{code}/admin/notify` endpoint gains a dual role:
- Default behavior (`action: "queue"` or omitted) — write `notification_pending` items
  for each recipient derived from `recipient_filter`.
- `action: "send"` — trigger the consumer inline (still asynchronous from the caller's
  perspective; the API returns once the items are enqueued, not once the emails are
  delivered).

The `POST /sessions/{code}/match/approve` endpoint queues one `notification_pending`
item per assigned participant when `notify: true` (the default).

## Alternatives Considered

### Alternative A: Synchronous in-loop (the previously locked decision)
- Pros: simplest mental model; no extra infrastructure; one fewer queue.
- Cons: 10s Lambda timeout risk for large sessions; API response blocked on Graph
  availability; partial-fan-out cannot be cleanly retried. **Rejected.**

### Alternative B: AWS Step Functions
- Pros: visual orchestration; native retries and DLQ; long-running workflows.
- Cons: overkill for a single-step fan-out with per-item retry; another IaC surface;
  cost and complexity not justified for MVP. **Rejected.**

### Alternative C: SQS → Lambda consumer (chosen)
- Pros: serverless-native; per-message retry with exponential backoff via the SQS
  redrive policy and the consumer's own retry counter; the consumer is independently
  scalable from the API; a transient Graph outage does not affect the API. Fits the
  existing architecture (DynamoDB + Lambda + SQS are all in-scope Phase 2 services).
- Cons: adds a queue and a consumer Lambda to provision and monitor; the
  `notification_pending` entity is a new data-model concept; admin visibility into
  "what is pending" requires a new query path. **Accepted.**

## Consequences
- **Positive:** API latency for approval endpoints no longer depends on Graph
  availability; Lambda timeouts no longer risk losing partial fan-out; the system
  can absorb a Microsoft 365 outage without losing notifications.
- **Positive:** A failed send is retried automatically up to 3 times before being
  flagged for admin review, which is a better user experience than the previous
  "admin retries the whole approval" path.
- **Positive:** The full v2 §10/§13 pipeline (SQS + DLQ + dedicated email Lambda)
  is now an incremental upgrade of the same skeleton — Phase 6 hardening can
  promote the inline consumer to a dedicated scheduled consumer without changing
  the data model.
- **Negative:** A new `notification_pending` entity is added to the data model
  (this ERD will be updated in Phase 2). The Phase 2 Terraform workspace must
  provision the SQS queue and DLQ; the Phase 5 implementation must add the
  consumer Lambda and a CloudWatch alarm on `failed` count.
- **Negative:** The `POST /sessions/{code}/admin/notify` endpoint contract gains
  a dual mode (`queue` vs `send`); clients that previously expected a synchronous
  delivery confirmation must adapt to read the response's `notifications_pending`
  field.
- **Neutral:** The fan-out write is still bounded by the number of recipients
  × per-recipient write units in DynamoDB; for very large sessions (>300 users)
  this should be batched with `BatchWriteItem`, which the implementation must handle
  in Phase 5.

## Links
- `plans/phase-1-discovery.md` — Decisions section, "Email delivery" line (now
  reflects this decision; the previous "synchronous" wording is superseded).
- `docs/requirements_baseline.md` §4 OQ-6 (Resolved) and §2 FR-10 clarification (a).
- `docs/api_contracts.md` §3.11 `POST /sessions/{code}/match/approve`,
  §3.13 `POST /sessions/{code}/admin/notify`, and §4 Pydantic stubs.
- `docs/functional_requirements_and_architecture.md` §10 (email pipeline) and §13
  (large-session async patterns).
