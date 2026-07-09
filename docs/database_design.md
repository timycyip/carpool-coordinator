# Database Design

## Overview

The platform uses **five DynamoDB tables**.
This follows ADR-0001: tables are named by data model instead of consolidating everything into one physical table.

## Table Map

| Table | Purpose | Notes |
|---|---|---|
| `app_data` | Durable business data | Internal single-table PK/SK model for users, sessions, registrations, matches, session admins, and audit logs |
| `session_cache` | Session-scoped transient state | TTL-backed ephemeral data |
| `rate_limit_cache` | Request rate counters | TTL-backed per-IP / per-user counters |
| `brute_force_counter` | Failed-auth lockout tracking | TTL-backed abuse protection state |
| `geocode_cache` | Postal-code geocode cache | TTL-backed location cache |

## `app_data` Model

`app_data` is the only table that uses PK/SK overloading. That design keeps related records colocated under the same partition key so the main access patterns stay single-table and single-query.

### Entities

- `USER#<sub>` / `METADATA`
- `SESSION#<code>` / `METADATA`
- `SESSION#<code>` / `REG#<sub>`
- `SESSION#<code>` / `MATCH#V<n>`
- `SESSION#<code>` / `ADMIN#<sub>`
- `AUDIT#<YYYY-MM-DD>` / `<ISO-ts>#<event_id>`

### GSIs

- `gsi_sessions_by_user`
  - PK: `gsi1_pk`
  - SK: `gsi1_sk`
  - Purpose: list sessions for a user
- `gsi_admins_by_user`
  - PK: `gsi2_pk`
  - SK: `gsi2_sk`
  - Purpose: list sessions a user administers

## Why the Tables Are Split

The cache and counter tables have very different traffic and retention characteristics from durable business data.
Keeping them separate lets us tune TTL, backup, and operational behavior independently instead of coupling everything to `app_data`.

## Access Pattern Summary

| Access pattern | Storage path |
|---|---|
| Get user / session | `GetItem` on `app_data` |
| List registrations for a session | `Query` on `app_data` with `SK begins_with REG#` |
| Get latest match version | `Query` on `app_data` with `SK begins_with MATCH#`, descending, limit 1 (the ERD's `gsi_latest_match_by_session` is intentionally not provisioned; main-table query is sufficient) |
| List sessions for a user | `gsi_sessions_by_user` |
| List sessions a user administers | `gsi_admins_by_user` |
| Rate limiting / brute force / geocode lookup | Direct-key queries on dedicated cache tables |

## Operational Notes

- All tables use `PAY_PER_REQUEST` (ADR-0007).
- All tables have SSE enabled.
- `app_data` has PITR enabled; cache tables do not.
- `app_data` should be protected with deletion protection in non-dev environments.
- Terraform state should be remote and locked before production deployment.

## References

- [ADR-0001: Tables Named Per Data Model](adr/0001-table-naming-by-data-model.md)
- [ADR-0007: DynamoDB On-Demand Capacity](adr/0007-dynamodb-on-demand.md)
- [Data Model & ERD](data_model_erd.md)
