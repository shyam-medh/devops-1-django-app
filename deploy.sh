#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Zero-touch deployment script for the Django Notes App on EKS
#
# Usage:
#   cd infra/terraform/environments/prod
#   bash ../../../../deploy.sh
#
# What this script does:
#   1. Reads dynamic Terraform outputs (RDS host, CloudFront URL) after apply.
#   2. Deploys all Helm charts in the correct dependency order.
#   3. Injects the dynamic RDS host and CloudFront URL into the Django chart
#      so no values.yaml ever needs to be edited manually.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="${SCRIPT_DIR}/infra"
TERRAFORM_DIR="${INFRA_DIR}/terraform/environments/prod"
HELM_DIR="${INFRA_DIR}/helm"
AWS_REGION="ap-south-1"
CLUSTER_NAME="django-notes-eks-prod"

echo "======================================================"
echo "  Django Notes App — Full Deployment"
echo "======================================================"

# ------------------------------------------------------------------------------
# Step 1: Update kubeconfig
# ------------------------------------------------------------------------------
echo ""
echo "[1/7] Updating kubeconfig..."
aws eks update-kubeconfig --region "${AWS_REGION}" --name "${CLUSTER_NAME}"

# ------------------------------------------------------------------------------
# Step 2: Read dynamic Terraform outputs
# ------------------------------------------------------------------------------
echo ""
echo "[2/7] Reading Terraform outputs..."
cd "${TERRAFORM_DIR}"

RDS_HOST=$(terraform output -raw rds_host)
# CLOUDFRONT_URL="https://$(terraform output -raw cloudfront_domain_url)"
CLOUDFRONT_URL="http://localhost" # Fallback while CloudFront is disabled
EXTERNAL_SECRETS_ROLE_ARN=$(terraform output -raw external_secrets_role_arn)
# S3_BUCKET=$(terraform output -raw frontend_s3_bucket)
S3_BUCKET="N/A"

echo "  RDS Host        : ${RDS_HOST}"
echo "  CloudFront URL  : ${CLOUDFRONT_URL}"
echo "  S3 Bucket       : ${S3_BUCKET}"

cd "${SCRIPT_DIR}"

# ------------------------------------------------------------------------------
# Step 3: Create Kubernetes namespaces
# ------------------------------------------------------------------------------
echo ""
echo "[3/7] Creating namespaces..."
for ns in django jenkins monitoring external-secrets robusta; do
  kubectl create namespace "${ns}" --dry-run=client -o yaml | kubectl apply -f -
done

# ------------------------------------------------------------------------------
# Step 4: Deploy External Secrets Operator
# ------------------------------------------------------------------------------
echo ""
echo "[4/7] Deploying External Secrets Operator..."
helm repo add external-secrets https://charts.external-secrets.io --force-update
helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="${EXTERNAL_SECRETS_ROLE_ARN}" \
  --wait --timeout 5m

# Apply the ClusterSecretStore and ExternalSecret manifests
kubectl apply -f "${INFRA_DIR}/kubernetes/external-secrets/" 2>/dev/null || true

# Wait for the DB secret to be synced before deploying Django
echo "  Waiting for django-backend-db-secret to be synced..."
kubectl wait --for=condition=Ready externalsecret django-backend-db-secret \
  -n django --timeout=120s 2>/dev/null || \
  echo "  WARNING: ExternalSecret not ready yet — continuing anyway."

# ------------------------------------------------------------------------------
# Step 5: Deploy Django backend with dynamic RDS host + CORS origins
# ------------------------------------------------------------------------------
echo ""
echo "[5/7] Deploying Django backend..."
helm upgrade --install django-backend "${HELM_DIR}/django-backend" \
  --namespace django \
  --set "env[0].value=${RDS_HOST}" \
  --set "env[9].value=${CLOUDFRONT_URL}" \
  --set "env[10].value=${CLOUDFRONT_URL}" \
  --wait --timeout 5m

# NOTE: Django DB migrations run automatically via the Helm post-install hook
# defined in templates/migrate-hook.yaml — no manual kubectl exec needed here.
echo "  Migrations will run automatically via Helm post-install hook."


# ------------------------------------------------------------------------------
# Step 6: Deploy Jenkins
# ------------------------------------------------------------------------------
echo ""
echo "[6/7] Deploying Jenkins..."
helm repo add jenkins https://charts.jenkins.io --force-update
helm upgrade --install jenkins jenkins/jenkins \
  --namespace jenkins \
  -f "${HELM_DIR}/jenkins/values.yaml" \
  --wait --timeout 10m

# Apply Jenkins ingress
kubectl apply -f "${HELM_DIR}/jenkins/jenkins-ingress.yaml"

# ------------------------------------------------------------------------------
# Step 7: Deploy Prometheus + Grafana monitoring stack
# ------------------------------------------------------------------------------
echo ""
echo "[7/7] Deploying Prometheus + Grafana..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  -f "${HELM_DIR}/prometheus/values.yaml" \
  --wait --timeout 10m

echo ""
echo "======================================================"
echo "  Deployment Complete!"
echo "======================================================"
echo ""
echo "  Frontend (CloudFront) : ${CLOUDFRONT_URL}"
echo "  Grafana               : Check monitoring namespace for ALB URL"
echo "  Jenkins               : Check jenkins namespace for ALB URL"
echo ""
echo "  Get all ingresses:"
echo "  kubectl get ingress -A"
echo ""
