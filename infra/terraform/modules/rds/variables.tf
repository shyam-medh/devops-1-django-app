variable "cluster_name" { type = string }
variable "vpc_id" { type = string }
variable "vpc_cidr_block" { type = string }
variable "database_subnet_group_name" { type = string }
variable "private_subnets" { type = list(string) }
variable "db_password" {
  type      = string
  sensitive = true
}

variable "allowed_security_group_id" {
  type        = string
  description = "The security group ID allowed to access the database"
}
