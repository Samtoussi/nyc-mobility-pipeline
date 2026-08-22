resource "aws_iam_role" "glue_crawler" {
  name        = "AWSGlueServiceRole-nyc-mobility"
  description = "Allows Glue to call AWS services on your behalf. "

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "glue.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service_role" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_silver_read" {
  name = "nyc-mobility-silver-read"
  role = aws_iam_role.glue_crawler.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = "s3:ListBucket"

        Resource = aws_s3_bucket.mobility.arn

        Condition = {
          StringLike = {
            "s3:prefix" = [
              "silver/yellow_tripdata/*"
            ]
          }
        }
      },
      {
        Effect = "Allow"

        Action = "s3:GetObject"

        Resource = "${aws_s3_bucket.mobility.arn}/silver/yellow_tripdata/*"
      }
    ]
  })
}

# -------------------------------------------------------------------
# ECS Fargate task execution role
#
# Used by ECS itself to:
# - pull container images from ECR
# - write container logs to CloudWatch
# -------------------------------------------------------------------

resource "aws_iam_role" "ecs_task_execution" {
  name = "nyc-mobility-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


# -------------------------------------------------------------------
# ECS Fargate task role
#
# Used by the application running inside the container.
# boto3 automatically receives temporary credentials from this role.
# -------------------------------------------------------------------

resource "aws_iam_role" "ecs_task" {
  name = "nyc-mobility-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}


# -------------------------------------------------------------------
# S3 access for the NYC Mobility pipeline
# -------------------------------------------------------------------

resource "aws_iam_role_policy" "ecs_pipeline_s3" {
  name = "nyc-mobility-pipeline-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]

        Resource = aws_s3_bucket.mobility.arn
      },
      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]

        Resource = "${aws_s3_bucket.mobility.arn}/*"
      }
    ]
  })
}