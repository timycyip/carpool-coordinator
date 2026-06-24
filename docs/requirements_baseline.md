# Carpool Coordinator — Requirements Baseline

| | |
| --- | --- |
| **Title** | Carpool Coordinator — Phase 1 Requirements Baseline |
| **Version** | 1.0 (Draft) |
| **Date** | 2026-06-23 |
| **Author Role** | Business Analyst |
| **Status** | **Draft — pending stakeholder sign-off** |
| **Source Spec** | `docs/functional_requirements_and_architecture.md` v3.0 |

This baseline is a **thin delta document** that records the Phase 1 review status of each
functional requirement, the open questions resolved during discovery, and the sign-off
process. All requirement content (canonical registration schema, NFRs with testable
acceptance criteria, FR details) lives in the **master spec**
(`docs/functional_requirements_and_architecture.md` v3.0), which has been updated to
incorporate all Phase 1 resolutions. This document does not duplicate that content — it
references it.

---

## 1. FR Status Summary

| Status | Count | FR IDs |
| --- | --- | --- |
| Accepted | 7 | FR-1, FR-5, FR-6, FR-7, FR-8, FR-9, FR-11 |
| Clarified | 4 | FR-2, FR-3, FR-4, FR-10 |
| Deferred (FR-level) | 0 | — |

> Note: FR-3 and FR-4 are listed separately for traceability to the v2 spec, but their
> field definitions have been **replaced by the canonical registration schema** in the
> master spec v3.0 §5 (FR-3/FR-4).

---

## 2. FR Status Table

| FR ID | Title | Status | Phase | Key Clarification |
| --- | --- | --- | --- | --- |
| **FR-1** | Authentication & Session Registration | Accepted | 2 | App session = short-lived JWT (1h TTL) stored in SPA memory (ADR-0002). Session code is the only registration gate; no embedded identity in invite links. |
| **FR-2** | Session Management | Clarified | 2 | Status enum fixed at 6 values in snake_case (`draft`, `registration_open`, etc.). `anchor_location` geocoded server-side from postal code. Session code case-insensitive unique. |
| **FR-3** | Registration (canonical schema) | Clarified | 3 | v2 field lists superseded. See master spec v3.0 §5 FR-3/FR-4 for the canonical registration schema (common, driver-specific, passenger-specific, server-derived, validation rules). |
| **FR-4** | User Registration (canonical schema) | Clarified | 3 | Merged into FR-3 canonical schema in the master spec. The v2 split into Common/Driver/Passenger tables is replaced by a single schema with role-specific optional fields. |
| **FR-5** | Geolocation (Nominatim + ORS) | Accepted | 3 | Geocoding = public Nominatim (cached, 30-day TTL). Routing = ORS free tier (not OSRM; OSRM self-hosting deferred). Matrix chunked to 50 locations per call. |
| **FR-6** | Matching Engine | Accepted | 4 | MVP solver = greedy heuristic, sync in Lambda (<300 users). Production solver (OR-Tools/LP) deferred. Deterministic for given input + seed. Versioned match items. |
| **FR-7** | Matching Approval Workflow | Accepted | 5 | State machine `run → proposed → reviewed → approved → published` enforced server-side. Unapproved versions admin-only. |
| **FR-8** | Manual Override | Accepted | 5 | Full override workflow in scope for MVP: move passenger (drag-to-reorder), unassign, lock/unlock, match version switching. Service contract (`PATCH /match/manual`) and admin UI both in scope. |
| **FR-9** | Visibility Rules | Accepted | 5 | Enforced server-side on every read. Matching score never exposed to drivers/passengers. Session Admin scoped to their session only. |
| **FR-10** | Notifications (email; SMS/push deferred) | Clarified | 5 | Deferred delivery per ADR-0008: API writes `notification_pending` items; SQS → Lambda consumer sends via Microsoft Graph `sendMail`. Synchronous sendMail from API path is superseded. HTML templates with org logo placeholder. SMS/WhatsApp/push deferred post-MVP. |
| **FR-11** | Audit Logging | Accepted | 5 (write-path); 6 (retention) | Audit items in `app_data` table keyed by `AUDIT#<date>`. Event types include `auth.login.*`, `session.*`, `registration.*`, `match.run.*`, `match.approved`, `match.override`, `match.lock`, `match.unlock`, `notification.sent`, `notification.failed`. 30-day S3 lifecycle via CloudWatch subscription. |

---

## 3. Content Moved to Master Spec

The following content was produced during Phase 1 Discovery and has been incorporated
into the master spec (`docs/functional_requirements_and_architecture.md` v3.0). This
baseline does not duplicate it.

| Content | Spec location | ADR / Reference |
| --- | --- | --- |
| Canonical registration schema (common, driver, passenger, server-derived, validation rules) | §5 FR-3 / FR-4 (replaced) | Supersedes v2 field lists; single source of truth for Phase 3 |
| NFRs with testable acceptance criteria (NFR-PERF-1..4, NFR-AVAIL-1..2, NFR-SCALE-1..3, NFR-SEC-1..7, NFR-OPS-1..4) | §6 (expanded) | Replaces vague v2 bullets; each NFR is now verifiable |
| Deferred notification delivery (SQS → Lambda consumer) | §5 FR-10 (updated) | ADR-0008 |
| Multi-table DynamoDB (5 tables named per data model) | §8 (updated) | ADR-0001 |
| ORS free-tier routing (replacing OSRM) | §5 FR-5 (updated) | OSRM self-hosting deferred to post-MVP |
| snake_case session status enum | §5 FR-2 (updated) | B3 resolution from consolidated review |
| Next.js (App Router) locked as frontend framework | §15 (updated) | Not "React or Next.js" — decision is locked |
| Idle cost corrected to ≤ $1/month | §10 Analytics (updated) | A9 advisory — CloudWatch Logs never $0 |
| AI agent note on team composition | §17 (added) | Solo dev + AI agents fill the recommended roles |

