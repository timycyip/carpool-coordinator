# Phase 5 — Approval & Notification Plan

Builds on Phase 4 (proposed, editable matches). Goal: admin approves a match version, it becomes visible to assigned participants, email notifications are sent synchronously from the API Lambda via M365 Exchange, and all actions are audit-logged.

## Open Questions (to refine)
- [ ] M365 Exchange integration method: Microsoft Graph `sendMail` (OAuth client credentials) vs SMTP relay to Exchange Online? Graph is recommended; confirm app registration + mailbox/sender address.
- [ ] Sender address: a shared service mailbox (e.g., carpool@org.com) or per-session sender? Recommend shared service mailbox.
- [ ] Post-approval edits: require re-approval or auto-publish with notification only? Recommend auto-publish + notification (matches FR-8 "changes after approval trigger notification").
- [ ] Email templates: HTML or plain text? Who owns copy/content?
- [ ] Should participants be able to acknowledge/RSVP via the app, or is email one-way? MVP: one-way.

## Goal
Close the loop: approve → publish → notify → log. Email is sent synchronously from the API Lambda via M365 Exchange (Microsoft Graph `sendMail`). On failure: log to CloudWatch, return error to admin, allow manual retry.

## Decisions (locked)
- Approval workflow (FR-7): `Matching Proposed → admin review → admin edits (optional) → admin approves → publish`.
- Pre-approval: proposed match hidden from drivers/passengers. Post-approval: visible to assigned users only (FR-9).
- Post-approval edits allowed (FR-8) and trigger notifications.
- Email delivery: synchronous send from API Lambda via Microsoft Graph `sendMail` (M365 Exchange). No SQS queue, no separate email Lambda. On failure: log to CloudWatch, return error to admin, allow manual retry.
- Notifications (FR-10, MVP): registration success, matching approved, match changed, session cancelled.
- Audit logging (FR-11): login attempts, auth failures, session changes, matching approvals, admin overrides.
- Idempotent sends keyed by event ID + recipient; on failure log to CloudWatch, return error to admin, allow manual retry.

## Tasks (ordered)

### Backend
1. **Approval API**: `POST /sessions/{code}/match/approve` (Session Admin) — promotes a specific match version to `Approved`, transitions session `Matching Proposed → Approved`. Enforce single approved version per session; prior approved versions archived.
2. **Publish service**: `app/services/publish.py` — on approval, compute per-participant visibility and write read-optimized views (driver sees own passengers + route; passenger sees own driver + route summary). Enforce FR-9 visibility matrix.
3. **Post-approval edit**: `PATCH /sessions/{code}/match/manual` after approval allowed; each change writes a new match version delta + sends a `match_changed` email synchronously.
4. **Session cancel**: `POST /sessions/{code}/cancel` (Admin/Manager/Superuser) — transitions to `Closed`/cancelled + sends `session_cancelled` email synchronously to all registered participants via Graph.
5. **Notification service**: on approval / change / cancel, the API Lambda sends email synchronously via Graph `sendMail` to affected participants. Idempotency key = event ID + recipient.
6. **Synchronous email send**: on approval/change/cancel, the API Lambda renders the email template per event type and sends via M365 Exchange (Graph `sendMail`) directly for each affected participant. On failure → log to CloudWatch, record failed recipients, return partial-success error to admin, allow manual retry.
7. **M365 Exchange integration**: app registration (client credentials), sender service mailbox, Graph `sendMail` permissions (`Mail.Send`). Implemented in the API Lambda (`app/services/email.py`). Secrets in Parameter Store; token caching.
8. **Email templates**: per-event templates (registration success, matching approved, match changed, session cancelled) with participant name, session title, assignment summary, and a deep link to the app.
9. **Audit logging**: `app/middleware/audit.py` (from Phase 2) extended to capture matching approvals, manual overrides (pre- and post-approval), session cancellations, and notification send/failure outcomes.
10. **Admin notify API** [DEFERRED]: `POST /sessions/{code}/admin/notify` (Admin) — send a free-text message to session participants via synchronous Graph send. _Deferred for 3-week MVP. Only the 4 event-driven email types are in scope._
11. **Audit API**: `GET /audit` (Superuser) — queryable audit log with filters (date range, event type, session, actor).

