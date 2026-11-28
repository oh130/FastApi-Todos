// Jenkins Item 이름 예: "Jenkins Deploy Docker legacy - team"
// own 버전과 stages 이하는 완전히 동일, environment 블록만 팀 서버 값으로 교체
// 사전 조건: 팀 서버(sogang005)에 Docker 설치 + sogang005 계정 docker 그룹 추가 완료,
//            본인 jenkins_deploy 공개키가 팀 서버 authorized_keys에 등록되어 있어야 함

pipeline {
    agent any

    environment {
        REMOTE_USER = 'sogang005'                     // 팀 서버 틸론 ID
        REMOTE_HOST = '163.239.77.78'
        REMOTE_PATH = '/home/sogang005@SGVDI.local'
        REPO_URL    = 'https://github.com/oh130/FastApi-Todos.git'
        BRANCH_NAME = 'master'
        REPO_DIR    = '20201603'                       // 본인 학번 - 팀원끼리 안 겹침
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
# [v9.0.0] compose가 PostgreSQL을 함께 띄우므로, 서버의 레포 폴더에 있는 .env(git에 안 올라감)에 POSTGRES_PASSWORD가 있어야 한다.
# 처음 한 번 서버에서 직접 추가한다: echo "POSTGRES_PASSWORD=<영문/숫자 12자 이상>" >> .env
if ! grep -q '^POSTGRES_PASSWORD=' .env 2>/dev/null; then
  echo "ERROR: $PWD/.env 에 POSTGRES_PASSWORD 가 없다. 서버에서 .env에 추가한 뒤 다시 실행해라." >&2
  exit 1
fi
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
