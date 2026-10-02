# Carpool Coordinator — Shared Agent Protocol

This file defines the shared project protocol for coding assistants, including Cline, Kilo Code,
Codex, ChatGPT, and other tools that read repository instructions. It describes project rules and
workflows without requiring a particular agent framework.

## Applicability

Follow this file whenever it is provided to you or loaded from the repository. If a tool
does not load `AGENTS.md`, the task setup or user must provide it. When loaded, these instructions
apply subject to higher-priority system/developer instructions and the user's direct instructions.

Use available skills, agents, commands, or workflow features when they help. If a named skill or
delegation feature is unavailable, follow the relevant guidance directly. Tool limitations are
not a reason to stop or silently skip necessary work.

## 1. Project Overview

Carpool Coordinator coordinates rides to events through registration, driver/passenger matching,
route optimization, administrator approval, and assignment publishing.

The repository contains a legacy Python CLI in `src/main.py` and a phased web-platform build. The
target stack is FastAPI + Mangum on AWS Lambda (Python 3.12, ARM64), Next.js App Router on
Cloudflare Pages, DynamoDB, Google OIDC, cached Nominatim geocoding, hosted OpenRouteService
routing, and a greedy matching MVP. Treat the legacy CLI as a behavioral reference. New platform
work belongs in `app/`, `frontend/`, and `infra/` as specified by the requirements and phase plans.

The master specification is `docs/functional_requirements_and_architecture.md`. Read the relevant
sections and the relevant phase plan before feature work. Phase and task plans live in
`doc/plans/`; ordinary project documentation lives in `docs/`.

## 2. Core Rules

1. **Inspect first.** Read the relevant files, check the working tree, and find existing patterns
   before editing. Preserve unrelated user changes.
2. **Keep plans together.** Every phase plan and task-level plan belongs in `doc/plans/`. Read and
   update the relevant plan as scope or progress changes. Do not create plans in tool-specific
   directories.
3. **Specify non-trivial work.** Before implementation, record scope, requirements, dependencies,
   and acceptance criteria in the relevant plan. The master specification is authoritative; phase
   plans decompose it into deliverable work.
4. **Use test-first development for behavior changes.** Add or update a failing test before
   implementing logic. Use pytest for new backend code and the frontend's configured test runner.
   Keep legacy `unittest` tests where they are unless the task touches them.
5. **Follow phase order.** Do not implement a later phase while required earlier-phase work is
   incomplete. Surface dependency conflicts instead of silently changing scope.
6. **Protect secrets.** Never add credentials, OAuth client secrets, API keys, tokens, or private
   keys to the repository. Use environment variables or the configured secret store.
7. **Respect decision gates.** Get user direction before changing the public API contract,
   authentication or authorization policy, database schema, a hard-to-reverse architecture
   decision, deprecating an existing feature, or deploying to production, unless the user has
   already explicitly authorized that specific action. Routine implementation choices within
   accepted decisions do not need new approval.
8. **Report evidence accurately.** State what changed and what was actually verified. Lint,
   type-check, syntax-check, and local mock results do not prove a live deployment or provider
   integration.

## 3. Agent Observability & Rationale Requirements

Leave enough rationale for another person or agent to understand important choices. Use the
relevant plan, ADR, commit message, or pull request description; avoid duplicating the same text in
every location.

| Responsibility | Record |
| --- | --- |
| Requirements analysis | Clarified requirements, resolved ambiguities, and accepted/deferred requirements in `docs/requirements_baseline.md` when applicable. |
| Architecture | Technology choices, trade-offs, data-model decisions, GSI design, and service boundaries. Write an ADR when required by this section. |
| Implementation | What changed, which specification or requirement it addresses, tests added, and deviations from the plan with reasons. |
| Review | Findings by correctness, security, performance, and maintainability; include severity and required fixes. |
| QA | Test plan, changed-code coverage when measured, edge cases, and applicable non-functional requirements. |
| Operations | Operational impact, observability gaps, rollback approach, alerts, and failure modes for infrastructure or deployment work. |
| Coordination | Phase progression, delegation choices when applicable, quality-gate results, and accepted risks. |

Any decision that is hard to reverse or affects external APIs, the data model, security posture,
or service architecture requires a numbered ADR in `docs/adr/NNNN-title.md`. Use
`docs/adr/0000-template.md` and link the ADR from the related plan or change description.

## 4. Intent → Skill Mapping

Use the matching skill when it is available in the current tool. If it is not available, apply the
workflow directly using this protocol and the linked project documentation.

