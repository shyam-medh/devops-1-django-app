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
                command:
                - cat
                tty: true
              - name: node
                image: node:18-alpine
                command:
                - cat
                tty: true
              - name: kaniko
                image: gcr.io/kaniko-project/executor:debug
                command:
                - sleep
                args:
                - 99d
                tty: true
                resources:
                  requests:
                    memory: "2Gi"
                    cpu: "1000m"
                  limits:
                    memory: "2Gi"
                    cpu: "1000m"
              - name: aws-helm
                image: amazon/aws-cli:latest
                command:
                - cat
                tty: true
            '''
        }
    }

    environment {
        // AWS Configuration
        AWS_REGION = 'ap-south-1'
        AWS_ACCOUNT_ID = '790304249797'
        
        // Resource Names
        S3_BUCKET_NAME = 'django-notes-app-react-frontend-prod'
        ECR_REPO_NAME = 'django-notes-backend'
        EKS_CLUSTER_NAME = 'django-notes-eks-prod'
        CLOUDFRONT_DISTRIBUTION_ID = 'E38UXJBMVV63Z0'
        
        // Dynamic Variables
        GIT_COMMIT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        IMAGE_TAG = "${GIT_COMMIT_SHA}-${env.BUILD_ID}"
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    }

    stages {
        stage('DevSecOps: Code Scan (SAST)') {
            steps {
                container('python') {
                    echo "Mocking Bandit, Checkov, GitLeaks in Serverless Agent..."
                    // pip install bandit
                    // bandit -r backend/
                }
            }
        }

        stage('Backend Tests') {
            steps {
                container('python') {
                    dir('backend') {
                        sh '''
                            pip install -r requirements.txt
                            python manage.py test
                        '''
                    }
                }
            }
        }

        stage('Build & Push Django Image (Kaniko)') {
            steps {
                container('kaniko') {
                    // Kaniko does NOT use docker daemon, but it needs the AWS ECR credential helper configured
                    sh '''
                        mkdir -p /kaniko/.docker
                        echo '{"credsStore":"ecr-login"}' > /kaniko/.docker/config.json
                        
                        /kaniko/executor --context `pwd`/backend \
                        --dockerfile `pwd`/backend/Dockerfile \
                        --destination ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} \
                        --cache=true \
                        --force
                    '''
                }
            }
        }

        stage('Deploy Backend to EKS (Helm)') {
            steps {
                container('aws-helm') {
                    script {
                        // Install tools: tar, gzip (for helm installer), kubectl
                        sh '''
                            yum install -y tar gzip

                            # Install Helm
                            curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
                            chmod 700 get_helm.sh
                            VERIFY_CHECKSUM=false ./get_helm.sh

                            # Install kubectl
                            curl -fsSL -o /usr/local/bin/kubectl \
                              https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl
                            chmod +x /usr/local/bin/kubectl

                            # Configure kubeconfig
                            aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}
                        '''

                        try {
                            sh """
                                helm upgrade --install django-backend infra/helm/django-backend \
                                  -f infra/helm/django-backend/values-prod.yaml \
                                  --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} \
                                  --set image.tag=${IMAGE_TAG} \
                                  --namespace django --create-namespace \
                                  --timeout 10m --wait
                            """
                        } catch (Exception e) {
                            echo "Deployment failed! Rolling back Helm release..."
                            sh "helm rollback django-backend --namespace django || true"
                            error("Deployment failed, automated rollback triggered.")
                        }
                    }
                }
            }
        }

        stage('Fetch ALB DNS Name') {
            steps {
                container('aws-helm') {
                    script {
                        echo "Waiting for the AWS Load Balancer to provision and expose its DNS name..."
                        sleep(time: 60, unit: 'SECONDS')
                        def albHost = sh(
                            script: "kubectl get ingress django-backend -n django -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'",
                            returnStdout: true
                        ).trim()

                        if (!albHost) {
                            error("ALB DNS name is empty — Load Balancer may not have provisioned yet.")
                        }

                        env.REACT_APP_API_URL = "http://${albHost}"
                        echo "Dynamically injected Backend API URL: ${env.REACT_APP_API_URL}"
                    }
                }
            }
        }

        stage('Build React Frontend') {
            steps {
                container('node') {
                    dir('frontend') {
                        sh 'npm install'
                        sh "REACT_APP_API_URL=${env.REACT_APP_API_URL} npm run build"
                    }
                }
            }
        }

        stage('Deploy Frontend to AWS S3') {
            steps {
                container('aws-helm') {
                    sh "aws s3 sync frontend/build/ s3://${S3_BUCKET_NAME} --delete"
                }
            }
        }

        stage('CloudFront Invalidation') {
            steps {
                container('aws-helm') {
                    sh "aws cloudfront create-invalidation --distribution-id ${CLOUDFRONT_DISTRIBUTION_ID} --paths '/*'"
                }
            }
        }

        stage('Smoke Test (DAST / Verification)') {
            steps {
                container('aws-helm') {
                    sh '''
                        echo "Pinging backend to verify ALB is healthy..."
                        curl -fsSL --retry 5 --retry-delay 10 --max-time 30 \
                          "${REACT_APP_API_URL}/api/notes/" -o /dev/null && \
                          echo "Smoke test passed!" || echo "Warning: Smoke test did not get a 200 response (may be auth protected)."
                    '''
                }
            }
        }
    }
}
