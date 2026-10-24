# State bucket and lock table are created by infra/terraform/bootstrap.
terraform {
  backend "s3" {
    bucket         = "sciagent-tfstate-dev"
    key            = "sciagent/dev/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "sciagent-tfstate-dev-lock"
    encrypt        = true
  }
}
