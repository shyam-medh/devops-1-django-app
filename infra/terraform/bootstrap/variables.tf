variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name for state bucket"
  type        = string
  default     = "django-notes-app"
}
