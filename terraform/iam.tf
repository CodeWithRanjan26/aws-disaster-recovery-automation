resource "aws_iam_role" "backup_lambda" {
  name = "${var.name_prefix}-backup-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "backup_lambda" {
  name = "${var.name_prefix}-backup-policy"
  role = aws_iam_role.backup_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListSourceBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.source.arn
      },
      {
        Sid      = "ReadSourceObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.source.arn}/*"
      },
      {
        Sid    = "WriteRecoveryObjects"
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.destination.arn}/${trim(var.backup_prefix, "/")}/*"
      },
      {
        Sid    = "WriteFunctionLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.backup.arn}:*"
      }
    ]
  })
}