# ADR-0014: Non-Production Environment Promotion and GitHub OIDC

**Status:** Accepted (2026-10-01)
**Decision owners:** Project owner / Tech Lead

## Context

Phase 2 needs a safe path to test feature branches without applying them to
production. The repository uses GitHub Actions, Cloudflare Pages for the
Next.js frontend, and AWS for the FastAPI/Lambda backend and DynamoDB. CI needs
cloud access without long-lived AWS access keys in source control.

## Decision

- Pushes to any non-`master` branch target the GitHub `dev` environment.
- Pushes to `master` target the GitHub `staging` environment. The staging
  environment is restricted to the `master` branch.
- Production deployment is intentionally not configured or enabled. Any future
  production promotion must follow a successful staging deployment and require
  an explicit, protected approval step.
- AWS access from GitHub Actions uses OIDC federation and short-lived role
  credentials. The environment-scoped `AWS_DEPLOY_ROLE_ARN` variable identifies
  the role; it is not an AWS credential. Dev and staging use separate,
  least-privilege IAM roles and isolated state/resources.
- Cloudflare Pages hosts the frontend; AWS Lambda remains the backend runtime.
  The static export and API-only Pages Function path are recorded in ADR-0016;
  build and deployment verification remain outstanding.

## Alternatives Considered

- Deploy every branch to staging: rejected because feature work needs an
  isolated dev target and should not overwrite the staging candidate.
- Deploy `master` directly to production: rejected because it skips the
  required staging validation step.
- Store static AWS access keys in GitHub Secrets: rejected in favor of OIDC
  federation and short-lived credentials.
- Move the Next.js frontend to Cloudflare Workers to bypass the current Pages
  adapter issue: not selected. The project explicitly specifies Pages; a host
  change requires a separate architecture decision.

## Consequences

- Feature pushes can deploy to dev after the workflows and environment values
  are published/configured; no deployment is triggered by this ADR.
- `master` is the staging promotion boundary. Dev and staging require separate
  GitHub environment variables, state keys, AWS roles, and runtime parameters.
- Production remains unavailable until a separately reviewed promotion
  workflow and protected GitHub environment are explicitly approved.
- The current checkout is detached and workflow changes are not yet published
  to GitHub, so the defined path is not active remotely yet.

## References

- [Phase 2 Foundation Plan](../../plans/phase-2-foundation.md)
- [Dev Deployment Setup](../dev-deployment-setup.md)
- [Terraform IaC in us-east-2](0003-terraform-iac-us-east-2.md)
