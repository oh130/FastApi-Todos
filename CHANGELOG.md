# Release notes

## v9.1.0 — 2026-11-26

- 쿠버네티스에 HPA(`k8s/hpa.yaml`)를 추가했습니다. CPU 사용률이 requests의 60%를 넘으면 앱 복제본을 최대 6개까지 늘리고, 부하가 사라지면 1분 뒤 줄입니다. 데이터를 DB에 두는 stateless 구조(v9.0.0)라서 복제본을 안전하게 늘릴 수 있습니다.
- 클러스터 안에서 실행하는 JMeter 부하테스트 Job(`k8s/jmeter-job.yaml`)을 추가했습니다. Service 주소로 요청을 보내 복제본들에 분산되는 실제 경로를 시험하고, 끝에 요청 수/오류/응답시간을 집계해 출력합니다.
- 같은 부하(동시 사용자 50명, 150초)로 비교한 결과: 복제본 2개 고정은 처리량 154건/초, 평균 302ms였고, HPA는 복제본을 2 → 6 → 2로 조절하며 처리량 234건/초, 평균 199ms였습니다 (오류는 모두 0건). 자세한 내용은 [k8s/README.md](k8s/README.md) 실험 8을 참고하세요.

## v9.0.0 — 2026-11-26

- **데이터 저장소를 파일(`todo.json`)에서 PostgreSQL로 바꿨습니다.** 앱이 여러 개(복제본)일 때 파일 저장 방식은 동시 쓰기가 유실되고 데이터가 갈라졌습니다(쿠버네티스 실험 2, 6). 이제 모든 앱이 같은 DB를 보고, 동시성은 앱의 `threading.Lock` 대신 DB가 처리합니다.
  - SQLAlchemy 2 + psycopg 3 사용. 접속 주소는 환경변수 `DATABASE_URL`로 정합니다. 설정이 없으면 SQLite 파일(`todo.db`)로 동작해서, DB 없이도 `uvicorn main:app`으로 로컬 실행할 수 있습니다.
  - id는 DB 시퀀스가 발급합니다 (예전의 "현재 최대값 + 1" 계산은 앱이 여러 개일 때 같은 번호를 동시에 가져갈 수 있었습니다).
  - 항목 수정은 행 잠금(`SELECT ... FOR UPDATE`)으로 읽습니다. 같은 항목을 동시에 완료 처리해도 완료 지표를 한 번만 셉니다.
  - 복제본이 동시에 시작해도 테이블 생성이 겹치지 않도록 PostgreSQL advisory lock을 쓰고, DB가 아직 뜨는 중이면 연결을 다시 시도합니다.
  - `todo_items_current` 게이지는 메모리 값이 아니라 DB를 세어서 맞춥니다 (앱이 재시작해도, 여러 개여도 같은 값).
- `docker-compose.yml`에 PostgreSQL(`postgres-sogang017`, 볼륨 `postgres-data`, healthcheck)을 추가하고, 앱은 DB가 준비된 뒤에 시작합니다. 비밀번호는 `.env`의 `POSTGRES_PASSWORD`로 설정합니다 (`.env.example` 참고).
- 쿠버네티스 매니페스트를 PostgreSQL StatefulSet + Secret + 앱 복제본 2개 구조로 바꿨습니다. 앱이 파일을 쓰지 않아서 루트 파일시스템을 읽기 전용으로 잠갔습니다.
- 같은 동시 등록 시험을 파일 방식과 DB 방식에서 각각 돌려 비교했습니다. 파일 방식은 복제본 2개에서 500 오류로 실패했고, DB 방식은 3회 모두 통과했습니다 ([k8s/README.md](k8s/README.md) 실험 7).
- 배포 후 API 테스트에 "복제본 여러 개로 동시 등록해도 유실이 없는지" 시험(`tests_deploy/test_concurrency_live.py`)을 추가했습니다.
- 단위 테스트는 임시 SQLite 파일로 돌고, `TEST_DATABASE_URL`로 비어 있는 테스트 전용 PostgreSQL을 지정하면 행 잠금 시험까지 실행됩니다.
- 저장소 정리: 실행 데이터인 `todo.json`과 컴파일 산출물(`__pycache__`)을 git에서 뺐습니다. 도커 이미지에 초기 데이터가 구워져 들어가던 것도 없앴습니다.

## v8.0.0 — 2026-11-11

- Grafana Loki + Grafana Alloy 로그 수집 스택을 추가했습니다 (Promtail은 EOL이라 공식 후속인 Alloy를 사용했습니다). Alloy가 Docker 소켓으로 `fastapi-app` 컨테이너의 stdout/stderr 로그를 읽어 Loki로 전송합니다.
- 애플리케이션 로그를 DEBUG/INFO/WARNING/ERROR 4단계로 남기도록 미들웨어를 추가했습니다. 모든 요청 로그에 `psutil`로 측정한 CPU/메모리 사용률을 같이 기록해 메트릭과 로그를 한 줄에서 상관 분석할 수 있게 했습니다.
- Grafana에 커스텀 대시보드("Counting Requests Per Path")와 커뮤니티 대시보드(ID 12611, "Logging Dashboard via Loki")를 연동했습니다. 전자는 요청 경로별 카운트, 후자는 실시간 로그 뷰·로그 레벨별 비율 등을 보여줍니다.
- docker-compose의 `fastapi-app` 컨테이너 이름이 Jenkins 배포 컨테이너와 충돌하던 문제를 수정했습니다 (`fastapi-app-sogang017` → `fastapi-app-compose-sogang017`).
- 앱 기능: To-Do 목록에 제목/설명 키워드 검색 필터를 추가했습니다 (기존 상태·우선순위 필터와 함께 적용).

