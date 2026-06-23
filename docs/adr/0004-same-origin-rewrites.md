# ADR-0004: Same-Origin via Cloudflare Pages rewrites()

## Status
Accepted

## Date
2026-06-23

## Context
The Next.js frontend is deployed to Cloudflare Pages. The FastAPI backend is deployed to an AWS
Lambda Function URL. These are different origins (`*.pages.dev` vs `*.lambda-url.us-east-2.on.aws`).
The frontend must call the backend API on every authenticated action.

Cross-origin API calls trigger CORS preflight (`OPTIONS`) requests, require explicit CORS headers
on the backend, and make `Authorization: Bearer <token>` handling more complex. If the app session
were a cookie (ADR-0002), cross-origin would also require `SameSite=None; Secure` which adds
browser compatibility concerns.

Forces at play:
- ADR-0002 chose JWT in-memory (not a cookie), so CORS technically works — but preflight adds
  latency and CORS header management is error-prone.
- The Lambda Function URL may change (redeploy, region change) — hardcoding it in the frontend
  is fragile.
- Cloudflare Pages supports `rewrites()` in `next.config.ts` which maps a path prefix to any
  backend URL at the edge, making the browser see a same-origin call.

## Decision
Configure **`rewrites()` in `next.config.ts`** to proxy `/api/*` to the Lambda Function URL.
The browser calls `https://<pages-domain>/api/...` (same origin); Cloudflare's Workers runtime
proxies it to the Lambda URL. The Lambda Function URL is injected as a build-time environment
variable (`NEXT_PUBLIC_API_URL` or a Pages environment variable).

```ts
// next.config.ts
async rewrites() {
  return [{
    source: '/api/:path*',
    destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
  }];
}
```

The backend does **not** need CORS headers for same-origin requests. The backend should still set
`Access-Control-Allow-Origin` as a safety net for direct API calls (e.g., during local dev when
the frontend runs on `localhost:3000` and the backend on `localhost:8000`).

## Alternatives Considered

### Alternative A: Direct cross-origin with CORS
Frontend calls the Lambda URL directly. Backend sets `Access-Control-Allow-Origin`, `Allow-Methods`,
`Allow-Headers`, handles `OPTIONS` preflight.

- Pros: explicit; no proxy hop; works if frontend moves off Cloudflare Pages.
- Cons: preflight adds ~100ms latency on first call; CORS misconfigurations are common; CORS
  headers must be maintained in the backend.

### Alternative B: Same-origin via rewrites (chosen)
- Pros: no CORS preflight (saves latency); Lambda URL hidden from browser; backend simpler;
  single origin for all requests; easy to swap the Lambda URL at build time.
- Cons: extra hop through Cloudflare Workers runtime (~10ms, within p95 budget); frontend and API
  are coupled at the Cloudflare project level; if Lambda URL changes, the Pages build must be
  redeployed.

## Consequences
- **Positive:** No CORS configuration needed (backend simpler); no preflight latency; Lambda URL
  is not exposed to the client; single origin simplifies security review.
- **Negative:** Extra proxy hop (~10ms, within p95 budget); frontend deploy is coupled to the API
  URL (must rebuild/redeploy if Lambda URL changes).
- **Action required:** Task 2.11 configures `rewrites()` in `next.config.ts`; the Lambda Function
  URL is set as a Cloudflare Pages environment variable at deploy time (Task 2.10).

## Links
- ADR-0002 (JWT in-memory): `docs/adr/0002-app-session-jwt.md`
- Phase 2 plan Task 2.11 (Frontend bootstrap): `plans/phase-2-foundation.md`
- ARCHITECTURE.md §Architecture Principles: `ARCHITECTURE.md`
