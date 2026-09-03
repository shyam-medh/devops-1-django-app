terraform {
  required_version = ">= 1.3.0"

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
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# The data sources below are commented out because they fail if the EKS cluster
# doesn't exist yet (chicken-and-egg problem when provisioning from scratch).
# Instead, the kubernetes and helm providers are configured using the exec plugin
# and the outputs directly from the EKS module.
#
# data "aws_eks_cluster" "cluster" {
#   name = module.eks.cluster_name
# }
# 
# data "aws_eks_cluster_auth" "cluster" {
#   name = module.eks.cluster_name
# }

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.aws_region]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.aws_region]
    }
  }
}
