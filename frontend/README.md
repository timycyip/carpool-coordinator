# Frontend — Carpool Coordinator

Next.js 16 (App Router) + TypeScript + Tailwind v4 frontend for the Carpool Coordinator platform.
Deployed to Cloudflare Pages via `@cloudflare/next-on-pages`.

## Quick Start

```bash
cd frontend
npm install
cp .env.example .env.local    # edit if backend is not on localhost:8000
npm run dev                    # http://localhost:3000
```

## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Next.js dev server (Turbopack) |
| `npm run build` | Production build (webpack, required for next-on-pages) |
| `npm run lint` | ESLint |
| `npx tsc --noEmit` | TypeScript type check |
| `npm test` | Vitest (api-client tests) |
| `npm run test:watch` | Vitest in watch mode |
| `npm run pages:build` | Cloudflare Pages build (`@cloudflare/next-on-pages`) |
| `npm run pages:deploy` | Deploy to Cloudflare Pages |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend API base URL. Used only in `next.config.ts` rewrites — the client always calls `/api/*` (same-origin). |

See `.env.example` for the template.

## Architecture

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout: AuthProvider + Nav wrapper
│   │   ├── page.tsx            # Landing page (auth-aware)
│   │   └── globals.css         # Tailwind v4 @theme tokens (emerald/slate)
│   ├── components/
│   │   └── Nav.tsx             # Role-aware nav with mobile disclosure
│   └── lib/
│       ├── types.ts            # Shared TypeScript types (API contract mirror)
│       ├── api-client.ts       # Fetch wrapper with JWT injection + error mapping
│       ├── api-client.test.ts  # Vitest tests (colocated)
│       ├── auth-context.tsx    # React auth context (login/logout/isAuthenticated)
│       └── route-guard.tsx     # ProtectedRoute component (redirects to /login)
├── next.config.ts              # Same-origin rewrites (/api/* → backend)
├── wrangler.toml               # Cloudflare Pages config
├── vitest.config.ts            # Test runner config
└── .env.example                # Environment template
```

### Key Design Decisions

| Decision | ADR |
|----------|-----|
| JWT stored in-memory (no localStorage/sessionStorage) | [ADR-0002](../docs/adr/0002-app-session-jwt.md) |
| Same-origin API via `next.config.ts` rewrites | [ADR-0004](../docs/adr/0004-same-origin-rewrites.md) |
| 401 → subscriber pattern (api-client notifies auth-context) | [ADR-0009](../docs/adr/0009-unauthorized-subscriber-pattern.md) |

### API Client (`src/lib/api-client.ts`)

- All API calls go through `/api/*` (same-origin, relative path).
- Module-scoped `authToken` variable; `setAuthToken` / `clearAuthToken` mutate it.
- `Authorization: Bearer <token>` header injected on every request when a token exists.
- Non-2xx responses parse the nested `ErrorResponse` shape (`{ error: { code, message, details? } }`).
- `401` responses clear the token and notify all `onUnauthorized` subscribers.

### Auth Context (`src/lib/auth-context.tsx`)

- `AuthProvider` wraps the app in `layout.tsx`.
- `login(idToken)` posts to `/auth/google`, stores the returned access token + user.
- `logout()` clears token and user state.
- `useAuth()` hook exposes `{ user, token, isAuthenticated, isLoading, login, logout }`.
- Subscribes to `onUnauthorized` on mount to react to server-revoked sessions.

### Design System

- **Palette:** emerald-600 primary, slate-neutral base (no gradients, no indigo/purple).
- **Tokens:** semantic CSS variables in `globals.css` (`--color-background`, `--color-primary`, etc.) mapped via Tailwind v4 `@theme inline`.
- **Radius:** `rounded-md` default, `rounded-lg` containers — no `rounded-2xl`.
- **Accessibility:** Nav has `aria-label`, active links have `aria-current="page"`, mobile disclosure uses `aria-expanded`/`aria-controls`, focus managed on open/close, Escape closes panel.

## Testing

Tests are colocated next to their source files (e.g., `api-client.test.ts` alongside `api-client.ts`).

Component/DOM tests for Nav and auth-context are deferred to a later task when Vitest component testing or Playwright is set up.

## Deferred to Later Tasks

| Item | Task |
|------|------|
| Google GIS sign-in button | 2.3 |
| Silent re-auth on page reload | 2.3 |
| `/login`, `/dashboard`, `/sessions/*` pages | Later tasks |
| Component tests (Nav, auth-context) | 2.5+ |
| Cloudflare Pages deploy CI | 2.10 |
