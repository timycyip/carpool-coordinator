# ADR-0002: App Session = JWT (In-Memory Browser Storage)

## Status
Accepted — human-reviewed and confirmed 2026-06-23

## Date
2026-06-23

## Context
After a user authenticates via Google OIDC, the backend must issue a persistent app session so
subsequent requests are authenticated without re-verification against Google. The two broad options
are **server-side sessions** (cookie + DB lookup) or **client-side sessions** (signed JWT, no DB
lookup). Within client-side sessions, the token can be stored in `localStorage`, `sessionStorage`,
or an in-memory JavaScript variable.

Forces at play:
- This is a Lambda + Cloudflare Pages serverless deployment — no sticky sessions, no in-process
  session store.
- Security: XSS can steal tokens from `localStorage`; the app should resist this.
- Performance: p95 API latency < 800ms — a DB session lookup on every request risks adding latency
  (especially DynamoDB cold reads).
- Simplicity: MVP is single-tenant; minimizing moving parts is desirable.
- The frontend is a Next.js SPA; full page reloads are infrequent (router-based navigation).

## Decision
Issue a **signed JWT** from the backend after successful Google OIDC verification. The frontend
stores the JWT **in an in-memory JavaScript variable** (not `localStorage`, not `sessionStorage`,
not cookies).

- The JWT is sent on every API call via `Authorization: Bearer <token>` header.
- The JWT is **cleared from memory on page reload** — the user must re-authenticate (via Google
  GIS, which is fast and non-interactive if the Google session cookie is present).
- The JWT includes: `sub` (Google subject), `email`, `name`, `global_role` (Superuser/Manager/none),
  `iat`, `exp`.
- JWT TTL: **1 hour** (short-lived). No refresh token in Phase 2; re-auth is via Google GIS silent
  sign-in. Refresh tokens can be added in Phase 6 if UX requires longer sessions.
- The signing secret is stored in AWS Parameter Store and loaded at Lambda cold-start.

## Alternatives Considered

### Alternative A: httpOnly signed cookie (same-origin via rewrites)
Backend sets an `httpOnly`, `Secure`, `SameSite=Lax` cookie. Requires same-origin (frontend and API
on the same domain) which can be achieved via Cloudflare Pages `rewrites()`.

- Pros: XSS-resistant (JS cannot read httpOnly cookies); survives page reloads; familiar web pattern.
- Cons: requires same-origin contract (fragile if Lambda URL changes or frontend moves); CSRF risk
  (mitigated by SameSite but still present); cookie rotation/logout is harder server-side.

### Alternative B: JWT in localStorage
- Pros: survives page reloads; simple implementation.
- Cons: vulnerable to XSS — any injected script can exfiltrate the token. **Rejected on security
  grounds.**

### Alternative C: JWT in sessionStorage
- Pros: cleared on tab close (better than localStorage).
- Cons: still readable by any script in the page (XSS risk, same as localStorage). Slightly less
  persistent than localStorage but equally vulnerable. **Rejected.**

### Alternative D: JWT in memory (chosen)
- Pros: XSS-resistant (token exists only in the current page's JS heap; cleared on reload);
  no CSRF risk (not a cookie); no DB session lookup; stateless and Lambda-friendly.
- Cons: user must re-authenticate on full page reload (mitigated by Google GIS silent sign-in if
  the Google session is still active).

## Consequences
- **Positive:** No server-side session store; no DynamoDB session-lookup on every request (saves
  latency and cost); XSS-resistant storage; no CSRF surface; simple implementation.
- **Negative:** Full page reload clears the session — the user must re-authenticate (Google GIS
  is fast/silent if the Google session cookie is present, so UX impact is minimal).
- **Action required:** Frontend `api-client.ts` must wire `Authorization: Bearer` on every fetch;
  `auth-context.tsx` must store/retrieve JWT from memory and trigger silent re-auth on page load.
- **Supersedes:** the "signed cookie or JWT" ambiguity in the earlier plan draft.

## Links
- Requirements doc §14 (Security Controls): `docs/functional_requirements_and_architecture.md`
- Phase 2 plan Task 2.3 (Google OIDC auth): `plans/phase-2-foundation.md`
- Phase 2 plan Task 2.11 (Frontend bootstrap / API client): `plans/phase-2-foundation.md`
- ARCHITECTURE.md §Login flow: `ARCHITECTURE.md`