### Frontend (Next.js)
1. **Admin approval screen**: review final proposed match → "Approve & Publish" action with confirmation. Status badge transitions to `Approved`.
2. **Post-approval edit UI**: allow edits with a banner "changes will notify affected participants"; one email sent per edit (admin can throttle their own edits).
3. **Participant assignment view**: driver sees assigned passengers + route; passenger sees assigned driver + pickup window + route summary. Visible only after approval.
4. **Session cancel UI**: admin action with confirmation → participants notified.
5. **Admin notify composer** [DEFERRED]: free-text message form → preview → send. _Deferred for 3-week MVP._
6. **Email content preview** [DEFERRED]: optional admin preview of rendered email templates before/after sending.
7. **Superuser audit log viewer**: paginated, filterable table of audit events.

## Deliverables
- Approval + publish APIs enforcing the visibility matrix.
- Synchronous email send from the API Lambda via M365 Exchange (no SQS, no separate Lambda).
- Email templates for the four MVP event types.
- Participant assignment views (driver + passenger).
- Audit log queryable via API + UI.

## Validation
- Pre-approval: a driver/passenger calling `GET /sessions/{code}/match` → 403/empty.
- Post-approval: driver sees only their own passengers; passenger sees only their own driver (FR-9).
- Approving a second version archives the prior approved version; only one active.
- Post-approval edit sends email synchronously; affected participants receive an email within seconds.
- Email send failure → logged to CloudWatch, admin sees failed-recipient list, manual retry succeeds.
- No duplicate emails on retry (event ID + recipient idempotency key).
- Audit log entry written for: approval, every manual override, cancellation, and notification send/fail.
- `GET /audit` returns only Superuser-accessible records; others → 403.

## Dependencies
- Phase 4: proposed matches + manual override service.
- Phase 2: RBAC, audit middleware, DynamoDB.
- M365 Exchange app registration + sender mailbox + Graph permissions provisioned.
- Lambda timeout risk for large fan-out: emailing 200+ participants synchronously may exceed Lambda 10s timeout — validate fan-out strategy (batch sends across multiple invocations or accept partial send + admin retry).

## Out of Scope
- SMS / WhatsApp / push notifications (future per FR-10).
- In-app real-time chat (future enhancement).
- Participant RSVP / acknowledgment flow (future).
- Load testing + security review (Phase 6).

---

## Task Breakdown

> Tasks are sized S or M. Each task has acceptance criteria, verification steps, dependencies, files likely touched, and a scope estimate.

### Task 5.1: Approval API + publish service [MVP]

**Description:** Implement `POST /sessions/{code}/match/approve` (Session Admin). Promotes a specific match version to Approved, transitions session to Approved status. On approval, computes per-participant visibility and writes read-optimized views (driver sees own passengers + route; passenger sees own driver + route summary). Enforces FR-9 visibility matrix.

