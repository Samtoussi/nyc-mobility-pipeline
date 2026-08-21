resource "aws_glue_catalog_database" "mobility" {
  name = "nyc_mobility"
}

resource "aws_glue_catalog_database" "mobility_gold" {
  name = "nyc_mobility_gold"
}