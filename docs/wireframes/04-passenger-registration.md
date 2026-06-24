# Wireframe 04 — Passenger Registration Form

## Screen name & route
- **Route (Next.js App Router):** `app/(app)/sessions/[code]/register/page.tsx`
  with `?role=passenger` (the same page component as Wireframe 03, gated on
  `role` from the query string or from existing registration).
- **URL examples:** `/sessions/ABC123/register?role=passenger`
- **Backed by:** Cloudflare Pages → same-origin `/api/sessions/ABC123/register`
  (per ADR-0004).

## Purpose
Collect the canonical registration fields plus passenger-specific fields
(FR-3 / FR-4 — accessibility requirements, special notes) for a single carpool
session, confirm the pickup area on a map, and submit the registration. After
success the user is routed to `/sessions/ABC123/me`.

## User role(s)
- Authenticated user registering as a **Passenger** for the session.
- Not yet registered, or editing an existing registration.

## Wireframe

```
┌──────────────────────────────────────────────────────────┐
│  [Logo]            Church Carpool · ABC123  [Avatar ▾]   │
├──────────────────────────────────────────────────────────┤
│  ← Back to dashboard                                     │
│                                                          │
│  Register as Passenger                                   │
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
│  ┌── Passenger-specific fields ────────────────────┐    │
│  │ Accessibility requirements (optional)          │    │
│  │  [                                          ▾ ] │    │
│  │  [ Free text — e.g., "Wheelchair user,    ]   │    │
│  │  [ ground-floor access preferred." (max 500) ]   │    │
│  │                                                  │    │
│  │ Special notes (optional)                        │    │
│  │  [                                          ▾ ] │    │
│  │  [ Free text — e.g., "Prefer non-smoking    ]   │    │
│  │  [ vehicle." (max 500)                      ]   │    │
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
│  may share your name with your assigned driver.          │
└──────────────────────────────────────────────────────────┘
```

## Components
- `SessionContextBar` — title, code, status, deadline.
- `FormSection` "Common fields" — same as Wireframe 03.
- `FormSection` "Passenger-specific" — single free-text
  `accessibility_requirements` field (0–500 chars) and a free-text `special_notes`
  field (0–500 chars). No structured flags; the matching engine treats the text
  as a soft constraint per `docs/requirements_baseline.md` §3.3.
- `MapPlaceholder` — same Leaflet/MapLibre + OSM pin as the driver form.
- `PostalCodeValidator` — same debounced `GET /api/geocode`.
- `PrimaryButton` "Submit registration".
- `LegalNotice` — privacy/consent line (FR-9: only the assigned driver sees the
  passenger's name; the driver does **not** see other drivers' passengers).
- `InlineAlert` — validation + error.
- `CharacterCounter` — under each free-text field (caps at 500 chars).

## Data bindings
- **API (read):** `GET /api/sessions/{code}` — context bar (title, deadline,
  status, anchor location).
- **API (read):** `GET /api/geocode?postal=…` — geocodes the passenger's postal
  code for the map pin (Nominatim, cached).
- **API (write):** `POST /api/sessions/{code}/register` with body (flat per
  canonical schema `docs/requirements_baseline.md` §3):
  ```json
  {
    "role": "passenger",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "postal_code": "L5N 1A2",
    "earliest_departure_time": "2026-06-27T08:30:00Z",
    "latest_departure_time":   "2026-06-27T09:00:00Z",
    "accessibility_requirements": "Wheelchair user, ground-floor access preferred.",
    "special_notes": "Prefer non-smoking vehicle."
  }
  ```
  Same partition/sort key shape as the driver registration: `PK = SESSION#ABC123`,
  `SK = REG#<sub>`.
- **API (write):** `PATCH /api/sessions/{code}/me` for editing existing
  registrations (no role flip).
- **Auth:** Bearer JWT.
- **Local autosave:** form state is written to `localStorage` on every change
  (key: `carpool:register:{code}:passenger`). Restored on reload. Cleared on
  successful submit or explicit "Discard".

## Interactions
1. **Mount** — same as driver form: prefill name + email, fetch session, restore
   any localStorage draft, render passenger-specific sections.
2. **Type accessibility / special notes** — `CharacterCounter` updates; hard cap
   at 500 chars each.
3. **Type postal code + blur** — same debounced geocode, map pin updates.
4. **Edit time pickers** — client-side validation: `earliest <= latest`,
   `earliest >= session.earliest_pickup` (warn — not block — if outside window).
5. **Click "Submit registration"** — `POST /api/sessions/{code}/register` → on 201
   navigate to `/sessions/ABC123/me?welcome=1`; on 409 redirect to `/me` with
   "already registered" banner.
6. **Back link** — return to `/dashboard`; dirty-form confirm if unsaved changes.

## Empty / loading / error states
- **Loading (session / geocode):** skeletons as in Wireframe 03.
- **Error — postal not found:** InlineAlert next to postal field, pin removed.
- **Error — invalid times:** InlineAlert under the affected picker; submit
  disabled.
- **Error — already registered (409):** redirect to `/me` with banner.
- **Error — registration closed (403):** form disabled, big banner "Registration
  is closed. Contact the admin."
- **Network / 5xx on submit:** toast + auto-save client-side draft
  (localStorage) so the user doesn't lose their input.
- **Empty initial render (no query role):** redirect to `/login` or `/dashboard`
  with "Choose a role to register" message — never silently render a blank form.