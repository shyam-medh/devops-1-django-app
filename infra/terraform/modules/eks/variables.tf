variable "cluster_name" { type = string }
variable "vpc_id" { type = string }
variable "private_subnets" { type = list(string) }
variable "cluster_version" {
  type        = string
  description = "Kubernetes version for EKS cluster"
  default     = "1.31"
}
variable "aws_region" {
  type        = string
  description = "AWS region — required for the CoreDNS Fargate patch provisioner"
  default     = "ap-south-1"
}
