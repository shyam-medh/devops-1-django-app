module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access = true

  vpc_id                   = var.vpc_id
  subnet_ids               = var.private_subnets
  control_plane_subnet_ids = var.private_subnets

  # Fargate profiles — kube-system is included so CoreDNS runs on Fargate
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

# ---------------------------------------------------------------------------
# CoreDNS Fargate patch — runs automatically after cluster creation.
# By default, AWS EKS configures CoreDNS with an EC2 node-selector annotation
# that prevents it from scheduling on Fargate. This resource:
#   1. Updates kubeconfig for the new cluster.
#   2. Removes the EC2 compute-type annotation from the CoreDNS deployment.
#   3. Restarts CoreDNS so the pods reschedule on Fargate.
# Without this, all cluster pods stay in Pending state forever.
# ---------------------------------------------------------------------------
resource "null_resource" "patch_coredns_for_fargate" {
  depends_on = [module.eks]

  triggers = {
    cluster_name = module.eks.cluster_name
  }

  provisioner "local-exec" {
    interpreter = ["powershell", "-Command"]
    command     = <<-EOT
      # Update kubeconfig
      aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}

      # Remove the EC2 compute-type annotation so CoreDNS can schedule on Fargate
      kubectl patch deployment coredns `
        -n kube-system `
        --type json `
        -p '[{"op":"remove","path":"/spec/template/metadata/annotations/eks.amazonaws.com~1compute-type"}]'

      # Force a rolling restart so the patched pods get recreated on Fargate
      kubectl rollout restart deployment/coredns -n kube-system

      # Wait for CoreDNS to be fully ready before Terraform continues
      kubectl rollout status deployment/coredns -n kube-system --timeout=300s
    EOT
  }
}
