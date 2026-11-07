// Jenkins Item 이름 예: "Jenkins Deploy Jmeter"
// New Item -> Pipeline -> 아래 스크립트를 그대로 Pipeline script 란에 붙여넣기
//
// 가이드 예시와 다르게 고친 부분:
// - REMOTE_PATH / DEPLOY_DIR 등 실제로 쓰이지 않는 변수는 제거
// - BRANCH_NAME: main -> master, sshagent credentials: admin -> deploy-key
// - CONTAINER_NAME/APP_HOST_PORT: 팀 서버(78)에 이미 떠 있는 다른 사람 컨테이너/포트와
//   겹치지 않게 본인 전용 이름(fastapi-app-sogang017)과 포트(8017)로 분리
// - 'Run JMeter Load Test' 단계의 --network host 제거 (가이드 자체의 "cf. 보안·버전 점검" 10번 항목이
//   이미 제거하라고 명시한 옵션인데 예시 코드엔 남아있었음). JMeter는 REMOTE_HOST의 공인 IP:포트로
//   나가는 외부 HTTP 요청만 하면 되므로 기본 브리지 네트워크로 충분함

pipeline {
    agent any

    environment {
        REMOTE_HOST           = "163.239.77.78"
        REMOTE_USER           = "sogang005"

        REPO_URL              = "https://github.com/oh130/FastApi-Todos.git"
        BRANCH_NAME           = "master"

        DOCKERHUB_CREDENTIALS = "dockerhub-credentials"
        IMAGE_NAME            = "oh130/fastapi-app"
        JMETER_IMAGE_NAME     = "my-jmeter-sogang017"

        CONTAINER_NAME        = "fastapi-app-sogang017"
        APP_HOST_PORT         = "8017"
        APP_CONTAINER_PORT    = "8000"
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
                    pip install pip-audit
                    pip-audit -r fastapi-app/requirements.txt || true
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

                    if [ -f "coverage.xml" ]; then
                        cp coverage.xml fastapi-app/coverage.xml
                    fi
                '''
            }
            post {
                always {
                    publishHTML(target: [
                        reportName           : 'Pytest HTML Report',
                        reportDir            : 'pytest_report',
                        reportFiles          : 'report.html',
                        keepAll              : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing         : true
                    ])
                    publishHTML(target: [
                        reportName           : 'Coverage Report',
                        reportDir            : 'htmlcov',
                        reportFiles          : 'index.html',
                        keepAll              : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing         : true
                    ])
                }
            }
        }

        stage('Build') {
            steps {
                dir('fastapi-app') {
                    script {
                        docker.build("${IMAGE_NAME}:${BUILD_NUMBER}", ".")
                    }
                }
            }
        }

        stage('Push') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', DOCKERHUB_CREDENTIALS) {
                        docker.image("${IMAGE_NAME}:${BUILD_NUMBER}").push()
                        docker.image("${IMAGE_NAME}:${BUILD_NUMBER}").push('latest')
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    sshagent(credentials: ['deploy-key']) {
                        sh """
                            set -e

                            mkdir -p ~/.ssh && chmod 700 ~/.ssh
                            ssh-keyscan -H ${REMOTE_HOST} >> ~/.ssh/known_hosts 2>/dev/null
                            sort -u ~/.ssh/known_hosts -o ~/.ssh/known_hosts

                            ssh -o StrictHostKeyChecking=yes ${REMOTE_USER}@${REMOTE_HOST} \\
                                'docker pull ${IMAGE_NAME}:${BUILD_NUMBER} && \\
                                 docker stop ${CONTAINER_NAME} || true && \\
                                 docker rm ${CONTAINER_NAME} || true && \\
                                 docker run -d \\
                                     --name ${CONTAINER_NAME} \\
                                     --restart unless-stopped \\
                                     -p ${APP_HOST_PORT}:${APP_CONTAINER_PORT} \\
                                     ${IMAGE_NAME}:${BUILD_NUMBER}'
                        """
                    }
                }
            }
        }

        stage('Build JMeter Image') {
            steps {
                dir('jmeter') {
                    script {
                        docker.build("${JMETER_IMAGE_NAME}:latest", ".")
                    }
                }
            }
        }

        stage('Run JMeter Load Test') {
            steps {
                sh '''
                    set -e
                    BASE_DIR="$WORKSPACE/jmeter"

                    rm -rf "$BASE_DIR/report" "$BASE_DIR/results.jtl" "$BASE_DIR/jmeter.log"
                    mkdir -p "$BASE_DIR"

                    TARGET_HOST="$REMOTE_HOST"
                    TARGET_PORT="$APP_HOST_PORT"

                    CONTAINER_ID=$(docker create -w /jmeter "$JMETER_IMAGE_NAME:latest" \
                        sh -c "jmeter -n -t /jmeter/test.jmx \
                            -JTARGET_HOST=$TARGET_HOST \
                            -JTARGET_PORT=$TARGET_PORT \
                            -l /jmeter/results.jtl \
                            -j /jmeter/jmeter.log \
                            -Jjmeter.save.saveservice.output_format=csv \
                            -e -o /jmeter/report")

                    docker cp "$BASE_DIR"/*.jmx "$CONTAINER_ID":/jmeter/test.jmx

                    docker start -a "$CONTAINER_ID" || true

                    docker cp "$CONTAINER_ID":/jmeter/report      "$BASE_DIR/report"       || true
                    docker cp "$CONTAINER_ID":/jmeter/results.jtl "$BASE_DIR/results.jtl"  || true
                    docker cp "$CONTAINER_ID":/jmeter/jmeter.log  "$BASE_DIR/jmeter.log"   || true

                    docker rm "$CONTAINER_ID"

                    echo "===== JMeter report 디렉터리 확인 ====="
                    ls -al "$BASE_DIR/report" || echo "report 생성 실패: jmeter.log 확인 필요"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'jmeter/report/**, jmeter/results.jtl, jmeter/jmeter.log',
                                     allowEmptyArchive: true
                    publishHTML(target: [
                        reportName           : 'JMeter HTML Report',
                        reportDir            : 'jmeter/report',
                        reportFiles          : 'index.html',
                        keepAll              : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing         : true
                    ])
                }
            }
        }
    }

    post {
        always {
            echo 'Pipeline completed.'
        }
    }
}
