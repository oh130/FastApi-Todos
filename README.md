# FastApi-Todos — DevOps 수업 실습 기록

FastAPI로 만든 간단한 To-do List 앱입니다. 매주 데브옵스 수업에서 배운 내용을 이 프로젝트에 실제로 적용해가며 발전시키고 있어서, 앱 기능 변경 이력이 곧 수업 진도 기록이기도 합니다. 상세한 기능 변경 내역은 [CHANGELOG.md](CHANGELOG.md), GitHub Release([링크](https://github.com/oh130/FastApi-Todos/releases))를 참고하세요.

## 진행 기록

### 기본 앱 & Git (2026-09-09)
- FastAPI로 To-do CRUD API 최초 구현 (`GET/POST/PUT/DELETE /todos`)
- Git 저장소 초기화, GitHub 원격 저장소 연결, 첫 커밋/푸시

### v2.0.0 — Jenkins CI/CD 입문 (2026-09-16)
- Ubuntu 서버에 Jenkins 설치(apt), 초기 관리자 계정 설정
- Jenkins Credentials에 배포 전용 SSH 키페어(`jenkins_deploy`, ID: `deploy-key`) 등록
- SSH Agent 플러그인 설치
- Jenkins Pipeline으로 "GitHub 코드 checkout → venv 생성 → 의존성 설치 → uvicorn 실행" 배포 자동화 구성
  - 본인 서버 배포, 팀 서버 배포(GitHub 경유 / 직접 scp 배포) — 총 3개 Job
- 앱 기능: 우선순위(`priority`)·마감일(`due_date`) 필드 추가, 상태/우선순위 필터링, Prometheus `/metrics` 엔드포인트

### v3.0.0 — Docker 컨테이너화 (2026-09-23)
- `Dockerfile` 작성 (non-root 사용자로 실행, 의존성 레이어 캐시 분리)
- `docker-compose.yml` 작성, `.dockerignore` 추가
- DockerHub 가입 및 Personal Access Token 발급, Jenkins Credentials 등록
- Jenkins Pipeline에 Docker 이미지 빌드/배포 단계 추가 — GitHub+docker-compose 경유, DockerHub 이미지 push/pull 경유 두 가지 방식
- Jenkins 빌드 실패 시 Gmail SMTP로 이메일 알림 발송 설정
- 앱 기능: 다크모드 토글 추가 (localStorage에 저장)
- 사용하지 않는 Prometheus 계측 코드 제거 (Docker 이미지 경량화)

### v4.0.0 — 자동 테스트 & CI 품질 게이트 (2026-09-30)
- `pytest` + `pyproject.toml`로 단위 테스트 구성 (CRUD, 유효성 검사, 404/422 케이스)
- `pytest-cov`로 코드 커버리지 측정, `pytest-html`로 HTML 테스트 리포트 생성
- Jenkins에 **HTML Publisher** 플러그인 설치, 파이프라인에서 pytest/coverage 리포트를 빌드 화면에 게시
- Jenkins Pipeline: Checkout → 테스트/커버리지 → Docker 빌드 → DockerHub Push → 배포 → **배포된 서버 대상 API 자동 테스트**까지 한 번에 수행
- `httpx2` 기반 배포 후 API 스모크 테스트(`tests_deploy/`), Playwright 기반 브라우저 UI 테스트(`tests_ui/`) 추가
- 보안 패치가 반영된 fastapi/starlette/httpx2/pytest 최신 버전으로 의존성 갱신
- 앱 기능: 완료 항목 일괄삭제 (`DELETE /todos/completed`)

### v5.0.0 / v5.1.0 — 정적 분석: SonarQube & OWASP Top 10 (2026-10-07)
- Docker로 SonarQube 설치, Jenkins Pipeline에 "테스트 이후 → Docker 빌드 이전" 단계로 정적 분석 추가
- SonarQube Scanner 플러그인, Webhook 연동(Quality Gate 결과를 Jenkins 빌드에 반영)
- Claude Code로 OWASP Top 10(2021) 1차 분석 수행, 발견사항 9건 문서화 → [SECURITY_OWASP_REVIEW.md](SECURITY_OWASP_REVIEW.md)
- 1차 분석(3건: 테스트코드 이미지 포함, description 길이 무제한, 보안 헤더 부재) 수정 → v5.0.0
- SonarQube 1차 분석 발견 3건(Dockerfile COPY 패턴, 불필요한 yield, 404 미문서화) + 수정 중 새로 생긴 이슈 1건까지 수정, 2차 분석 확인 → v5.1.0
- 앱 기능: UI 전면 리디자인(카드형 레이아웃)

### v6.0.0 — 모니터링: Prometheus & Grafana (2026-11-07)
- `docker-compose.yml`에 Prometheus, Grafana, Node Exporter, cAdvisor 추가
- `/metrics` 엔드포인트 재노출, Grafana에 Node Exporter Full(ID 1860)·cAdvisor(ID 13946) 대시보드 연동
- 앱 기능: To-do 앱 고유의 Prometheus 비즈니스 지표 추가 (`todo_created_total`, `todo_completed_total`, `todo_deleted_total`, `todo_items_current`)

### v7.0.0 — 부하 테스트: JMeter & InfluxDB (2026-11-07)
- JMeter 테스트 플랜 작성(초기화면/조회/등록/수정/삭제 5개 엔드포인트), 전용 Docker 이미지로 패키징
- InfluxDB 추가 + JMeter Backend Listener로 부하테스트 결과를 실시간 전송, Grafana 대시보드(ID 4026 등)로 시각화
- Jenkins Pipeline에 JMeter 부하테스트 단계 통합 (배포 직후 자동 실행)
- `fastapi-app` 컨테이너에 메모리/CPU 제한을 걸어 한계점 테스트
- **부하 테스트로 실제 동시성 버그 발견**: 동시 요청이 몰리면 `todo.json`이 손상되어 에러율 67.79% 발생 → `threading.Lock` + 원자적 파일 교체(`os.replace`)로 수정, 같은 부하에서 에러율 0%로 확인 (회귀 테스트 추가)
- 앱 기능: `prompt()`/`confirm()` 기반 수정 UX를 인라인 편집 + 토스트 알림으로 교체

### v8.0.0 — 로그 수집: Grafana Loki & Alloy (2026-11-11)
- `docker-compose.yml`에 Grafana Loki + Grafana Alloy 추가 (Promtail은 EOL이라 공식 후속인 Alloy 사용)
- Alloy가 Docker 소켓으로 `fastapi-app` 컨테이너 로그를 읽어 Loki로 전송하도록 파이프라인 구성 (`alloy/config.alloy`)
- 요청 로그를 DEBUG/INFO/WARNING/ERROR 4단계로 남기도록 미들웨어 추가, 모든 로그에 `psutil` CPU/메모리 사용률 같이 기록 (메트릭-로그 상관 분석용)
- Grafana에 커스텀 대시보드("Counting Requests Per Path")와 커뮤니티 대시보드(ID 12611, "Logging Dashboard via Loki") 연동
- `fastapi-app` 컨테이너 이름이 Jenkins 배포 컨테이너와 충돌하던 문제 수정 (`fastapi-app-sogang017` → `fastapi-app-compose-sogang017`)
- 앱 기능: To-Do 목록에 제목/설명 키워드 검색 필터 추가

### 쿠버네티스 — 로컬 클러스터 실습 (2026-11-17)
- Docker Desktop 내장 쿠버네티스(kind 모드, 노드 1개)에 앱을 올려, compose에서 하던 설정을 쿠버네티스 방식으로 옮겨 봄 → 매니페스트와 실험 기록은 [k8s/](k8s/README.md)
  - Deployment + Service(ClusterIP, `kubectl port-forward`로 접속)
  - `resources.limits`: compose의 `mem_limit: 128m`, `cpus: 0.5` 대응
  - readiness/liveness probe, `securityContext`(non-root, 권한 상승 금지, capability 전체 제거)
  - PVC(1Gi)를 `/data`에 마운트해 데이터를 파드 밖에 저장
- 실제로 실행해서 확인한 동작
  - 파드를 삭제하면 Deployment가 새 파드를 띄워 자동 복구
  - 메모리 한도를 20Mi로 낮추면 새 파드는 OOMKilled → CrashLoopBackOff, 기존 파드는 계속 `Running`이라 서비스는 유지 (롤링 업데이트)
  - 이미지 태그 변경 후 롤링 업데이트, `rollout undo`로 롤백
  - 볼륨 없이 복제본 2개: 파드마다 `todo.json`을 따로 가져 조회 결과가 갈라짐 (5건 / 3건)
  - PVC 적용 후 파드를 삭제해도 데이터 유지
  - PVC를 공유하는 복제본 2개에 동시 POST 40건: 13건 유실. `main.py`의 락(`threading.Lock`)이 프로세스 안에서만 유효해서 파드 사이의 동시 쓰기를 막지 못함 → 파일 저장 방식은 복제본 1개 전제, 늘리려면 DB 필요
  - 같은 태그로 이미지를 다시 빌드하면 노드에 캐시된 옛 이미지가 계속 쓰이는 문제 확인 (태그를 바꿔서 해결)
- 앱 변경: 저장 파일 경로를 환경변수 `TODO_FILE`로 지정할 수 있게 함 (기본값은 기존 `todo.json`이라 compose 배포는 그대로)
- 로컬 클러스터에서만 실습했고, 서버에는 배포하지 않음. HPA와 클러스터 대상 부하테스트는 해보지 않음

### v9.0.0 — 데이터 저장소를 DB로 (2026-11-26)
- 데이터를 파일(`todo.json`)에서 **PostgreSQL**로 옮김. 쿠버네티스 실험에서 복제본을 늘리면 파일 저장 방식은 데이터가 갈라지고(실험 2) 동시 쓰기가 유실(실험 6)되는 한계를 확인했고, 그 한계를 DB로 해결
- SQLAlchemy 2 + psycopg 3. 접속 주소는 환경변수 `DATABASE_URL`(없으면 SQLite 파일). id는 DB 시퀀스가 발급하고, 수정은 행 잠금(`SELECT ... FOR UPDATE`)으로 읽음
- `docker-compose.yml`에 PostgreSQL 추가(볼륨, healthcheck, 앱은 DB 준비 후 시작), 쿠버네티스는 Postgres StatefulSet + Secret + 앱 복제본 2개
- 전/후 비교: 같은 동시 등록 시험이 파일 방식(복제본 2개)에서는 500 오류로 실패, DB 방식에서는 3회 모두 통과 → [k8s/README.md](k8s/README.md) 실험 7
- 배포 후 API 테스트에 복제본 여러 개 동시 등록 시험 추가, 단위 테스트는 임시 SQLite(또는 `TEST_DATABASE_URL`의 PostgreSQL)로 실행
- `todo.json`, `__pycache__`를 git에서 제거

## 버전 현황

| 버전 | 날짜 | 주요 내용 |
|---|---|---|
| v9.0.0 | 2026-11-26 | PostgreSQL 전환(복제본 확장 가능), 동시 쓰기 유실 해결 |
| [v8.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v8.0.0) | 2026-11-11 | Grafana Loki/Alloy 로그 수집, 컨테이너 이름 충돌 수정, 검색 필터 |
| [v7.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v7.0.0) | 2026-11-07 | JMeter 부하테스트, InfluxDB, 동시성 버그 수정, 인라인 편집 |
| [v6.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v6.0.0) | 2026-11-07 | Prometheus/Grafana 모니터링, 비즈니스 지표 |
| [v5.1.0](https://github.com/oh130/FastApi-Todos/releases/tag/v5.1.0) | 2026-10-07 | SonarQube 2차 분석, 발견사항 수정 |
| [v5.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v5.0.0) | 2026-10-07 | SonarQube 연동, OWASP Top 10 분석, UI 리디자인 |
| [v4.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v4.0.0) | 2026-09-30 | pytest/coverage, CI 테스트 게이트, 완료 항목 일괄삭제 |
| [v3.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v3.0.0) | 2026-09-23 | Docker/DockerHub 배포, 다크모드 |
| [v2.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v2.0.0) | 2026-09-16 | Jenkins CI/CD, 우선순위·마감일 |

## 프로젝트 구조

```
App/
├── CHANGELOG.md
├── README.md
├── SECURITY_OWASP_REVIEW.md     # Claude Code OWASP Top 10 / SonarQube 분석 결과
├── docker-compose.yml           # fastapi-app, postgres, jmeter, influxdb, sonarqube, prometheus, grafana, node-exporter, loki, alloy
├── .env.example                 # Grafana·PostgreSQL 비밀번호 (.env로 복사해서 사용, git에 안 올라감)
├── ci/                          # Jenkins Pipeline 스크립트 (참고용, 실제 설정은 Jenkins Job에 붙여넣음)
├── prometheus/prometheus.yml    # Prometheus 스크레이프 설정
├── jmeter/                      # JMeter Dockerfile + 부하테스트 시나리오(.jmx)
├── alloy/config.alloy           # Grafana Alloy 로그 수집 파이프라인 설정
├── k8s/                         # 로컬 쿠버네티스 실습 (앱 Deployment, Postgres StatefulSet, Service, Secret) + 실험 기록
└── fastapi-app/
    ├── main.py                  # FastAPI 앱
    ├── database.py              # DB 연결, 테이블 모델 (환경변수 DATABASE_URL)
    ├── requirements.txt         # 운영 의존성
    ├── requirements-dev.txt     # UI 테스트 전용 의존성 (playwright)
    ├── pyproject.toml           # pytest 설정
    ├── sonar-project.properties # SonarQube 분석 설정
    ├── Dockerfile / .dockerignore
    ├── templates/index.html     # 프론트엔드
    ├── tests/                   # 단위 테스트 (TestClient)
    ├── tests_deploy/            # 배포된 서버 대상 API 테스트
    └── tests_ui/                # Playwright UI 테스트
```

## 로컬 실행

```bash
cd fastapi-app
python -m venv venv
venv\Scripts\activate   # (Windows) / source venv/bin/activate (macOS·Linux)
pip install -r requirements.txt
uvicorn main:app --reload
```

`http://127.0.0.1:8000` 접속. `DATABASE_URL`을 지정하지 않으면 앱 폴더의 SQLite 파일(`todo.db`)에 저장합니다.
PostgreSQL을 쓰려면 `DATABASE_URL=postgresql+psycopg://todo:<비밀번호>@<호스트>:5432/todos`를 지정합니다.
docker compose로 실행하면 `.env`의 `POSTGRES_PASSWORD`로 PostgreSQL 컨테이너가 함께 뜨고 앱이 자동으로 연결됩니다.

## 쿠버네티스 로컬 실행

Docker Desktop의 Settings > Kubernetes에서 Enable 한 뒤:

```bash
docker build -t fastapi-todo:db ./fastapi-app
kubectl create secret generic todo-db --from-literal=POSTGRES_PASSWORD='원하는비밀번호'
kubectl apply -f k8s/fastapi-todo.yaml
kubectl port-forward svc/fastapi-todo 8000:8000   # http://localhost:8000
```

실험 방법과 결과는 [k8s/README.md](k8s/README.md)를 참고하세요.

## 테스트 실행

```bash
cd fastapi-app
pip install -r requirements.txt pytest-playwright
pytest tests --html=pytest_report/report.html --self-contained-html --cov=. --cov-report=html:htmlcov
```

단위 테스트는 임시 SQLite 파일로 실행됩니다. PostgreSQL에서 실행하려면(행 잠금 시험 포함) **비어 있는 테스트 전용 DB**를 지정하세요.
테스트가 시작할 때마다 테이블을 지우고 다시 만들기 때문에 실제 데이터가 있는 DB를 가리키면 안 됩니다.

```bash
TEST_DATABASE_URL=postgresql+psycopg://todo:<비밀번호>@localhost:5432/todos_test pytest tests
```
