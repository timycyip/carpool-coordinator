# ADR-0007: DynamoDB On-Demand Capacity

## Status
Accepted

## Date
2026-06-23

## Context
DynamoDB offers two capacity modes: **on-demand** (pay-per-request) and **provisioned** (pre-set
RCU/WCU with optional auto-scaling). The carpool platform has highly bursty traffic: near-idle
between events, then hundreds/thousands of requests when registration opens or a session runs.

Forces at play:
- Business goal: $0 idle cost.
- NFR: handle bursts up to 5000 req/min (spec §6 / §14).
- Phase 2 is MVP / single-tenant — operational simplicity matters more than cost optimization.
- Provisioned capacity with auto-scaling has a warm-up delay (minutes) which may miss burst spikes.
- ADR-0001 means multiple DynamoDB tables — each would need independent capacity tuning if
  provisioned.

## Decision
Use **on-demand capacity** for all DynamoDB tables. Tables scale automatically to accommodate
traffic patterns without pre-provisioning. Per-request pricing is used.

This applies to all tables: application data, session cache, rate-limit cache, brute-force counter,
and any future tables (Phase 3+).

## Alternatives Considered

### Alternative A: Provisioned capacity with auto-scaling
- Pros: cheaper at sustained high traffic (~70% cheaper at predictable steady-state load);
  reserved capacity offers further discounts.
- Cons: auto-scaling has a warm-up delay (minutes); burst spikes can be throttled before scaling
  kicks in; each table needs independent scaling policies; more operational burden for MVP.

### Alternative B: Provisioned capacity (fixed)
- Pros: predictable cost.
- Cons: must estimate peak capacity upfront; over-provisioned at idle ($$); under-provisioned at
  peak (throttling). **Rejected for bursty workload.**

### Alternative C: On-demand (chosen)
- Pros: $0 idle; scales instantly with traffic; no capacity planning; no auto-scaling config;
  works with multiple tables (ADR-0001) without per-table tuning.
- Cons: ~7x more expensive per request than provisioned at steady-state high traffic. At 5000
  req/min sustained, on-demand costs ~$0.625/1M WRUs vs ~$0.09/1M WRUs provisioned. For bursty
  event-based usage the absolute cost difference is negligible (pennies per event).

## Consequences
- **Positive:** Zero operational burden; scales automatically; $0 idle; burst-proof; simplifies
  multi-table management.
- **Negative:** Higher per-request cost at sustained high traffic. If the platform grows to
  sustained high traffic (thousands of requests/second, 24/7), switch to provisioned with
  auto-scaling — revisit in Phase 6 hardening.
- **Action required:** Terraform sets `billing_mode = "PAY_PER_REQUEST"` on all DynamoDB tables.

## Links
- ADR-0001 (tables per data model): `docs/adr/0001-table-naming-by-data-model.md`
- Phase 2 plan Task 2.2 (DynamoDB schema): `plans/phase-2-foundation.md`
- ARCHITECTURE.md §Technology Stack: `ARCHITECTURE.md`
