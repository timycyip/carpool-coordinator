locals {
  lambda_name           = local.name_prefix
  lambda_log_group_name = "/aws/lambda/${local.lambda_name}"
}

resource "aws_s3_bucket" "lambda_artifacts" {
  bucket = "${local.name_prefix}-lambda-deploy"

  tags = {
    Application = "carpool-coordinator"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_public_access_block" "lambda_artifacts" {
  bucket                  = aws_s3_bucket.lambda_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  rule {
    id     = "expire-old-deployment-artifacts"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "lambda_artifacts_tls" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.lambda_artifacts.arn,
      "${aws_s3_bucket.lambda_artifacts.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "lambda_artifacts_tls" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  policy = data.aws_iam_policy_document.lambda_artifacts_tls.json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = local.lambda_log_group_name
  retention_in_days = 30

  tags = {
    Application = "carpool-coordinator"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name_prefix}-lambda-execution"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Application = "carpool-coordinator"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "aws_iam_policy_document" "lambda_execution" {
  statement {
    sid       = "WriteFunctionLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }

  statement {
    sid    = "AccessEnvironmentTables"
    effect = "Allow"
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:DeleteItem",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:TransactWriteItems",
      "dynamodb:UpdateItem",
    ]
    resources = flatten([
      [
        aws_dynamodb_table.app_data.arn,
        "${aws_dynamodb_table.app_data.arn}/index/*",
      ],
      [
        aws_dynamodb_table.session_cache.arn,
        aws_dynamodb_table.rate_limit_cache.arn,
        aws_dynamodb_table.brute_force_counter.arn,
        aws_dynamodb_table.geocode_cache.arn,
      ],
    ])
  }
}

resource "aws_iam_role_policy" "api_execution" {
  name   = "${local.name_prefix}-lambda-execution"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.lambda_execution.json
}

resource "aws_lambda_function" "api" {
  function_name = local.lambda_name
  description   = "Carpool Coordinator ${var.environment} FastAPI API"
  role          = aws_iam_role.api.arn
  runtime       = "python3.12"
  handler       = "app.main.handler"
  architectures = ["arm64"]
  timeout       = 10
  memory_size   = 256

  # Bootstrap the bucket first, upload lambda.zip, then create the function. CI
  # must upload the replacement package before each Terraform function update.
  s3_bucket = aws_s3_bucket.lambda_artifacts.id
  s3_key    = "lambda.zip"

  environment {
    variables = {
      APP_ENVIRONMENT                = var.environment
      APP_DATA_TABLE_NAME            = aws_dynamodb_table.app_data.name
      SESSION_CACHE_TABLE_NAME       = aws_dynamodb_table.session_cache.name
      RATE_LIMIT_CACHE_TABLE_NAME    = aws_dynamodb_table.rate_limit_cache.name
      BRUTE_FORCE_COUNTER_TABLE_NAME = aws_dynamodb_table.brute_force_counter.name
      GEOCODE_CACHE_TABLE_NAME       = aws_dynamodb_table.geocode_cache.name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.api,
    aws_iam_role_policy.api_execution,
  ]

  tags = {
    Application = "carpool-coordinator"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "public_function_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "public_function_invoke_via_url" {
  statement_id             = "AllowInvokeViaPublicFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.api.function_name
  principal                = "*"
  invoked_via_function_url = true
}
