pipeline {
    agent any

    options {
        timestamps()
    }

    environment {
        DJANGO_SECRET_KEY = 'jenkins-ci-secret-key'
        DEBUG = 'False'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PYTHONDONTWRITEBYTECODE = '1'
    }

    stages {
        stage('Verify Toolchain') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python3 --version'
                        sh 'node --version'
                        sh 'npm --version'
                    } else {
                        bat 'python --version'
                        bat 'node --version'
                        bat 'npm --version'
                    }
                }
            }
        }

        stage('Build Frontend') {
            steps {
                dir('frontend') {
                    script {
                        if (isUnix()) {
                            if (fileExists('package-lock.json')) {
                                sh 'npm ci'
                            } else {
                                sh 'npm install'
                            }
                            sh 'npm run build'
                        } else {
                            if (fileExists('package-lock.json')) {
                                bat 'npm ci'
                            } else {
                                bat 'npm install'
                            }
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
                        sh '.venv/bin/python -m pip install --upgrade pip'
                        sh '.venv/bin/python -m pip install -r backend/requirements.txt'
                    } else {
                        bat 'python -m venv .venv'
                        bat '.\\.venv\\Scripts\\python.exe -m pip install --upgrade pip'
                        bat '.\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt'
                    }
                }
            }
        }

        stage('Validate Django App') {
            steps {
                script {
                    if (isUnix()) {
                        sh '.venv/bin/python backend/manage.py check'
                        sh '.venv/bin/python backend/manage.py test'
                        sh '.venv/bin/python backend/manage.py collectstatic --no-input'
                    } else {
                        bat '.\\.venv\\Scripts\\python.exe backend\\manage.py check'
                        bat '.\\.venv\\Scripts\\python.exe backend\\manage.py test'
                        bat '.\\.venv\\Scripts\\python.exe backend\\manage.py collectstatic --no-input'
                    }
                }
            }
        }

        stage('Validate Docker Compose') {
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
                        def dockerStatus = sh(script: 'command -v docker >/dev/null 2>&1', returnStatus: true)
                        if (dockerStatus == 0) {
                            sh 'docker compose config'
                        } else {
                            echo 'Docker is not available on this Jenkins agent. Skipping docker compose validation.'
                        }
                    } else {
                        def dockerStatus = bat(script: '@where docker >nul 2>nul', returnStatus: true)
                        if (dockerStatus == 0) {
                            bat 'docker compose config'
                        } else {
                            echo 'Docker is not available on this Jenkins agent. Skipping docker compose validation.'
                        }
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
