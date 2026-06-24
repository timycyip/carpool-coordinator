# Carpool Coordinator

A carpool coordination platform for events — church gatherings, conferences, school
activities, group trips. Automates ride registration, passenger-driver matching, route
optimization, admin approval, and assignment publishing.

Built with **FastAPI** (AWS Lambda) + **Next.js** (Cloudflare Pages) + **DynamoDB**.

## Quick Start

### Backend (Python 3.12+)

```bash
# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/ -v

# Start local dev server
uv run uvicorn app.main:app --port 8000 --reload

# Health check
curl localhost:8000/health
# → {"status":"ok"}
```

### Legacy CLI (preserved, not modified)

```bash
pip install -r requirements.txt
python3 src/main.py <input_csv> <output_csv>
```

## Commands

### Backend

| Command | Description |
|---------|-------------|
| `uv sync --extra dev` | Install all dependencies (runtime + dev) |
| `uv run pytest tests/ -v` | Run tests with verbose output |
| `uv run pytest --cov=app --cov-report=term-missing` | Run tests with coverage |
| `uv run ruff check .` | Lint (ruff) |
| `uv run ruff format --check .` | Format check |
| `uv run ruff format .` | Auto-format |
| `uv run mypy .` | Type check (strict mode) |
| `uv run uvicorn app.main:app --port 8000 --reload` | Local dev server |
| `uv run python -c "from app.main import handler"` | Verify Lambda handler import |

### Legacy CLI

| Command | Description |
|---------|-------------|
| `pip install -r requirements.txt` | Install legacy dependencies |
| `python3 src/main.py <in.csv> <out.csv>` | Run matching algorithm |
| `python3 -m unittest` | Run legacy tests |

## API Documentation

FastAPI auto-generates interactive API docs from Pydantic models:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

### Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/health` | Liveness probe | None |

Additional endpoints (auth, sessions, registration, matching, admin) are defined in
`docs/api_contracts.md` and will be implemented in Phase 2–5.

### Error Format

All errors follow a consistent envelope (`docs/api_contracts.md` §2, ADR-0009):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description.",
    "details": { "fields": [...] }
  }
}
```

## Architecture

```
app/                        Backend (FastAPI + Mangum → AWS Lambda)
  main.py                   FastAPI app + Mangum handler export
  api/                      Route modules (health, auth, sessions, ...)
  models/                   Pydantic models (request/response contracts)
  auth/                     Google OIDC verification
  services/                 Business logic
  repositories/             DynamoDB data access
  middleware/                auth, rbac, rate_limit, audit
tests/                      pytest tests (mirrors app/ layout)
src/                        Legacy CLI (untouched)
test/                       Legacy unittest tests (untouched)
mock/                       Legacy CSV fixtures
docs/                       Requirements, architecture, Phase 1 artifacts
  adr/                      Architecture Decision Records (0001–0009)
plans/                      Phase plans (phase-1 through phase-6)
infra/                      IaC (Terraform) — Phase 2+
frontend/                   Next.js app — Phase 2+
```

### Key Design Decisions

| Decision | ADR |
|----------|-----|
| DynamoDB tables named per data model (multi-table, not consolidated) | [ADR-0001](docs/adr/0001-table-naming-by-data-model.md) |
| App session JWT (not opaque tokens) | [ADR-0002](docs/adr/0002-app-session-jwt.md) |
| AWS region = us-east-2 (Ohio) | [ADR-0003](docs/adr/0003-terraform-iac-us-east-2.md) |
| Same-origin rewrites (Cloudflare → Lambda) | [ADR-0004](docs/adr/0004-same-origin-rewrites.md) |
| Middleware ordering (rate_limit → auth → rbac → audit) | [ADR-0005](docs/adr/0005-middleware-ordering.md) |
| DynamoDB on-demand capacity | [ADR-0007](docs/adr/0007-dynamodb-on-demand.md) |
| Deferred notification delivery (SQS → Lambda) | [ADR-0008](docs/adr/0008-deferred-notification-delivery.md) |
| Contract-first API with shared error envelope | [ADR-0009](docs/adr/0009-contract-first-error-envelope.md) |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend runtime | Python 3.12, FastAPI, Mangum (Lambda adapter) |
| Database | DynamoDB (on-demand, multi-table) |
| Auth | Google OIDC → app session JWT |
| Geocoding | Nominatim (public, cached) |
| Routing | OpenRouteService free-tier API |
| Package manager | uv (backend), npm (frontend) |
| Linting/formatting | ruff |
| Type checking | mypy --strict |
| Testing | pytest + pytest-asyncio |
| IaC | Terraform (Phase 2+) |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Edge/CDN | Cloudflare (Pages + Free tier) |

## Contributing

### Quality Gates (must pass before commit)

```bash
# Backend
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest tests/ -v
```

### Conventions

- `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE` enums.
- `mypy --strict` — no `Any` without justification.
- `async` route handlers.
- Pydantic `response_model` on every endpoint (contract-first, ADR-0009).
- Shared `ErrorResponse` for all error responses.
- `ruff format` (line-length 88).
- TDD: write a failing test before implementing logic.
- Never commit secrets. Use AWS Parameter Store / environment variables.

### Architecture Decision Records

Significant technical decisions are recorded in `docs/adr/`. See the
[template](docs/adr/0000-template.md) for format. Every ADR captures context,
decision, alternatives considered, and consequences.

## References

- [Functional Requirements & Architecture](docs/functional_requirements_and_architecture.md)
- [REST API Contract](docs/api_contracts.md)
- [Phase Plans](plans/)
- [Knowledge Base](KNOWLEDGE.md)
