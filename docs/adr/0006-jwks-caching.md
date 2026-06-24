# ADR-0006: Google JWKS Cached in Lambda (TTL ~1h)

## Status
Accepted

## Date
2026-06-23

## Context
The backend verifies Google ID tokens by checking the JWT signature against Google's public JWKS
(JSON Web Key Set), fetched from `https://www.googleapis.com/oauth2/v3/certs`. A naive
implementation fetches the JWKS on every login request, adding a network round-trip to Google's
servers.

Forces at play:
- NFR: p95 API latency < 800ms on smoke routes. A JWKS fetch adds ~50-200ms per login.
- Google rotates signing keys infrequently (typically months apart, with a grace period).
- Lambda functions are stateless per invocation but the process can persist across warm invocations
  (up to several hours). Module-level variables survive between warm invocations.
- On cold start, there is no cached JWKS — the first verify must fetch it. This is acceptable
  because cold starts are rare and the fetch only happens on `POST /auth/google`, not on every
  API call.

## Decision
Cache Google's JWKS in a **module-level variable** in `app/auth/oidc.py` with a **TTL of ~1 hour**.

```python
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600  # 1 hour

async def _get_jwks() -> dict:
    """Fetch and cache Google JWKS."""
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache
    # fetch from https://www.googleapis.com/oauth2/v3/certs
    _jwks_cache = await _fetch_google_jwks()
    _jwks_fetched_at = now
    return _jwks_cache
```

If the fetch fails (network error), fall back to the **cached** value even if expired. If there is
no cached value (cold start + Google down), return `503 Service Unavailable` — the user cannot log
in, but this is a rare degraded state.

## Alternatives Considered

### Alternative A: Fetch JWKS on every verify
- Pros: always up-to-date; no stale-key window.
- Cons: adds 50-200ms per login; against NFR (p95 < 800ms); rate-limits on Google's JWKS endpoint
  under burst traffic.

### Alternative B: Fetch once at cold start, never refresh
- Pros: zero runtime fetch latency.
- Cons: if a Lambda stays warm for days, JWKS may be very stale; if Google rotates keys, all
  verifications fail until a new cold start. **Rejected.**

### Alternative C: Cache with TTL (chosen)
- Pros: negligible latency on warm invocations; self-healing (refreshes after TTL); resilient to
  transient Google failures (fall back to cache).
- Cons: up to 1h stale-key window (acceptable — Google gives advance notice for key rotation and
  old keys remain valid during grace periods).

## Consequences
- **Positive:** Login latency is dominated by JWT verification (in-memory, <1ms) not by a network
  fetch. Warm invocations hit the cache. p95 stays under 800ms.
- **Negative:** Up to 1h stale-key window. If Google rotates keys mid-TTL, new tokens may fail
  verification until cache refresh. This is an acceptable risk — Google publishes key rotation
  timelines and provides a grace period where both old and new keys work.
- **Fallback:** If JWKS fetch fails and cache is empty, return `503` with a clear error message.
  The login flow shows "temporarily unavailable, try again" (better than a cryptic 401).

## Links
- Phase 2 plan Task 2.3 (Google OIDC auth): `plans/phase-2-foundation.md`
- ARCHITECTURE.md §Failure Modes: `ARCHITECTURE.md`
