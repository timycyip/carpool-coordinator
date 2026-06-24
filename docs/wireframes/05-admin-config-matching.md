# Wireframe 05 — Admin Session Config + Matching Review/Edit

## Screen name & route
- **Route (Next.js App Router):** `app/(app)/sessions/[code]/admin/page.tsx`
- **URL examples:** `/sessions/ABC123/admin`, `/sessions/ABC123/admin?tab=matching`
- **Backed by:** Cloudflare Pages → same-origin `/api/sessions/ABC123/*`
  (per ADR-0004).

## Purpose
Single console for the Session Admin to (a) configure session attributes, (b) see
the registration status of drivers and passengers, (c) trigger the matching
algorithm, and (d) review and manually edit the proposed match before approval
(FR-7, FR-8). Edit controls enforce FR-8 (move, unassign, lock).

## User role(s)
- **Session Admin** of the session (FR-1 §4.2.2), or
- **Manager / Superuser** (Section 4 — implicit global override).

## Wireframe

```
┌──────────────────────────────────────────────────────────┐
│  [Logo]     Church Carpool · ABC123         [Avatar ▾]   │
├──────────────────────────────────────────────────────────┤
│  Admin console                                           │
│  Tabs: [ Config ] [ Registrations ] [ Matching * ] [ Audit ] │
│  Status pill: [ Matching Proposed ]   V2 (latest)        │
│  ─────────────────────────────────────────────────────   │
│                                                          │
│  TAB = Matching (default after first match run)          │
│                                                          │
│  ┌── Run + summary ──────────────────────────────────┐   │
│  │  Last run: 2026-06-26 21:14 by admin@… (V2)       │   │
│  │  Total: 12 drivers, 18 passengers, 30 seats      │   │
│  │  Assigned: 17 / 18   Unassigned: 1                │   │
│  │  Total detour: 41 km  ·  p95 pickup wait: 6 min   │   │
│  │  [ Re-run matching ]  [ Approve match → ]         │   │
│  │  [ Notify participants ]   (enabled after approve)│   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Proposed match (V2) — table view ───────────────┐   │
│  │ Driver             Pickup order          Edit    │   │
│  │ ────────────── ──────────────────────── ──────── │   │
│  │ Jane D. (3 seats)                           ⋮     │   │
│  │   1. Alice P.    08:35  L5N 1A2                  │   │
│  │   2. Bob M.      08:42  L5N 2B1                  │   │
│  │   3. —                                         │   │
│  │ [ Move passenger ]  [ Unassign ]  [ Lock row 🔒 ] │   │
│  │ ────────────── ──────────────────────── ──────── │   │
│  │ Sam K. (4 seats)                                 │   │
│  │   1. Lin H.     08:30  L5N 1A2                   │   │
│  │   2. Pia R.     08:50  L5N 3C2                   │   │
│  │ …                                                │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Unassigned (1) ────────────────────────────────┐    │
│  │ Theo Z.  L5N 9Z9  08:55                          │    │
│  │ Reason: "No driver with overlapping window"      │    │
│  │ [ Manually assign… ]                             │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Tabs continue:                                          │
│   [ Config ] [ Registrations ] [ Audit ]                 │
└──────────────────────────────────────────────────────────┘
```

### Tab = Config
```
┌── Config ──────────────────────────────────────────────┐
│ Title *           [ Church Carpool               ]     │
│ Description       [ ___ multi-line ___           ]     │
│ Trip mode *       (•) TO_DESTINATION  ( ) FROM_ORIGIN  │
│ Anchor (dest/orig) postal: [ _____ ] [Resolve] ◉ map   │
│ Earliest pickup * [ 2026-06-27 08:30 ]                 │
│ Latest arrival *  [ 2026-06-27 09:30 ]                 │
│ Registration deadline * [ 2026-06-27 18:00 ]           │
│ Status *          [ Registration Open ▾ ]               │
│                                                       │
│ [ Save ] [ Open registration ] [ Close registration ]  │
└───────────────────────────────────────────────────────┘
```

### Tab = Registrations
```
┌── Registrations (12 drivers / 18 passengers) ─────────┐
│ Tabs: [ Drivers (12) ] [ Passengers (18) ]            │
│ Search [____]   Filter [ Unassigned only ☐ ]          │
│ ┌──────────────────────────────────────────────────┐  │
│ │ Name        Postal   Pickup window   Status     │  │
│ │ Jane D.     L5N 1A2  08:30–09:00      Driver     │  │
│ │ Sam K.      L5N 2B1  08:15–08:45      Driver     │  │
│ │ Alice P.    L5N 1A2  08:35–08:55      Passenger  │  │
│ │ …                                               │  │
│ └──────────────────────────────────────────────────┘  │
│ [ Export CSV ]                                        │
└──────────────────────────────────────────────────────┘
```

