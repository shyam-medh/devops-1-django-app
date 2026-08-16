module "vpc" {
  source       = "../../modules/vpc"
  cluster_name = var.cluster_name
  vpc_cidr     = "10.0.0.0/16"
}

module "eks" {
  source          = "../../modules/eks"
  cluster_name    = var.cluster_name
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnets
}

module "rds" {
  source                     = "../../modules/rds"
  cluster_name               = var.cluster_name
  vpc_id                     = module.vpc.vpc_id
  vpc_cidr_block             = module.vpc.vpc_cidr_block
  database_subnet_group_name = module.vpc.database_subnet_group_name
  private_subnets            = module.vpc.private_subnets
  db_password                = var.db_password
}

module "ecr" {
  source = "../../modules/ecr"
}
