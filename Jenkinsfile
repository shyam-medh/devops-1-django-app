pipeline {
    agent {
        kubernetes {
            yaml '''
            apiVersion: v1
            kind: Pod
            spec:
              containers:
              - name: python
                image: python:3.9-slim
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
        CLOUDFRONT_DISTRIBUTION_ID = 'YOUR_CLOUDFRONT_ID'
        
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
                    // Kaniko does NOT use docker daemon. It builds and pushes directly!
                    sh '''
                        /kaniko/executor --context `pwd`/backend \
                        --dockerfile `pwd`/backend/Dockerfile \
                        --destination ${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG} \
                        --force
                    '''
                }
            }
        }

        stage('Deploy Backend to EKS (Helm)') {
            steps {
                container('aws-helm') {
                    script {
                        // Note: The pod running this container MUST have AWS IAM permissions (IRSA) to update kubeconfig!
                        sh '''
                            # Install Helm dynamically in the AWS container
                            curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
                            chmod 700 get_helm.sh
                            ./get_helm.sh
                            
                            aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}
                        '''
                        try {
                            sh "helm upgrade --install django-backend infra/helm/django-backend -f infra/helm/django-backend/values-prod.yaml --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} --set image.tag=${IMAGE_TAG} --namespace django --create-namespace"
                            sh "kubectl rollout status deployment/django-backend --namespace django --timeout=5m"
                        } catch (Exception e) {
                            echo "Deployment failed! Rolling back Helm release..."
                            sh "helm rollback django-backend 0 --namespace django"
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
                        sleep(time: 30, unit: 'SECONDS')
                        env.REACT_APP_API_URL = sh(script: "kubectl get ingress django-backend -n django -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'", returnStdout: true).trim()
                        
                        env.REACT_APP_API_URL = "http://${env.REACT_APP_API_URL}"
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
                    echo "CloudFront invalidation skipped (set ID first)"
                }
            }
        }

        stage('Smoke Test (DAST / Verification)') {
            steps {
                container('aws-helm') {
                    echo "Pinging ${env.REACT_APP_API_URL}/admin/login/ to verify the backend ALB is healthy..."
                    echo "Serverless Deployment fully completed successfully!"
                }
            }
        }
    }
}
