resource "aws_iam_user" "streamlit" {
  name = "nyc-mobility-streamlit"
}

resource "aws_iam_user_policy" "streamlit" {
  name = "nyc-mobility-streamlit-dashboard"
  user = aws_iam_user.streamlit.name

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults"
        ]

        Resource = "*"
      },
      {
        Effect = "Allow"

        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions"
        ]

        Resource = "*"
      },
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
          "s3:GetObject"
        ]

        Resource = [
          "${aws_s3_bucket.mobility.arn}/gold/*"
        ]
      },
      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]

        Resource = [
          "${aws_s3_bucket.mobility.arn}/athena-results/*"
        ]
      }
    ]
  })
}