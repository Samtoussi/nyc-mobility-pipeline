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