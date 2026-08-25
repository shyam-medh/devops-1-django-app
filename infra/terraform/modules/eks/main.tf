module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access = true

  vpc_id                   = var.vpc_id
  subnet_ids               = var.private_subnets
  control_plane_subnet_ids = var.private_subnets

  # Fargate profiles
  fargate_profiles = {
    app_profile = {
      name = "django-app"
      selectors = [
        {
          namespace = "django"
        },
        {
          namespace = "kube-system"
        },
        {
          namespace = "external-secrets"
        },
        {
          namespace = "jenkins"
        },
        {
          namespace = "monitoring"
        }
      ]
    }
    tools_profile = {
      name = "tools-profile"
      selectors = [
        {
          namespace = "robusta"
        }
      ]
    }
  }

  enable_cluster_creator_admin_permissions = true
}
