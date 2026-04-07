pipeline {
    agent {label 'dard'}

    environment {
        DJANGO_SECRET_KEY = 'jenkins-ci-secret-key'
        DEBUG = 'False'
        DOCKERHUB_USERNAME = 'shyammedh'
        IMAGE_TAG = 'v1'
    }

    stages {
        stage('Build Frontend') {
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

        stage('Install Backend Dependencies') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python3 -m venv .venv'
                        sh '.venv/bin/python -m pip install -r backend/requirements.txt'
                    } else {
                        bat 'python -m venv .venv'
                        bat '.\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt'
                    }
                }
            }
        }

        stage('Test Backend') {
            steps {
                script {
                    if (isUnix()) {
                        sh '.venv/bin/python backend/manage.py check'
                        sh '.venv/bin/python backend/manage.py test'
                    } else {
                        bat '.\\.venv\\Scripts\\python.exe backend\\manage.py check'
                        bat '.\\.venv\\Scripts\\python.exe backend\\manage.py test'
                    }
                }
            }
        }

        stage('Deploy Containers') {
            steps {
                script {
                    if (!fileExists('.env') && fileExists('.env.example')) {
                        if (isUnix()) {
                            sh 'cp .env.example .env'
                        } else {
                            bat 'copy /Y .env.example .env'
                        }
                    }

                    if (isUnix()) {
                        sh '''
                        docker-compose down || true
                        docker-compose pull
                        docker-compose up -d
                        '''
                    } else {
                        bat '''
                        docker-compose down || true
                        docker-compose pull
                        docker-compose up -d
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'frontend/build/**', allowEmptyArchive: true
        }
    }
}
