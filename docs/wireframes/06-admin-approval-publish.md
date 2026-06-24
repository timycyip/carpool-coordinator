# Wireframe 06 — Admin Approval + Publish

## Screen name & route
- **Route (Next.js App Router):** `app/(app)/sessions/[code]/admin/approve/page.tsx`
  (or a modal on `/admin?tab=matching` — listed separately here per Phase 1 plan).
- **URL examples:** `/sessions/ABC123/admin/approve?version=2`
- **Backed by:** Cloudflare Pages → same-origin `/api/sessions/ABC123/*` (per ADR-0004).

## Purpose
Allow the Session Admin to review the proposed match one last time, approve a
specific match version, and trigger the participant notification fan-out (FR-7,
FR-10). After approval, the match becomes visible to assigned participants per
FR-9 visibility rules.

## User role(s)
- **Session Admin** of the session, or
- **Manager / Superuser** (override).

## Wireframe

```
┌──────────────────────────────────────────────────────────┐
│  [Logo]     Church Carpool · ABC123         [Avatar ▾]   │
├──────────────────────────────────────────────────────────┤
│  ← Back to admin console                                 │
│                                                          │
│  Approve & publish match                                 │
│  ─────────────────────────────────────────────────────   │
│                                                          │
│  ┌── Match version ──────────────────────────────────┐   │
│  │  Version:  V2 (latest)        Run at: 2026-06-26  │   │
│  │  Status:   [ Matching Proposed ]                  │   │
│  │  Computed: 30 km total detour · p95 wait 6 min   │   │
│  │  Drivers:  12   Passengers: 18 (17 assigned)     │   │
│  │  Unassigned: 1 (Theo Z.)                         │   │
│  │  [ View full match table → ]                     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Pre-approval checks ─────────────────────────────┐  │
│  │  ✓ Registration is closed                         │  │
│  │  ✓ No hard constraints violated                   │  │
│  │  ✓ All drivers have at least one assigned stop    │  │
│  │  ⚠  1 passenger unassigned — notification copy:   │  │
│  │     "We could not match you. Please contact the   │  │
│  │      admin at admin@…"                            │  │
│  │  [ Edit notification copy ]                       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌── Who will be notified on publish ─────────────────┐  │
│  │  • 12 drivers — "You have N passenger(s)…"        │  │
│  │  • 17 assigned passengers — "Your driver is…"      │  │
│  │  • 1 unassigned passenger — "We could not match…"  │  │
│  │  Channel: [ Email ▾ ]  (SMS / push: future)       │  │
│  │  [ Preview email templates ]                      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌── Approve controls ────────────────────────────────┐  │
│  │  [ Cancel ]      [ Approve only ]                  │  │
│  │  [ Approve & publish now ▶ ]   ← primary button   │  │
│  │  By approving, the match is locked to this        │  │
│  │  version. Subsequent admin edits will require a   │  │
│  │  new match run or a manual override.              │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  Footer                                                  │
└──────────────────────────────────────────────────────────┘
```

### State: approve success
```
┌──────────────────────────────────────────────────────────┐
│  ✓ Match V2 approved at 2026-06-26 21:33 by you          │
│  Notifications queued: 30 pending. You will be notified   │
│  when delivery completes.                                │
│  Unassigned passenger Theo Z. — queued separately.       │
│  Session status: [ Approved ]                            │
│                                                          │
│  ┌── Notification status ────────────────────────────┐   │
│  │  Queued: 30   Sent: 0   Failed: 0                │   │
│  │  [ Refresh ]   [ Retry failed ]                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  [ View audit log ]   [ Back to admin console ]          │
└──────────────────────────────────────────────────────────┘
```

## Components
- `MatchVersionCard` — version, run timestamp, summary metrics, "view full table"
  link (routes back to Wireframe 05 with `?tab=matching`).
- `PreApprovalChecklist` — green check / amber warning items, each with details
  on hover.
- `UnassignedNoticeEditor` — inline textarea for the unassigned-passenger email
  copy; persisted to the match record.
- `NotificationPreviewList` — three rows (drivers / assigned passengers /
  unassigned passengers) with channel dropdown + "Preview template" modal link.
- `ApproveControls` — `Cancel` (returns to admin console), `Approve only` (locks
  version, does not send), `Approve & publish` (primary).
