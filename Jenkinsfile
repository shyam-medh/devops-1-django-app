pipeline {
    agent { label 'dard' }

    environment {
        // AWS Configuration (Please update these with your actual AWS details)
        AWS_REGION = 'us-east-1'
        AWS_ACCOUNT_ID = 'YOUR_AWS_ACCOUNT_ID'
        
        // Resource Names (Must match your Terraform configurations)
        S3_BUCKET_NAME = 'django-notes-app-react-frontend-prod'
        ECR_REPO_NAME = 'django-notes-backend'
        EKS_CLUSTER_NAME = 'django-notes-eks'
        
        // Dynamic Variables
        IMAGE_TAG = "v${env.BUILD_ID}"
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    }

    stages {
        stage('Build Frontend (React)') {
            steps {
                dir('frontend') {
                    script {
                        if (isUnix()) {
                            sh 'npm install'
                            sh 'npm run build'
                        } else {
                            bat 'npm install'
                            bat 'npm run build'
                        }
                    }
                }
            }
        }

        stage('Deploy Frontend to AWS S3') {
            steps {
                script {
                    // This syncs the compiled React files directly to the S3 bucket, overriding old ones
                    if (isUnix()) {
                        sh "aws s3 sync frontend/build/ s3://${S3_BUCKET_NAME} --delete"
                    } else {
                        bat "aws s3 sync frontend\\build\\ s3://${S3_BUCKET_NAME} --delete"
                    }
                }
            }
        }

        stage('Build Backend (Django Docker Image)') {
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

        stage('Push Backend to AWS ECR') {
            steps {
                script {
                    // Authenticate Docker to AWS ECR, then push the newly built image
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
                    // Configure kubectl for the EKS cluster, then run helm upgrade
                    // We dynamically override the image repo and tag using the --set flag
                    if (isUnix()) {
                        sh "aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}"
                        sh "helm upgrade --install django-backend infra/django-notes-app/django --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} --set image.tag=${IMAGE_TAG}"
                    } else {
                        bat "aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}"
                        bat "helm upgrade --install django-backend infra\\django-notes-app\\django --set image.repository=${ECR_REGISTRY}/${ECR_REPO_NAME} --set image.tag=${IMAGE_TAG}"
                    }
                }
            }
        }
    }

    post {
        always {
            echo "Pipeline complete. Check CloudFront for frontend updates and EKS for backend rollouts!"
        }
    }
}
