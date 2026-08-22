# -------------------------------------------------------------------
# GitHub Actions OIDC provider
# -------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]
}


# -------------------------------------------------------------------
# GitHub Actions deployment role
# -------------------------------------------------------------------

resource "aws_iam_role" "github_actions" {
  name = "nyc-mobility-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }

        Action = "sts:AssumeRoleWithWebIdentity"

        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:Samtoussi@179637459/nyc-mobility-pipeline@1335888278:ref:refs/heads/main"
          }
        }
      }
    ]
  })
}


# -------------------------------------------------------------------
# GitHub Actions deployment permissions
# -------------------------------------------------------------------

resource "aws_iam_role_policy" "github_actions" {
  name = "nyc-mobility-github-actions-deploy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "ecr:GetAuthorizationToken"
        ]

        Resource = "*"
      },
      {
        Effect = "Allow"

        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]

        Resource = aws_ecr_repository.nyc_mobility.arn
      },
      {
        Effect = "Allow"

        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DescribeTaskDefinition"
        ]

        Resource = "*"
      },
      {
        Effect = "Allow"

        Action = [
          "iam:PassRole"
        ]

        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      },
      {
        Effect = "Allow"

        Action = [
          "scheduler:GetSchedule",
          "scheduler:UpdateSchedule"
        ]

        Resource = aws_scheduler_schedule.nyc_mobility.arn
      }
    ]
  })
}