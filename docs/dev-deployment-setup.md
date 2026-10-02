# Dev Deployment Setup

This guide describes the intended non-production deployment path and the setup
required before the current CI workflows can deploy it. It is based on the
repository architecture and the workflows/IaC currently checked in.

> **Production is out of scope now. Do not run a production deployment or apply
> production infrastructure as part of this setup.** The production GitHub
> environment is a future, explicitly gated promotion target only.

## Architecture: Cloudflare Pages and AWS

These services host different parts of the application; Cloudflare Pages does
not replace the API runtime:

- **Frontend:** Next.js is built for and hosted on Cloudflare Pages. The Pages
  project in `frontend/wrangler.toml` is `carpool-coordinator`.
- **Backend:** The architecture specifies FastAPI adapted by Mangum and hosted
  on AWS Lambda ARM64. The frontend calls the API through `/api/*`; the
  deployment must configure the frontend's API origin/rewrite to reach the
  Lambda Function URL or other API origin.
- **Data:** DynamoDB tables and CloudWatch Logs are AWS resources. The
  architecture diagram places the Lambda API between Cloudflare and DynamoDB.

Therefore, **yes, the specified architecture needs Lambda for the FastAPI
backend** unless the project deliberately changes its backend hosting
architecture. Cloudflare Pages hosts the frontend, not this Python FastAPI
service. That architecture change would require an explicit design decision;
this guide assumes Lambda remains the backend.

## Branch Promotion and GitHub Environments

GitHub Environments `dev` and `staging` have been created. `dev` allows feature
branches; `staging` is restricted to `master`. Production is intentionally not
created or configured yet. Environments are deployment/configuration scopes,
not branch names. Configure environment-scoped variables and secrets so a
workflow selects the credentials/configuration for its target environment.

| Source branch / action | Target | Intended behavior |
| --- | --- | --- |
| Any feature branch | `dev` | Allow deploys for testing. Cloudflare Pages uses the stable `dev` branch deployment; AWS resources/configuration are scoped to dev. |
| `master` | `staging` | Deploy only after the feature has been merged to master and CI passes. Cloudflare Pages uses its stable `staging` branch deployment. |
| Explicit, approved promotion from staging | `production` | Future only. Require a protected GitHub Environment with required reviewers and an explicit release/promotion action. Do not deploy production now. |

Keep dev, staging, and production AWS roles, state, parameters, and resources
isolated. Do not make a push to `master` implicitly target production.

### Current workflow behavior and remaining alignment

The current checkout contains in-progress workflow changes that implement
parts of this routing model:

- `backend-ci.yml` and `terraform.yml` run non-production deployment jobs on
  branch pushes, mapping `master` to `staging` and other branches to `dev`.
- `frontend-ci.yml` uses the same GitHub Environment mapping and deploys feature
  branches to the stable Pages branch `dev`, and `master` to Pages branch
  `staging`.
- The Terraform workflow sets `TF_VAR_environment` to `dev` or `staging`, uses
  a per-environment state key, and no longer defines a production apply job.
- Workflows now read `vars.AWS_DEPLOY_ROLE_ARN` and
  `vars.CLOUDFLARE_ACCOUNT_ID`; Cloudflare API authentication remains the
  `CLOUDFLARE_API_TOKEN` secret.

These workflow edits are present in the working tree but have not been
validated/deployed. GitHub environments exist but their required variables and
secrets still need to be configured. The workflow changes have not been pushed
to GitHub, and the following deployment blockers remain. This document does not
trigger any workflow.

## GitHub Environment Variables and Secrets

Set values at the narrowest environment scope that supports the deployment.
For dev, configure the following under the `dev` environment. Add separate
staging values when staging is ready. Leave production deployment credentials
and values unconfigured until the production release process is approved.

### Variables (not secret)

