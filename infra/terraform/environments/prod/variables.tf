variable "aws_region" {
  default = "ap-south-1"
}

variable "cluster_name" {
  default = "django-notes-eks-prod"
}

variable "cluster_version" {
  description = "Kubernetes version for EKS cluster"
  default     = "1.31"
}

variable "db_password" {
  sensitive = true
}
