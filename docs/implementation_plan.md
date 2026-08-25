# V2 — Master Implementation Checklist

This is the definitive, ordered roadmap for the V2 EKS upgrade. Follow steps strictly in order. **Do not jump ahead.**

---

## Stage 1: Clean Up Django & React ✅

- [x] Keep `v1-docker-compose` branch untouched as the working reference.
- [x] Create and work exclusively on the `feature/eks-fargate-upgrade` branch.
- [x] Remove all hardcoded database config from Django `settings.py`. Replace with environment variables:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- [x] Configure Django for production:
  - `DEBUG=False`
  - `ALLOWED_HOSTS` from environment variable
  - CORS configured properly
  - CSRF configured properly
- [x] Change the React frontend so the Django API URL is configurable via an environment variable instead of hardcoded `/api/...`.
- [x] Test the application locally one final time. Confirm React → Django communication still works.

---

## Stage 2: Terraform State Bootstrap ✅

- [x] Create an S3 bucket for Terraform remote state.
- [x] Configure DynamoDB table for state locking.
- [x] Configure the production Terraform environment to use that remote state backend.
- [x] Run `terraform init`, `terraform validate`, and `terraform plan`. Ensure clean output before touching AWS.

---

## Stage 3: VPC (Completed)

- [x] Create the VPC using Terraform.
- [x] Create multiple Availability Zones with public and private subnets.
- [x] Place internet-facing resources in public subnets, application and database resources in private subnets.
- [x] Create Internet Gateway, NAT Gateway, route tables, and security groups.

---

## Stage 4: ECR

- [x] Create the ECR repository for the Django backend using Terraform.
- [x] Build the Django Docker image locally and verify it runs correctly.
- [x] Push that image manually to ECR and confirm it exists there.

---

## Stage 5: RDS (Provisioning)

- [x] Create the RDS MySQL database using Terraform in private subnets.
- [x] Create a dedicated application database user (not `root`).
- [x] Configure the RDS security group so only the application layer (Django) can connect on port `3306`.

---

## Stage 6: EKS Cluster ✅

- [x] Create the EKS cluster using Terraform.
- [x] Update Kubernetes version to a currently supported version (not `1.30`).
- [x] Make the Kubernetes version configurable through a Terraform variable.
- [x] Use **AWS Fargate** as the compute model (no EC2 nodes to manage, fully serverless).
- [x] Create a **Fargate Profile** that targets the correct namespaces (e.g., `default`, `kube-system`, `django`).
- [x] Create the required IAM roles and permissions for EKS and the Fargate execution role.
- [x] Apply Terraform and verify the EKS cluster is created successfully.
- [x] Connect local `kubectl` to the EKS cluster using the AWS CLI.
- [x] Run `kubectl get svc` and confirm cluster API is visible.

> ⚠️ **Fargate Constraints to Remember:**
> - No `DaemonSets` — tools like Fluentd must use a sidecar container pattern instead.
> - No privileged containers — standard Django/Nginx containers are fine.
> - No persistent volumes using `hostPath` — use AWS EFS or EBS CSI driver instead.
> - Fargate Pods are always placed in **private subnets only**.

---

## Stage 7: EKS Deployment (Backend) [COMPLETED]

- [x] Configure Helm chart for Django (`infra/k8s/django-backend`)
- [x] Inject RDS endpoint, credentials, and Django `SECRET_KEY` as Secrets/Environment variables via `values.yaml`
- [x] Deploy Django to EKS Fargate using Helm (`helm install`)
- [x] Run Django database migrations on EKS (`kubectl exec ... python manage.py migrate`)
- [x] Create a Django superuser for testing (`kubectl exec ... python manage.py createsuperuser`)
- [x] Test full CRUD (create, read, update, delete) through Django.
- [x] ✅ Confirm this path works: `Internet → EKS → Django → RDS`

---

## Stage 8: AWS Load Balancer Controller & ALB ✅

- [x] Install the AWS Load Balancer Controller into EKS.
- [x] Grant the Load Balancer Controller the required AWS IAM permissions.
- [x] Verify the controller is running correctly inside the cluster.
- [x] Create a Kubernetes Ingress for Django.
- [x] Configure the Ingress to create an internet-facing ALB.
- [x] Verify the ALB is created in AWS.
- [x] ✅ Confirm this path works: `Internet -> ALB -> Django Service -> Django Pods -> RDS`

> **Do not move to frontend until this backend flow is fully working.**

---

## Stage 9: Secrets Management (Post-Helm)

- [x] Move database credentials out of plain YAML into **AWS Secrets Manager**.
- [x] Integrate Secrets Manager with Kubernetes so Django receives credentials securely.

---

## Stage 10: React Frontend (S3 + CloudFront) ✅

