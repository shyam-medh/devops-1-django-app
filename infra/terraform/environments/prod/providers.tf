terraform {
  required_version = ">= 1.3.0"

  # Run the code in `infra/terraform/bootstrap` first to generate your unique bucket name,
  # then replace `YOUR_UNIQUE_BUCKET_NAME_HERE` below with the output.
  backend "s3" {
    bucket         = "django-notes-app-terraform-state-faf36919"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "django-notes-app-terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
