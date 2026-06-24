# ADR-0003: Terraform IaC in us-east-2

## Status
Accepted — human-reviewed and confirmed 2026-06-23

## Date
2026-06-23

## Context
Phase 2 provisions AWS infrastructure (Lambda, DynamoDB tables, Parameter Store, S3, IAM, Lambda
Function URL). This infrastructure must be version-controlled, reproducible, and deployable via
CI/CD. The region choice also constrains OSRM extract geography (Phase 4) and general latency to
end users.

Forces at play:
- Repo already uses GitHub Actions (legacy `pylint.yml` / `unittest.yml`).
- The team is familiar with TypeScript (frontend) and Python (backend).
- Target region should be US-based (primary user base is in North America per the initial
  stakeholder).
- Single-region MVP is acceptable; multi-region is Phase 6+.

## Decision
Use **Terraform** (HCL) for all AWS infrastructure provisioning, executed by GitHub Actions on merge
to main. Deploy to **`us-east-2` (Ohio)**.

Terraform state is stored in an S3 backend with DynamoDB table locking (standard pattern).

The Terraform workspace lives in `infra/` at the repo root. It provisions:
- Lambda function + Function URL + IAM role
- DynamoDB tables (per the Phase 1 ERD — see ADR-0001)
- Parameter Store entries (Google client ID, JWT secret)
- S3 bucket for CloudWatch log archival (30-day lifecycle)
- CloudWatch log group for the Lambda

## Alternatives Considered

### Alternative A: AWS CDK (TypeScript)
- Pros: TypeScript aligns with frontend; composable constructs; mature Lambda/DDB support.
- Cons: heavier; CDK synthesis step; steeper learning curve for infra-only; CDK version pinning.
  Rejected in favor of Terraform's broader adoption and simpler HCL.

### Alternative B: AWS SAM
- Pros: designed for Lambda; simpler YAML.
- Cons: less composable for non-Lambda resources (DynamoDB, S3, Parameter Store); SAM + Terraform
  for the rest would be two IaC tools. Rejected.

### Alternative C: Plain zip via GitHub Actions (no IaC)
- Pros: minimal tooling.
- Cons: infrastructure is implicit; no drift detection; no rollback; manual console changes.
  Rejected on reproducibility grounds.

### Alternative D: Terraform (chosen)
- Pros: declarative HCL; broad AWS support; drift detection (`terraform plan`); state management;
  GitHub Actions integration is well-documented; works for Lambda + DDB + S3 + IAM in one tool.
- Cons: HCL is another language; state backend (S3 + DynamoDB lock) needs initial bootstrap;
  HCL is less composable than CDK for complex patterns.

## Consequences
- **Positive:** Infrastructure is version-controlled, reproducible, and auditable. `terraform plan`
  in PRs shows exactly what will change before merge. Single tool for all resources.
- **Negative:** HCL is a new language for the team; state backend needs bootstrapping (one-time);
  `infra/` is a separate codebase from `app/` and `frontend/`.
- **Action required:** Task 2.10 sets up the Terraform S3 backend, the GitHub Actions workflow
  (`terraform init && terraform plan` on PR; `terraform apply` on main), and the initial Lambda +
  DDB + S3 resources.
- **Region locked to `us-east-2`** — affects latency to users and OSRM extract geography in Phase 4.

## Links
- Phase 2 plan Task 2.2 (DynamoDB schema): `plans/phase-2-foundation.md`
- Phase 2 plan Task 2.10 (CI/CD): `plans/phase-2-foundation.md`
- ARCHITECTURE.md §Technology Stack: `ARCHITECTURE.md`