| User intent | Skill(s) |
| --- | --- |
| Build a feature or implement a requirement | `spec-driven-development` → `planning-and-task-breakdown` → `incremental-implementation` → `test-driven-development` |
| Fix a bug | `debugging-and-error-recovery` → `test-driven-development` |
| Refactor or simplify | `code-simplification` → `test-driven-development` |
| Design an API or data model | `api-and-interface-design` → `system-architect` |
| Review a change | `code-review-and-quality` → `reviewer` |
| Set up or change CI/CD | `ci-cd-and-automation` and/or `devops` |
| Harden security or authentication | `security-and-hardening` → `security` |
| Optimize matching performance | `performance-optimization` → `system-architect` |
| Define a test strategy | `quality-assurance` → `test-driven-development` |
| Ship or prepare a release | `shipping-and-launch` → `sre` |
| Investigate an incident | `sre` → `debugging-and-error-recovery` |
| Write or update documentation or an ADR | `documentation-and-adrs` |
| Migrate or deprecate old code | `deprecation-and-migration` |
| Build or polish frontend UI | `frontend-ui-engineering` → `browser-testing-with-devtools` |
| Refine a vague idea | `idea-refine` → `analyst` |
| Wrap up completed work | `wrap_up_task` |
| Configure a specific agent tool | Use that tool's configuration guidance; `kilo-config` applies only to Kilo configuration. |

## 5. Skill References

Skill names refer to reusable workflow guidance that may be installed in a tool's skill catalog or
provided as files. They are not commands that every tool must expose.

### Core workflow skills

| Skill | Purpose |
| --- | --- |
| `spec-driven-development` | Resolve scope and requirements before implementation. |
| `planning-and-task-breakdown` | Break work into ordered tasks. |
| `incremental-implementation` | Deliver changes in small, verifiable steps. |
| `test-driven-development` | Write tests before behavior changes. |
| `code-review-and-quality` | Review correctness, security, and maintainability. |
| `git-workflow-and-versioning` | Branching, commits, and versioning. |
| `documentation-and-adrs` | Record decisions and update project documentation. |
| `using-agent-skills` | Discover and select applicable skills when this meta-skill is available. |

### Specialized skills

| Skill | Purpose |
| --- | --- |
| `analyst` | Clarify requirements and translate them into specifications. |
| `api-and-interface-design` | Design stable APIs and module boundaries. |
| `browser-testing-with-devtools` | Verify frontend behavior in a browser. |
| `ci-cd-and-automation` | Set up or modify CI/CD. |
| `code-simplification` | Refactor for clarity while preserving behavior. |
| `collaboration-protocol` | Coordinate work across agents when supported. |
| `context-engineering` | Curate project instructions and task context. |
| `debugging-and-error-recovery` | Find and resolve the cause of failures. |
| `deprecation-and-migration` | Migrate or retire existing systems safely. |
| `devops` | CI/CD, deployment automation, and infrastructure as code. |
| `frontend-ui-engineering` | Build production-quality frontend interfaces. |
| `idea-refine` | Refine an early or ambiguous idea. |
| `performance-optimization` | Profile and improve performance. |
| `programmer` | Implement features using project conventions. |
| `quality-assurance` | Plan and validate software quality. |
| `reviewer` | Review changes and report actionable findings. |
| `security` | Assess security design and implementation. |
| `security-and-hardening` | Harden authentication, input handling, and integrations. |
| `shipping-and-launch` | Prepare a release and rollout. |
| `source-driven-development` | Ground technical decisions in authoritative documentation. |
| `sre` | Address reliability, observability, and operations. |
| `system-architect` | Make and document architecture decisions. |
| `tech-lead` | Coordinate technical direction and quality gates. |
| `wrap_up_task` | Summarize and close out completed work. |

`kilo-config` applies only when configuring Kilo Code; it is tool-specific and is not required by
this shared protocol.

## 6. Agent Delegation & Responsibilities

Delegate a separable task when the current environment supports agents and delegation will improve
coverage or speed. Delegation is optional when unavailable or when the task is small. The primary
agent remains responsible for integrating the work, checking its evidence, and reporting the
result. Do not claim an independent review or test that was not performed.

| Work area | Suggested responsibility |
| --- | --- |
| Requirements clarification | Analyst; update the requirements baseline when needed. |
| Architecture or data design | System architect; write an ADR for a decision that meets §3. |
| Implementation | Programmer; follow the plan and test-first rule. |
| Code review | Reviewer; report findings and required fixes. |
| Test design or coverage | QA; report what was covered and what remains unverified. |
| Security assessment | Security reviewer; focus on trust boundaries, secrets, auth, and input handling. |
| Deployment or operations | DevOps/SRE; document operational impact and rollback. |
| Task coordination | Tech lead; keep phase, scope, quality gates, and risks visible. |

