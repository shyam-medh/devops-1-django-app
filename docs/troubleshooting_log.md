# Project Troubleshooting & Error Log

This document tracks the major errors and roadblocks encountered during the deployment of the Django + React application on AWS (EKS Fargate, RDS, S3, CloudFront), and how they were resolved.

---

## 1. AWS Load Balancer Controller: 403 AccessDenied

**Error:**
When the AWS Load Balancer Controller tried to provision the ALB for the Kubernetes Ingress, it failed with a `403 AccessDenied` error. Specifically, it lacked permission to perform `elasticloadbalancing:DescribeListenerAttributes`.

**Root Cause:**
The IAM policy downloaded for the controller (v2.4.0/v2.5.0) was outdated and did not include the newer `DescribeListenerAttributes` permission required by the latest controller version.

**Fix:**
We updated the IAM Policy document using the latest version from the AWS `main` branch, updated the IAM Policy in AWS, and restarted the controller pods. The ALB was then provisioned successfully.

---

## 2. CoreDNS Pods Stuck in `Pending` on Fargate

**Error:**
After creating the EKS cluster using only Fargate profiles, the `coredns` pods in the `kube-system` namespace were stuck in a `Pending` state forever.

**Root Cause:**
By default, AWS EKS configures the CoreDNS deployment with an annotation `eks.amazonaws.com/compute-type: ec2`, which forces it to look for EC2 worker nodes. Since we had a 100% serverless Fargate cluster, there were no EC2 nodes available.

**Fix:**
We patched the CoreDNS deployment to remove the `compute-type: ec2` annotation, allowing the Fargate scheduler to pick up the CoreDNS pods and run them.

```bash
kubectl patch deployment coredns -n kube-system --type json -p='[{"op": "remove", "path": "/spec/template/metadata/annotations/eks.amazonaws.com~1compute-type"}]'
```

---

## 3. Django Pods Unable to Connect to RDS Database

**Error:**
The Django pods were failing to start or failing health checks with a `Connection timed out` error when trying to reach the MySQL database on port `3306`.

**Root Cause:**
The RDS security group was not configured to accept incoming connections from the Fargate pods. Fargate pods use the EKS cluster's primary security group.

**Fix:**
We updated the Terraform `rds` module to add an ingress rule to the RDS security group, allowing TCP port 3306 traffic from the EKS Cluster's primary security group.

---

## 4. 500 Internal Server Error at ALB Root Path

**Error:**
Visiting the ALB DNS name returned a `500 Internal Server Error` at the root path (`/`). The logs showed a `TemplateDoesNotExist` error.

**Root Cause:**
The Django backend was strictly acting as an API server, but the `urls.py` was mapped to render a `TemplateView` for the root path. Since we didn't configure a template directory or have templates in the backend, Django crashed trying to render the HTML.

**Fix:**
We modified `backend/notesapp/urls.py` to replace the `TemplateView` with a simple health check API endpoint returning JSON (`{"status": "ok", "message": "Django Notes API is running"}`).

---

## 5. Missing Static Files (Django Admin Styling Broken)

**Error:**
When visiting the `/admin/` path, the page loaded without CSS or JavaScript, and the browser console showed `404 Not Found` for static assets.

**Root Cause:**
The Docker container was running Gunicorn (via WhiteNoise) to serve static files, but the `python manage.py collectstatic` command was never run, meaning the static files were never gathered into the `STATIC_ROOT` folder.

**Fix:**
We added `RUN python manage.py collectstatic --noinput` to the backend `Dockerfile` so that the static files are permanently baked into the image during the build phase.

---

## 6. Docker Desktop Daemon Unresponsive

**Error:**
Commands like `docker build` and `docker push` were hanging indefinitely because the local Docker Engine on the host machine became unresponsive.

**Root Cause:**
Local Docker Desktop resource constraints/glitch on Windows.

**Fix:**
Instead of restarting the Docker daemon, rebuilding the image, and pushing it to ECR to apply a hotfix, we directly injected the fixes into the running production pods. We used `kubectl exec` to overwrite the bad Python files, and then sent a `SIGHUP` signal to the Gunicorn master process via Python (`os.kill(1, signal.SIGHUP)`). This gracefully reloaded the web workers with the new code without downtime.

---

## 7. Missing Terraform Output for CloudFront

**Error:**
Running `terraform output -json cloudfront_domain_url` failed with `Output "cloudfront_domain_url" not found`.

**Root Cause:**
The CloudFront distribution takes ~5 minutes to provision. The `terraform apply` command was still running in the background, meaning the Terraform state file had not yet been updated with the final outputs.