- `ConfirmDialog` for `Approve & publish now` (irreversible for participants;
  changes after this point trigger re-notification per FR-8).
- `SuccessPanel` shown after approve.
- `Toast` + `InlineAlert` for errors.

## Data bindings
- **API (read):** `GET /api/sessions/{code}` — current status (must be
  `Matching Proposed` to render primary button).
- **API (read):** `GET /api/sessions/{code}/match?version=2` — full proposed
  match for the version card and pre-approval checklist (unassigned list, metric
  rollups).
- **API (read):** `GET /api/sessions/{code}/registrations?role=…` — used by
  `NotificationPreviewList` to enumerate recipients.
- **API (write):** `PATCH /api/sessions/{code}/match/manual` to persist an
  edited unassigned-notice copy before approving.
- **API (write):** `POST /api/sessions/{code}/match/approve` with body:
  ```json
  {
    "version": 2,
    "publish": true
  }
  ```
  - Server sets session `status = "approved"`.
  - When `publish: true`, the approved match is immediately visible to assigned
    participants (FR-9) AND one `notification_pending` item is written per
    affected participant (per ADR-0008 — deferred delivery).
  - The response includes `publish: true` and `notifications_queued: 30` (count
    of items written to the queue). The success panel polls
    `GET /api/sessions/{code}/notifications` for the aggregated delivery report
    (queued / sent / failed counts).
- **API (write):** `POST /api/sessions/{code}/admin/notify` — explicit re-send
  or queued-batch send (used by post-approval manual overrides per FR-8 and the
  success-panel "Retry failed" button). Body includes `action: "send"` to drain
  pending items or `action: "resend"` to re-queue previously failed items.
- **Auth + RBAC:** only session-scoped admins (or higher). Backend double-checks.

## Interactions
1. **Mount** — fetch session + match V(`?version` or `latest`) in parallel; run
   pre-approval checks client-side (soft validation — server is the source of
   truth).
2. **Edit unassigned notice copy** — autosave on blur via
   `PATCH …/match/manual` with `op=edit_unassigned_copy`.
3. **Change channel** — currently only `email` is selectable; dropdown is locked
   with a "Coming soon" tooltip on SMS / WhatsApp / push per FR-10 future scope.
4. **Preview templates** — opens a modal with the templated email body for each
   role (driver, assigned passenger, unassigned passenger), showing merge fields
   resolved with the actual data.
5. **Click "Approve only"** — confirm dialog → `POST …/match/approve` with
   `publish: false`; session status → `approved`; success panel: "Match locked.
   Use 'Notify participants' when ready."
6. **Click "Approve & publish now"** — confirm dialog → `POST …/match/approve`
   with `publish: true`; success panel shows queued count and a refresh button
   polling the delivery report; failures surface in a per-recipient retry list
   that triggers `POST /api/sessions/{code}/admin/notify` with
   `action: "send"`.
7. **Cancel** — back to `/sessions/ABC123/admin?tab=matching`; no API call.
8. **Post-approval redirect** — clicking "Back to admin console" returns to
   Wireframe 05, which now shows the match in read-only-approved mode with a
   "Make changes (creates override)" button (FR-8).

## Empty / loading / error states
- **Loading:** skeleton version card, checklist skeletons.
- **Empty — no match yet:** full-page empty state with CTA "Run matching first"
  → `/sessions/ABC123/admin?tab=matching`.
- **Error — wrong status (e.g., already Approved):** banner "This session has
  already been approved. Use the override flow to make changes." Replaces
  primary buttons with a single "Go to override" link.
- **Error — version mismatch (409):** banner "The latest match version changed
  since you opened this page. [Refresh]" — fetches the new version on confirm.
- **Error — partial notification failure:** success panel's "Notification
  status" section highlights failed recipients; the "Retry failed" button
  triggers `POST /api/sessions/{code}/admin/notify` with `action: "send"`.
- **Error — pre-approval check failed (hard constraint):** primary buttons
  disabled; checklist row expands to show which driver / passenger is the
  blocker; link to the match table at the offending row.
- **Audit log link:** always visible at the bottom; routes to
  `/sessions/ABC123/admin?tab=audit` (FR-11).
