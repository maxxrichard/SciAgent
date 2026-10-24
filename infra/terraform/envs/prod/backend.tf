# State bucket and lock table are created by infra/terraform/bootstrap.
terraform {
  backend "s3" {
    bucket         = "sciagent-tfstate-prod"
    key            = "sciagent/prod/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "sciagent-tfstate-prod-lock"
    encrypt        = true
  }
}
