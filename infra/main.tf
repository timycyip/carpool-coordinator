locals {
  name_prefix = "carpool-${var.environment}"
}

# ---------------------------------------------------------------------------
# 1. app_data — all business entities (single-table PK/SK overloading)
#    GSIs: sessions-by-user, admins-by-user
#    PITR enabled; NO TTL (durable business data)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "app_data" {
  name              = "${local.name_prefix}-app-data"
  billing_mode      = "PAY_PER_REQUEST"
  hash_key          = "PK"
  range_key         = "SK"
  deletion_protection = true

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "gsi1_pk"
    type = "S"
  }

  attribute {
    name = "gsi1_sk"
    type = "S"
  }

  attribute {
    name = "gsi2_pk"
    type = "S"
  }

  attribute {
    name = "gsi2_sk"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi_sessions_by_user"
    hash_key        = "gsi1_pk"
    range_key       = "gsi1_sk"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "gsi_admins_by_user"
    hash_key        = "gsi2_pk"
    range_key       = "gsi2_sk"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# 2. session_cache — session-scoped ephemeral state (TTL)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "session_cache" {
  name         = "${local.name_prefix}-session-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# 3. rate_limit_cache — per-IP / per-user request counters (TTL)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "rate_limit_cache" {
  name         = "${local.name_prefix}-rate-limit-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# 4. brute_force_counter — failed-auth counter for lockout (TTL)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "brute_force_counter" {
  name         = "${local.name_prefix}-brute-force-counter"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# 5. geocode_cache — postal-code → (lat, lon) cache (TTL, 30 days)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "geocode_cache" {
  name         = "${local.name_prefix}-geocode-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }
}
