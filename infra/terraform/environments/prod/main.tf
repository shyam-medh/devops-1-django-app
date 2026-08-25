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

resource "aws_iam_policy" "jenkins_eks_access" {
  name        = "jenkins-eks-access"
  description = "Allow Jenkins to access EKS cluster config"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "eks:DescribeCluster",
        ]
        Effect   = "Allow"
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_policy" "jenkins_cloudfront_invalidation" {
  name        = "jenkins-cloudfront-invalidation"
  description = "Allow Jenkins to invalidate CloudFront distributions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["cloudfront:CreateInvalidation"]
        Effect   = "Allow"
        Resource = "*"
      },
    ]
  })
}

module "jenkins_irsa" {
  source                        = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version                       = "~> 5.0"
  role_name                     = "jenkins-serverless-agent"
  attach_vpc_cni_policy         = false
  
  # Allow full ECR access to build and push images
  role_policy_arns = {
    AmazonEC2ContainerRegistryPowerUser = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
    AmazonS3FullAccess                  = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
    JenkinsEKSAccess                    = aws_iam_policy.jenkins_eks_access.arn
    JenkinsCloudfrontInvalidation       = aws_iam_policy.jenkins_cloudfront_invalidation.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["jenkins:default", "jenkins:jenkins"]
    }
  }
}

resource "aws_eks_access_entry" "jenkins_access" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.jenkins_irsa.iam_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "jenkins_admin" {
  cluster_name  = module.eks.cluster_name
  principal_arn = module.jenkins_irsa.iam_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope {
    type = "cluster"
  }
}

resource "aws_iam_role_policy_attachment" "fargate_logging" {
  role       = module.eks.fargate_profiles["app_profile"].iam_role_name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}