**Fix:**
Instead of waiting for Terraform to finish and output the domain, we used the AWS CLI (`aws cloudfront list-distributions`) to fetch the domain name of the newly created distribution directly from AWS.

---

## 8. EKS Cluster Creation: Unsupported Kubernetes Version

**Error:**
During the initial `terraform apply` to create the EKS cluster, AWS returned an error stating that Kubernetes version 1.30 was not supported or invalid.

**Root Cause:**
AWS EKS sometimes lags behind the upstream Kubernetes releases, or specific regions (like Mumbai `ap-south-1`) do not immediately support the absolute latest version. Hardcoding 1.30 in the Terraform module caused the creation to fail.

**Fix:**
We parameterized the Kubernetes version in the Terraform module (`var.cluster_version`) and downgraded it to a stable, supported version for the region (e.g., 1.29 / 1.31).

---

## 9. IAM OIDC Provider Missing for Service Accounts

**Error:**
The AWS Load Balancer Controller pods were failing to assume their AWS IAM Role, resulting in permissions errors.

**Root Cause:**
EKS requires an IAM OIDC (OpenID Connect) provider to allow Kubernetes Service Accounts (IRSA) to assume AWS IAM Roles. Without the OIDC provider provisioned in Terraform, the `aws-load-balancer-controller` service account had no way to authenticate to AWS.

**Fix:**
We updated the EKS Terraform module to explicitly create the IAM OIDC provider (`enable_irsa = true` / provisioning the `aws_iam_openid_connect_provider`), which linked the Kubernetes RBAC to AWS IAM securely.

---

## 10. EKS Fargate Profile Subnet Restrictions

**Error:**
When configuring the Fargate Profile, we initially faced issues or warnings regarding the subnets provided.

**Root Cause:**
AWS Fargate does not allow pods to be scheduled in public subnets (subnets that route directly to an Internet Gateway). Fargate pods *must* run in private subnets with a NAT Gateway.

**Fix:**
We ensured that the `private_subnets` output from the VPC module was explicitly passed to the EKS Fargate Profile configuration, and verified the NAT Gateway was correctly routing their outbound traffic.

---

## 11. External Secrets Operator Pods Pending (Missing Fargate Profile)

**Error:**
After installing External Secrets Operator (ESO) via Helm into the `external-secrets` namespace, all three pods (`external-secrets`, `cert-controller`, `webhook`) stayed in `Pending` state indefinitely.
Pod events:
```
Warning  FailedScheduling  0/6 nodes are available: 6 node(s) had untolerated taint {eks.amazonaws.com/compute-type: fargate}
```

**Root Cause:**
EKS Fargate requires a **Fargate Profile** for each namespace where you want to run pods. Without a matching profile, no Fargate node is provisioned and pods remain unscheduled.

**Fix:**
Added `external-secrets` to the selectors list in the Fargate profile inside `infra/terraform/modules/eks/main.tf`, then ran `terraform apply` to create the profile.

---

## 12. External Secrets Webhook Validation TLS Error on Fargate

**Error:**
Helm upgrades or `ExternalSecret` creation failed with `x509: certificate is valid for ip-..., not external-secrets-webhook.external-secrets.svc`.

**Root Cause:**
On EKS Fargate, the Fargate nodes do not use standard networking for the pod IP SANs in the TLS cert generated by the ESO cert-controller, causing the API server to reject the webhook validation.

**Fix:**
Disabled the webhook in the `external-secrets` Helm chart (`--set webhook.create=false`). This allows External Secrets to function correctly on Fargate without cert mismatches.

---

## 13. Jenkins on EKS Fargate: `Permission Denied` on EFS Persistent Volume

**Error:**
Jenkins controller pod repeatedly crashed on startup or failed to initialize `/var/jenkins_home` with `touch: cannot touch '/var/jenkins_home/copy_reference_file.log': Permission denied`.

**Root Cause:**
- AWS Fargate runs containers as non-root and disallows running privileged init containers or `chown` operations on NFS volumes.
- The standard AWS EFS root filesystem is owned by `root:root` (UID 0), while Jenkins runs as UID `1000`.

**Fix:**
1. Provisioned an **AWS EFS Access Point** (`aws_efs_access_point`) in Terraform with POSIX User UID/GID `1000` and creation directory permissions `0755` owned by `1000:1000`.
2. Updated the Kubernetes Persistent Volume (`jenkins-pv.yaml`) to reference the Access Point via `volumeHandle: <fs_id>::<access_point_id>`.