**Acceptance criteria:**
- [ ] `POST /sessions/{code}/match/approve` promotes match version to Approved
- [ ] Only one approved version per session; prior approved versions archived
- [ ] Session status transitions: Matching Proposed → Approved
- [ ] Publish service writes per-participant view: driver → own passengers + route; passenger → own driver + pickup window
- [ ] Pre-approval: driver/passenger `GET /sessions/{code}/match` → 403
- [ ] Post-approval: driver sees only own passengers; passenger sees only own driver (FR-9)

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_approval.py -v`
- [ ] Manual check: approve a match, verify driver sees own passengers only
- [ ] Manual check: passenger cannot see other passengers or other drivers

**Dependencies:** Task 4.6

**Files likely touched:**
- `app/api/matching.py` (extend)
- `app/services/publish.py`
- `tests/api/test_approval.py`

**Estimated scope:** M

### Task 5.2: Synchronous email service [MVP]

**Description:** Implement synchronous email sending from the API Lambda. On approval/match-change/cancel, the API Lambda calls Microsoft Graph `sendMail` directly for each affected participant. On failure: log to CloudWatch, record the failed-recipient list, return partial-success error to admin, allow manual retry.

**Acceptance criteria:**
- [ ] Email send called synchronously within the API request for each affected participant
- [ ] Failed sends logged with recipient + reason to CloudWatch
- [ ] Admin can trigger a retry of failed sends via a UI action
- [ ] No SQS queue or separate Lambda
- [ ] Idempotency: re-sending to a participant who already received the same event is skipped (event ID + recipient key)

**Verification:**
- [ ] Manual check: approve a match → emails sent synchronously → participants receive within seconds
- [ ] Manual check: force a Graph API failure → error logged, admin sees failed recipients, retry succeeds

**Dependencies:** Task 5.1

**Files likely touched:**
- `app/services/email.py`
- `app/services/notification.py`
- `tests/services/test_email.py`

**Estimated scope:** M

### Task 5.3: M365 Exchange integration [MVP]

**Description:** Configure M365 Exchange integration: app registration (client credentials), sender service mailbox, Microsoft Graph `sendMail` permission. Implement the Graph client in the API Lambda (`app/services/email.py`). Store secrets in AWS Parameter Store; token caching to avoid re-auth on every send.

**Acceptance criteria:**
- [ ] Azure AD app registration with client credentials flow
- [ ] Graph `Mail.Send` permission granted for sender mailbox
- [ ] API Lambda acquires token via client credentials, calls Graph `sendMail`
- [ ] Sender address configurable (shared service mailbox)
- [ ] Secrets (client ID, client secret, tenant ID) in Parameter Store, not hardcoded
- [ ] Token caching to avoid re-auth on every send

**Verification:**
- [ ] Manual check: trigger a notification → email delivered to participant's inbox
- [ ] Manual check: invalid credentials → API Lambda logs auth error to CloudWatch
- [ ] Manual check: verify email `From` address is the service mailbox

**Dependencies:** Task 5.2

**Files likely touched:**
- `app/services/email.py`
- `infra/parameter-store.ts`

**Estimated scope:** S

### Task 5.4: Email templates [MVP]

**Description:** Create per-event email templates: registration success, matching approved, match changed, session cancelled. Templates include participant name, session title, assignment summary, and a deep link to the app.

**Acceptance criteria:**
- [ ] 4 templates: `registration_success`, `matching_approved`, `match_changed`, `session_cancelled`
- [ ] Each template includes: participant name, session title, relevant details, deep link
- [ ] Templates render with Jinja2 or equivalent
- [ ] `matching_approved`: lists driver's passengers or passenger's driver + pickup time
- [ ] `match_changed`: describes what changed (old → new assignment)
- [ ] Templates tested with sample data

**Verification:**
- [ ] Tests pass: `pytest tests/services/test_email_templates.py -v`
- [ ] Manual check: render each template with sample data, verify content

**Dependencies:** Task 5.2

**Files likely touched:**
- `app/services/email_templates/registration_success.html`
- `app/services/email_templates/matching_approved.html`
- `app/services/email_templates/match_changed.html`
- `app/services/email_templates/session_cancelled.html`
- `tests/services/test_email_templates.py`

**Estimated scope:** S

### Task 5.5: Post-approval edit + notifications [MVP]

**Description:** Allow admins to edit matches after approval (FR-8). Each post-approval change writes a new match version delta and sends a `match_changed` email synchronously via Graph to affected participants. If multiple edits happen, send one email per edit; admin can throttle their own edits.

**Acceptance criteria:**
- [ ] `PATCH /sessions/{code}/match/manual` works after approval (not just before)
- [ ] Each post-approval change writes a new match version with delta metadata
- [ ] `match_changed` email sent synchronously via Graph for affected participants
- [ ] One email sent per edit (no debounce window); admin can throttle their own edits
- [ ] Publish service re-computes visibility views on each change
- [ ] Audit log records every post-approval override

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_post_approval_edit.py -v`
- [ ] Manual check: edit after approval → affected participants receive email
- [ ] Manual check: 3 quick edits → one email per edit per participant (no debounce)

**Dependencies:** Task 4.7, Task 5.1, Task 5.2

**Files likely touched:**
- `app/services/override.py` (extend)
- `app/services/notification.py` (extend)
- `tests/api/test_post_approval_edit.py`

**Estimated scope:** M

### Task 5.6: Session cancel + notifications [MVP]

**Description:** Implement `POST /sessions/{code}/cancel` (Admin/Manager/Superuser). Transitions session to Closed/Cancelled and sends `session_cancelled` email synchronously to all registered participants via Graph.

**Acceptance criteria:**
- [ ] `POST /sessions/{code}/cancel` transitions session to Cancelled/Closed
- [ ] `session_cancelled` email sent synchronously via Graph to all registered participants
- [ ] Cancellation blocked if session already Closed
- [ ] Audit log entry written with actor + reason
- [ ] Frontend admin UI has cancel action with confirmation dialog

**Verification:**
- [ ] Tests pass: `pytest tests/api/test_cancel.py -v`
- [ ] Manual check: cancel session → all participants receive email
- [ ] Manual check: cancel already-closed session → 409

**Dependencies:** Task 5.2