| Name | Scope | Purpose / source |
| --- | --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | Per environment | IAM role ARN that GitHub Actions assumes through OIDC. The ARN is not a credential; the role's trust and permissions are the security boundary. Prefer separate least-privilege roles for dev and staging. Current non-production workflows read `vars.AWS_DEPLOY_ROLE_ARN`. |
| `AWS_REGION` | Per environment | `us-east-2` for the current dev Terraform default and ADR. Staging should be explicitly chosen/configured rather than inheriting a production value. |
| `TF_VAR_environment` | Workflow-controlled | The Terraform workflow sets `dev` or `staging` from the selected GitHub Environment; do not manually set this GitHub variable. |
| `TF_STATE_BUCKET` | Per environment | Existing S3 bucket used for Terraform state. Current Terraform workflow passes this to `terraform init`; create/bootstrap the dev bucket before applying. |
| `TF_STATE_LOCK_TABLE` | Per environment | Existing DynamoDB state-lock table. Current Terraform workflow passes this to `terraform init`; create/bootstrap the dev table before applying. |
| `LAMBDA_FUNCTION_NAME` | Per environment | Function name from Terraform's `api_function_name` output. Set the output value as an environment variable after the initial Terraform apply. |
| `LAMBDA_ARTIFACT_BUCKET` | Per environment | Bucket name from Terraform's `lambda_artifact_bucket_name` output. Set the output value as an environment variable after Terraform creates the bucket. |
| `CLOUDFLARE_ACCOUNT_ID` | Per environment or repository | Cloudflare account containing the Pages project. It is an identifier, not a secret. The current frontend workflow reads it from `vars.CLOUDFLARE_ACCOUNT_ID`. |
| `CLOUDFLARE_PAGES_PROJECT` | Per environment or repository | `carpool-coordinator`, matching `frontend/wrangler.toml`; the frontend workflow reads this variable and falls back to the documented project name. |
| `DEV_API_ORIGIN` | Cloudflare Pages Preview runtime variable | Dev Lambda Function URL from the Terraform `api_function_url` output. Configure in Cloudflare Pages Preview settings. |
| `STAGING_API_ORIGIN` | Cloudflare Pages Preview runtime variable | Staging Lambda Function URL from the Terraform `api_function_url` output. Configure in Cloudflare Pages Preview settings. The Pages Function selects by `CF_PAGES_BRANCH`. |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Per environment | Google Identity Services web client ID authorized for the environment's frontend origin. Public by design; it is embedded in the frontend build. The deploy job injects this variable when building Pages. |
| `NEXT_PUBLIC_API_BASE_URL` | Local development only | Backend origin for the Next dev rewrite. The deployed static frontend uses the Pages Function and its `DEV_API_ORIGIN` / `STAGING_API_ORIGIN` runtime variables instead. |
| `COST_ALERT_EMAIL` | Dev secret only | Email subscriber for the single $5/month account-wide AWS Budget, managed by dev Terraform. Actual spend alerts at 80%; forecast alerts above 100%. Leave unset in staging to avoid creating duplicate account-wide budgets. |