---

## 4. Open Questions Register

Open questions carried forward from `plans/phase-1-discovery.md` plus new ambiguities
surfaced during baseline drafting. All 13 are **Resolved**. None block Phase 2.

| ID | Question | Resolution |
| --- | --- | --- |
| OQ-1 | Who owns formal sign-off on the requirements baseline? | Team Lead + Product Owner + Business Analyst agents each review independently; Tim (human) consolidates and provides final sign-off. |
| OQ-2 | Is there an existing design language / branding system? | No brand — define from scratch. Clean, minimal look. Tailwind CSS. |
| OQ-3 | Are there compliance constraints (PII residency, GDPR/PIPEDA)? | Defer to post-MVP. MVP ships without special compliance. |
| OQ-4 | Is localization / i18n required for MVP? | English only; i18n deferred. |
| OQ-5 | ORS free-tier matrix chunk size? | 50 locations per matrix call. Sessions >100 users need batching. |
| OQ-6 | Synchronous vs deferred email delivery? | Deferred per ADR-0008: API writes `notification_pending` items; SQS → Lambda consumer sends via Microsoft Graph. Reverses the earlier "synchronous" decision. |
| OQ-7 | Return-trip (`FROM_ORIGIN`) support in MVP? | `TO_DESTINATION` only for MVP. `FROM_ORIGIN` deferred to post-MVP. |
| OQ-8 | Team composition — who owns frontend/backend/infra? | Solo dev + AI agents. No multi-person team. AI agents fill the roles defined in spec §17. |
| OQ-9 | First-deployment AWS region? | `us-east-2` (Ohio). Confirmed by ADR-0003. |
| OQ-10 | Email templates (subject + body + sender identity)? | HTML with org logo placeholder. Professional look without design work. |
| OQ-11 | Maximum acceptable seat capacity? | No cap. Driver enters any number ≥1. |
| OQ-12 | Cross-session role conflicts (driver in A, passenger in B)? | Allow independent per session. No conflict. |
| OQ-13 | Minors / guardians policy? | Defer to post-MVP. No minor-specific handling for MVP. |

---

## 5. Sign-off

Stakeholder sign-off is **required before Phase 2 (Foundation) begins**.

The Team Lead agent, Product Owner agent, and Business Analyst agent each review the Phase 1
artifacts independently and produce review comments. Tim (human) consolidates the reviews
and provides final sign-off. Per OQ-1 / OQ-8, this is a solo-dev project: the Solution
Architect and Stakeholder Representative roles are **not** separate signers; their concerns
are folded into the Team Lead and Product Owner reviews respectively.

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Team Lead Agent | _TBD_ | _TBD_ | _TBD_ |
| Product Owner Agent | _TBD_ | _TBD_ | _TBD_ |
| Business Analyst Agent | _TBD_ | _TBD_ | _TBD_ |
| Final Approver (Human) | Tim | _TBD_ | _TBD_ |

**Sign-off criteria** (all must be true before this section is marked complete):

1. Every FR-1 through FR-11 has a row in §2 with an explicit Accepted / Clarified / Deferred status.
2. The canonical registration schema in the master spec v3.0 §5 (FR-3/FR-4) is reviewed and approved by the Product Owner.
3. All Open Questions in §4 are either Resolved or explicitly Deferred with an owner and target date.
4. The NFRs in the master spec v3.0 §6 have no rows marked "needs definition".
5. The master spec v3.0 and this baseline are committed on the default branch and linked from the Phase 1 plan's validation checklist.

---

## Appendix A — Traceability: FR → Phase → Source Document

| FR | Phase | Primary plan reference | Primary ADR / doc reference |
| --- | --- | --- | --- |
| FR-1 | 2 | `plans/phase-2-foundation.md` | ADR-0002 (JWT session) |
| FR-2 | 2 | `plans/phase-2-foundation.md` | — |
| FR-3, FR-4 | 3 | `plans/phase-3-registration.md` | Master spec v3.0 §5 (canonical schema) |
| FR-5 | 3 | `plans/phase-3-registration.md` | `docs/ideas/carpool-mvp-scope.md` (ORS choice) |
| FR-6 | 4 | `plans/phase-4-matching-engine.md` | Master spec v3.0 §12 |
| FR-7 | 5 | `plans/phase-5-approval-notification.md` | — |
| FR-8 | 5 | `plans/phase-5-approval-notification.md` | — |
| FR-9 | 5 | `plans/phase-5-approval-notification.md` | `docs/rbac_matrix.md` |
| FR-10 | 5 | `plans/phase-5-approval-notification.md` | ADR-0008 (deferred delivery) |
| FR-11 | 5 (write-path) / 6 (retention) | `plans/phase-5-approval-notification.md`, `plans/phase-6-hardening.md` | Master spec v3.0 §10 |
