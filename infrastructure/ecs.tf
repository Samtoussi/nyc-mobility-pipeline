resource "aws_ecs_cluster" "nyc_mobility" {
  name = "nyc-mobility"
}


resource "aws_cloudwatch_log_group" "nyc_mobility" {
  name              = "/ecs/nyc-mobility"
  retention_in_days = 7
}


resource "aws_ecs_task_definition" "nyc_mobility" {
  family                   = "nyc-mobility"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = "1024"
  memory = "4096"

  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "nyc-mobility"
      image     = "${aws_ecr_repository.nyc_mobility.repository_url}:v3"
      essential = true

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nyc_mobility.name
          "awslogs-region"        = "eu-north-1"
          "awslogs-stream-prefix" = "pipeline"
        }
      }
    }
  ])
}