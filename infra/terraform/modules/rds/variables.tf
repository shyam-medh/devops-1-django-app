variable "cluster_name" { type = string }
variable "vpc_id" { type = string }
variable "vpc_cidr_block" { type = string }
variable "db_password" { 
  type = string 
  sensitive = true
}
variable "database_subnet_group_name" { type = string }
variable "private_subnets" { type = list(string) }
