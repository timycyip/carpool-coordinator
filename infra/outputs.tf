output "app_data_table_name" {
  description = "Name of the app_data DynamoDB table"
  value       = aws_dynamodb_table.app_data.name
}

output "session_cache_table_name" {
  description = "Name of the session_cache DynamoDB table"
  value       = aws_dynamodb_table.session_cache.name
}

output "rate_limit_cache_table_name" {
  description = "Name of the rate_limit_cache DynamoDB table"
  value       = aws_dynamodb_table.rate_limit_cache.name
}

output "brute_force_counter_table_name" {
  description = "Name of the brute_force_counter DynamoDB table"
  value       = aws_dynamodb_table.brute_force_counter.name
}

output "geocode_cache_table_name" {
  description = "Name of the geocode_cache DynamoDB table"
  value       = aws_dynamodb_table.geocode_cache.name
}
