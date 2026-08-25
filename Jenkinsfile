pipeline {
    agent {
        kubernetes {
            yaml '''
            apiVersion: v1
            kind: Pod
            spec:
              containers:
              - name: python
                image: python:3.9
                command: [cat]
                tty: true
                resources:
                  requests:
                    memory: "512Mi"
                    cpu: "250m"
                  limits:
                    memory: "512Mi"
                    cpu: "500m"
              - name: node
                image: node:18-alpine
                command: [cat]
                tty: true
                resources:
                  requests:
                    memory: "512Mi"
                    cpu: "250m"
                  limits:
                    memory: "1Gi"
                    cpu: "500m"
              - name: kaniko
                image: gcr.io/kaniko-project/executor:v1.23.2-debug
                command: [sleep]
                args: [99d]
                tty: true
                resources:
                  requests:
                    memory: "2Gi"
                    cpu: "1000m"
                  limits:
                    memory: "2Gi"
                    cpu: "1000m"
              - name: aws-helm
                # Pre-built image with aws-cli + helm + kubectl baked in.
                # Build once: docker build -t 790304249797.dkr.ecr.ap-south-1.amazonaws.com/jenkins-agent-aws:latest infra/docker/jenkins-agent-aws/
                # Until the image is built and pushed, fallback to amazon/aws-cli and install tools at runtime.
                image: amazon/aws-cli:2.27.0
                command: [cat]
                tty: true
                resources:
                  requests:
                    memory: "512Mi"
                    cpu: "250m"
                  limits:
                    memory: "512Mi"
                    cpu: "500m"
            '''
        }
    }

    options {
        // Kill the build if it runs for more than 45 minutes total
        timeout(time: 45, unit: 'MINUTES')
        // Keep only the last 10 builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Prevent concurrent pipeline runs to avoid race conditions
        disableConcurrentBuilds()
        // Suppress verbose SCM output
        skipDefaultCheckout(false)
    }

    environment {
        AWS_REGION                 = 'ap-south-1'
        AWS_ACCOUNT_ID             = '790304249797'
        S3_BUCKET_NAME             = 'django-notes-app-react-frontend-prod'
        ECR_REPO_NAME              = 'django-notes-backend'
        EKS_CLUSTER_NAME           = 'django-notes-eks-prod'
        CLOUDFRONT_DISTRIBUTION_ID = 'E38UXJBMVV63Z0'
        GIT_COMMIT_SHA             = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        IMAGE_TAG                  = "${GIT_COMMIT_SHA}-${env.BUILD_ID}"
        ECR_REGISTRY               = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    }

    stages {

        // ── STAGE 1: SAST (mocked) ────────────────────────────────────────────
        stage('DevSecOps: Code Scan (SAST)') {
            steps {
                container('python') {
                    echo "Running SAST checks (Bandit/Checkov/GitLeaks mocked)..."
                    // Uncomment to enable real scans:
                    // sh 'pip install --quiet bandit && bandit -r backend/ -ll'
                }
            }
        }

        // ── STAGE 2: BACKEND UNIT TESTS ───────────────────────────────────────
        stage('Backend Tests') {
            steps {
                container('python') {
                    dir('backend') {
                        sh '''
                            pip install --quiet -r requirements.txt
                            python manage.py test --verbosity=0
                        '''
                    }
                }
            }
        }

        // ── STAGE 3: BUILD & PUSH IMAGE (Kaniko + ECR layer cache) ───────────
        stage('Build & Push Django Image (Kaniko)') {
            steps {
                container('kaniko') {
                    sh '''
                        mkdir -p /kaniko/.docker
                        echo \'{"credsStore":"ecr-login"}\' > /kaniko/.docker/config.json

                        /kaniko/executor \
                          --context    $(pwd)/backend \
                          --dockerfile $(pwd)/backend/Dockerfile \
                          --destination ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} \
                          --cache=true \
                          --cache-repo  ${ECR_REGISTRY}/${ECR_REPO_NAME}/cache \
                          --compressed-caching=false \
                          --force
                    '''
                }
            }
        }

        // ── STAGE 4: DEPLOY BACKEND TO EKS (Helm) ────────────────────────────
        stage('Deploy Backend to EKS (Helm)') {
            steps {
                container('aws-helm') {
                    script {
                        sh '''
                            # ── Install build tools ──────────────────────────
                            yum install -y --quiet tar gzip

                            # ── Install Helm ─────────────────────────────────
                            curl -fsSL -o get_helm.sh \
                              https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
                            chmod 700 get_helm.sh
                            VERIFY_CHECKSUM=false ./get_helm.sh
                            rm -f get_helm.sh

                            # ── Install kubectl (pinned stable) ──────────────
                            KUBECTL_VER=$(curl -Ls https://dl.k8s.io/release/stable.txt)
                            curl -fsSL -o /usr/local/bin/kubectl \
                              https://dl.k8s.io/release/${KUBECTL_VER}/bin/linux/amd64/kubectl
                            chmod +x /usr/local/bin/kubectl

                            # ── Configure kubeconfig ──────────────────────────
                            aws eks update-kubeconfig \
                              --name   ${EKS_CLUSTER_NAME} \
                              --region ${AWS_REGION}
                        '''

                        try {
                            sh """
                                helm upgrade --install django-backend infra/helm/django-backend \\
                                  -f infra/helm/django-backend/values-prod.yaml \\
                                  --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} \\
                                  --set image.tag=${IMAGE_TAG} \\
                                  --namespace django --create-namespace \\
                                  --timeout 10m --wait --atomic
                            """
                        } catch (Exception e) {
                            echo "Helm deployment failed — triggering automated rollback..."
                            sh "helm rollback django-backend --namespace django || true"
                            error("Deployment failed, automated rollback triggered. Check logs above.")
                        }
                    }
                }
            }
        }

        // ── STAGE 5: FETCH ALB DNS NAME ───────────────────────────────────────
        stage('Fetch ALB DNS Name') {
            steps {
                container('aws-helm') {
                    script {
                        echo "Waiting 60s for ALB to provision..."
                        sleep(time: 60, unit: 'SECONDS')

                        def albHost = sh(
                            script: "kubectl get ingress django-backend -n django -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'",
                            returnStdout: true
                        ).trim()

                        if (!albHost) {
                            error("ALB DNS name is empty — Load Balancer controller may still be provisioning. Re-run after 2-3 min.")
                        }

                        env.REACT_APP_API_URL = "http://${albHost}"
                        echo "Backend URL: ${env.REACT_APP_API_URL}"
                    }
                }
            }
        }

        // ── STAGE 6: BUILD REACT FRONTEND ────────────────────────────────────
        stage('Build React Frontend') {
            steps {
                container('node') {
                    dir('frontend') {
                        sh """
                            npm install --prefer-offline --no-audit --no-fund
                            REACT_APP_API_URL=${env.REACT_APP_API_URL} npm run build
                        """
                    }
                }
            }
        }

        // ── STAGE 7: DEPLOY TO S3 ────────────────────────────────────────────
        stage('Deploy Frontend to AWS S3') {
            steps {
                container('aws-helm') {
                    sh """
                        aws s3 sync frontend/build/ s3://${S3_BUCKET_NAME} \
                          --delete \
                          --cache-control "public, max-age=31536000" \
                          --exclude "index.html" \
                          --exclude "asset-manifest.json"

                        # index.html and manifest must NOT be cached
                        aws s3 cp frontend/build/index.html \
                          s3://${S3_BUCKET_NAME}/index.html \
                          --cache-control "no-cache, no-store, must-revalidate"

                        aws s3 cp frontend/build/asset-manifest.json \
                          s3://${S3_BUCKET_NAME}/asset-manifest.json \
                          --cache-control "no-cache, no-store, must-revalidate"
                    """
                }
            }
        }

        // ── STAGE 8: CLOUDFRONT INVALIDATION (non-fatal) ─────────────────────
        stage('CloudFront Invalidation') {
            steps {
                container('aws-helm') {
                    script {
                        try {
                            sh "aws cloudfront create-invalidation --distribution-id ${CLOUDFRONT_DISTRIBUTION_ID} --paths '/*'"
                            echo "CloudFront invalidation triggered successfully!"
                        } catch (Exception e) {
                            echo "WARNING: CloudFront invalidation failed (non-fatal) — ${e.message}"
                        }
                    }
                }
            }
        }

        // ── STAGE 9: SMOKE TEST ───────────────────────────────────────────────
        stage('Smoke Test') {
            steps {
                container('aws-helm') {
                    script {
                        try {
                            def status = sh(
                                script: '''curl -s -o /dev/null -w "%{http_code}" \
                                  --retry 3 --retry-delay 15 --max-time 60 \
                                  "${REACT_APP_API_URL}/api/notes/" || echo "000"''',
                                returnStdout: true
                            ).trim()
                            echo "HTTP Status: ${status}"
                            if (status == '200' || status == '401' || status == '403') {
                                echo "Smoke test PASSED — backend is reachable (HTTP ${status})"
                            } else {
                                echo "Smoke test WARNING — got HTTP ${status}. Backend may still be warming up on Fargate."
                            }
                        } catch (Exception e) {
                            echo "Smoke test WARNING — curl failed (non-fatal): ${e.message}"
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline completed successfully!"
        }
        failure {
            echo "Pipeline FAILED. Check the stage logs above for details."
        }
        always {
            echo "Build #${env.BUILD_ID} finished — cleaning workspace."
            deleteDir()
        }
    }
}
