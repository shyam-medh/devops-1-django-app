variable "aws_region" {
  default = "ap-south-1"
}

variable "cluster_name" {
  default = "django-notes-eks-prod"
}

variable "db_password" {
  sensitive = true
}
