#!/bin/bash
# 서버에서 실행하는 배포 스크립트. Jenkins가 ssh로 이 파일 내용을 보내서 실행한다 (jenkins-deploy-*.groovy의 Deploy 단계).
#
# v9.0.0부터 앱이 파일이 아니라 PostgreSQL에 데이터를 저장하므로, 앱 컨테이너만 띄우면 안 되고 DB 컨테이너가 같이 있어야 한다.
# 이 스크립트는 같은 도커 네트워크 안에 (1) PostgreSQL 컨테이너(없을 때만 새로 만들고, 있으면 데이터를 그대로 둔다)와
# (2) 앱 컨테이너(매번 새 이미지로 교체)를 띄운다.
#
# 필요한 환경변수 (호출하는 쪽에서 export):
#   IMAGE              배포할 앱 이미지 (예: oh130/fastapi-app:12)
#   APP_NAME           앱 컨테이너 이름. DB 컨테이너(<APP_NAME>-db), 네트워크(<APP_NAME>-net), 볼륨(<APP_NAME>-db-data) 이름도 여기서 만든다
#   HOST_PORT          서버에 열 포트
#   POSTGRES_PASSWORD  DB 비밀번호 (Jenkins Credentials의 Secret text `todo-db-password`). 영문/숫자 권장, 작은따옴표는 쓰지 않는다
# 선택:
#   CONTAINER_PORT     앱 컨테이너 포트 (기본 8000)
#   SKIP_PULL=1        docker pull을 건너뜀 (서버에 이미 있는 이미지로 로컬에서 시험할 때만 쓴다)
#
# 주의: DB 비밀번호는 DB 볼륨을 처음 만들 때 정해진다. 나중에 Credentials 값만 바꾸면 앱이 접속하지 못하므로,
# 바꾸려면 DB 컨테이너와 볼륨을 지우고 새로 만들어야 한다 (데이터도 지워진다).
set -euo pipefail

: "${IMAGE:?IMAGE 가 필요하다}" "${APP_NAME:?APP_NAME 이 필요하다}" "${HOST_PORT:?HOST_PORT 가 필요하다}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD 가 필요하다 (Jenkins Credentials todo-db-password)}"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
DB_NAME="${APP_NAME}-db"
NETWORK="${APP_NAME}-net"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null

if docker container inspect "$DB_NAME" >/dev/null 2>&1; then
  # 이미 있는 DB 컨테이너는 지우지 않는다 (데이터 유지). 멈춰 있으면 시작만 한다.
  docker start "$DB_NAME" >/dev/null
else
  docker run -d --name "$DB_NAME" --network "$NETWORK" \
    --restart unless-stopped \
    --security-opt no-new-privileges:true \
    -e POSTGRES_USER=todo -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -e POSTGRES_DB=todos \
    -v "${DB_NAME}-data:/var/lib/postgresql/data" \
    postgres:17-alpine >/dev/null
fi

# DB가 연결을 받을 때까지 최대 30초 기다린다 (앱도 시작할 때 연결을 재시도하지만, 배포 단계에서 먼저 확인한다)
ready=0
for _ in $(seq 1 30); do
  if docker exec "$DB_NAME" pg_isready -U todo -d todos >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" != 1 ]; then
  echo "ERROR: DB 컨테이너 $DB_NAME 가 30초 안에 준비되지 않았다" >&2
  exit 1
fi

if [ "${SKIP_PULL:-0}" != 1 ]; then
  docker pull "$IMAGE"
fi
docker rm -f "$APP_NAME" >/dev/null 2>&1 || true
docker run -d --name "$APP_NAME" --network "$NETWORK" \
  --restart unless-stopped \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -p "$HOST_PORT:$CONTAINER_PORT" \
  -e "DATABASE_URL=postgresql+psycopg://todo:${POSTGRES_PASSWORD}@${DB_NAME}:5432/todos" \
  "$IMAGE" >/dev/null

docker ps --filter "name=$APP_NAME"
