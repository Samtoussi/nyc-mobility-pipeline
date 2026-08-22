variable "alert_email" {
  type        = string
  description = "Email address that receives NYC Mobility pipeline failure alerts"
}


# -------------------------------------------------------------------
# SNS topic and email subscription
# -------------------------------------------------------------------

resource "aws_sns_topic" "pipeline_alerts" {
  name = "nyc-mobility-alerts"
}

resource "aws_sns_topic_subscription" "pipeline_alert_email" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}


# -------------------------------------------------------------------
# EventBridge rule for failed ECS tasks
#
# Successful Fargate batch tasks also end in STOPPED state.
# Therefore we only alert when the nyc-mobility container exits
# with a non-zero exit code.
# -------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "ecs_pipeline_failure" {
  name        = "nyc-mobility-pipeline-failure"
  description = "Detect failed NYC Mobility ECS pipeline tasks"

  event_pattern = jsonencode({
    source = [
      "aws.ecs"
    ]

    detail-type = [
      "ECS Task State Change"
    ]

    detail = {
      clusterArn = [
        aws_ecs_cluster.nyc_mobility.arn
      ]

      lastStatus = [
        "STOPPED"
      ]

      containers = {
        name = [
          "nyc-mobility"
        ]

        exitCode = [
          {
            anything-but = 0
          }
        ]
      }
    }
  })
}


# -------------------------------------------------------------------
# Send matching failure events to SNS
# -------------------------------------------------------------------

resource "aws_cloudwatch_event_target" "ecs_pipeline_failure_sns" {
  rule      = aws_cloudwatch_event_rule.ecs_pipeline_failure.name
  target_id = "nyc-mobility-failure-sns"
  arn       = aws_sns_topic.pipeline_alerts.arn
}


# -------------------------------------------------------------------
# Allow EventBridge to publish to the SNS topic
# -------------------------------------------------------------------

resource "aws_sns_topic_policy" "pipeline_alerts" {
  arn = aws_sns_topic.pipeline_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"

        Principal = {
          Service = "events.amazonaws.com"
        }

        Action = "sns:Publish"

        Resource = aws_sns_topic.pipeline_alerts.arn

        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.ecs_pipeline_failure.arn
          }
        }
      }
    ]
  })
}