**Files likely touched:**
- `app/api/sessions.py` (extend)
- `app/services/session.py` (extend)
- `tests/api/test_cancel.py`

**Estimated scope:** S

### Task 5.7: Participant assignment views (frontend) [MVP]

**Description:** Build the post-approval participant views: driver sees assigned passengers + route; passenger sees assigned driver + pickup window + route summary. Visible only after approval.

**Acceptance criteria:**
- [ ] Driver view: assigned passengers (names, pickup locations on map), full route polyline, departure time
- [ ] Passenger view: assigned driver name, pickup time window, route summary to destination
- [ ] Both views show session title + deep link to share
- [ ] Pre-approval: view shows "Matching in progress" placeholder
- [ ] No visibility into other drivers' passengers or other passengers' drivers (FR-9)

**Verification:**
- [ ] Manual check: driver logs in post-approval → sees own passengers + route
- [ ] Manual check: passenger logs in post-approval → sees own driver + pickup time
- [ ] Manual check: pre-approval → "Matching in progress"

**Dependencies:** Task 5.1, Task 3.3 (route map)

**Files likely touched:**
- `frontend/src/app/sessions/[code]/assignment/page.tsx`
- `frontend/src/components/DriverAssignment.tsx`
- `frontend/src/components/PassengerAssignment.tsx`

**Estimated scope:** M

### Task 5.8: Admin notify composer (frontend) [DEFERRED]

**Description:** Build the admin free-text notification composer: `POST /sessions/{code}/admin/notify`. Admin writes a message, previews, and sends to all session participants via synchronous Graph send. _Deferred for 3-week MVP. Only the 4 event-driven email types are in scope._

**Acceptance criteria:**
- [ ] Text area for free-text message with character count
- [ ] Preview of rendered email before sending
- [ ] Send button calls `POST /sessions/{code}/admin/notify`
- [ ] Confirmation after send with recipient count
- [ ] Only Session Admin/Manager/Superuser can access

**Verification:**
- [ ] Manual check: compose message, preview, send → participants receive email
- [ ] Manual check: non-admin → 403

**Dependencies:** Task 5.2, Task 2.4

**Files likely touched:**
- `frontend/src/app/sessions/[code]/admin/notify/page.tsx`
- `frontend/src/components/NotifyComposer.tsx`

**Estimated scope:** S

### Task 5.9: Superuser audit log viewer (frontend) [MVP]

**Description:** Build the Superuser audit log viewer: `GET /audit` rendered as a paginated, filterable table. Filters: date range, event type, session code, actor.

**Acceptance criteria:**
- [ ] Paginated table: timestamp, actor, action, resource, IP, result
- [ ] Filters: date range picker, event type dropdown, session code search, actor search
- [ ] Only Superuser can access (RBAC enforced)
- [ ] Export to CSV (optional, time-permitting)

**Verification:**
- [ ] Manual check: Superuser views audit log, filters by event type
- [ ] Manual check: non-Superuser → 403

**Dependencies:** Task 2.9

**Files likely touched:**
- `frontend/src/app/audit/page.tsx`
- `frontend/src/components/AuditLogTable.tsx`

**Estimated scope:** S

### Checkpoint: End of Phase 5
- [ ] All tests pass
- [ ] Admin can approve a match; participants see assignments + receive email
- [ ] Post-approval edits trigger notifications
- [ ] Session cancel triggers notifications
- [ ] Audit log queryable via UI
- [ ] **Review with human before proceeding to Phase 6**

### Parallelization notes
- Task 5.1 (approval + publish) is the foundation; Tasks 5.5, 5.6, 5.7 depend on it.
- Task 5.2 (synchronous email service) and Task 5.3 (M365) are sequential.
- Task 5.4 (email templates) can be built in parallel with 5.3 (M365 integration) since rendering is decoupled from transport.
- Tasks 5.7 and 5.9 are independent UI tasks that can run in parallel. Task 5.8 (admin notify composer) is deferred.

### Risks (Phase 5 specific)
| Risk | Impact | Mitigation |
|------|--------|------------|
| M365 Graph auth failure blocks all notifications | High | Token caching; alert on auth errors; admin can retry failed sends |
| Duplicate emails on retry | Medium | Idempotency key (event ID + recipient) checked before send |
| Visibility leak in publish service (FR-9) | High | Server-side filter unit-tested per role; never return cross-participant data |
| Lambda timeout on large fan-out (200+ participants) | Medium | Validate fan-out strategy: batch sends across multiple invocations or accept partial send + admin retry |