---

## 14. Observability on Fargate: Prometheus `node-exporter` DaemonSet Failure

**Error:**
When installing `kube-prometheus-stack` via Helm, the `prometheus-node-exporter` pods failed to schedule and threw errors.

**Root Cause:**
`node-exporter` is deployed as a Kubernetes `DaemonSet` to collect hardware metrics from physical host nodes. AWS Fargate is a serverless compute platform and explicitly does not support DaemonSets.

**Fix:**
Disabled `nodeExporter` and `prometheus-node-exporter` in `infra/k8s/prometheus-values.yaml`:
```yaml
nodeExporter:
  enabled: false
prometheus-node-exporter:
  enabled: false
```

---

## 15. Monitoring Pods Stuck in `Pending` (Missing Fargate Profile)

**Error:**
After deploying `kube-prometheus-stack` to the `monitoring` namespace, all monitoring pods (Prometheus Operator, Alertmanager, Grafana) remained in `Pending` state.

**Root Cause:**
The EKS Fargate Profile did not have a selector for the `monitoring` namespace.

**Fix:**
Added `{ namespace = "monitoring" }` to `fargate_profiles` in `infra/terraform/modules/eks/main.tf` and ran `terraform apply`.

---

## 16. Grafana 503 Service Temporarily Unavailable / OOMKilled (Exit Code 137)

**Error:**
Accessing Grafana through the ALB URL returned `503 Service Temporarily Unavailable`. Checking `kubectl describe pod` revealed Grafana crashed with `Exit Code 137` and failed both Liveness and Readiness probes (`connection refused` on port 3000).

**Root Cause:**
- On EKS Fargate, if no CPU/memory requests are specified in the pod spec, Fargate provisions the smallest instance size: **0.25 vCPU and 512MB RAM**.
- Grafana (v13.x) requires ~1GB memory during initialization and API registration. The container hit memory limits and was killed (`OOMKilled`) before it could start listening on port 3000.

**Fix:**
Configured explicit resource requests in `infra/k8s/prometheus-values.yaml`:
```yaml
grafana:
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 1000m
      memory: 2Gi
```
Fargate then provisioned a 1 vCPU / 2GB RAM container, allowing Grafana to start cleanly with HTTP 200 response on ALB.

---

## 17. Jenkins Helm Plugin Dependency Auto-Resolution

**Error:**
Jenkins failed to install required plugins on initialization due to version incompatibility with the latest Jenkins base LTS image.

**Root Cause:**
Pinning plugin versions manually in values caused conflicts when child dependencies required newer versions.

**Fix:**
Specified only plugin artifact names (`kubernetes`, `workflow-aggregator`, `git`, `configuration-as-code`) in `jenkins-values.yaml`, allowing Jenkins to auto-resolve compatible versions at startup.

---

## 18. AWS Ingress & ALB Cleanup Before Infrastructure Teardown

**Error:**
Running `terraform destroy` directly can stall or fail to delete the VPC and Subnets because the ALBs provisioned dynamically by the AWS Load Balancer Controller remain bound to the subnets.

**Fix / SOP:**
Always delete Kubernetes Ingress resources across all namespaces before running `terraform destroy`:
```bash
kubectl delete ingress --all --all-namespaces
```
This signals the AWS Load Balancer Controller to delete the ALBs and Target Groups first, ensuring a clean and error-free Terraform teardown.

---

## 19. V2 Architecture: Decoupling React & Dynamic ALB Routing (No-Domain)

**Error / Challenge:**
When decoupling the React frontend (to S3/CloudFront) from the Django backend (EKS Fargate), we faced a routing challenge because no custom domain name was available. The AWS Application Load Balancer (ALB) URL is generated dynamically *after* the Kubernetes Ingress is provisioned, meaning the React app couldn't be built with a hardcoded backend API URL beforehand.

**Root Cause:**
Without a stable custom domain name (e.g., `api.example.com`) mapped to the ALB in Route53, the backend endpoint is strictly ephemeral until the ALB is fully created by the AWS Load Balancer Controller. 

**Fix:**
We restructured the Jenkins CI/CD pipeline to deploy the backend first. We added a pipeline stage that uses `kubectl get ingress` to fetch the dynamically generated AWS ALB DNS name from the cluster. This URL is then injected as the `REACT_APP_API_URL` environment variable into the subsequent React build step, before uploading the compiled static assets to the S3 bucket. Additionally, we removed the hardcoded host from the Helm `values.yaml` Ingress configuration, allowing the ALB to act as a "catch-all" route.