## Components
- `AdminTabs` — `Config`, `Registrations`, `Matching`, `Audit` (active tab in URL).
- `SessionConfigForm` — title, description, trip mode radio, anchor postal +
  resolve button (calls `GET /api/geocode`), time pickers, status select.
- `RunSummaryCard` — match version, totals, assignment counts, aggregate metrics,
  primary action buttons.
- `MatchTable` — rows = drivers (collapsible), each row shows assigned passengers
  in pickup order with timestamp + postal; per-row action menu.
- `RowActionMenu` — `Move passenger…`, `Unassign`, `Lock row`, `Edit pickup time`.
- `MovePassengerModal` — searchable driver list, drag-to-reorder pickup order,
  confirms with `PATCH /api/sessions/{code}/match/manual`.
- `UnassignedList` — separate panel with reason text + manual-assign action.
- `MatchVersionSwitcher` — compare V1 vs V2 etc. (FR-7: each run writes a new
  versioned `MATCH#V{n}`).
- `Toast` / `InlineAlert` for success and error feedback.
- `ConfirmDialog` — required for "Re-run matching" (warns current proposed match
  will be archived but unchanged locked rows are preserved per FR-8).

## Data bindings
- **API (read):** `GET /api/sessions/{code}` — config + status; `app_data`
  `PK = SESSION#ABC123`.
- **API (read):** `GET /api/sessions/{code}/registrations` — registrations
  (`registrations-by-session` access pattern); powers both Registrations tab and
  the matching summary counts.
- **API (read):** `GET /api/sessions/{code}/match?version={n}` — the proposed
  match (`MATCH#V{n}` item); supports `version=latest`.
- **API (write):** `PATCH /api/sessions/{code}` — saves the Config tab fields.
  Body conforms to the API contracts schema.
- **API (write):** `POST /api/sessions/{code}/match/run` — kicks off matching;
  returns `202 Accepted` with a job id; poll or websocket for completion
  (large sessions may run async per §13).
- **API (write):** `PATCH /api/sessions/{code}/match/manual` — applies FR-8 edits
  (move, unassign, lock, reorder). Body:
  ```json
  {
    "version": 2,
    "ops": [
      { "op": "move", "passenger_sub": "user_…", "to_driver_sub": "user_…" },
      { "op": "unassign", "passenger_sub": "user_…" },
      { "op": "lock", "driver_sub": "user_…", "locked": true }
    ]
  }
  ```
- **Auth + RBAC:** only users with `admin` (or higher) role for this session can
  hit any of these endpoints; backend enforces, but UI hides controls for
  non-admins.

## Interactions
1. **On mount** — fetch session, registrations, and latest match in parallel;
   land on the active tab from `?tab=…` (default = Matching once V1 exists).
2. **Save config** — `PATCH /api/sessions/{code}`; toast "Saved."; status pill
   updates on success.
3. **Open / close registration** — `PATCH /api/sessions/{code}` with `status`
   change; confirm dialog (closing registration is irreversible for users).
4. **Click "Re-run matching"** — confirm → `POST /api/sessions/{code}/match/run`;
   show progress indicator; on completion refresh match table; locked drivers are
   preserved per FR-8.
5. **Move passenger** — open modal, select target driver, set pickup position →
   `PATCH …/match/manual` with `op=move`; row re-renders optimistically.
6. **Unassign passenger** — confirm dialog → `PATCH …/match/manual` with
   `op=unassign`; passenger moves to the Unassigned panel.
7. **Lock row** — `PATCH …/match/manual` with `op=lock`; row gets 🔒 badge; locked
   rows are preserved on re-runs.
8. **Switch match version** — fetches `MATCH#V{n-1}` for side-by-side compare;
   switch back via tab.
9. **Approve match** — button enabled only when `status == 'Matching Proposed'`
   and at least one driver has assignments; routes to Wireframe 06
   (`/sessions/ABC123/admin/approve`).

## Empty / loading / error states
- **Loading (any tab):** skeleton table + skeleton summary.
- **Empty — no match yet:** "No match has been run. Click 'Run matching' to
  generate a proposal." Run button enabled only when registrations exist.
- **Empty — no registrations:** Run button disabled with tooltip "Need at least
  1 driver and 1 passenger to match."
- **Error — match run failed (5xx):** InlineAlert: "Matching failed. [Retry]" +
  link to last CloudWatch log id (SRE).
- **Error — manual edit conflict (409):** optimistic update rolls back, toast
  "Someone else edited this match. Refresh to see the latest."
- **Error — locked by another admin:** banner with their name + "Read-only" mode
  for non-conflicting controls.
- **Empty — unassigned panel:** panel hidden when zero unassigned.
- **Audit tab:** empty state "No audit entries yet."