Use the closest available role names in the host tool. If delegation is unavailable, do the work
directly and state that no independent agent review occurred when that fact matters.

## 7. Lifecycle Mapping

| Lifecycle stage | Typical skills and work |
| --- | --- |
| **DEFINE** | `analyst`, `spec-driven-development`, `idea-refine`; settle scope and acceptance criteria. |
| **PLAN** | `planning-and-task-breakdown`, `system-architect`, `api-and-interface-design`; write or update `doc/plans/`. |
| **BUILD** | `incremental-implementation`, `test-driven-development`, `programmer`, `frontend-ui-engineering`. |
| **VERIFY** | `quality-assurance`, `test-driven-development`, `browser-testing-with-devtools`; run relevant checks. |
| **REVIEW** | `code-review-and-quality`, `reviewer`, `security-and-hardening`, `sre`, `performance-optimization`. |
| **SHIP** | `ci-cd-and-automation`, `devops`, `shipping-and-launch`, `git-workflow-and-versioning`, `documentation-and-adrs`. |

## 8. Agent-Driven Orchestration

For each request:

1. Check the applicable requirements in `docs/functional_requirements_and_architecture.md` and
   the relevant phase plan in `doc/plans/`. Identify the phase and requirement when applicable.
2. Choose the workflow and available skills using §§4 and 7 before making substantial changes.
3. Inspect current files and changes, then work in small, reviewable steps.
4. Delegate independent, specialized work when supported and useful; keep shared changes
   coordinated.
5. Validate against the Definition of Done in §11, adapting checks to the task's scope.
6. Surface unresolved security, data-model, external-API, or architecture decisions before making
   dependent changes. Honor approval already explicitly given by the user.

## 9. Agent-Driven Development Workflow

For non-trivial implementation work, follow these stages. Combine or omit a stage only when it is
not applicable, and record material omissions and reasons in the task summary or plan.

1. **PLANNING** — Analyze requirements, dependencies, and acceptance criteria; write or update the
   relevant plan in `doc/plans/`.
2. **IMPLEMENTATION** — Add/update tests first for behavior changes; implement incrementally.
3. **REVIEW** — Review correctness, security, performance, and maintainability. Use an independent
   reviewer when available and useful.
4. **TESTING** — Run configured tests and quality gates relevant to the changed area; assess edge
   cases and applicable non-functional requirements.
5. **AUDIT** — For security, infrastructure, or deployment work, assess operational impact,
   failure modes, observability, and rollback.
6. **FIX** — Address review and audit findings, then repeat affected checks.
7. **DOCUMENTATION** — Update README/docs, API documentation, `KNOWLEDGE.md`, plans, or ADRs as
   appropriate.
8. **COMMIT** — Commit with a descriptive message when the user asks or the active workflow
   requires a commit.
9. **PULL REQUEST** — Create or update a pull request when the user asks or the active workflow
   requires one; link the relevant requirement, plan, and ADRs.

## 10. Definition of Done (DoD)

Apply these gates to relevant code changes. Documentation-only changes do not require application
tests. User scope and higher-priority instructions may narrow what can be run; report any skipped
or unavailable checks and the reason.

### Tests

- All relevant tests pass.
- Changed behavior has appropriate coverage; the project target is over 80% for changed code when
  coverage can be measured.
- No new warnings are introduced, or warnings are explained.

### Quality gates

- Relevant lint, formatting, and type checks pass.
- Frontend build and type checks pass for frontend changes.

### Documentation and rationale

- Update `README.md` for user-facing behavior or setup changes.
- Document public functions/modules where the project conventions require it.
- Update `KNOWLEDGE.md` with durable lessons or gotchas when useful.
- Write an ADR for architecture decisions covered by §3.

### Review and operations

- Review the diff for correctness, security, performance, maintainability, and unintended edits.
- Obtain independent review when available and useful; report when it was not performed.
- For infrastructure/deployment changes, record operational effects, verification, and rollback
  considerations.

## 11. Completion Criteria

A task is complete when the requested work is in place, relevant checks have passed or their
limitations are reported, and required documentation is updated. Before claiming completion,
confirm as applicable:

- [ ] Requested behavior or documentation is implemented.
- [ ] Relevant tests, type checks, lint, and format checks are run and their results recorded.
- [ ] Changed-code coverage is measured when required and available.
- [ ] `KNOWLEDGE.md` is updated when durable lessons were found.
- [ ] Documentation and ADRs are updated where relevant.
- [ ] Review and operational impact are reported where relevant.
- [ ] Commit, pull request, or deployment is completed only when requested or required by the
      active workflow; do not claim an action that did not happen.

