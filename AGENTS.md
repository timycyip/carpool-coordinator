# AGENTS.md — Carpool Coordinator

This file is the single source of truth for how AI agents (Kilo, subagents, Team Lead)
operate on this repository. Read it before doing any work. It defines the project context,
toolchain, workflow, quality gates, and the mapping from intent → skill → agent.

---

## 1. Project Overview

Carpool Coordinator is a **carpool coordination platform** for events (church gatherings,
conferences, volunteering, school activities, group trips). It automates ride registration,
passenger-driver matching, route optimization, an admin approval workflow, and assignment
publishing.

The repository is mid-transformation:

- **Legacy** (`src/main.py`): a Python CLI script that reads a CSV of drivers/riders, geocodes
  addresses with Nominatim, builds a scipy distance matrix, and writes matched carpools to a
  CSV. Dependencies: `pandas`, `geopy`, `scipy`. Tests in `test/` are `unittest`-based stubs.
- **Target** (per `docs/functional_requirements_and_architecture.md` v2): a full-stack web app —
  FastAPI + Mangum on AWS Lambda ARM64, Next.js (App Router) on Cloudflare Pages, DynamoDB
  single-table, Google OIDC, Nominatim (geocode) + self-hosted OSRM (matrix/route), and a
  greedy matching MVP that reuses the legacy `src/main.py` logic relocated into
  `app/services/matching.py`.

The build-out is phased: **Phase 1 Discovery → Phase 6 Hardening** (see `plans/`).

---

## 2. Current Project Status

| Area | State |
| --- | --- |
| Legacy CLI | Present in `src/main.py`; superseded by the platform build but retained as the matching-algorithm reference. |
| Phase 1 — Discovery | **Active.** Producing design artifacts (requirements baseline, RBAC matrix, workflow diagrams, ERD, API contracts, wireframes) in `docs/`. No production code ships this phase. |
| Phase 2 — Foundation | Planned. FastAPI skeleton, Google OIDC, session CRUD, RBAC middleware, rate limiting, DynamoDB schema, Next.js bootstrap. |
| Phase 3 — Registration | Planned. Registration workflow, maps integration, driver/passenger UI. |
| Phase 4 — Matching Engine | Planned. Route matrix, scoring, optimization (CVRPTW), admin override. Most complex phase. |
| Phase 5 — Approval & Notification | Planned. Approval workflow, email via SQS → email Lambda → M365 Exchange, audit logging. |
| Phase 6 — Hardening | Planned. Load testing, security review, observability, production readiness. |
| CI | Legacy: `.github/workflows/{pylint,unittest}.yml` on Python 3.8–3.10. Target: ruff + mypy + pytest + Lambda/Pages deploy pipelines (Phase 2). |
| Repo layout | `src/` (legacy), `test/` (legacy), `mock/` (CSV fixtures), `docs/` (requirements + architecture), `plans/` (phase plans), `.github/workflows/`. Target layout adds `app/` (backend) and a frontend project. |

---

## 3. Development Environment

**Backend (target / all new Python work):**
- Python **3.12** (Lambda ARM64 runtime target). Legacy code targets 3.8+.
- Package manager: **`uv`** (preferred for new work); `pip` + `requirements.txt` still present for the legacy CLI.
- Testing: **`pytest`**. Legacy tests use `unittest`; migrate as code is touched.
- Linting/formatting: **`ruff`** (replaces `pylint`).
- Type checking: **`mypy --strict`**.
- Framework: FastAPI + Mangum (Lambda adapter).

**Frontend (Phase 2+):**
- Node.js LTS + **Next.js** (App Router), TypeScript, Tailwind CSS.
- Deployed via `next-on-pages` to Cloudflare Pages.
- Tooling: `eslint`, `prettier`, `tsc --noEmit`, Vitest/Playwright (TBD in Phase 2).

**Infrastructure:**
- AWS Lambda ARM64, DynamoDB, S3, CloudWatch, Parameter Store, (SQS / Step Functions for large sessions).
- Cloudflare (Pages + Free tier edge/WAF).
- Self-hosted OSRM for routing; public Nominatim (cached) for geocoding.

---

