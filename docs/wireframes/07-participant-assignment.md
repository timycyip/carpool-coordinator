# Wireframe 07 — Participant "My Assignment" View

> **Phase scope: Phase 5 (Approval & Notification).** This wireframe depends on
> `GET /sessions/{code}/match` (approved version) and `GET /sessions/{code}/assignment`
> — both unavailable until Phase 4 (matching engine) and Phase 5 (approval workflow)
> are complete. Included here as a Phase 1 design reference; do not implement in Phase 2.

## Screen name & route
- **Route (Next.js App Router):** `app/(app)/sessions/[code]/me/page.tsx`
- **URL examples:** `/sessions/ABC123/me`
- **Backed by:** Cloudflare Pages → same-origin `/api/sessions/ABC123/me` and
  `/api/sessions/ABC123/match` (role-filtered per FR-9) — per ADR-0004.

## Purpose
Show a participant the information they need to complete the carpool ride, in
strict accordance with FR-9 visibility rules. The screen is read-only and
intentionally narrow — it is the post-approval "you have a ride" page.

## User role(s)
- **Driver** in the session (sees own assigned passengers + own route).
- **Passenger** in the session (sees assigned driver + own route).
- Session Admin / Manager / Superuser fall through to the admin console;
  the "My assignment" view is the participant experience.

## Wireframe — Driver view

```
┌──────────────────────────────────────────────────────────┐
│  [Logo]      Church Carpool · ABC123       [Avatar ▾]    │
├──────────────────────────────────────────────────────────┤
│  Your ride — Saturday 2026-06-27                         │
│  Status: [ Approved ]   Role: Driver                     │
│  ─────────────────────────────────────────────────────   │
│                                                          │
│  ┌── Route summary ──────────────────────────────────┐   │
│  │  Destination:  123 Main St., Destination ON       │   │
│  │  Depart anchor: 09:00  ·  Arrive by: 09:25        │   │
│  │  Total distance: 18 km  ·  Detour: +4 km          │   │
│  │  ┌──────────────────────────────────────────┐    │   │
│  │  │        ( Map: route + stops )            │    │   │
│  │  │  ◉ you → ① Alice → ② Bob → ◉ destination │    │   │
│  │  └──────────────────────────────────────────┘    │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Your passengers (pickup order) ─────────────────┐   │
│  │  1. Alice P.   pickup 08:35   L5N 1A2             │   │
│  │       Notes: "Service animal"                     │   │
│  │  2. Bob M.     pickup 08:42   L5N 2B1             │   │
│  │       Notes: —                                   │   │
│  │  (You will not see other drivers or their         │   │
│  │   passengers — per privacy policy.)               │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Quick actions ─────────────────────────────────┐   │
│  │  [ Update my registration ]   [ Sign out ]        │   │
│  │  Need help?  Contact admin: admin@example.com     │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Wireframe — Passenger view

```
┌──────────────────────────────────────────────────────────┐
│  [Logo]      Church Carpool · ABC123       [Avatar ▾]    │
├──────────────────────────────────────────────────────────┤
│  Your ride — Saturday 2026-06-27                         │
│  Status: [ Approved ]   Role: Passenger                  │
│  ─────────────────────────────────────────────────────   │
│                                                          │
│  ┌── Your driver ────────────────────────────────────┐   │
│  │  Jane D.                                         │   │
│  │  Vehicle: Sedan, 2 child seats                   │   │
│  │  Phone: revealed on day-of (contact admin)       │   │
│  │  ★ You will not see other passengers or drivers. │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Pickup ─────────────────────────────────────────┐   │
│  │  Pickup time:  08:35                             │   │
│  │  Pickup area:  L5N 1A2  (approximate, see map)   │   │
│  │  ┌────────────────────────────────────────┐      │   │
│  │  │   ( Map: single pin at pickup +  ⭐   │      │   │
│  │  │     driver anchor, route polyline  )  │      │   │
│  │  └────────────────────────────────────────┘      │   │
│  │  Drop-off (destination):  123 Main St., …        │   │
│  │  Estimated arrival: 09:25                        │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Quick actions ─────────────────────────────────┐   │
│  │  [ Update my registration ]  [ Sign out ]         │   │
│  │  Need help?  Contact admin: admin@example.com    │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Components
- `SessionContextBar` — title, code, status, date.
- `RouteSummaryCard` (driver only) — destination, departure / arrival times,
  total km + detour, map with route polyline + ordered stops.
