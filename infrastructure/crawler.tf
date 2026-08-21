resource "aws_glue_crawler" "silver" {
  name          = "nyc-mobility-silver-crawler"
  database_name = aws_glue_catalog_database.mobility.name
  role          = aws_iam_role.glue_crawler.arn
  description   = "Discovers and catalogs NYC Mobility Silver Parquet data stored in S3."

  s3_target {
    path = "s3://${aws_s3_bucket.mobility.bucket}/silver/yellow_tripdata/"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  configuration = jsonencode({
    Version = 1.0

    CreatePartitionIndex = true
  })
}