## v7.0.0 — 2026-11-07

- JMeter 부하 테스트 시나리오(초기화면/조회/등록/수정/삭제 5개 엔드포인트)를 추가하고, 결과를 InfluxDB로 전송해 Grafana 대시보드로 시각화했습니다.
- Jenkins 파이프라인에 JMeter 부하 테스트 단계를 통합해 배포 직후 자동으로 실행되게 했습니다.
- 부하 테스트 중 **실제 동시성 버그를 발견**했습니다 — 동시 요청이 몰리면 `todo.json`이 손상되어 에러율 67.79%까지 치솟았습니다. `threading.Lock`과 원자적 파일 교체로 수정해 같은 부하에서 에러율 0%로 확인했고, 회귀 테스트를 추가했습니다.
- To-Do 항목 수정 방식을 `prompt()`/`confirm()` 대화상자 대신 인라인 편집 + 토스트 알림으로 교체했습니다.
- `fastapi-app` 컨테이너에 메모리/CPU 제한을 걸어 한계점을 테스트할 수 있게 했습니다.

## v6.0.0 — 2026-11-07

- Prometheus, Grafana, Node Exporter, cAdvisor를 docker-compose.yml에 추가해 애플리케이션/시스템/컨테이너 모니터링 환경을 구축했습니다.
- `/metrics` 엔드포인트를 다시 노출하고(Prometheus용), To-Do 앱 고유의 비즈니스 지표(`todo_created_total`, `todo_completed_total`, `todo_deleted_total`, `todo_items_current`)를 추가했습니다.
- Grafana에 Node Exporter Full(ID 1860), cAdvisor(ID 13946) 대시보드를 연동했습니다.

## v5.1.0 — 2026-10-07

- SonarQube 1차 분석에서 발견된 이슈 3건을 수정했습니다 (Dockerfile의 `COPY` 패턴, pytest fixture의 불필요한 `yield`, 404 응답 미문서화).
- 위 수정 중 새로 발생한 Docker 권한 이슈(런타임에 쓰기가 필요 없는 파일이 non-root 유저 소유였던 문제)를 추가로 고쳤습니다.
- SonarQube Quality Gate 통과를 확인했습니다 (2차 분석).

## v5.0.0 — 2026-10-07

- To-Do List UI를 카드형 레이아웃의 모던한 디자인으로 전면 리디자인했습니다 (다크모드 유지).
- Claude Code로 OWASP Top 10 1차 분석을 수행해 발견사항 9건을 문서화하고, 그중 3건(설명 길이 제한, 테스트 코드 이미지 제외, 보안 응답 헤더 추가)을 수정했습니다.
- Jenkins 파이프라인에 SonarQube 정적 분석 단계(테스트 이후, Docker 빌드 이전)를 추가했습니다.

## v4.0.0 — 2026-09-30

- 완료된 항목을 한 번에 지우는 "완료 항목 일괄삭제" 기능과 `DELETE /todos/completed` API를 추가했습니다.
- pytest 기반 CRUD/유효성 검사 자동 테스트(`tests/`)와 커버리지 측정을 추가했습니다.
- 배포된 서버를 대상으로 한 API 자동 테스트(`tests_deploy/`)를 추가했습니다.
- Playwright 기반 UI 자동 테스트(`tests_ui/`)를 추가했습니다.
- Jenkins 파이프라인에 테스트·커버리지·배포 후 API 테스트 단계와 HTML 리포트 게시를 추가했습니다.
- 보안 패치가 반영된 최신 fastapi/starlette/httpx2/pytest 버전으로 의존성을 갱신했습니다.

## v3.0.0 — 2026-09-23

- 다크모드 토글을 추가했습니다. 선택한 테마는 브라우저에 저장되어 다음 방문 시에도 유지됩니다.
- Docker 이미지 빌드 및 Jenkins 기반 Docker 배포 파이프라인을 구축했습니다 (본인 서버 배포, GitHub 경유 팀 서버 배포, DockerHub 경유 팀 서버 배포).
- Jenkins 빌드 실패 시 이메일로 알림을 받도록 설정했습니다.
- Docker 이미지 크기와 빌드 호환성을 위해 사용하지 않던 Prometheus 계측 코드를 제거했습니다.

## v2.0.0 — 2026-09-16

- To-Do 항목에 우선순위(높음·보통·낮음)와 마감일을 추가했습니다.
- 완료 여부와 우선순위로 목록을 필터링할 수 있습니다.
- Prometheus metrics endpoint(`/metrics`)를 추가했습니다.
- 배포 재현성을 위해 런타임 의존성 버전을 고정했습니다.
