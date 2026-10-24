# State bucket and lock table are created by infra/terraform/bootstrap.
terraform {
  backend "s3" {
    bucket         = "sciagent-tfstate-staging"
    key            = "sciagent/staging/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "sciagent-tfstate-staging-lock"
    encrypt        = true
  }
}