## 4. Key Commands

### Backend (Python — `app/` and any new code)

```bash
# Install (uv)
uv sync                                   # or: pip install -r requirements.txt
uv pip install -e ".[dev]"                # dev extras (pytest, ruff, mypy) once pyproject.toml exists

# Test
pytest                                    # all tests
pytest tests/ -k matching                 # filtered
pytest --cov=app --cov-report=term-missing

# Quality gates (all must pass before merge)
ruff check .
ruff format --check .
mypy .
```

### Legacy CLI (still runnable)

```bash
pip install -r requirements.txt
python3 src/main.py <input_csv> <output_csv>
python3 -m unittest                       # legacy tests (test/)
```

### Frontend (Phase 2+)

```bash
npm install
npm run dev                               # local Next.js
npm run lint                              # eslint
npx tsc --noEmit                          # type check
npm run build                             # production build (next-on-pages)
npm test                                  # unit/integration (TBD)
```

### Infrastructure (Phase 2+)

```bash
# IaC (CDK or SAM — to be chosen in Phase 2)
# Deploy Lambda package + Cloudflare Pages via GitHub Actions on merge to main
```

---

## 5. Core Rules

1. **Skills first.** Before writing code, check the Intent → Skill Mapping (§7) and Lifecycle
   Mapping (§8). Invoke the matching skill(s) via the `skill` tool. Do not "just implement".
2. **Plan files live in `plans/`.** Every phase has a plan (`plans/phase-N-*.md`). Task-level
   plans go in `plans/` as well. Read the relevant phase plan before starting work in that phase.
3. **Skill / reference / agent locations:**
   - **Global:** `~/.config/kilo/skills/`, `~/.config/kilo/agent/`.
   - **Project-local:** `.kilo/skills/`, `.kilo/agent/`, `.kilo/command/`. Project-local overrides win.
   - The `kilo-config` skill for this project is loaded from a project-local `builtin` location.
4. **Specs before code.** Non-trivial features require a spec (use `spec-driven-development`)
   before implementation. The `docs/functional_requirements_and_architecture.md` is the master
   spec; phase plans decompose it.
5. **Tests before code.** Follow `test-driven-development`. No logic lands without a failing
   test first.
6. **One phase at a time.** Do not implement Phase 4 code while Phase 2 artifacts are incomplete.
   Respect the dependency order in `plans/`.
7. **Legacy code is a reference, not the standard.** `src/main.py` matching logic is reused by
   adaptation, not copy-paste. New code follows the target toolchain (ruff/mypy/pytest) and the
   `app/` layout (§11 of the requirements doc).
8. **Never commit secrets.** Google OAuth client secrets, AWS keys, OSRM endpoints go in AWS
   Parameter Store / environment — never in the repo.

---

## 6. Agent Observability & Rationale Requirements

Every agent must leave a visible rationale trail so decisions are traceable, reviewable, and
auditable. Record rationale in the PR description, commit messages, `docs/adr/` (ADRs), and
`KNOWLEDGE.md`.

| Agent Role | Must Document |
| --- | --- |
| **Analyst** | Clarified requirements, resolved ambiguities, accepted/deferred FRs (update `docs/requirements_baseline.md`). |
| **System Architect** | Technology choices, trade-offs, data-model decisions, GSI design, service boundaries. ADR required for any non-trivial architecture decision. |
| **Programmer** | What was implemented, which spec/FR it satisfies, tests added, deviations from plan and why. |
| **Reviewer** | Findings by axis (correctness, security, performance, maintainability), severity, and required fixes. |
| **QA** | Test plan, coverage delta, edge cases covered, NFRs validated (p95 latency, 500-user matching < 30s). |
| **SRE** | Ops impact, observability gaps, rollback plan, CloudWatch/alert additions, failure modes. |
| **Tech Lead** | Phase progression decisions, delegation choices, quality-gate pass/fail rationale, risk acceptance. |

**ADR requirement:** Any decision that is hard to reverse or affects external APIs, the data
model, security posture, or the service architecture requires an Architecture Decision Record in
`docs/adr/NNNN-title.md` (template: `docs/adr/0000-template.md`). Link the ADR from the PR.

