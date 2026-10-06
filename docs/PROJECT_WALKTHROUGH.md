# 🚀 Django Notes App — DevOps Project Walkthrough

## ✅ Project Complete!

A full production-grade DevOps pipeline for a Django + React notes application, running on AWS EKS with GitOps CI/CD, monitoring, and an AI-powered self-healing agent.

---

## 🏗️ Architecture Overview

```
Developer (Git Push)
        ↓
Jenkins CI/CD (EKS Fargate)
   ├── Kaniko → ECR (Docker Registry)
   ├── Helm → EKS Fargate (Django Backend)
   └── aws s3 sync → S3 (React Frontend)
        ↓
AWS EKS Fargate
   ├── Django Backend (ALB Ingress)
   └── RDS MySQL (Private)
        ↓
Robusta AI-SRE Agent (watches EKS)
   └── Gemini AI (diagnose + heal)
        ↓
Prometheus + Grafana (Observability)
```

---

## 🌐 Live URLs

| Service | URL |
|---|---|
| **React Frontend** | `http://django-notes-app-react-frontend-prod.s3-website.ap-south-1.amazonaws.com` |
| **Django Backend API** | `http://k8s-django-djangoba-e112d234ba-2069131524.ap-south-1.elb.amazonaws.com` |
| **Jenkins CI/CD** | `http://k8s-jenkins-jenkinsi-9efad8b017-804706565.ap-south-1.elb.amazonaws.com` |
| **Grafana** | `http://k8s-monitori-kubeprom-a9b6b602b6-1926179739.ap-south-1.elb.amazonaws.com` |
| **Prometheus** | `http://k8s-monitori-kubeprom-ebfad42a68-1753043819.ap-south-1.elb.amazonaws.com` |

---

## 🧩 Components Built

### 1. Infrastructure (Terraform)
- **VPC** — public/private subnets across 2 AZs
- **EKS Cluster** — fully serverless on AWS Fargate (no EC2 nodes)
- **RDS MySQL** — private subnets, security group locked to EKS only
- **S3 Bucket** — React static website hosting
- **ECR** — Docker image registry with layer caching
- **EFS** — Persistent storage for Jenkins
- **IAM/IRSA** — Pod-level AWS permissions, zero hardcoded credentials
- **External Secrets Operator** — AWS Secrets Manager → Kubernetes Secrets
- **AWS Load Balancer Controller** — Automatic ALB provisioning from Ingress

### 2. CI/CD Pipeline (Jenkins — 9 Stages)

| Stage | What it does |
|---|---|
| **1. SAST** | Bandit security scan on Python code |
| **2. Backend Tests** | Django unit tests |
| **3. Build & Push** | Kaniko builds Docker image → ECR with layer cache |
| **4. Deploy Backend** | Helm upgrade → EKS with auto-rollback on failure |
| **5. Fetch ALB DNS** | Waits for ALB, captures backend URL dynamically |
| **6. Build React** | `npm build` with `REACT_APP_API_URL` injected |
| **7. Deploy Frontend** | `aws s3 sync` with correct cache-control headers |
| **8. CloudFront** | *(Ready — pending AWS account verification)* |
| **9. Smoke Test** | curl verifies backend is reachable |

### 3. AI-SRE Agent (Robusta + Gemini AI)

**How it works:**
```
Failure Detected (CrashLoop / OOMKilled / Job Fail / Alert)
      ↓
Phase 1 → Gemini reads logs, events, describe output → diagnoses root cause
      ↓
Phase 2 → Gemini requests targeted extra data (memory limits, ECR tags, DB connectivity)
      ↓
Gemini generates EXACT fix (kubectl patch, not just a restart)
      ↓
Safe fixes   → Auto-executed (rollout restart, scale)
Risky fixes  → Surfaced to human with copy-paste commands
```

**Triggers:**
- `on_pod_crash_loop` → `ai_sre_pod_failure`
- `on_pod_oom_killed` → `ai_sre_pod_failure`
- `on_job_failure` → `ai_sre_job_failure`
- `on_prometheus_alert` → `ai_sre_prometheus_alert`

### 4. Security
- ✅ Zero hardcoded credentials
- ✅ IRSA — pods get AWS permissions via service account (no access keys)
- ✅ External Secrets — DB password lives in AWS Secrets Manager
- ✅ Private RDS — not internet-accessible
- ✅ SAST scanning (Bandit) in every Jenkins build
- ✅ Kaniko — Docker builds without privileged Docker socket

---

## 📁 Project Structure

```
django-notes-app/
├── backend/              # Django REST API
├── frontend/             # React app
├── docs/                 # Project documentation
├── Jenkinsfile           # 9-stage CI/CD pipeline
└── infra/
    ├── terraform/
    │   ├── environments/prod/   # Root module (apply here)
    │   └── modules/             # vpc, eks, rds, ecr, s3_frontend, efs, secrets
    ├── helm/
    │   ├── django-backend/      # Helm chart for the backend
    │   └── robusta-values.yaml  # AI-SRE configuration
    └── kubernetes/
        └── ai-sre-agent/
            └── action-configmap.yaml  # Gemini healing actions
```

---

## ⏳ One Remaining Item

| Item | Status | Action |
|---|---|---|
| **CloudFront CDN** | Code written & ready | Contact AWS Support → verify account → `terraform apply` |

---

## 🧪 Test the AI-SRE Agent

```bash
# Deploy a pod that will fail (ImagePullBackOff)
kubectl run bad-pod --image=nonexistent-image:fake-tag -n django

# Watch the AI agent detect and diagnose it
kubectl logs -n robusta deployment/robusta-runner -f

# Clean up
kubectl delete pod bad-pod -n django
```

---

## 🔐 Default Credentials

**Grafana:** `admin` / `prom-operator`

**Jenkins password:**
```bash
kubectl exec -n jenkins jenkins-0 -- cat /run/secrets/additional/chart-admin-password
```

---

*Stack: AWS EKS • Fargate • RDS MySQL • S3 • ECR • EFS • Terraform • Helm • Jenkins • Kaniko • Robusta • Gemini AI • Prometheus • Grafana • External Secrets • AWS Load Balancer Controller*
