# Wireframe 01 — Login + Session-Code Entry

## Screen name & route
- **Route (Next.js App Router):** `app/(auth)/login/page.tsx`
- **URL examples:** `/`, `/login`, `/login?session=ABC123`
- **Backed by:** Cloudflare Pages → same-origin rewrite to `/api/auth/*` (per ADR-0004).

## Purpose
Authenticate the user with Google OIDC, then collect / validate the session code that
identifies the carpool session they want to register for. After successful validation the
user is routed to the session dashboard (or directly into the registration form if a
session code is pre-populated).

## User role(s)
- Unauthenticated visitor (entry point for everyone).
- After login: any authenticated user. Managers / Superusers may bypass the session code
  step (FR-1: "Managers and Superusers may create sessions without session code").

## Wireframe

```
┌──────────────────────────────────────────────────────────┐
│  [Logo: Carpool Coordinator]              [Help ⓘ]      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                Welcome to Carpool Coordinator            │
│                ─────────────────────────────             │
│                                                          │
│   ┌────────────────────────────────────────────────┐     │
│   │  Step 1 — Sign in                              │     │
│   │  ┌──────────────────────────────────────────┐  │     │
│   │  │   [G  Sign in with Google]               │  │     │
│   │  └──────────────────────────────────────────┘  │     │
│   │  (Status: not signed in)                       │     │
│   └────────────────────────────────────────────────┘     │
│                                                          │
│   ┌────────────────────────────────────────────────┐     │
│   │  Step 2 — Enter session code                   │     │
│   │  Session code:  [ ABC123             ] [Go]    │     │
│   │  (Pre-filled from ?session= query param)       │     │
│   │  Error: "Session not found" / "Expired"        │     │
│   └────────────────────────────────────────────────┘     │
│                                                          │
│   Manager / Superuser? [ Create a new session → ]        │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  v1.0 · © 2026 · Privacy · Terms                         │
└──────────────────────────────────────────────────────────┘
```

### State: signed-in + code validated
```
┌──────────────────────────────────────────────────────────┐
│  [Logo]                       [Avatar ▾ Jane D.  ↩]      │
├──────────────────────────────────────────────────────────┤
│  ✓ Signed in as jane@example.com                         │
│  ✓ Session code ABC123 accepted — "Church Carpool"       │
│                                                          │
│  Session status:  [ Registration Open ]                  │
│  Registration deadline:  Sat 2026-06-27 18:00             │
│                                                          │
│  Choose your role to continue:                           │
│   [  Register as Driver   ]  [  Register as Passenger  ] │
│   [  View dashboard (already registered)  ]              │
└──────────────────────────────────────────────────────────┘
```

## Components
- `Header` (logo, optional user avatar menu, help link).
- `AuthCard` — "Sign in with Google" button (Google Identity Services button).
- `SessionCodeForm` — single text field + submit, prefills from `?session=`.
- `StatusPill` — session status badge.
- `RoleChooser` — three primary buttons (driver / passenger / dashboard).
- `InlineAlert` — for error / success messages.
- Footer with version + legal links.

## Data bindings
- **API:** `POST /api/auth/google` — exchanges Google ID token for a backend JWT
  (stored in memory per ADR-0002). Returns `user` profile.
- **API:** `GET /api/sessions/{code}` — validates the session code; returns session
  metadata + status. Used to show the "Session accepted" state and to surface the
  registration deadline.
- **API:** `GET /api/sessions?user={sub}` — only used after auth to check if the user
  is already registered, to decide whether to show the dashboard link.
- **Query param:** `?session=ABC123` — pre-populates the session code field on first
  render, no API call needed.

## Interactions
1. **Click "Sign in with Google"** → opens Google One-Tap / popup → on success,
   `POST /api/auth/google` → JWT stored in memory → header updates with user avatar.
2. **Type session code + Enter (or click Go)** → `GET /api/sessions/{code}` → on 200
   show the "Step 2 accepted" panel and the role chooser; on 404 show inline error.
3. **Click "Register as Driver"** → `router.push('/sessions/ABC123/register?role=driver')`.
4. **Click "Register as Passenger"** → `router.push('/sessions/ABC123/register?role=passenger')`.
5. **Click "View dashboard"** → `router.push('/dashboard')` (or directly to `/sessions/ABC123/me`).
6. **Manager / Superuser link** → `router.push('/sessions/new')` (out of scope here; stub).
7. **Browser back / sign-out** → clears JWT from memory and returns to step 1.

## Empty / loading / error states
- **Loading (auth):** Spinner inside the Google button; rest of card disabled.
- **Loading (session code):** Spinner inside the "Go" button; field becomes read-only.
- **Error — invalid code:** InlineAlert under the field: "Session not found. Check the
  code and try again." Field is cleared, focus returns.
- **Error — expired session:** InlineAlert: "This session has closed. Contact the admin."
- **Error — not yet open:** InlineAlert: "Registration is not open yet. Opens at
  <earliest_pickup>." Show countdown.
- **Error — Google auth fail:** InlineAlert at top of card: "Sign-in failed. Retry."
- **Empty — pre-filled from URL:** Field populated and ready; auto-validates on mount
  if a session code is present in the query string and the user is already signed in.
- **Empty — never visited:** "Sign in" card highlighted, Step 2 disabled until authed.