---

## 7. Intent → Skill Mapping

| User Intent | Skill(s) to Trigger |
| --- | --- |
| "Build feature X" / "Implement FR-N" | `spec-driven-development` → `planning-and-task-breakdown` → `incremental-implementation` → `test-driven-development` |
| "Fix this bug" | `debugging-and-error-recovery` → `test-driven-development` |
| "Refactor this" / "clean up" | `code-simplification` (behavior-preserving) → `test-driven-development` |
| "Design the API / data model" | `api-and-interface-design` → `system-architect` |
| "Review this change / PR" | `code-review-and-quality` → `reviewer` |
| "Set up CI/CD / deploy" | `ci-cd-and-automation` / `devops` |
| "Harden security / auth" | `security-and-hardening` → `security` |
| "Optimize matching performance" | `performance-optimization` → `system-architect` |
| "Test strategy / coverage" | `quality-assurance` → `test-driven-development` |
| "Ship to production" | `shipping-and-launch` → `sre` |
| "Investigate incident / outage" | `sre` → `debugging-and-error-recovery` |
| "Write/update docs or ADR" | `documentation-and-adrs` |
| "Migrate / deprecate old code" | `deprecation-and-migration` |
| "Build/polish frontend UI" | `frontend-ui-engineering` → `browser-testing-with-devtools` |
| "Refine a vague idea" | `idea-refine` → `analyst` |
| "Wrap up this task" | `wrap_up_task` |
| "Set up / fix Kilo config" | `kilo-config` |

---

## 8. Lifecycle Mapping

High-level phases map to skills as follows:

| Phase | Skills |
| --- | --- |
| **DEFINE** (requirements, scope) | `analyst`, `spec-driven-development`, `idea-refine` |
| **PLAN** (break down, estimate) | `planning-and-task-breakdown`, `system-architect`, `api-and-interface-design` |
| **BUILD** (implement) | `incremental-implementation`, `test-driven-development`, `programmer`, `frontend-ui-engineering` |
| **VERIFY** (test, QA) | `quality-assurance`, `test-driven-development`, `browser-testing-with-devtools` |
| **REVIEW** (code/security/audit) | `code-review-and-quality`, `reviewer`, `security-and-hardening`, `sre`, `performance-optimization` |
| **SHIP** (deploy, launch) | `ci-cd-and-automation`, `devops`, `shipping-and-launch`, `git-workflow-and-versioning`, `documentation-and-adrs` |

---

## 9. Agent-Driven Orchestration

Agents operate autonomously within the workflow below. Principles:

1. **Analyze** the request against `docs/functional_requirements_and_architecture.md` and the
   relevant `plans/phase-N-*.md`. Identify which FR and which phase task this satisfies.
2. **Determine the workflow** using §8 and §10. Pick skills before picking up a text editor.
3. **Execute** incrementally — small, verifiable steps. Run the verification commands (§15)
   after each step.
4. **Delegate** to subagents when a task is specialized or parallelizable (see §12).
5. **Validate** against the Definition of Done (§11) before declaring complete.
6. **Admit uncertainty.** If a requirement is ambiguous or a decision needs human approval
   (§12), stop and ask. Do not guess on security, data-model, or external-API changes.

---

## 10. Development Workflow (Agent-Driven)

Every non-trivial task follows these 9 mandatory phases in order:

```
1. PLANNING → 2. IMPLEMENTATION → 3. REVIEW → 4. TESTING → 5. AUDIT
→ 6. FIX → 7. DOCUMENTATION → 8. COMMIT → 9. PULL REQUEST
```

1. **PLANNING** — Analyze requirements; break into ordered subtasks; identify dependencies;
   write/update the relevant `plans/` artifact. Delegate to: `analyst`, `system-architect`.
2. **IMPLEMENTATION** — Write tests first (TDD); implement incrementally; run verification
   continuously. Delegate to: `programmer` with `test-driven-development`.
3. **REVIEW** — Code, security, and architecture review. Delegate to: `reviewer`, `security`,
   `system-architect`.
4. **TESTING** — Coverage validation, edge cases, integration tests, NFR checks (latency,
   500-user matching < 30s). Delegate to: `quality-assurance`.
