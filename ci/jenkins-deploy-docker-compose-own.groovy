// Jenkins Item 이름 예: "Jenkins Deploy Docker legacy - own"
// New Item -> Pipeline -> 아래 스크립트를 그대로 Pipeline script 란에 붙여넣기
//
// 실제 레포 구조(FastApi-Todos)는 가이드 예시(Dev5ps/FastApi_Todos 중첩)와 달리
// 레포 루트에 docker-compose.yml, fastapi-app/ 이 바로 있으므로 APP_DIR 없이 REPO_DIR까지만 이동합니다.
// 기본 브랜치도 main이 아니라 master이므로 BRANCH_NAME을 master로 바꿨습니다.

pipeline {
    agent any

    environment {
        REMOTE_USER = 'sogang017'                    // 본인 틸론 ID
        REMOTE_HOST = '163.239.77.90'
        REMOTE_PATH = '/home/sogang017@SGVDI.local'   // $pwd로 확인
        REPO_URL    = 'https://github.com/oh130/FastApi-Todos.git'
        BRANCH_NAME = 'master'
        REPO_DIR    = '20201603'                      // 본인 학번 (todo.json 기준 추정 - 다르면 수정)
    }

    options {
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                git url: "${REPO_URL}", branch: "${BRANCH_NAME}"
            }
        }

        stage('Deploy') {
            steps {
                sshagent(credentials: ['deploy-key']) {
                    sh '''
ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "REMOTE_PATH='${REMOTE_PATH}' REPO_URL='${REPO_URL}' BRANCH_NAME='${BRANCH_NAME}' REPO_DIR='${REPO_DIR}' bash -se" <<'ENDSSH'
set -euo pipefail
cd "$REMOTE_PATH"

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch --prune origin
  git -C "$REPO_DIR" checkout "$BRANCH_NAME"
  git -C "$REPO_DIR" reset --hard "origin/$BRANCH_NAME"
else
  git clone --branch "$BRANCH_NAME" "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
docker compose up -d --build --remove-orphans
docker compose ps
ENDSSH
'''
                }
            }
        }
    }

    post {
        failure {
            mail to: 'dhtmdals130@naver.com',
                 subject: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                 body: "빌드 실패. 콘솔 로그: ${env.BUILD_URL}console"
        }
    }
}
