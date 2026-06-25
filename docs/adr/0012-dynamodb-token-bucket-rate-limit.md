# ADR-0012: DynamoDB Atomic Token-Bucket Rate Limiting

## Status
Accepted

## Date
2026-06-25

## Context
Phase 2 Task 2.8 requires rate limiting: 60 req/min per IP, 120 req/min per user, with
`Retry-After` headers and `X-RateLimit-*` response headers per API contracts §1.4. The
rate limiter runs first in the middleware chain (ADR-0005) to reject abusive traffic before
any expensive downstream work (JWT verification, DynamoDB reads for RBAC, audit writes).

Forces at play:
- **Atomicity**: Multiple concurrent requests from the same IP must not race past the
  limit. A read-check-write pattern (GetItem → condition → UpdateItem) is not safe under
  concurrent invocations from a single Lambda process or across Lambda instances.
- **Cost**: Rate-limit checks are the most frequent DynamoDB operations (once per request).
  They must minimize RCU/WCU consumption. On-demand billing (ADR-0007) means every
  operation costs money.
- **Latency**: Rate limiting must add negligible p50/p95 latency. The check should be a
  single DynamoDB round-trip.
- **TTL cleanup**: Old rate-limit records must auto-expire without a background sweeper.
- **Abuse detection** (e.g., brute-force login escalation) is deferred to post-MVP.

## Decision

### Atomic `UpdateItem` with ConditionExpression

Use a **single** DynamoDB `UpdateItem` call per rate-limit bucket, combining increment and
cap-check atomically:

```python
response = ddb_client.update_item(
    TableName="rate_limit_cache",
    Key={"PK": {"S": pk}, "SK": {"S": sk}},  # e.g., PK=RATELIMIT#IP#1.2.3.4, SK=1700000000
    UpdateExpression="ADD #count :inc",
    ConditionExpression="attribute_not_exists(#ts) OR (#ts = :window_start AND #count <= :limit)",
    ExpressionAttributeNames={"#count": "count", "#ts": "ts"},
    ExpressionAttributeValues={
        ":inc": {"N": "1"},
        ":window_start": {"N": str(window_start)},
        ":limit": {"N": str(limit)},
    },
    ReturnValues="UPDATED_NEW",
)
```

**How it works:**
- `ADD #count :inc` increments the counter atomically.
- `ConditionExpression` fails (raises `ConditionalCheckFailedException`) if:
  - The item exists AND its `ts` matches the current window AND count > limit.
- On condition failure, the rate limiter catches the exception and returns 429.
- `ReturnValues="UPDATED_NEW"` returns the post-increment count for response headers.

**Window rotation:** When `SK` changes (new `window_start` floor), `attribute_not_exists(#ts)`
is true for the new partition/SK combination, creating a fresh item. The old window's item
has a different `SK` so the new write doesn't conflict.

### PK/SK Design

| Bucket | PK | SK |
|--------|----|----|
| Per-IP | `RATELIMIT#IP#<ip>` | `<window_start>` (Unix timestamp floored to window size) |
| Per-user | `RATELIMIT#USER#<sub>` | `<window_start>` (Unix timestamp floored to window size) |

For authenticated requests, **both** the per-IP and per-user buckets are checked within
the same request. Both must pass for the request to proceed. The per-user bucket uses the
`sub` from the JWT (available after auth, but rate limiting runs before auth — so the
per-user check only applies to authenticated requests that also exceeded the IP limit).

### TTL

`rate_limit_cache` table items have a `ttl` attribute set to `window_start + 2 * window_seconds`.
DynamoDB auto-deletes expired items within 48 hours (free).

### Configuration

Environment variables with defaults:
- `RATE_LIMIT_PER_IP=60`
- `RATE_LIMIT_PER_USER=120`
- `RATE_LIMIT_WINDOW_IP=60` (seconds)
- `RATE_LIMIT_WINDOW_USER=60` (seconds)

## Alternatives Considered

### Alternative A: In-memory rate limiting (rejected)
Store counters in a Python `dict` or `functools.lru_cache`.

- Pros: Zero latency; zero cost; simplest implementation.
- Cons: Not shared across Lambda instances; a second cold-started Lambda has no memory
  of the first instance's rate-limit state. Users could trivially bypass by waiting for
  Lambda scale-out. Rejected: the rate limiter must be consistent across all invocation
  paths.

### Alternative B: GetItem → condition → UpdateItem (rejected)
Read current count, check threshold in code, then write.

- Pros: Slightly simpler code; no need for error-based control flow.
- Cons: Race condition — two concurrent requests both read `count=59`, both pass the
  check, both increment to 60 → neither gets 429. This is a classic check-then-act
  anti-pattern under concurrency. Rejected: must be atomic.

### Alternative C: DynamoDB Transactions (rejected)
Use `TransactWriteItems` to read and update atomically.

- Pros: Stronger consistency guarantee; no condition-expression coupling.
- Cons: 2× WCU consumption per check; 2× latency (round-trip for read + write);
  transactions cost more than a single `UpdateItem`. Rejected: overkill for rate limiting;
  the `ConditionExpression` approach achieves the same goal at lower cost.

### Alternative D: AWS WAF rate-based rules (rejected)
Delegate IP rate limiting to AWS WAF at the API Gateway layer.

- Pros: No application code; AWS-managed; handles volumetric DDoS.
- Cons: Can't do per-user rate limiting (WAF sees IPs, not JWT claims); adds API Gateway
  cost; Cloudflare Free WAF is already the edge layer. Rejected: Cloudflare + app-level
  rate limiting is sufficient for MVP.

### Alternative E: Atomic UpdateItem + ConditionExpression (chosen)
- Pros: Single round-trip; atomic (no race); single WCU per check; simple error-based
  control flow; TTL handles cleanup.
- Cons: The error-based control flow is slightly unusual (exceptions for capacity);
  requires careful `ExpressionAttributeNames`/`Values` construction.

## Consequences
- **Positive:** 1 WCU per request per bucket (= $0.00000125). No race conditions.
  Auto-cleanup via TTL. Configurable limits and windows per environment.
- **Negative:** Per-user bucket is wasted on unauthenticated requests (the sub is unknown
  before auth, but rate limiting runs before auth per ADR-0005). The per-user check only
  applies to authenticated requests. Abusive unauthenticated traffic is caught by the
  per-IP bucket.
- **Negative:** The `ConditionalCheckFailedException` catch is not typed — DynamoDB
  reports it as a generic `ClientError`. The exception message parsing is brittle. Fine
  for MVP; add a typed error wrapper in a future hardening pass.

## Performance Note (2026-06-25)

The initial implementation included an unnecessary `GetItem` before the `UpdateItem` to
pre-check the count. This was removed in commit `5a11522` because the `ConditionExpression`
handles the check atomically within the `UpdateItem` itself. The `GetItem` was dead code
that cost an extra RCU per request.

## Links
- ADR-0005 (middleware ordering — rate_limit first)
- API contracts §1.4 (rate-limit headers)
- `app/middleware/rate_limit.py` — implementation
- `tests/middleware/test_rate_limit.py` — 12 tests