5. **AUDIT** — Operational, performance, and security audit. Delegate to: `sre`, `security`.
6. **FIX** — Address review/audit feedback; fix bugs; iterate. Delegate to: `programmer`.
7. **DOCUMENTATION** — Update README/docs, API docs, `KNOWLEDGE.md`, and ADRs for architectural
   decisions. Delegate to: `documentation-and-adrs`.
8. **COMMIT** — Commit with a descriptive message; create a PR. Delegate to:
   `git-workflow-and-versioning`.
9. **PULL REQUEST** — Submit; address feedback; obtain approval. Delegate to: `reviewer`.

---

## 11. Definition of Done (DoD) Protocol

No task is "Finished" until ALL checks pass.

### Mandatory Checks

1. **Tests Validated**
   ```bash
   pytest --cov=app --cov-report=term-missing      # backend
   npm test                                          # frontend (Phase 2+)
   ```
   - [ ] All tests pass
   - [ ] Coverage meets threshold (>80% for changed code)
   - [ ] No new warnings

2. **Quality Gates Pass**
   ```bash
   ruff check .                # lint
   ruff format --check .       # format
   mypy .                      # types (strict)
   npm run lint && npx tsc --noEmit   # frontend (Phase 2+)
   ```
   - [ ] Linting passes
   - [ ] Type checking passes
   - [ ] Formatting correct

3. **Documentation Updated**
   - [ ] `README.md` for user-facing changes
   - [ ] Docstrings for new functions/modules
   - [ ] `KNOWLEDGE.md` with lessons learned
   - [ ] ADR for any architectural decision

4. **Review Completed**
   - [ ] Code reviewed by at least one subagent
   - [ ] QA verified coverage
   - [ ] SRE reviewed ops impact (for infra/deploy changes)

---

## 12. Team Lead Agent — Delegation & Responsibilities

The Team Lead coordinates the workflow and delegates to specialized agents.

### Delegation Triggers

| Task | Delegate To |
| --- | --- |
| Requirements clarification | `analyst` skill |
| Architecture / design decision | `system-architect` agent + ADR |
| Code review needed | `code-review-and-quality` skill |
| Tests needed | `test-driven-development` skill |
| Security review | `security-and-hardening` skill |
| Planning / breakdown | `planning-and-task-breakdown` skill |
| Debug an issue | `debugging-and-error-recovery` skill |
| Deploy / ship | `shipping-and-launch` skill |
| Wrap up a task | `wrap_up_task` skill |

### Autonomous Actions (no human approval needed)
- Call a subagent for code review.
- Request QA validation.
- Move IMPLEMENTATION → REVIEW when tests pass.
- Fix bugs and iterate through phases.
- Make architectural decisions within existing patterns (no new ADR needed).
- Commit and create PRs when all checks pass.

### Requires Human Approval
- [ ] Architecture changes requiring a new ADR (e.g., switching matching solver, DB engine).
- [ ] Deprecation of existing features (e.g., retiring the legacy CLI).
- [ ] Release/deploy to production.
- [ ] Changes affecting external APIs (REST contract changes per §9 of the requirements doc).
- [ ] Security policy changes (auth flow, RBAC model, rate limits).
- [ ] Database schema changes (DynamoDB table/GSI changes).

---

## 13. Anti-Rationalization

Ignore these incorrect thoughts; follow the correct behavior instead.

| Incorrect Thought | Correct Behavior |
| --- | --- |
| "This is too small for a skill." | Always check for and use a skill first. |
| "I can just quickly implement this." | Plan first; write tests first. |
| "I'll gather context first" (endlessly). | Time-box exploration; then act. |
| "The spec will slow us down." | Spec before code for non-trivial work. |
| "I know what to do, no need for planning." | Use `planning-and-task-breakdown`. |
| "I'll skip tests, they slow me down." | TDD is mandatory for logic changes. |
| "Documentation can wait until later." | Update docs/ADR in the DOCUMENTATION phase. |
| "I told the other agent verbally." | Record handoffs in `KNOWLEDGE.md` / PR. |
| "They can check the code." | Document rationale explicitly. |
| "I'll remember to update docs later." | Update them now, in phase 7. |
| "Legacy `src/main.py` is fine as-is." | New code follows the `app/` layout + ruff/mypy/pytest. |

