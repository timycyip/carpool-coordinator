# Cost Controls and Low-Cost Operating Limits

The owner target is near-zero infrastructure spend, including with three environments. Free allowances are account-wide or provider-key-wide; dev, staging, and production do not each get a separate allowance. This is an optimization target, not a promise that arbitrary traffic remains free. Confirm that the AWS account is eligible for DynamoDB's always-free provisioned allowance in Billing; newer AWS signup plans may apply credits rather than the legacy always-free service allowance.

## DynamoDB capacity

Use provisioned capacity as recorded in [ADR-0015](adr/0015-cost-first-capacity-controls.md). The current Terraform baseline sets every one of five tables to 1 RCU and 1 WCU, plus two GSIs at 1 RCU/WCU each per environment. Three environments therefore consume 21 provisioned units in each dimension, within the documented 25-unit free pool and leaving four units for reallocation. This calculation assumes all environments share the same account and region, all table/GSI classes remain eligible, and no other workloads consume that pool.

At this baseline, a hot table or GSI can throttle well below an event-registration burst. Provisioned mode lowers steady traffic cost; it does not make a sudden burst free or guarantee it will succeed. Do not raise capacities or enable auto scaling without measuring table and GSI consumption and understanding the added monthly cost. Return retryable back-pressure when DynamoDB throttles. SQS can smooth writes while using its own free request allowance, but an asynchronous registration acceptance flow needs idempotency and visible pending status; Phase 3/API contract must decide that before implementation. Redis/ElastiCache has a continuous service cost and cannot replace authoritative registration, audit, or counter writes, so it is not a fit for this cost target.

## Backups

PITR is disabled in dev and staging. Those datasets are disposable and reseeded from deterministic fixtures. Production must enable PITR before the production deployment gate is lifted. This reduces non-production backup storage charges while retaining recoverability for real user data.

## Routing and geocoding quotas

Dev/staging use fixtures for Nominatim, ORS, and email; live integration runs are explicit and controlled. Production caches geocoding and matrix results. Enforce provider-wide daily and per-minute quotas because per-user limits cannot protect a quota shared by all users. As an initial operating limit, cap shared live ORS usage at 400 matrix requests/day and 1,600 directions requests/day (80% of the currently published Standard allowance), with 32 requests/minute across the account. Also limit each user's uncached matching to 5 runs/day and one run per session per 10 minutes; charge quota only for provider calls, not cache hits. Adjust these numbers after measuring calls per matching run and confirm against the application account. The current published ORS Standard plan lists 500 matrix requests/day and 2,000 directions requests/day, with 40 requests/minute; the matrix endpoint also limits a request to 3,500 origin-destination pairs.

## Email queue sizing

SQS includes 1 million requests/month. A simple, unbatched successful delivery usually needs at least one send, one receive, and one delete request: roughly 333,000 deliveries could use one million API requests before retries and empty long polls. Batch APIs can process up to 10 messages per request, so the theoretical delivery count can be higher (around 3.3 million at three batch operations per ten messages), with actual usage reduced by empty polling, retries, and payload chunking. This counts SQS API requests, not emails. Batch sends/deletes and use long polling; monitor queue age and approximate request count.

## Encryption and parameter storage

SSM Parameter Store is a parameter/secrets store, not a replacement for encryption. Standard `String` parameters avoid KMS but store plaintext and are unsuitable for credentials such as `JWT_SECRET`. `SecureString` uses KMS; choosing the AWS-managed `aws/ssm` key avoids a customer-managed key's monthly key fee, while KMS API request pricing and applicable service behavior still need to be checked. The DynamoDB Terraform encryption block uses the default AWS-owned key. For S3, SSE-S3 (`AES256`) is a lower-cost managed-at-rest-encryption option, but current NFR-SEC-4 requires SSE-KMS, so changing that requirement needs an explicit security decision. Do not put secret values in Terraform state or ordinary String parameters.

## Cost alerts and current monitoring resources

Terraform manages one $5/month account-wide AWS Budget from dev state. It emails at 80% actual spend and when forecast spend exceeds 100%; set the `COST_ALERT_EMAIL` secret in the GitHub `dev` Environment. It is an alert only, not a spending cap. Billing data may arrive with delay. The current Terraform has a 30-day Lambda log group and no CloudWatch metric alarms, dashboards, or custom metrics; Phase 6 plan entries for those are future work, not deployed resources.

The M365 mailbox and Exchange service are assumed to be existing organizational services and are excluded from this infrastructure cost estimate.

## Static frontend and API usage

Serve the exported frontend as static Pages assets and invoke a Pages Function only for `/api/*`, using `public/_routes.json` to keep static asset requests off the Function. Cloudflare's Workers Free allowance currently includes 100,000 requests/day and a 10 ms CPU limit per invocation; only proxied API calls count against that runtime allowance. Keep API responses small and bound expensive work at the backend. Check current limits before launch because provider quotas can change.