`AWS_DEPLOY_ROLE_ARN` is a role identifier supplied to GitHub Actions; the
workflow exchanges a GitHub OIDC token for short-lived AWS credentials. No AWS
access key is stored in GitHub. Follow [GitHub's AWS OIDC guide](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
and create an IAM OIDC provider with issuer `https://token.actions.githubusercontent.com`
and audience `sts.amazonaws.com`. Create separate IAM roles for dev and staging.
For this repository, scope the trust policy `sub` to
`repo:timycyip/carpool-coordinator:environment:dev` or
`repo:timycyip/carpool-coordinator:environment:staging`, respectively, and
scope the role's AWS permissions to that environment's state, tables, Lambda,
artifact bucket, and parameters. GitHub's `id-token: write` permission is
already present in the AWS workflows. See [AWS's OIDC role guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html).
Do not add `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, or long-lived AWS tokens to GitHub variables/secrets,
workflow files, or the repository.

In the AWS IAM console, add the GitHub OIDC identity provider once, then create
one role per environment using a trust policy like this (substitute your AWS
account ID and the environment name):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:timycyip/carpool-coordinator:environment:dev"
      }
    }
  }]
}
```

Use `...:environment:staging` for the staging role. Attach a separate
least-privilege permissions policy to each role. Terraform apply needs resource
creation/update permissions for its environment; code deploy needs S3 artifact
upload and Lambda update permissions. Do not use the Lambda execution role as
the GitHub deployment role. After the role exists, copy its ARN into
**Repository Settings → Environments → `dev`/`staging` → Environment variables**
as `AWS_DEPLOY_ROLE_ARN`.

The dev Terraform role also needs the AWS Budgets create/update/delete and
notification management actions for the one account-wide budget (`budgets:CreateBudget`,
`budgets:ModifyBudget`, `budgets:DeleteBudget`, `budgets:CreateNotification`,
`budgets:UpdateNotification`, and `budgets:DeleteNotification`). Scope these to
the account budget where IAM supports resource scoping; some Budgets actions
require `Resource: "*"`.

### Secrets

| Name | Scope | Purpose / source |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | Per environment or repository | Cloudflare API token limited to the required account and Pages project permissions. Store as a GitHub secret. Use Pages Write/Edit permission needed to create deployments, scoped to the target account. The current frontend workflow reads this secret. |

Do not put Google client secrets in the frontend. The current app uses a public
Google client ID in the browser and verifies Google ID tokens on the backend.
Backend signing material belongs in AWS Systems Manager Parameter Store, not in
GitHub. AWS access is through OIDC only.

The frontend is a static Next.js export. Cloudflare Pages runs a small Function
only for `/api/*`; `frontend/public/_routes.json` keeps static routes off the
Functions invocation quota. Configure the dev and staging API origins in Pages
Preview runtime settings. The proxy follows the deployment policy: `master`
uses staging and all other branches use dev. Production has no Pages deployment
or API origin until its gate is approved. The API URLs are identifiers, not
secrets.

## AWS Systems Manager Parameter Store

The backend code currently reads configuration from Lambda environment
variables; **it does not call SSM Parameter Store or resolve SSM parameters at
startup**. Store the values below in Parameter Store, then arrange for the
deployment/runtime configuration to inject them into the Lambda environment,
or implement SSM retrieval before relying on Parameter Store alone.

Recommended dev parameter names in `us-east-2`:

| Parameter | Type | Required? | Backend use |
| --- | --- | --- | --- |
| `/carpool/dev/GOOGLE_CLIENT_ID` | `String` | Yes for Google sign-in | Backend verifies token audience against `GOOGLE_CLIENT_ID`; use the same client ID as the frontend build variable. |
| `/carpool/dev/JWT_SECRET` | `SecureString` | Yes for app session tokens | HMAC signing/verification key read as `JWT_SECRET`. Generate a high-entropy random value. Never commit or print it. |
| `/carpool/dev/RATE_LIMIT_PER_IP` | `String` | Optional | Defaults to 60 requests per window. |
| `/carpool/dev/RATE_LIMIT_PER_USER` | `String` | Optional | Defaults to 120 requests per window. |
| `/carpool/dev/RATE_LIMIT_WINDOW_IP` | `String` | Optional | Defaults to 60 seconds. |
| `/carpool/dev/RATE_LIMIT_WINDOW_USER` | `String` | Optional | Defaults to 60 seconds. |

The current rate-limit implementation reads these optional values from
environment variables and falls back to its defaults. `AWS_REGION` defaults
to `us-east-2` in the DynamoDB client. Active app-data and rate-limit table
names are passed by Terraform as Lambda environment variables; local runs
retain the old table-name defaults. The app does not yet use the other cache
tables.

The architecture spec mentions API keys, but current backend code has no
implemented ORS/geocoding integration or associated API-key setting to list as
a required runtime parameter. Add a suitably scoped parameter (for example,
`/carpool/dev/ORS_API_KEY`, `SecureString`) only when the routing integration
is implemented. Never create a fake value to make deployment appear complete.

Create the dev parameters using an authorized AWS operator identity, for
example:

```sh
aws ssm put-parameter --region us-east-2 \
  --name /carpool/dev/GOOGLE_CLIENT_ID --type String \
  --value "$GOOGLE_CLIENT_ID" --overwrite

aws ssm put-parameter --region us-east-2 \
  --name /carpool/dev/JWT_SECRET --type SecureString \
  --value "$JWT_SECRET" --overwrite
```

Supply values through a protected local shell/session; do not paste secret
values into chat, source control, command logs, or a pull request. The current
deployment workflow does not read these parameters or set Lambda environment
variables from them; that integration is a deployment prerequisite.

## Terraform State Bootstrap

The remote backend in `infra/terraform.tf` expects these resources in
`us-east-2`:

- S3 bucket: `carpool-dev-terraform-state`
- DynamoDB lock table: `carpool-dev-terraform-lock`, partition key `LockID`
  (string)

They must exist **before** `terraform init` with the configured S3 backend.
The current Terraform workflow's comment says it bootstraps these resources,
but its command only runs `terraform init`; it does not create them. Bootstrap
once with an authorized operator identity that has the required S3 and
DynamoDB permissions. Do not put operator access keys in the repository or
GitHub. Example commands for the configured dev backend:

```sh
aws s3api create-bucket \
  --bucket carpool-dev-terraform-state \
  --region us-east-2 \
  --create-bucket-configuration LocationConstraint=us-east-2

aws s3api put-public-access-block \
  --bucket carpool-dev-terraform-state \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-versioning \
  --bucket carpool-dev-terraform-state \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket carpool-dev-terraform-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms","SSEKMSKeyId":"alias/aws/s3"}}]}'

aws dynamodb create-table \
  --table-name carpool-dev-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-2
```

Check that the bucket and table exist and are in the expected account/region
before running Terraform. Keep state access restricted to the deployment
roles/operators. `infra/terraform.tf` has dev bucket/table defaults; the
current workflow edits pass environment-specific bucket/table values and a
key of `infra/<environment>/terraform.tfstate`. Verify those overrides are
configured and staging uses isolated state before a staging apply. Do not
point staging or production at the dev state.

## Initial Non-Production Deployment Order

1. **Prepare Cloudflare Pages:** create/confirm the `carpool-coordinator`
  project, configure the intended dev preview domain/origin, and create a
  narrowly scoped API token with Pages write access. Add the token and account
  ID to the appropriate GitHub environment settings. See [Cloudflare Pages API
  token permissions](https://developers.cloudflare.com/pages/configuration/api/).
2. **Prepare GitHub environments and branch rules:** `dev` and `staging` are
  created. `dev` permits branch deployments; `staging` is restricted to
  `master`. Add the per-environment variables/secrets from the tables above.
  Production is intentionally not created or configured.
3. **Prepare AWS OIDC:** create an IAM OIDC provider/trust policy for GitHub
   Actions and a least-privilege dev role. Restrict trust to this repository
   and the `dev` environment subject. Add its role ARN as the `AWS_ROLE_ARN`
   GitHub environment variable. Do not create static AWS credentials for CI.
4. **Bootstrap Terraform state:** create and verify the dev S3 state bucket and
   DynamoDB lock table using the commands above.
5. **Resolve IaC/backend gaps before applying:** the current `infra/lambda.tf`
   adds Terraform resources for the Lambda execution role/function, Function
   URL, CloudWatch log group, and artifact bucket. Verify IAM permissions,
   output names, and the initial artifact bootstrap before applying. Fix the
   mismatch between Terraform's prefixed table names (for example,
   `carpool-dev-app-data`) and backend hard-coded table names (for example,
   `app_data`). Ensure the dev apply uses the `dev` GitHub Environment and
   `TF_VAR_environment=dev`.
6. **Create dev runtime parameters:** add the required Google client ID and
   JWT signing secret to SSM. Implement secure SSM-to-Lambda environment
   integration and grant the Lambda execution role access only to the needed
   dev parameters. The current Lambda Terraform configuration does not yet
   inject these values.
7. **Bootstrap and verify the backend in dev:** the Lambda Terraform resource
   points at `lambda.zip` in the artifact bucket. Ensure the package has been
   built and uploaded before Terraform creates the function; the existing
   Terraform workflow does not build/upload that initial artifact. Then apply
   only dev resources, deploy/update the Lambda package, and verify its health
   endpoint plus DynamoDB access. No production resources should be selected or
   changed.
8. **Deploy and verify the frontend to dev:** first resolve the Pages build
   incompatibility below, then inject the dev Google client ID and dev API
   origin at the correct Cloudflare build/runtime stage, deploy a
   feature-branch preview to the dev target, and verify login/API calls against
   the dev backend.
9. **Promote to staging later:** merge the tested feature to `master`, deploy
   the staging configuration/state/resources, and run staging acceptance
   checks. Production remains a separate, explicitly approved promotion and is
   not part of this setup.

## Current Blockers and Gaps

- CI branch/environment routing has been edited in the current working tree
  for feature → `dev` and `master` → `staging`; production has no apply job in
  the current workflow edits. These edits and GitHub environment settings
  still need validation before deployment.
- `infra/lambda.tf` now declares the Lambda function/execution role, Function
  URL, log group, and artifact bucket. However, initial function creation
  needs `lambda.zip` to already exist in the bucket, while the Terraform
  workflow does not build or upload that artifact. The backend workflow
  expects an existing function when it updates function code, so first-deploy
  ordering still needs to be made deterministic.
- Terraform table names include `carpool-${environment}-`, while backend
  repositories and middleware use hard-coded names such as `app_data` and
  `rate_limit_cache`. The new Lambda configuration sets table-name environment
  variables, but the backend code does not currently consume them. As-is, the
  Lambda cannot use the tables Terraform creates unless naming is reconciled.
- Terraform remote-state resources are not created by the workflow; the S3
  bucket and lock table must be bootstrapped before backend-enabled
  `terraform init`. Current workflow edits accept their names as variables
  and use environment-specific state keys, but do not create the resources.
- The backend requires `GOOGLE_CLIENT_ID` and `JWT_SECRET` environment
  variables, but does not read SSM. Current deploy jobs do not retrieve the
  documented SSM values or update Lambda configuration with them.
- The frontend now uses a static Next.js export and an API-only Pages Function
  proxy, as recorded in [ADR-0016](adr/0016-static-pages-api-proxy.md). This
  avoids the `next-on-pages` peer incompatibility with Next.js 16. The code path
  and configuration are present, but the Pages build/deploy has not been run;
  configure the Preview API-origin variables and verify it before calling the
  Cloudflare deployment operational.
- The frontend deploy workflow does not inject
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Without it, the Google sign-in button cannot
  be configured. Deployed API requests use the Pages Function origins described
  above; `NEXT_PUBLIC_API_BASE_URL` is for local Next.js development only.
- The backend workflow expects the Lambda function and artifact bucket to
  pre-exist and only updates Lambda code; its workflow does not create the
  resources or configure runtime environment variables.
- Staging state isolation is being configured through the current workflow's
  environment-specific state key; verify backend initialization and separate
  state bucket/lock resources before a staging apply. Production state and
  promotion remain intentionally unconfigured/out of scope.
- No item in this guide constitutes evidence that a cloud resource is already
  deployed. Verify AWS account, region, resource state, and Pages deployment
  from authorized consoles/CLI before treating any environment as live.