---

## 14. Skills Reference

Skills live globally in `~/.config/kilo/skills/` and project-locally in `.kilo/skills/`
(project-local overrides win). Invoke via the `skill` tool.

### Core Workflow Skills (7)
The backbone of the development lifecycle.

| Skill | Purpose |
| --- | --- |
| `spec-driven-development` | Create specs before coding; resolve ambiguity up front. |
| `planning-and-task-breakdown` | Break work into ordered, implementable tasks; estimate scope. |
| `incremental-implementation` | Deliver multi-file changes in small, verifiable increments. |
| `test-driven-development` | Drive implementation with failing tests first. |
| `code-review-and-quality` | Multi-axis review before merge. |
| `git-workflow-and-versioning` | Branching, committing, conflict resolution, versioning. |
| `documentation-and-adrs` | Record decisions, ADRs, and docs. |

### Composite / Meta Skills (2)
| Skill | Purpose |
| --- | --- |
| `using-agent-skills` | Discover which skill applies to the current task (meta-skill). |
| `wrap_up_task` | Final checks, reflection, logging, and documentation for a completed task. |

### Specialized Skills (24)
| Skill | Purpose |
| --- | --- |
| `analyst` | Gather/clarify requirements; translate needs into specifications. |
| `api-and-interface-design` | Design stable APIs, module boundaries, REST/GraphQL contracts. |
| `browser-testing-with-devtools` | Test in real browsers via Chrome DevTools (frontend). |
| `ci-cd-and-automation` | Set up/modify build & deploy pipelines, quality gates. |
| `code-simplification` | Refactor for clarity without changing behavior. |
| `collaboration-protocol` | Standardized subagent collaboration and state sharing. |
| `context-engineering` | Optimize agent context, rules files, session setup. |
| `debugging-and-error-recovery` | Systematic root-cause debugging. |
| `deprecation-and-migration` | Sunset old systems; migrate users safely. |
| `devops` | CI/CD, deployment automation, IaC (Docker/Kubernetes/AWS). |
| `frontend-ui-engineering` | Build production-quality UIs (Next.js/React). |
| `idea-refine` | Refine ideas via structured divergent/convergent thinking. |
| `kilo-config` | Kilo configuration (project-local builtin for this repo). |
| `performance-optimization` | Profile and fix performance bottlenecks; Core Web Vitals. |
| `programmer` | Implement features; write clean, standard-compliant code. |
| `quality-assurance` | Design test strategies; create test plans; ensure quality. |
| `reviewer` | Review PRs; provide code feedback; ensure quality. |
| `security` | Security by design; identify vulnerabilities; implement controls. |
| `security-and-hardening` | Harden code handling untrusted input, auth, sessions, integrations. |
| `shipping-and-launch` | Pre-launch checklist, monitoring, staged rollout, rollback. |
| `source-driven-development` | Ground decisions in official documentation. |
| `sre` | Reliability, incidents, observability, on-call, monitoring. |
| `system-architect` | System architecture, technology decisions, technical direction. |
| `tech-lead` | Code-quality standards, architecture decisions, mentoring. |

### Agent Personas (Global)
- **Team Lead** — orchestrates the 9-phase workflow, delegates to subagents, enforces quality
  gates. (Defined in the global agent configuration; see §12.)
- **Subagent types** available via the `task` tool: `explore` (fast codebase search),
  `general` (multi-step research/execution), `security-auditor` (vulnerability-focused review),
  `team-lead` (coordination/delegation).

### Project Agent Roles
*None defined yet in `.kilo/agent/`.* As the project matures, add project-specific agent roles
here (e.g., `matching-engine-dev`, `frontend-dev`, `infra-dev`). Place their definitions in
`.kilo/agent/*.md`. Project-local agents override global ones of the same name.

