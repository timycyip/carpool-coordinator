# Wireframe 03 — Driver Registration Form

## Screen name & route
- **Route (Next.js App Router):** `app/(app)/sessions/[code]/register/page.tsx`
  with `?role=driver` (default behaviour: render the form for whichever role is in
  the query string).
- **URL examples:** `/sessions/ABC123/register?role=driver`
- **Backed by:** Cloudflare Pages → same-origin `/api/sessions/ABC123/register`
  (per ADR-0004).

## Purpose
Collect the canonical registration fields plus driver-specific fields (FR-3 / FR-4)
for a single carpool session, give the user a visual confirmation of their
approximate pickup area on a map, and submit the registration. After success the
user is routed to `/sessions/ABC123/me` (a confirmation / waiting state until the
admin runs matching).

## User role(s)
- Authenticated user registering as a **Driver** for the session.
- Not yet registered for this session (or editing an existing draft — see
  `PATCH /api/sessions/{code}/me`).

## Wireframe

```
┌──────────────────────────────────────────────────────────┐
│  [Logo]            Church Carpool · ABC123  [Avatar ▾]   │
├──────────────────────────────────────────────────────────┤
│  ← Back to dashboard                                     │
│                                                          │
│  Register as Driver                                      │
│  Deadline: Sat 2026-06-27 18:00  ·  [Status: Open]      │
│  ─────────────────────────────────────────────────────   │
│                                                          │
│  ┌── Common fields ─────────────────────────────────┐   │
│  │ Full name *      [ Jane Doe                  ]   │   │
│  │ Google email *   [ jane@example.com (locked)  ]   │   │
│  │ Postal code *    [ L5N 1A2                  ]   │   │
│  │ Earliest departure time *  [ 2026-06-27 08:30 ▾ ]   │   │
│  │ Latest departure time *    [ 2026-06-27 09:00 ▾ ]   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌── Driver-specific fields ───────────────────────┐    │
│  │ Seat capacity *  [  3  ]                        │    │
│  │ Earliest pickup time *  [ 2026-06-27 08:30 ▾ ]  │    │
│  │ Latest pickup time *    [ 2026-06-27 09:00 ▾ ]  │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌── Pickup area (map) ────────────────────────────┐    │
│  │   ┌────────────────────────────────────────┐   │    │
│  │   │                                        │   │    │
│  │   │           ( Map placeholder )          │   │    │
│  │   │             ◉  L5N 1A2                 │   │    │
│  │   │                                        │   │    │
│  │   │   Pin is approximate (postal centroid) │   │    │
│  │   └────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  [ Submit registration → ]                                │
│                                                          │
│  Progress is saved locally in your browser               │
│  (localStorage). Complete the form and click              │
│  Register to submit.                                     │
│                                                          │
│  By submitting you confirm the carpool coordinator       │
│  may share your name with passengers assigned to you.    │
└──────────────────────────────────────────────────────────┘
```

## Components
- `SessionContextBar` — title, session code, status pill, deadline countdown.
- `FormSection` "Common fields" — name (read-only if pre-filled from Google),
  email (locked), postal code, earliest/latest departure time pickers.
- `FormSection` "Driver-specific" — seat capacity (number stepper, no upper
  bound), earliest/latest pickup time pickers.
- `MapPlaceholder` — Leaflet/MapLibre + OSM tiles, shows a single pin at the
  geocoded centroid of the postal code (FR-5: Nominatim). Read-only.
- `PostalCodeValidator` — debounced lookup via `GET /api/geocode?postal=…`; on
  success the map pin animates to the new centroid.
- `PrimaryButton` "Submit registration".
- `LegalNotice` — short privacy/consent sentence.
- `InlineAlert` — for validation and API errors.
- `ProgressIndicator` (top) — "1. Details · 2. Confirm · 3. Done" (only if multi-step).

## Data bindings
- **API (read):** `GET /api/sessions/{code}` — to render the context bar
  (deadline, status, anchor location for the map).
- **API (read):** `GET /api/geocode?postal=L5N1A2` — resolves postal code →
  lat/lon (cached Nominatim). Result drives the map pin. Cache key in `app_data`
  with TTL.
- **API (write):** `POST /api/sessions/{code}/register` with body (flat per
  canonical schema `docs/requirements_baseline.md` §3):
  ```json
  {
    "role": "driver",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "postal_code": "L5N 1A2",
    "earliest_departure_time": "2026-06-27T08:30:00Z",
    "latest_departure_time":   "2026-06-27T09:00:00Z",
    "seat_capacity": 3,
    "earliest_pickup_time": "2026-06-27T08:30:00Z",
    "latest_pickup_time":   "2026-06-27T09:00:00Z"
  }
  ```
  Writes a single `REG#USER#<sub>` item under `PK = SESSION#ABC123`.
- **API (write):** `PATCH /api/sessions/{code}/me` — used when re-opening an
  existing registration to edit fields (same body shape minus `role`, which is
  not updatable).
- **Auth:** `Authorization: Bearer <jwt>` (in-memory per ADR-0002).
- **Local autosave:** form state is written to `localStorage` on every change
  (key: `carpool:register:{code}:driver`). Restored on reload. Cleared on
  successful submit or explicit "Discard".

## Interactions
1. **Mount** — fetch session context, prefill email + name from JWT claims,
   restore any localStorage draft.
2. **Type postal code + blur** — debounced geocode; map pin moves; clear pin if no
   match.
3. **Adjust time pickers** — client-side validation: `earliest <= latest`,
   `earliest_pickup >= earliest_departure`; show inline error if violated.
4. **Click "Submit registration"** — full client-side validation, then
   `POST /api/sessions/{code}/register`. On 201 → success page
   (`/sessions/ABC123/me?welcome=1`); on 409 (already registered) → redirect to
   `/sessions/ABC123/me` with banner "You're already registered."
5. **Back link** — returns to `/dashboard` (confirmation modal if dirty form).
6. **Time picker shortcuts** — buttons "Earliest now", "Latest = session arrival"
  to autofill from session context.

## Empty / loading / error states
- **Loading (session):** skeleton context bar; form disabled.
- **Loading (geocode):** spinner next to postal-code field; map shows a faded
  default region pin.
- **Error — postal not found:** InlineAlert next to field: "We couldn't locate that
  postal code. Try the closest one." Map pin removed.
- **Error — invalid times:** InlineAlert under affected field; submit button
  disabled until resolved.
- **Error — already registered (409):** redirect to `/me` with banner.
- **Error — registration closed (403):** form disabled, big banner "Registration
  is closed. Contact the admin."
- **Error — session code unknown (404):** full-page "Session not found" with
  "Back to dashboard" link.
- **Network / 5xx on submit:** toast "Could not submit. Your draft is saved."
  Draft remains in localStorage as a safety net for the user to retry.