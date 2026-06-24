# ADR-0009: Contract-First API Design with Shared Error Envelope

## Status
Accepted

## Date
2026-06-24

## Context
Task 2.1 (backend scaffold) establishes the patterns every subsequent endpoint follows.
Two foundational decisions are needed before Task 2.2+ adds real endpoints:

1. **Response contract approach** — how endpoints declare their response shape.
2. **Error response format** — how all error responses are structured.

The Phase 1 API contracts doc (`docs/api_contracts.md` §2, §5) already specifies the error
envelope and Pydantic stubs, but the contract was not yet implemented in code. The master spec
(`docs/functional_requirements_and_architecture.md` v3 §11) prescribes FastAPI + Pydantic but
does not mandate the response-model pattern.

The `api-and-interface-design` skill mandates: "Every endpoint has typed input and output
schemas" and "Error responses follow a single consistent format."

## Decision

### Contract-First with Pydantic `response_model`

Every API endpoint declares a Pydantic `response_model` parameter on the route decorator.
The handler function returns the Pydantic model instance (not a raw dict). FastAPI
auto-generates the OpenAPI 3.1.0 schema from these models — the types ARE the documentation.

```python
@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
```

### Shared Error Envelope

All error responses use `ErrorResponse` / `ErrorBody` from `app/models/error.py`, matching
the contract in `docs/api_contracts.md` §2:

```json
{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {...}}}
```

The `code` field is a machine-readable constant from the §2.1 error code table. The `message`
is human-safe (no PII, no stack traces). The `details` field is optional structured context.

### Input/Output Model Separation

Each resource will have separate Create, Update, and Response Pydantic models (e.g.,
`SessionCreate`, `SessionUpdate`, `SessionResponse`) following the stubs in
`docs/api_contracts.md` §5. This prevents leaking server-generated fields (IDs, timestamps)
into input schemas.

## Alternatives Considered

### Alternative A: Raw dict returns (rejected)
Return `dict[str, Any]` from handlers, no `response_model`.

- Pros: Less boilerplate; quick to write.
- Cons: No OpenAPI schema for responses; no type enforcement; consumers must read source
  code or prose docs to know the shape; mypy can't catch response-shape bugs. Violates
  the "types ARE the documentation" principle.
- Rejected: contract-first is a project requirement per the api-and-interface-design skill.

### Alternative B: Exception-based errors with no shared model (rejected)
Raise `HTTPException(status_code=422, detail="...")` with ad-hoc detail strings or dicts.

- Pros: Built into FastAPI; minimal code.
- Cons: Inconsistent error shapes across endpoints (some strings, some dicts); clients
  can't reliably parse errors; no machine-readable `code` field; the `detail` text becomes
  a de facto contract that changes unexpectedly (Hyrum's Law).
- Rejected: violates "Consistent Error Semantics" from the api-and-interface-design skill.

### Alternative C: Custom exception handlers (rejected)
Define domain exceptions (`SessionNotFound`, `ValidationError`) and register FastAPI
exception handlers that serialize them into `ErrorResponse`.

- Pros: Clean `raise` syntax in service code; centralized error serialization.
- Cons: Adds an exception hierarchy before any real endpoints exist (premature abstraction);
  the handler mapping is invisible from the route definition; harder to see which errors
  an endpoint can return. Can be layered on later if service code grows complex.
- Rejected for MVP: the explicit `ErrorResponse` return is simpler for the current scope.
  Revisit if exception-driven flow becomes common in Phase 3+.

## Consequences
- **Positive:** OpenAPI schema is auto-generated and always in sync with the code. Clients
  (including the Next.js frontend) can generate typed API clients from the schema.
- **Positive:** Every endpoint's response shape is visible from the route decorator — no
  need to read the handler body.
- **Positive:** All errors have the same JSON structure, so frontend error handling is
  uniform (`response.data.error.code`).
- **Negative:** Slightly more boilerplate per endpoint (Pydantic model + `response_model`
  parameter). Acceptable; the models serve as both runtime validation and documentation.
- **Neutral:** The `docs/api_contracts.md` §5 Pydantic stubs are the source of truth for
  model definitions. `app/models/` implementations must match them. If the contract is
  updated, the models must be updated in lockstep.

## Links
- `docs/api_contracts.md` §2 (Error Taxonomy), §5 (Pydantic stubs)
- `docs/functional_requirements_and_architecture.md` v3 §11 (backend tech stack)
- `plans/phase-2-foundation.md` §Code Style (conventions)
- Task 2.1 plan: `.kilo/plans/1782326611319-backend-scaffold-health-endpoint.md`