### Project-Specific References
*None in `.kilo/skills/` yet.* The project's own reference material lives in:
- `docs/functional_requirements_and_architecture.md` — master spec (FR-1..FR-11, RBAC, data model, API).
- `plans/phase-{1..6}-*.md` — phased implementation plans.
- `docs/requirements_baseline.md`, `docs/rbac_matrix.md`, `docs/data_model_erd.md`,
  `docs/api_contracts.md`, `docs/diagrams/`, `docs/wireframes/` — Phase 1 deliverables (as produced).
- `docs/adr/` — Architecture Decision Records.
- `KNOWLEDGE.md` — lessons learned (created on first task wrap-up).

---

## 15. Verification Commands

**Every change must pass these before being marked done.** Backend commands run from repo root
(or `app/` once bootstrapped); frontend commands run from the frontend project root (Phase 2+).

```bash
# Backend
pytest                                    # tests
ruff check .                              # lint
ruff format --check .                     # format
mypy .                                    # types (strict)

# Frontend (Phase 2+)
npm run lint                              # eslint
npx tsc --noEmit                          # type check
```

If a command is not yet configured for the area you're touching (e.g., frontend not bootstrapped),
note it explicitly in the PR and skip only with justification — do not silently skip.

---

## 16. Completion Criteria

A task is complete only when ALL of the following are true:

- [ ] All tests pass (`pytest` / `npm test`).
- [ ] Type check passes (`mypy .` / `tsc --noEmit`).
- [ ] Lint passes (`ruff check .` / `npm run lint`).
- [ ] Format check passes (`ruff format --check .`).
- [ ] Coverage on changed code ≥ 80%.
- [ ] `KNOWLEDGE.md` updated with lessons learned (if any).
- [ ] Code reviewed by at least one subagent.
- [ ] Documentation updated (README, docstrings, API docs as relevant).
- [ ] ADR written for any architectural decision.
- [ ] Change committed with a descriptive message.
- [ ] Pull request created and linked to the relevant FR/phase task.

---

## 17. Knowledge Base

- **`KNOWLEDGE.md`** (repo root) — running log of lessons learned, gotchas, and decisions. Update
  in the DOCUMENTATION phase of every task.
- **`docs/adr/`** — Architecture Decision Records. Filename: `NNNN-short-title.md`. Template:
  `docs/adr/0000-template.md` (create on first ADR). Every ADR records context, decision,
  alternatives considered, and consequences.

---

## 18. Configuration

Runtime/configuration knobs for the platform (values set via environment / AWS Parameter Store,
not hardcoded):

| Setting | Default / Spec | Notes |
| --- | --- | --- |
| Geocoding provider | Nominatim (public, cached) | FR-5; self-host if rate-limited. |
| Routing provider | OSRM (self-hosted) | FR-5; provides `/route`, `/matrix`. |
| Matching algorithm | Greedy heuristic (MVP) | FR-6; OR-Tools/LP for production (>300 users). |
| Matching problem | CVRPTW | Capacitated Vehicle Routing Problem with Time Windows. |
| Rate limit (per IP) | 60 req/min | §14 of requirements doc. |
| Rate limit (per user) | 120 req/min | §14 of requirements doc. |
| Lambda runtime | Python 3.12, ARM64, 256 MB, 5–10s timeout | §10 of requirements doc. |
| Large-session async | SQS / Step Functions / Fargate | For sessions > 300 users (§13). |
| DynamoDB tables | `app_data` (single-table) + `session_cache`, `rate_limit_cache`, `brute_force_counter` | §10; TTL on cache/rate-limit tables. |
| Auth | Google OIDC + session code | FR-1; session code = registration invite only. |
| Notifications | Email via SQS → email Lambda → M365 Exchange | FR-10. |
| Log retention | CloudWatch → S3 (30-day lifecycle) → Athena | §10. |
| Edge / CDN | Cloudflare Free | §9 architecture. |
| AWS region | TBD (Phase 2 open question) | Affects OSRM extract geography. |

---

## 19. Contact / Support

- **Architecture & requirements:** [`docs/functional_requirements_and_architecture.md`](docs/functional_requirements_and_architecture.md)
- **Phase plans:** [`plans/`](plans/)
- **README:** [`README.md`](README.md)
- **Repository:** https://github.com/timycyip/carpool-coordinator
