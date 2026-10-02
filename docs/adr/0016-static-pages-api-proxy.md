# ADR-0016: Static Cloudflare Pages Frontend with API Proxy Function

## Status
Accepted

## Date
2026-10-01

## Context
The project targets Cloudflare Pages and near-zero operating cost. The previous frontend depended on `@cloudflare/next-on-pages`, which rejects the repository's Next.js 16 version, and used Next.js rewrites for same-origin API calls. Next.js static export does not support rewrites, so the adapter path cannot both build and meet the cost target.

## Decision
Build the App Router frontend as a static Next.js export. Keep the browser's `/api/*` calls same-origin by adding one Cloudflare Pages Function at that route. It forwards to staging when `CF_PAGES_BRANCH` is `staging` (the Pages deployment branch used for pushes to `master`) or `master`, and to dev for all other branches. Use `_routes.json` to invoke the Function only for `/api/*`; all static asset requests bypass Functions. Local `next dev` keeps a localhost rewrite for the API.

Configure `DEV_API_ORIGIN` and `STAGING_API_ORIGIN` as Pages Preview runtime variables. The values are public endpoint identifiers, not credentials. The production origin is added only when production deployment is approved.

## Alternatives Considered

### Keep `next-on-pages`
Rejected because the current adapter peer dependency excludes Next.js 16.2.9 and its Pages build fails.

### Direct browser calls to Lambda
Avoids the Pages Function quota, but requires API CORS configuration and exposes a cross-origin integration to browser code. The same-origin proxy is small and is invoked only for API requests.

### Run every request through a Pages Function
Rejected because it spends Workers Free requests on static assets. `_routes.json` limits the invocation set to `/api/*`.

## Consequences
- Static frontend asset requests use Cloudflare Pages static delivery; the API proxy consumes the shared Workers Free allowance (currently 100,000 requests/day and 10 ms CPU per request).
- The Pages Function adds a deployment-time dependency on per-environment API origin configuration.
- Cloudflare Pages Preview needs both dev and staging API origins; the function routes the stable `staging` deployment branch to staging and feature branches to dev.
- Next.js server-only features cannot be added without revisiting the static-export decision.
- The AWS Lambda Function URL remains independently reachable; the Pages proxy is not an access-control boundary.

## Links
- Supersedes [ADR-0004](0004-same-origin-rewrites.md) for deployed frontend routing.
- [Phase 2 plan](../../doc/plans/phase-2-foundation.md)
- [Cloudflare Pages Functions routing](https://developers.cloudflare.com/pages/functions/routing/)
- [Next.js static export](https://nextjs.org/docs/app/building-your-application/deploying/static-exports)
