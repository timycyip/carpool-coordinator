# ADR-0001: DynamoDB Tables Named Per Data Model (Not Consolidated)

## Status
Accepted

## Date
2026-06-23

## Context
Section 10 of `docs/functional_requirements_and_architecture.md` lists **four** DynamoDB
tables: `app_data`, `session_cache`, `rate_limit_cache`, `brute_force_counter`.

An earlier draft of the Phase 2 plan proposed consolidating these into a **single**
`app_data` table, storing rate-limit counters and geocode-cache items as TTL items within
it. The rationale was operational simplicity (one table to provision, monitor, and reason
about) and the natural fit of TTL items for ephemeral counters/caches.

This consolidation would have **superseded** the requirements doc Section 10, so per
AGENTS.md §12 it required a human-approved ADR.

The human review (2026-06-23) **rejected** the single-table consolidation. The directive
is to name DynamoDB tables **by data model** rather than collapsing everything into one
table. This keeps the storage layer a faithful reflection of the data model produced by
Phase 1 Discovery (`docs/data_model_erd.md`) and avoids overloading one table with
heterogeneous access patterns.

## Decision
DynamoDB tables are **named per data model** as defined by the Phase 1 ERD
(`docs/data_model_erd.md`). We will **not** consolidate all entities into a single
`app_data` table.

Concretely:
- Phase 1 Discovery (`plans/phase-1-discovery.md` Task 4) produces the canonical ERD with
  explicit table boundaries, partition/sort keys, GSIs, and TTL attributes.
- Each logical entity group (e.g., application data, session cache, rate-limit counters,
  brute-force counters, geocode cache) maps to a **named table** decided by the ERD — not
  a single overloaded table.
- TTL attributes are still used on ephemeral/cache tables (rate-limit, brute-force,
  session cache, geocode cache) where appropriate.
- The exact set of tables and their names will be finalized in Phase 1 and recorded in
  `docs/data_model_erd.md`. The list in Section 10 of the requirements doc (`app_data`,
  `session_cache`, `rate_limit_cache`, `brute_force_counter`) is the **starting point**,
  subject to refinement during Phase 1 design.

## Alternatives Considered
### Alternative A: Single table `app_data` (rejected)
Store every entity (users, sessions, registrations, matches, audit, rate-limit counters,
geocode cache) in one table, discriminating by PK prefix (`USER#`, `SESSION#`, `REG#`,
`MATCH#`, `AUDIT#`, `RL#`, `GEO#`) and using TTL on ephemeral items.

- Pros: one table to provision/monitor; fewer IaC resources; single-table design is a
  well-known DynamoDB pattern for efficient joins.
- Cons: overloads one table with wildly different access patterns and traffic profiles
  (hot rate-limit writes vs. cold audit writes); blurs the data model; makes per-table
  capacity, TTL, and backup policies harder to tune; couples cache/ephemeral data lifetime
  to durable application data. **Rejected by human review.**

### Alternative B: Tables named per data model (chosen)
Each logical entity group gets its own table, named to reflect its data model. TTL and
per-table settings are tuned independently.

- Pros: storage layer mirrors the data model; independent capacity/TTL/backups per concern;
  clearer ownership and reasoning; aligns storage with the Phase 1 ERD.
- Cons: more tables to provision and monitor (acceptable; operational cost is low with
  IaC).

## Consequences
- **Positive:** The data model in `docs/data_model_erd.md` is the single source of truth
  for table design. Per-table TTL, capacity, and PITR can be tuned to each entity's needs.
  Hot rate-limit traffic is isolated from application data.
- **Negative:** More DynamoDB tables to manage in Terraform; cross-table transactions
  (if ever needed) are limited to DynamoDB transaction APIs across up to 25 items.
- **Action required:** Phase 1 Discovery must finalize the table list and names in
  `docs/data_model_erd.md` before Phase 2 Task 2.2 (DynamoDB schema + repository layer)
  can begin. Task 2.2 is updated to provision tables per the ERD via Terraform.
- **Supersedes:** the "single table `app_data`" statements previously in
  `plans/phase-2-foundation.md` (now corrected).

## Links
- Requirements doc Section 10 (Database): `docs/functional_requirements_and_architecture.md`
- Phase 1 plan Task 4 (Data model ERD): `plans/phase-1-discovery.md`
- Phase 2 plan Task 2.2 (DynamoDB schema + repository layer): `plans/phase-2-foundation.md`
