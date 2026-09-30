// Jenkins Item 이름 예: "Jenkins Deploy Pytest_Coverage"
// New Item -> Pipeline -> 아래 스크립트를 그대로 Pipeline script 란에 붙여넣기
//
// 지난주 "Jenkins Deploy Docker direct - team" Job과 같은 대상(팀 서버, 포트 5002)을 씁니다.
// 컨테이너 이름도 지난주와 동일한 fastapi-app2로 맞춰서, 이 파이프라인이 그 컨테이너를 교체합니다
// (이름을 다르게 하면 같은 포트를 두 컨테이너가 쓰려다 충돌납니다).
//
// 가이드 예시의 BRANCH_NAME='main', credentials(['admin'])은 이 레포 실제 값과 달라서
// master / deploy-key로 고쳤습니다.

pipeline {
    agent any

    environment {
        DOCKERHUB_CREDENTIALS = 'dockerhub-credentials'
        IMAGE_NAME     = 'oh130/fastapi-app'
        IMAGE_TAG      = "${env.BUILD_NUMBER}"
        REMOTE_USER    = 'sogang005'
        REMOTE_HOST    = '163.239.77.78'
        REPO_URL       = 'https://github.com/oh130/FastApi-Todos.git'
        BRANCH_NAME    = 'master'
        APP_DIR        = 'fastapi-app'
        CONTAINER_NAME = 'fastapi-app2'
        HOST_PORT      = '5002'
        CONTAINER_PORT = '8000'
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
                    python3 --version
                    python3 -m venv venv
                    . venv/bin/activate
                    python -m pip install --upgrade pip
                    pip install -r "$APP_DIR/requirements.txt"
                '''
            }
        }

        stage('Test & Coverage') {
            steps {
                sh '''
                    . venv/bin/activate
                    mkdir -p pytest_report
                    pytest "$APP_DIR/tests" \
                      --html=pytest_report/report.html \
                      --self-contained-html \
                      --cov="$APP_DIR" \
                      --cov-report=html:htmlcov
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

        stage('Build') {
            steps {
                dir("${APP_DIR}") {
                    script {
                        docker.build("${IMAGE_NAME}:${IMAGE_TAG}", ".")
                    }
                }
            }
        }

        stage('Push') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDENTIALS) {
                        def image = docker.image("${IMAGE_NAME}:${IMAGE_TAG}")
                        image.push()
                        image.push('latest')
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
"export IMAGE_NAME='${IMAGE_NAME}' IMAGE_TAG='${IMAGE_TAG}' CONTAINER_NAME='${CONTAINER_NAME}' HOST_PORT='${HOST_PORT}' CONTAINER_PORT='${CONTAINER_PORT}'; /bin/bash -se" <<'ENDSSH'
set -e

docker pull "\$IMAGE_NAME:\$IMAGE_TAG"
docker rm -f "\$CONTAINER_NAME" || true
docker run -d --name "\$CONTAINER_NAME" -p "\$HOST_PORT:\$CONTAINER_PORT" "\$IMAGE_NAME:\$IMAGE_TAG"
ENDSSH
"""
                    }
                }
            }
        }

        stage('API Test (Deployed)') {
            steps {
                sh '''
                    . venv/bin/activate
                    sleep 5
                    mkdir -p api_test_report
                    API_BASE_URL="http://${REMOTE_HOST}:${HOST_PORT}" \
                      pytest "$APP_DIR/tests_deploy" \
                      --html=api_test_report/report.html \
                      --self-contained-html
                '''
            }
            post {
                always {
                    publishHTML(target: [
                        reportName : 'Deployed API Test Report',
                        reportDir  : 'api_test_report',
                        reportFiles: 'report.html',
                        keepAll    : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing: true
                    ])
                }
            }
        }
    }

    post {
        failure {
            mail to: 'dhtmdals130@naver.com',
                 subject: "빌드 실패: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                 body: """젠킨스 빌드에서 오류가 발생했습니다.
프로젝트: ${env.JOB_NAME}
빌드 번호: ${env.BUILD_NUMBER}
상세 정보: ${env.BUILD_URL}
확인 후 조치 부탁드립니다."""
        }
        always {
            echo 'Pipeline completed.'
        }
    }
}
