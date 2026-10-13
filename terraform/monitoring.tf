resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-backup-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "backup_errors" {
  alarm_name          = "${var.name_prefix}-backup-lambda-errors"
  alarm_description   = "Backup Lambda reported a failed run after configured retries."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.backup.function_name
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}