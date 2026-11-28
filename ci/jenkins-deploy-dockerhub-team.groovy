// Jenkins Item 이름 예: "Jenkins Deploy Docker direct - team"
// DockerHub에 이미지 빌드/푸시 후, 팀 서버가 그 이미지를 pull해서 실행
// 사전 조건: DockerHub 가입 + PAT 발급, Jenkins Credentials에 dockerhub-credentials 등록,
//            Docker Pipeline 플러그인 설치, 팀 서버 Docker 설치 완료
//
// 실제 레포는 root 바로 아래 fastapi-app/ 이므로 dir()도 'fastapi-app'만 지정 (가이드 예시의
// 'FastApi_Todos/fastapi-app' 중첩 경로는 이 레포 구조와 다름)

// [v9.0.0] 앱이 DB(PostgreSQL)에 데이터를 저장하므로 Deploy 단계는 ci/remote-deploy.sh를 서버에서 실행한다 (DB 컨테이너 + 앱 컨테이너).
// 사전 조건: Jenkins Credentials에 Secret text `todo-db-password`(영문/숫자 12자 이상)를 등록해야 한다.

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
                // DB 비밀번호는 Credentials에서 꺼내 ssh 표준입력으로만 서버에 보낸다 (명령줄/로그에 남지 않게)
                withCredentials([string(credentialsId: 'todo-db-password', variable: 'POSTGRES_PASSWORD')]) {
                    sshagent(credentials: ['deploy-key']) {
                        sh '''
{
  printf "export IMAGE='%s' APP_NAME='%s' HOST_PORT='%s' CONTAINER_PORT='%s'\\n" "${IMAGE_NAME}:${IMAGE_TAG}" "$CONTAINER_NAME" "$HOST_PORT" "$CONTAINER_PORT"
  printf "export POSTGRES_PASSWORD='%s'\\n" "$POSTGRES_PASSWORD"
  cat ci/remote-deploy.sh
} | ssh -o StrictHostKeyChecking=accept-new "$REMOTE_USER@$REMOTE_HOST" bash -se
'''
                    }
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
