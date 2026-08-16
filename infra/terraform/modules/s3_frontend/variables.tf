variable "bucket_name" {
  description = "The name of the S3 bucket to host the React frontend"
  type        = string
}

variable "environment" {
  description = "The deployment environment (e.g., prod, dev)"
  type        = string
  default     = "prod"
}
