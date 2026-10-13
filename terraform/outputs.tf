output "source_bucket_name" {
  description = "Name of the source S3 bucket for test data."
  value       = aws_s3_bucket.source.id
}

output "destination_bucket_name" {
  description = "Name of the cross-region recovery S3 bucket."
  value       = aws_s3_bucket.destination.id
}

output "backup_function_name" {
  description = "Lambda function that creates immutable, per-run recovery prefixes."
  value       = aws_lambda_function.backup.function_name
}

output "alert_topic_arn" {
  description = "SNS topic ARN for failure alerts. Confirm the email subscription after apply."
  value       = aws_sns_topic.alerts.arn
}