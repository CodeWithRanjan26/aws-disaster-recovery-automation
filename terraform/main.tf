data "aws_caller_identity" "current" {}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "source" {
  bucket = "${var.name_prefix}-${data.aws_caller_identity.current.account_id}-${random_id.bucket_suffix.hex}-src"
}

resource "aws_s3_bucket" "destination" {
  provider = aws.destination
  bucket   = "${var.name_prefix}-${data.aws_caller_identity.current.account_id}-${random_id.bucket_suffix.hex}-dr"
}

resource "aws_s3_bucket_versioning" "source" {
  bucket = aws_s3_bucket.source.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "destination" {
  provider = aws.destination
  bucket   = aws_s3_bucket.destination.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "source" {
  bucket                  = aws_s3_bucket.source.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "destination" {
  provider                = aws.destination
  bucket                  = aws_s3_bucket.destination.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "source" {
  bucket = aws_s3_bucket.source.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "destination" {
  provider = aws.destination
  bucket   = aws_s3_bucket.destination.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "destination" {
  provider = aws.destination
  bucket   = aws_s3_bucket.destination.id

  rule {
    id     = "expire-recovery-points"
    status = "Enabled"
    filter {
      prefix = "${trim(var.backup_prefix, "/")}/"
    }
    expiration {
      days = var.retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = var.retention_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "archive_file" "backup_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/backup"
  output_path = "${path.module}/backup-lambda.zip"
}

resource "aws_cloudwatch_log_group" "backup" {
  name              = "/aws/lambda/${var.name_prefix}-s3-backup"
  retention_in_days = 14
}

resource "aws_lambda_function" "backup" {
  function_name    = "${var.name_prefix}-s3-backup"
  role             = aws_iam_role.backup_lambda.arn
  runtime          = "python3.12"
  handler          = "app.handler"
  filename         = data.archive_file.backup_lambda.output_path
  source_code_hash = data.archive_file.backup_lambda.output_base64sha256
  timeout          = 900
  memory_size      = 256

  environment {
    variables = {
      SOURCE_BUCKET      = aws_s3_bucket.source.id
      DESTINATION_BUCKET = aws_s3_bucket.destination.id
      SOURCE_REGION      = var.source_region
      DESTINATION_REGION = var.destination_region
      BACKUP_PREFIX      = trim(var.backup_prefix, "/")
    }
  }

  depends_on = [aws_cloudwatch_log_group.backup]
}

resource "aws_lambda_function_event_invoke_config" "backup" {
  function_name                = aws_lambda_function.backup.function_name
  maximum_event_age_in_seconds = 3600
  maximum_retry_attempts       = 2
}

resource "aws_cloudwatch_event_rule" "daily_backup" {
  name                = "${var.name_prefix}-daily-s3-backup"
  description         = "Starts the cross-region S3 recovery-point copy once per day."
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "backup" {
  rule      = aws_cloudwatch_event_rule.daily_backup.name
  target_id = "${var.name_prefix}-backup-lambda"
  arn       = aws_lambda_function.backup.arn

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 2
  }

  depends_on = [aws_lambda_permission.allow_eventbridge]
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_backup.arn
}