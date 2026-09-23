// Jenkins Item 이름 예: "Jenkins Deploy Docker direct - team"
// DockerHub에 이미지 빌드/푸시 후, 팀 서버가 그 이미지를 pull해서 실행
// 사전 조건: DockerHub 가입 + PAT 발급, Jenkins Credentials에 dockerhub-credentials 등록,
//            Docker Pipeline 플러그인 설치, 팀 서버 Docker 설치 완료
//
// 실제 레포는 root 바로 아래 fastapi-app/ 이므로 dir()도 'fastapi-app'만 지정 (가이드 예시의
// 'FastApi_Todos/fastapi-app' 중첩 경로는 이 레포 구조와 다름)

pipeline {
    agent any

    environment {
        DOCKERHUB_CREDENTIALS = 'dockerhub-credentials'
        IMAGE_NAME     = 'oh130/fastapi-app'
        IMAGE_TAG      = "${env.BUILD_NUMBER}"
        REMOTE_USER    = 'sogang005'                    // 팀 서버 틸론 ID
        REMOTE_HOST    = '163.239.77.78'
        REPO_URL       = 'https://github.com/oh130/FastApi-Todos.git'
        BRANCH_NAME    = 'master'
        CONTAINER_NAME = 'fastapi-app2'
        HOST_PORT      = '5002'
        CONTAINER_PORT = '8000'
    }

    options {
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                git url: "${REPO_URL}", branch: "${BRANCH_NAME}"
            }
        }

        stage('Build') {
            steps {
                dir('fastapi-app') {
                    script {
                        docker.build("${IMAGE_NAME}:${IMAGE_TAG}", "--pull .")
                    }
                }
            }
        }

        stage('Push') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDENTIALS) {
                        def img = docker.image("${IMAGE_NAME}:${IMAGE_TAG}")
                        img.push()
                        img.push('latest')
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                sshagent(credentials: ['deploy-key']) {
                    sh '''
ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "IMAGE='${IMAGE_NAME}:${IMAGE_TAG}' CONTAINER_NAME='${CONTAINER_NAME}' HOST_PORT='${HOST_PORT}' CONTAINER_PORT='${CONTAINER_PORT}' bash -se" <<'ENDSSH'
set -euo pipefail

docker pull "$IMAGE"
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker run -d --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -p "$HOST_PORT:$CONTAINER_PORT" \
  "$IMAGE"
docker ps --filter "name=$CONTAINER_NAME"
ENDSSH
'''
                }
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
        failure {
            mail to: 'dhtmdals130@naver.com',
                 subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                 body: "빌드 실패. 콘솔 로그: ${env.BUILD_URL}console"
        }
    }
}
