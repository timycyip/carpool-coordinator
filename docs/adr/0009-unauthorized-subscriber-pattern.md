# ADR-0009: 401 Unauthorized Subscriber Pattern (api-client → auth-context bridge)

## Status
Accepted

## Date
2026-06-24

## Context
The frontend api-client (`src/lib/api-client.ts`) holds a module-scoped JWT token variable.
The React auth context (`src/lib/auth-context.tsx`) holds a separate `useState` copy of the
token and user for re-render triggering. Both must be cleared on a `401` response so that
`isAuthenticated` flips to `false` and the `ProtectedRoute` component redirects to `/login`.

The problem: `api-client` is a plain TypeScript module with no React dependency. It cannot
import `useAuth()` or call `setState` on the context. A `401` response clears the module
token (`clearAuthToken()`) but has no way to notify the React layer.

Forces at play:
- ADR-0002 mandates in-memory JWT storage — no `localStorage` event listeners to bridge the gap.
- The api-client must remain framework-agnostic (usable outside React if needed).
- The auth context must react to server-revoked sessions without waiting for a full page reload.
- Silent re-auth on reload (Google GIS) is deferred to Task 2.3; until then, a `401` is the
  only mechanism for session invalidation.

## Decision
Add a **subscriber pattern** to `api-client.ts`:

1. A module-level `Set<() => void>` named `unauthorizedListeners`.
2. An exported `onUnauthorized(cb)` function that registers a callback and returns an
   unsubscribe function.
3. On `401`, after calling `clearAuthToken()`, iterate over all registered callbacks.

`AuthProvider` subscribes via `useEffect` on mount:

```ts
useEffect(() => {
  return onUnauthorized(() => {
    setToken(null);
    setUser(null);
  });
}, []);
```

The unsubscribe function is returned from `useEffect` for cleanup on unmount.

## Alternatives Considered

### Alternative A: Custom DOM events
Dispatch `window.dispatchEvent(new Event("unauthorized"))` from api-client; listen with
`window.addEventListener` in AuthProvider.

- Pros: No explicit wiring between modules; standard browser API.
- Cons: Global event namespace pollution; harder to type; tests must mock `window.dispatchEvent`;
  feels heavy for a two-module communication.

### Alternative B: Import auth-context from api-client
Have api-client import a `forceLogout()` function exported from auth-context.

- Pros: Direct, no indirection.
- Cons: **Circular dependency** — auth-context imports from api-client (for `post`,
  `setAuthToken`); api-client would import from auth-context. Also couples the
  framework-agnostic api-client to React.

### Alternative C: React context with ref callback
Expose a `registerLogout(fn)` from a top-level React context that api-client calls.

- Pros: Same idea, different wiring.
- Cons: Requires api-client to know about the function at import time, before React mounts.
  The subscriber pattern (chosen) is simpler.

### Alternative D: Subscriber pattern (chosen)
- Pros: No circular deps; api-client stays framework-agnostic; unsubscribe on cleanup;
  testable with simple mocks; zero runtime cost when no listeners registered.
- Cons: Slight indirection (one extra file to understand).

## Consequences
- **Positive:** The 401 → redirect chain works end-to-end without a page reload. The api-client
  remains React-free. The pattern is extensible (future listeners for telemetry, audit, etc.).
- **Negative:** Two sources of truth for the token (module variable + React state) must be kept
  in sync manually. The subscriber is invoked synchronously in the 401 branch; if a subscriber
  throws, subsequent listeners are skipped (acceptable for MVP; wrap in try/catch if needed later).
- **Neutral:** The `onUnauthorized` export adds one more symbol to the api-client surface area.
  The pattern is standard (similar to EventEmitter / RxJS `subscribe`) and familiar to JS devs.

## Links
- ADR-0002 (JWT in-memory): `docs/adr/0002-app-session-jwt.md`
- ADR-0004 (same-origin rewrites): `docs/adr/0004-same-origin-rewrites.md`
- Phase 2 plan Task 2.11: `plans/phase-2-foundation.md`
- `frontend/src/lib/api-client.ts` — subscriber registration + 401 invocation
- `frontend/src/lib/auth-context.tsx` — `useEffect` subscription on mount
