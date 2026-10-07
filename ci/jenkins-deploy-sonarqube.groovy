// Jenkins Item 이름 예: "Jenkins Deploy Sonarqube"
// New Item -> Pipeline -> 아래 스크립트를 그대로 Pipeline script 란에 붙여넣기
//
// 가이드 예시와 다르게 고친 부분:
// - 레포 구조가 'FastApi_Todos/fastapi-app' 중첩이 아니라 루트 바로 아래 fastapi-app/ 이므로 경로에서 중첩 제거
// - BRANCH_NAME: main -> master (이 레포의 실제 기본 브랜치)
// - sshagent credentials: admin -> deploy-key (실제 등록된 SSH 크리덴셜 ID)
// - sonar-project.properties는 fastapi-app/ 안에 있음 (dir('fastapi-app')에서 스캐너를 실행하므로)
// - CONTAINER_NAME/HOST_PORT: 3주차 docker-compose가 이미 'FastApi-app' 이름으로 5001 포트를 쓰고 있어서
//   이름이 겹치면 그 컨테이너가 매 빌드마다 삭제됨 -> 별도 이름/포트(fastapi-app-ci, 5003) 사용

pipeline {
    agent any

    environment {
        DOCKERHUB_CREDENTIALS = 'dockerhub-credentials'
        IMAGE_NAME     = 'oh130/fastapi-app'
        REMOTE_USER    = 'sogang017'
        REMOTE_HOST    = '163.239.77.90'
        REPO_URL       = 'https://github.com/oh130/FastApi-Todos.git'
        BRANCH_NAME    = 'master'
        CONTAINER_NAME = 'fastapi-app-ci'
        HOST_PORT      = '5003'
        CONTAINER_PORT = '8000'
        // SONAR_TOKEN, SONAR_HOST_URL은 여기 두지 않음 -> withSonarQubeEnv가 주입
    }

    stages {
        stage('Checkout') {
            steps {
                git url: "${REPO_URL}", branch: "${BRANCH_NAME}"
            }
        }

        stage('Setup Environment & Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r fastapi-app/requirements.txt
                    pip install pytest pytest-html pytest-cov
                '''
            }
        }

        stage('Test & Coverage') {
            steps {
                sh '''
                    . venv/bin/activate
                    mkdir -p pytest_report

                    pytest fastapi-app/tests \
                      --html=pytest_report/report.html \
                      --self-contained-html \
                      --cov=fastapi-app \
                      --cov-report=xml:coverage.xml \
                      --cov-report=html:htmlcov

                    cp coverage.xml fastapi-app/coverage.xml
                '''
            }
            post {
                always {
                    publishHTML(target: [
                        reportName : 'Pytest HTML Report',
                        reportDir  : 'pytest_report',
                        reportFiles: 'report.html',
                        keepAll    : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing: true
                    ])
                    publishHTML(target: [
                        reportName : 'Coverage Report',
                        reportDir  : 'htmlcov',
                        reportFiles: 'index.html',
                        keepAll    : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing: true
                    ])
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                dir('fastapi-app') {
                    script {
                        def scannerHome = tool 'sonar'
                        withSonarQubeEnv('sonarqube') {
                            sh "${scannerHome}/bin/sonar-scanner"
                        }
                    }
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build') {
            steps {
                dir('fastapi-app') {
                    script {
                        docker.build("${IMAGE_NAME}:latest", ".")
                    }
                }
            }
        }

        stage('Push') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDENTIALS) {
                        docker.image("${IMAGE_NAME}:latest").push()
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    sshagent(credentials: ['deploy-key']) {
                        sh """
ssh -o StrictHostKeyChecking=accept-new ${REMOTE_USER}@${REMOTE_HOST} \\
"export IMAGE_NAME='${IMAGE_NAME}' CONTAINER_NAME='${CONTAINER_NAME}' HOST_PORT='${HOST_PORT}' CONTAINER_PORT='${CONTAINER_PORT}'; /bin/bash -se" <<'ENDSSH'
set -e

docker pull "\$IMAGE_NAME:latest"
docker rm -f "\$CONTAINER_NAME" || true
docker run -d --name "\$CONTAINER_NAME" -p "\$HOST_PORT:\$CONTAINER_PORT" "\$IMAGE_NAME:latest"
ENDSSH
"""
                    }
                }
            }
        }
    }

    post {
        failure {
            mail to: 'dhtmdals130@naver.com',
                 subject: "빌드 실패: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                 body: "콘솔 로그: ${env.BUILD_URL}console"
        }
        always {
            echo 'Pipeline completed.'
        }
    }
}