Do not equate static checks or mocks with live operation. State deployment and provider status
only from observed evidence.

## 12. Anti-Rationalization

| Avoid this rationale | Required behavior |
| --- | --- |
| “This is too small to inspect.” | Read the relevant files and preserve existing work. |
| “I can implement quickly without a plan.” | Record a lightweight plan for non-trivial work. |
| “Tests slow me down.” | Use test-first development for behavior changes and run relevant checks. |
| “The spec is inconvenient.” | Follow the specification or surface the conflict. |
| “I know what the user intended.” | Resolve ambiguity from project evidence; ask when a material decision is still unclear. |
| “I told another agent verbally.” | Keep consequential decisions and handoffs in the plan or change record. |
| “Documentation can wait.” | Update relevant docs and ADRs before reporting completion. |
| “A successful lint means it is deployed.” | Report only the evidence each check provides. |
| “The tool lacks that skill or agent.” | Follow the workflow directly using this file. |

## 13. Verification Commands

Run commands relevant to the change from the indicated directory. Do not run irrelevant suites;
report required checks that are unavailable or skipped and why.

### Backend (`app/` and new Python code)

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest --cov=app --cov-report=term-missing
```

If the project is not using `uv` for the current checkout, use the equivalent installed commands:
`pytest`, `ruff check .`, `ruff format --check .`, and `mypy .`.

### Legacy CLI

```bash
pip install -r requirements.txt
python3 src/main.py <input_csv> <output_csv>
python3 -m unittest
```

### Frontend (run from `frontend/`)

```bash
npm install
npm test
npm run lint
npx tsc --noEmit
npm run build
```

### Infrastructure

Use the Terraform validation/plan/apply steps in the relevant phase plan and environment guide.
Do not apply infrastructure changes outside the user's authorization or the environment workflow;
production deployment requires explicit approval as described in §2.

## 14. Knowledge Base

- `KNOWLEDGE.md` at the repository root is the running log of durable lessons, gotchas, and
  decisions useful to future contributors and agents.
- Update it when a task discovers reusable knowledge; do not add routine progress notes that
  belong in a plan or pull request.
- Store architecture decisions in `docs/adr/`, not only in the knowledge base.

## 15. Configuration

Runtime values belong in environment configuration or AWS Parameter Store, not hard-coded source
or committed secrets.

| Setting | Project default / decision | Notes |
| --- | --- | --- |
| Geocoding | Cached Nominatim | Dev/staging use deterministic fixtures; production enforces a shared 1 request/second limit. |
| Routing | Hosted OpenRouteService | Use `/v2/directions` and `/v2/matrix`; cache results and enforce shared provider quotas. |
| Matching | Greedy heuristic MVP | OR-Tools/LP is a future option for larger sessions; do not change solvers without an architecture decision. |
| Matching model | CVRPTW | Capacitated Vehicle Routing Problem with Time Windows. |
| Rate limits | 60 requests/minute per IP; 120/minute per user | See the master specification and current implementation. |
| Lambda | Python 3.12, ARM64, 256 MB, 5–10 second timeout | Follow the deployed environment's approved settings. |
| Large sessions | SQS / Step Functions / Fargate | For sessions over 300 users, per the architecture plan. |
| Data stores | `app_data`, `session_cache`, `rate_limit_cache`, `brute_force_counter`, plus model-defined tables | Consult the current ERD, Terraform, and ADRs; do not infer schema changes from this summary. |
| Authentication | Google OIDC plus app session JWT | Session code is a registration invite, not an authentication credential. |
| Notifications | SQS → email Lambda → M365 Exchange | See ADR-0008 and the current phase plan. |
| Logs | CloudWatch → S3 with 30-day lifecycle → Athena | See the master specification and infrastructure plan. |
| Edge/CDN | Cloudflare Pages and Free tier edge/WAF | Only the API proxy function should handle `/api/*`. |
| AWS region | `us-east-2` | See ADR-0003. |

If this summary conflicts with a current accepted ADR, specification, or deployed configuration,
surface the discrepancy and use the authoritative source rather than silently changing behavior.

## 16. Reference Documents

- Master requirements and architecture: `docs/functional_requirements_and_architecture.md`
- Phase and task plans: `doc/plans/`
- Requirements baseline: `docs/requirements_baseline.md`
- API contracts: `docs/api_contracts.md`
- Data model: `docs/data_model_erd.md` and `docs/database_design.md`
- RBAC: `docs/rbac_matrix.md`
- ADRs: `docs/adr/`
- Knowledge base: `KNOWLEDGE.md`
- Setup and commands: `README.md`
