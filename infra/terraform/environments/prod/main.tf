module "vpc" {
  source       = "../../modules/vpc"
  cluster_name = var.cluster_name
  vpc_cidr     = "10.0.0.0/16"
}

module "eks" {
  source          = "../../modules/eks"
  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version
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
  allowed_security_group_id  = module.eks.cluster_primary_security_group_id
}

module "ecr" {
  source = "../../modules/ecr"
}

module "s3_frontend" {
  source      = "../../modules/s3_frontend"
  bucket_name = "django-notes-app-react-frontend"
  environment = "prod"
}

module "secrets" {
  source            = "../../modules/secrets"
  cluster_name      = var.cluster_name
  db_password       = var.db_password
  oidc_provider_arn = module.eks.oidc_provider_arn
}

module "efs" {
  source                     = "../../modules/efs"
  project_name               = "django-notes"
  environment                = "prod"
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnets
  allowed_security_group_ids = [module.eks.cluster_primary_security_group_id]
}