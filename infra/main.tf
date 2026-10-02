locals {
  name_prefix = "carpool-${var.environment}"
}

# ---------------------------------------------------------------------------
# 1. app_data — all business entities (single-table PK/SK overloading)
#    GSIs: sessions-by-user, admins-by-user
#    production PITR only; NO TTL (durable business data)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "app_data" {
  name                        = "${local.name_prefix}-app-data"
  billing_mode                = "PROVISIONED"
  read_capacity               = 1
  write_capacity              = 1
  hash_key                    = "PK"
  range_key                   = "SK"
  deletion_protection_enabled = true

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
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 1

    key_schema {
      attribute_name = "gsi1_pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "gsi1_sk"
      key_type       = "RANGE"
    }
  }

  global_secondary_index {
    name            = "gsi_admins_by_user"
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 1

    key_schema {
      attribute_name = "gsi2_pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "gsi2_sk"
      key_type       = "RANGE"
    }
  }

  # Keep non-production free of continuous backup charges. Production must
  # explicitly enable PITR when the production environment is authorized.
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# 2. session_cache — session-scoped ephemeral state (TTL)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "session_cache" {
  name           = "${local.name_prefix}-session-cache"
  billing_mode   = "PROVISIONED"
  read_capacity  = 1
  write_capacity = 1
  hash_key       = "PK"
  range_key      = "SK"

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
  name           = "${local.name_prefix}-rate-limit-cache"
  billing_mode   = "PROVISIONED"
  read_capacity  = 1
  write_capacity = 1
  hash_key       = "PK"
  range_key      = "SK"

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
  name           = "${local.name_prefix}-brute-force-counter"
  billing_mode   = "PROVISIONED"
  read_capacity  = 1
  write_capacity = 1
  hash_key       = "PK"
  range_key      = "SK"

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
  name           = "${local.name_prefix}-geocode-cache"
  billing_mode   = "PROVISIONED"
  read_capacity  = 1
  write_capacity = 1
  hash_key       = "PK"
  range_key      = "SK"

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
