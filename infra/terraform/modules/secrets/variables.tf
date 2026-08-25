variable "cluster_name" {
  description = "The name of the EKS cluster"
  type        = string
}

variable "db_password" {
  description = "The password for the RDS database"
  type        = string
}

variable "oidc_provider_arn" {
  description = "The ARN of the OIDC Provider for EKS IRSA"
  type        = string
}
