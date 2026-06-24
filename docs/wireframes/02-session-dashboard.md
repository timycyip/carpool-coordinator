# Wireframe 02 — Session List / Dashboard

## Screen name & route
- **Route (Next.js App Router):** `app/(app)/dashboard/page.tsx`
- **URL examples:** `/dashboard`
- **Backed by:** Cloudflare Pages → same-origin `/api/sessions?user=…` (per ADR-0004).

## Purpose
Give an authenticated user a single landing page that lists every carpool session
they are part of — as a Driver, a Passenger, or a Session Admin — and lets them
navigate into the next action (register, view assignment, or open the admin console).
The page is the FR-1 "browse app" surface.

## User role(s)
- Any authenticated user (Driver, Passenger, Session Admin, Manager, Superuser).
- Content varies by role: drivers/passengers see sessions they belong to; admins see
  the same plus a "Administer" link; managers / superusers also see sessions they
  own (FR-2 / Section 4).

## Wireframe

```
┌──────────────────────────────────────────────────────────┐
│  [Logo: Carpool Coordinator]      [Avatar ▾ Jane D.  ⎋] │
├──────────────────────────────────────────────────────────┤
│  Hi Jane — your carpool sessions                         │
│  [ + Join a session (enter code) ]                       │
│                                                          │
│  Filter: [ All ▾ ]  Role: [ Any ▾ ]   Sort: [ Soonest ] │
│                                                          │
│  ┌─ ACTIVE ──────────────────────────────────────────┐   │
│  │ ┌────────────────────────────────────────────┐   │   │
│  │ │ Church Carpool · ABC123                    │   │   │
│  │ │ [Registration Open]   Role: Driver         │   │   │
│  │ │ Sat 2026-06-27 09:00 · 12 / 20 registered  │   │   │
│  │ │ [Open session →]                           │   │   │
│  │ └────────────────────────────────────────────┘   │   │
│  │ ┌────────────────────────────────────────────┐   │   │
│  │ │ Hiking Trip · HKE42                        │   │   │
│  │ │ [Matching Proposed]   Role: Admin          │   │   │
│  │ │ Sun 2026-07-05 08:30 · 18 / 18 registered  │   │   │
│  │ │ [Open admin console →]                     │   │   │
│  │ └────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─ UPCOMING ───────────────────────────────────────┐    │
│  │ (collapsed by default — click to expand)        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─ CLOSED / PAST ──────────────────────────────────┐    │
│  │ (collapsed by default)                           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  Footer                                                  │
└──────────────────────────────────────────────────────────┘
```

## Components
- `AppHeader` with user avatar menu (sign out, settings).
- `JoinSessionButton` — opens the session-code modal (re-uses Wireframe 01 Step 2).
- `SessionFilterBar` — status filter, role filter, sort.
- `SessionCard` — title, session code, status pill, role pill, datetime, registration
  count, primary action button. Click target = whole card.
- `StatusPill` — colored badge. Display text is human-readable (e.g.,
  "Registration Open", "Matching Proposed", "Approved", "Closed"); the underlying
  enum value sent to / received from the API is `snake_case` per API §1.8 —
  values are `draft`, `registration_open`, `matching_pending`, `matching_proposed`,
  `approved`, `closed`.
- `RolePill` — Driver / Passenger / Admin / Manager.
- `EmptyState` — illustration + "No sessions yet" copy + join CTA.
- `SkeletonCard` — for loading.

## Data bindings
- **API:** `GET /api/sessions?user={user_sub}` — returns the list of sessions the
  user belongs to. Powered by the `sessions-by-user` GSI (§3.2 of ERD) for
  sessions where the user is a Driver or Passenger, and by the
  `gsi_admins_by_user` GSI (§3.4 of ERD) for the "Administer" tab where the user
  holds Session Admin grants without a registration. Each item includes
  `session_code`, `title`, `status`, `trip_mode`, `earliest_pickup`,
  `latest_arrival`, `registration_deadline`, `user_role_in_session`, and
  `registration_count`.
- **Optional API:** `GET /api/sessions?owned=true` — for Manager / Superuser, fetches
  sessions they own but aren't personally registered in.
- No write API is called from this page; navigation only.

## Interactions
1. **On mount** — fetch the user's sessions via the GSI-backed list endpoint.
2. **Click a SessionCard** — route to:
   - `role === 'admin'` → `/sessions/ABC123/admin` (Phase 5 — admin console; **Phase 2 stub**: this link is inactive/disabled until Phase 5 admin console lands)
   - `status === 'registration_open' && !user_registered` → `/sessions/ABC123/register`
   - `status === 'approved' || 'closed'` → `/sessions/ABC123/me`
   - otherwise (`draft`, `matching_pending`, `matching_proposed`) → read-only
     `/sessions/ABC123/me`.
3. **Click "Join a session"** — opens modal that mirrors Wireframe 01 Step 2; on
   success routes to `/sessions/{code}/register`.
4. **Filter / sort** — client-side; no extra API call. (Re-fetch if a deep-link
   query string forces a server-side filter in a future iteration.)
5. **Avatar menu → Sign out** — clears JWT, routes to `/login`.
6. **Empty state** — single CTA "Join a session" opens the modal.

## Empty / loading / error states
- **Loading:** Three `SkeletonCard` placeholders in the Active section.
- **Empty:** "You haven't joined any sessions yet." with a single "Join a session"
  button. No Active / Upcoming / Closed sections rendered.
- **Error (network / 5xx):** InlineAlert above the filter bar: "We couldn't load your
  sessions. [Retry]" — re-fetches the same endpoint.
- **Error (401):** JWT expired → silent refresh attempt → on failure redirect to
  `/login` with `?next=/dashboard`.
- **Manager / Superuser view** — additionally shows a "Sessions I manage" section at
  the top, before "Active".