- `MapPlaceholder` — Leaflet/MapLibre + OSM tiles; shows either a single pin
  (passenger) or a route polyline with numbered stops (driver). Read-only.
- `PassengerListCard` (driver only) — ordered list of assigned passengers with
  pickup time, postal, and any accessibility / special notes. **No other
  drivers' passengers are listed or reachable from this screen** (FR-9).
- `DriverCard` (passenger only) — driver name, vehicle notes, contact hint.
- `PickupCard` (passenger only) — pickup time, area, map pin, drop-off, ETA.
- `QuickActions` — links to update registration (re-uses Wireframe 03/04 in
  read/edit mode) and to sign out.
- `EmptyState` — used when the user is registered but matching has not run or
  has not assigned them yet.
- `Banner` — privacy reminder shown in both views, enforcing FR-9.

## Data bindings
- **API:** `GET /api/sessions/{code}/me` — returns the current user's
  registration (role, status, accessibility / vehicle flags) and a role-scoped
  slice of the latest approved match. The backend **enforces** FR-9 visibility
  on this endpoint — drivers never receive other drivers' passenger lists;
  passengers never receive the driver list or other passengers' data.
- **API:** `GET /api/sessions/{code}/match?version=approved` — fetches the
  approved `MATCH#V{n}` to drive the map polyline and ordered stops. Response
  is **already filtered by the backend** to the caller's role (FR-9); the
  frontend must not perform client-side filtering that could be reversed.
- **Auth:** Bearer JWT; the backend resolves the caller's `sub` to apply
  visibility rules.

## Interactions
1. **On mount** — fetch `/me` and the approved match in parallel; render the
   driver or passenger view based on `me.role`.
2. **Click "Update my registration"** — routes to
   `/sessions/ABC123/register?role={role}&edit=1` (re-uses the form page in
   edit mode via `PATCH /me`).
3. **Click map pin / stop number** — opens a side-panel with details (postal
   centroid, pickup time, accessibility note for the stop).
4. **Click "Sign out"** — clears JWT, routes to `/login`.
5. **Click admin contact link** — opens `mailto:admin@example.com`.
6. **No direct edit of the match** — there is intentionally no `Edit` button
   on this screen; participants request changes via the admin.

## Empty / loading / error states
- **Loading:** skeleton route card + skeleton list/pickup card.
- **Empty — registered but not yet assigned:**
  - Driver: "You are registered. Matching is in progress. You'll be notified
    when passengers are assigned."
  - Passenger: "You are registered. We'll email you once a driver is assigned."
- **Empty — registered but unassigned after approval:** "We could not match you
  for this session. The admin has been notified. [Update my registration] or
  [Contact admin]."
- **Empty — not registered:** "You haven't registered for this session yet.
  [Register as Driver] / [Register as Passenger]."
- **Error — match not approved yet:** "Matching is still in progress. Check
  back after the admin publishes the results."
- **Error — match version mismatch / override in progress:** "Your assignment
  was just updated by the admin. Refresh to see the latest." Auto-refresh
  with a 30s backoff.
- **Error — 401/403:** silent refresh → on failure redirect to `/login` with
  `?next=/sessions/ABC123/me`.
- **Error — 5xx:** InlineAlert with retry; cached last-known-good data shown
  in greyed-out mode with a "stale" badge.
- **Privacy invariant UI** — both views show the FR-9 reassurance line ("You
  will not see other drivers / passengers") so participants understand why the
  screen is intentionally minimal.
