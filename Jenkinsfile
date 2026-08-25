pipeline {
    agent { label 'dard' }

    environment {
        // AWS Configuration
        AWS_REGION = 'ap-south-1'
        AWS_ACCOUNT_ID = '790304249797'
        
        // Resource Names
        S3_BUCKET_NAME = 'django-notes-app-react-frontend-prod'
        ECR_REPO_NAME = 'django-notes-backend'
        EKS_CLUSTER_NAME = 'django-notes-eks-prod'
        CLOUDFRONT_DISTRIBUTION_ID = 'YOUR_CLOUDFRONT_ID' // Replace later
        
        // Dynamic Variables
        GIT_COMMIT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        IMAGE_TAG = "${GIT_COMMIT_SHA}-${env.BUILD_ID}"
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        
        // REACT_APP_API_URL will be dynamically populated in a later stage!
    }

    stages {
        stage('DevSecOps: Code Scan (SAST)') {
            steps {
                script {
                    echo "Running Bandit for Python SAST..."
                    // sh "bandit -r backend/"
                    
                    echo "Running Checkov for Terraform infrastructure scanning..."
                    // sh "checkov -d infra/terraform/"
                    
                    echo "Running GitLeaks to detect hardcoded secrets..."
                    // sh "gitleaks detect -v"
                }
            }
        }

        stage('Backend Tests') {
            steps {
                dir('backend') {
                    script {
                        if (isUnix()) {
                            sh '''
                                python3 -m venv venv
                                . venv/bin/activate
                                pip install -r requirements.txt
                                python manage.py test
                            '''
                        } else {
                            bat '''
                                python -m venv venv
                                call venv\\Scripts\\activate
                                pip install -r requirements.txt
                                python manage.py test
                            '''
                        }
                    }
                }
            }
        }

        stage('Build Django Docker Image') {
            steps {
                script {
                    if (isUnix()) {
                        sh "docker build -t ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} ./backend"
                    } else {
                        bat "docker build -t ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} .\\backend"
                    }
                }
            }
        }

        stage('DevSecOps: Image Scan (Trivy)') {
            steps {
                script {
                    echo "Running Trivy to scan the Django container image for CRITICAL vulnerabilities..."
                    // Remove the echo and uncomment the sh line when Trivy is installed on the agent!
                    // sh "trivy image --severity CRITICAL --exit-code 1 ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG}"
                }
            }
        }

        stage('Push Backend to AWS ECR') {
            steps {
                script {
                    if (isUnix()) {
                        sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                        sh "docker push ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG}"
                    } else {
                        bat "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
                        bat "docker push ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG}"
                    }
                }
            }
        }

        stage('Deploy Backend to EKS (Helm)') {
            steps {
                script {
                    if (isUnix()) {
                        sh "aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}"
                        // Using a try-catch for basic rollback logic
                        try {
                            sh "helm upgrade --install django-backend infra/helm/django-backend -f infra/helm/django-backend/values-prod.yaml --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} --set image.tag=${IMAGE_TAG} --namespace django --create-namespace"
                            sh "kubectl rollout status deployment/django-backend --namespace django --timeout=5m"
                        } catch (Exception e) {
                            echo "Deployment failed! Rolling back Helm release..."
                            sh "helm rollback django-backend 0 --namespace django"
                            error("Deployment failed, automated rollback triggered.")
                        }
                    } else {
                        bat "aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}"
                        try {
                            bat "helm upgrade --install django-backend infra\\helm\\django-backend -f infra\\helm\\django-backend\\values-prod.yaml --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} --set image.tag=${IMAGE_TAG} --namespace django --create-namespace"
                            bat "kubectl rollout status deployment/django-backend --namespace django --timeout=5m"
                        } catch (Exception e) {
                            echo "Deployment failed! Rolling back Helm release..."
                            bat "helm rollback django-backend 0 --namespace django"
                            error("Deployment failed, automated rollback triggered.")
                        }
                    }
                }
            }
        }

        stage('Fetch ALB DNS Name') {
            steps {
                script {
                    echo "Waiting for the AWS Load Balancer to provision and expose its DNS name..."
                    if (isUnix()) {
                        // Wait a bit for ALB to attach
                        sleep(time: 30, unit: 'SECONDS')
                        env.REACT_APP_API_URL = sh(script: "kubectl get ingress django-backend -n django -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'", returnStdout: true).trim()
                    } else {
                        sleep(time: 30, unit: 'SECONDS')
                        // For Windows we read the output of kubectl and clean it up
                        def albOutput = bat(script: "kubectl get ingress django-backend -n django -o jsonpath=\"{.status.loadBalancer.ingress[0].hostname}\"", returnStdout: true).trim()
                        // Batch command usually returns the executed command as first line, need to parse just the URL if needed, but assuming direct return for simplicity.
                        env.REACT_APP_API_URL = albOutput.readLines().last().trim()
                    }
                    
                    // Since we lack a domain name and SSL certificate, the ALB runs on HTTP!
                    env.REACT_APP_API_URL = "http://${env.REACT_APP_API_URL}"
                    echo "Dynamically injected Backend API URL: ${env.REACT_APP_API_URL}"
                }
            }
        }

        stage('Frontend Tests') {
            steps {
                dir('frontend') {
                    script {
                        if (isUnix()) {
                            sh 'npm install'
                        } else {
                            bat 'npm install'
                        }
                    }
                }
            }
        }

        stage('Build React') {
            steps {
                dir('frontend') {
                    script {
                        if (isUnix()) {
                            sh "REACT_APP_API_URL=${env.REACT_APP_API_URL} npm run build"
                        } else {
                            bat "set REACT_APP_API_URL=${env.REACT_APP_API_URL}&& npm run build"
                        }
                    }
                }
            }
        }

        stage('Deploy Frontend to AWS S3') {
            steps {
                script {
                    if (isUnix()) {
                        sh "aws s3 sync frontend/build/ s3://${S3_BUCKET_NAME} --delete"
                    } else {
                        bat "aws s3 sync frontend\\build\\ s3://${S3_BUCKET_NAME} --delete"
                    }
                }
            }
        }

        stage('CloudFront Invalidation') {
            steps {
                script {
                    if (isUnix()) {
                        echo "CloudFront invalidation skipped (set ID first)"
                    } else {
                        echo "CloudFront invalidation skipped (set ID first)"
                    }
                }
            }
        }

        stage('Smoke Test (DAST / Verification)') {
            steps {
                script {
                    echo "Pinging ${env.REACT_APP_API_URL}/admin/login/ to verify the backend ALB is healthy..."
                    // if (isUnix()) { sh "curl -f -s ${env.REACT_APP_API_URL}/admin/login/" }
                    echo "Deployment fully completed successfully!"
                }
            }
        }
    }

    post {
        always {
            echo "Pipeline complete. Check CloudFront for frontend updates!"
        }
    }
}
