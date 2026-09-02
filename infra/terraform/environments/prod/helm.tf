# ------------------------------------------------------------------------------
# 1. Namespaces
# ------------------------------------------------------------------------------

resource "kubernetes_namespace" "django" {
  metadata {
    name = "django"
  }
}

resource "kubernetes_namespace" "jenkins" {
  metadata {
    name = "jenkins"
  }
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "kubernetes_namespace" "external_secrets" {
  metadata {
    name = "external-secrets"
  }
}

resource "kubernetes_namespace" "robusta" {
  metadata {
    name = "robusta"
  }
}

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  wait       = true

  set {
    name  = "clusterName"
    value = data.aws_eks_cluster.cluster.name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.albc_irsa.iam_role_arn
  }

  set {
    name  = "region"
    value = "ap-south-1"
  }

  set {
    name  = "vpcId"
    value = module.vpc.vpc_id
  }
}

# ------------------------------------------------------------------------------
# 2. Helm Releases
# ------------------------------------------------------------------------------

resource "helm_release" "external_secrets" {
  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  namespace  = kubernetes_namespace.external_secrets.metadata[0].name
  wait       = true

  set {
    name  = "installCRDs"
    value = "true"
  }

  set {
    name  = "webhook.create"
    value = "false"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.secrets.external_secrets_role_arn
  }
}

resource "kubernetes_storage_class" "efs_sc" {
  metadata {
    name = "efs-sc"
  }
  storage_provisioner = "efs.csi.aws.com"
}

resource "kubernetes_persistent_volume" "jenkins_efs_pv" {
  metadata {
    name = "efs-pv"
  }
  spec {
    capacity = {
      storage = "5Gi"
    }
    volume_mode = "Filesystem"
    access_modes = ["ReadWriteMany"]
    persistent_volume_reclaim_policy = "Retain"
    storage_class_name = kubernetes_storage_class.efs_sc.metadata[0].name
    persistent_volume_source {
      csi {
        driver = "efs.csi.aws.com"
        volume_handle = "${module.efs.file_system_id}::${module.efs.access_point_id}"
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim" "jenkins_efs_claim" {
  metadata {
    name      = "efs-claim"
    namespace = kubernetes_namespace.jenkins.metadata[0].name
  }
  spec {
    access_modes = ["ReadWriteMany"]
    storage_class_name = kubernetes_storage_class.efs_sc.metadata[0].name
    resources {
      requests = {
        storage = "5Gi"
      }
    }
    volume_name = kubernetes_persistent_volume.jenkins_efs_pv.metadata[0].name
  }
}

resource "helm_release" "jenkins" {
  name       = "jenkins"
  repository = "https://charts.jenkins.io"
  chart      = "jenkins"
  namespace  = kubernetes_namespace.jenkins.metadata[0].name
  wait       = true
  timeout    = 600

  values = [
    file("../../../helm/jenkins/values.yaml")
  ]

  depends_on = [kubernetes_persistent_volume_claim.jenkins_efs_claim]
}

resource "helm_release" "kube_prometheus_stack" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  wait       = true
  timeout    = 600

  values = [
    file("../../../helm/prometheus/values.yaml")
  ]
}

resource "helm_release" "django_backend" {
  name       = "django-backend"
  chart      = "../../../helm/django-backend"
  namespace  = kubernetes_namespace.django.metadata[0].name
  wait       = true
  timeout    = 300

  values = [
    yamlencode({
      env = [
        {
          name  = "DB_HOST"
          value = split(":", module.rds.db_instance_endpoint)[0]
        },
        {
          name  = "DB_PORT"
          value = "3306"
        },
        {
          name  = "DB_NAME"
          value = "notes_db"
        },
        {
          name  = "DB_USER"
          value = "notes_app"
        },
        {
          name = "DB_PASSWORD"
          valueFrom = {
            secretKeyRef = {
              name = "django-backend-db-secret"
              key  = "password"
            }
          }
        },
        {
          name  = "ALLOWED_HOSTS"
          value = "*"
        },
        {
          name  = "DEBUG"
          value = "False"
        },
        {
          name  = "CORS_ALLOW_ALL_ORIGINS"
          value = "False"
        },
        {
          name  = "CORS_ALLOWED_ORIGINS"
          value = "http://localhost"
        },
        {
          name  = "CSRF_TRUSTED_ORIGINS"
          value = "http://localhost"
        }
      ]
    })
  ]

  depends_on = [helm_release.external_secrets]
}

# ------------------------------------------------------------------------------
# 3. Raw Manifests (CRDs & Ingress) via null_resource
# ------------------------------------------------------------------------------

resource "null_resource" "apply_jenkins_ingress" {
  depends_on = [helm_release.jenkins]

  triggers = {
    hash = filemd5("../../../helm/jenkins/jenkins-ingress.yaml")
  }

  provisioner "local-exec" {
    command = <<EOT
aws eks update-kubeconfig --region ap-south-1 --name django-notes-eks-prod
kubectl apply -f ../../../helm/jenkins/jenkins-ingress.yaml
EOT
  }
}