- [x] Build the React application using the production API URL.
- [x] Create the S3 bucket for the React frontend using Terraform.
- [x] Upload the React build files to S3.
- [x] Create the CloudFront distribution using Terraform, pointing at the S3 bucket.
- [x] Configure HTTPS and caching behaviour. Ensure S3 is not exposed directly to the internet.

---

## Stage 11: Route53 & DNS

- [x] Create Route53 records (Bypassed - No Domain Name):
  - `notes.example.com` → CloudFront (frontend)
  - `api.example.com` → ALB (backend)
- [x] Configure React to use `https://api.example.com` as its API endpoint (Bypassed - Using dynamic AWS ALB URL instead).
- [x] Test the complete application from the browser.
- [x] ✅ Confirm this full path works:
  ```
  User → CloudFront URL → S3 → React
                                              ↓
                                        AWS ALB URL → ALB → EKS → Django → RDS
  ```
- [x] Test every CRUD operation from the frontend.

---

## Stage 12: Reliability (HPA & Resilience Testing)

- [x] Delete one Django Pod manually and confirm Kubernetes recreates it.
- [x] Run multiple replicas and confirm traffic continues when one Pod goes down.
- [x] Add HPA (Horizontal Pod Autoscaler) after the basic deployment is stable.
- [x] Configure HPA to scale Django replicas based on CPU/memory usage.

---

## Stage 13: Jenkins CI/CD Pipeline

- [x] Provision the Jenkins Master on an EC2 instance using Terraform.
- [x] Make Jenkins run backend tests.
- [x] Make Jenkins run frontend tests.
- [x] Make Jenkins build the React application.
- [x] Make Jenkins build the Django Docker image.
- [x] Tag the Docker image with the Git commit SHA (not `latest`).
- [x] Make Jenkins push the versioned image to ECR.
- [x] Make Jenkins deploy the new image to EKS using Helm.
- [x] Make Jenkins upload the React build to S3.
- [x] Make Jenkins invalidate CloudFront after a frontend deployment.
- [x] Make Jenkins wait for the Kubernetes rollout to complete.
- [x] Make Jenkins run a health/smoke test after deployment.
- [x] Fail the pipeline automatically if the new deployment is unhealthy.
- [x] Add Helm rollback logic so a failed deployment returns to the previous working version.
- [x] Fix the `Jenkinsfile` so region and EKS cluster name match actual Terraform outputs.
- [x] Remove duplicated infrastructure values. Terraform is the single source of truth.

---

## Stage 14: DevSecOps

- [x] Add **GitLeaks** to detect hardcoded secrets.
- [x] Add **Bandit** to SAST-scan the Python/Django code.
- [x] Add **Checkov** to scan Terraform infrastructure code.
- [x] Add **Trivy** to scan the Django container image.
- [x] Configure Jenkins to fail the pipeline on serious security findings.

---

## Stage 15: Observability

- [ ] Add **Prometheus** to the cluster.
- [ ] Add **Grafana** dashboards to monitor:
  - Django Pods, CPU, memory, request rate, errors, latency, replica count.
- [ ] Add **CloudWatch** monitoring for AWS infrastructure.
- [ ] Add centralized logging after basic Kubernetes logging is working.

---

## Stage 16: Advanced Security & AI Self-Healing

> ⚠️ Only implement these after all previous stages are fully stable.

- [ ] Add advanced Kubernetes security (network policies, Pod security).
- [ ] Add **Falco** runtime security to detect malicious activity inside Pods.
- [ ] Add **Robusta AI** for automated Kubernetes incident analysis (OpenAI API integration).
- [ ] Add **OWASP ZAP** for post-deployment dynamic security testing (DAST).
- [ ] Add Jenkins pipeline auto-rollback triggered by OWASP ZAP findings.
- [ ] Add **AWS WAF** to the ALB to block SQL injection, XSS, and DDoS.
- [ ] Generate **SBOM** (Software Bill of Materials) for compliance tracking.
- [ ] Implement AI-assisted pipeline failure analysis using the OpenAI API.

---

## The Order to Follow

```
V1 (stable, tagged)
 ↓
Clean Django + React ✅
 ↓
Terraform State ✅
 ↓
VPC ✅ → ECR ✅ → EKS ✅ → RDS (Provisioning)
 ↓
Django on EKS (Helm Deployment)
 ↓
Django → RDS
 ↓
AWS Load Balancer Controller
 ↓
ALB → Django
 ↓
S3 → CloudFront → Route53
 ↓
Full application test
 ↓
HPA
 ↓
Jenkins CI/CD
 ↓
Rollback
 ↓
DevSecOps
 ↓
Prometheus + Grafana + CloudWatch
 ↓
Advanced Security
 ↓
Self-Healing / AI
```
