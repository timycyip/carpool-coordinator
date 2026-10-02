# ADR-0015: Cost-First Capacity and Non-Production Data Protection

## Status
Accepted for the non-production Terraform configuration; production adoption remains gated by the existing production approval.

## Date
2026-10-01

## Context
The owner set a cost target of near-zero AWS spend, including under high traffic, and specifically prefers DynamoDB's always-free provisioned capacity. The existing five-table-per-environment setup used on-demand billing and enabled continuous backups on business data in every environment. Those defaults can charge per request and per stored backup GB.

The DynamoDB free allowance is shared across the AWS account and region. With dev, staging, and production, the five tables per environment and two GSIs on `app_data` create 21 independently provisioned table/index capacities per read/write dimension. Provisioning each at 1 RCU and 1 WCU uses 21 of the 25 free provisioned units in each dimension, leaving four units for measured allocation. Actual operation capacity is lower where writes also update GSIs, and the allowance is not a guarantee against throttling during bursts.

## Decision
Use provisioned DynamoDB capacity, initially 1 RCU and 1 WCU for each table and 1 RCU/WCU for each `app_data` GSI. Do not enable auto scaling by default: it can raise capacity beyond the free allowance and cause charges. Add capacity only after measuring the account-wide total and accepting any expected charge. Handle traffic beyond provisioned capacity with back-pressure and clear retry responses.

Disable point-in-time recovery in dev and staging. Require production to enable PITR before production Terraform is authorized. Non-production environments use disposable test data and can be reseeded from fixtures.

Manage one monthly account cost budget from dev Terraform state, with actual spend notification at 80% and forecasted spend notification above 100%. The budget is an alert, not a spending cap. Provision its email subscriber through the dev GitHub Environment secret `COST_ALERT_EMAIL`; without that value the budget resource is not created.

Use deterministic fixtures for geocoding, routing, and notification delivery in dev and staging. Keep live-provider calls opt-in for controlled integration checks. Apply provider-wide daily and per-minute quotas, plus per-user and per-session match-run limits, in addition to the existing general API limits.

## Alternatives Considered

### DynamoDB on-demand
Scales without capacity planning and handles abrupt peaks, but every request is billed. Rejected as the default because the owner prioritizes the free provisioned allowance and accepts back-pressure above it.

### Provisioned capacity with auto scaling
Can raise capacity for load but may exceed the free allocation and incurs a warm-up interval. Deferred until measured usage justifies the additional cost.

### Redis/ElastiCache in front of DynamoDB
A cache may reduce repeated reads, but registrations, rate-limit updates, and audit writes remain durable writes. A managed cache adds a continuously running cost and does not solve the provisioned write-capacity bottleneck. Rejected for the near-zero-cost target.

### SQS buffering for writes
SQS can smooth bursts, but accepting a registration before DynamoDB persistence changes the API to asynchronous acceptance, requires idempotency/status handling, and can create an unbounded queue if drain capacity is inadequate. Defer until a separate API contract decision. SQS remains a possible burst buffer if eventual persistence is acceptable.

### PITR in non-production
Provides fast recovery but adds continuous backup storage cost. Rejected for disposable dev and staging datasets; retained as a production requirement.

## Consequences
- Quiet environments have no provisioned-capacity request charge while total provisioned table and index capacity stays within the account's free allowance.
- The initial 1/1 allocation is a low-cost baseline, not a high-throughput guarantee. The application must surface throttling and clients must retry safely.
- Three environments share the free allowance; each environment does not receive a separate 25-unit pool.
- No provisioned-capacity charge budget is enforced automatically. AWS Budgets alerts do not stop usage.
- Dev/staging lose point-in-time recovery and must use disposable fixtures.
- Provider quotas must be coordinated at the account/key level because dev, staging, and production could otherwise compete for a shared upstream API key.

## Links
- Supersedes the default billing-mode decision in [ADR-0007](0007-dynamodb-on-demand.md) for this cost-first deployment.
- [Phase 2 plan](../../doc/plans/phase-2-foundation.md)
- [Phase 3 plan](../../doc/plans/phase-3-registration.md)
- [Phase 4 plan](../../doc/plans/phase-4-matching-engine.md)
- [Phase 5 plan](../../doc/plans/phase-5-approval-notification.md)
