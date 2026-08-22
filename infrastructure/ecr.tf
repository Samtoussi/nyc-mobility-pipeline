resource "aws_ecr_repository" "nyc_mobility" {
  name                 = "nyc-mobility"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}