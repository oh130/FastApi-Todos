# FastApi-Todos — DevOps 수업 실습 기록

FastAPI로 만든 간단한 To-do List 앱입니다. 매주 데브옵스 수업에서 배운 내용을 이 프로젝트에 실제로 적용해가며 발전시키고 있어서, 앱 기능 변경 이력이 곧 수업 진도 기록이기도 합니다. 상세한 기능 변경 내역은 [CHANGELOG.md](CHANGELOG.md), GitHub Release([링크](https://github.com/oh130/FastApi-Todos/releases))를 참고하세요.

> Week 0(Git 이전에 한 주가 더 있었는지)은 이 레포 기록만으로는 확인이 안 돼서 비워뒀습니다. 있었다면 내용 채워 넣으면 됩니다.

## 주차별 진행 기록

### Week 1 — 기본 앱 & Git (2026-09-09)
- FastAPI로 To-do CRUD API 최초 구현 (`GET/POST/PUT/DELETE /todos`)
- Git 저장소 초기화, GitHub 원격 저장소 연결, 첫 커밋/푸시

### Week 2 — Jenkins CI/CD 입문 (v2.0.0, 2026-09-16)
- Ubuntu 서버에 Jenkins 설치(apt), 초기 관리자 계정 설정
- Jenkins Credentials에 배포 전용 SSH 키페어(`jenkins_deploy`, ID: `deploy-key`) 등록
- SSH Agent 플러그인 설치
- Jenkins Pipeline으로 "GitHub 코드 checkout → venv 생성 → 의존성 설치 → uvicorn 실행" 배포 자동화 구성
  - 본인 서버 배포, 팀 서버 배포(GitHub 경유 / 직접 scp 배포) — 총 3개 Job
- 앱 기능: 우선순위(`priority`)·마감일(`due_date`) 필드 추가, 상태/우선순위 필터링, Prometheus `/metrics` 엔드포인트

### Week 3 — Docker 컨테이너화 (v3.0.0, 2026-09-23)
- `Dockerfile` 작성 (non-root 사용자로 실행, 의존성 레이어 캐시 분리)
- `docker-compose.yml` 작성, `.dockerignore` 추가
- DockerHub 가입 및 Personal Access Token 발급, Jenkins Credentials 등록
- Jenkins Pipeline에 Docker 이미지 빌드/배포 단계 추가 — GitHub+docker-compose 경유, DockerHub 이미지 push/pull 경유 두 가지 방식
- Jenkins 빌드 실패 시 Gmail SMTP로 이메일 알림 발송 설정
- 앱 기능: 다크모드 토글 추가 (localStorage에 저장)
- 사용하지 않는 Prometheus 계측 코드 제거 (Docker 이미지 경량화)

### Week 4 — 자동 테스트 & CI 품질 게이트 (v4.0.0, 2026-09-30)
- `pytest` + `pyproject.toml`로 단위 테스트 구성 (CRUD, 유효성 검사, 404/422 케이스)
- `pytest-cov`로 코드 커버리지 측정, `pytest-html`로 HTML 테스트 리포트 생성
- Jenkins에 **HTML Publisher** 플러그인 설치, 파이프라인에서 pytest/coverage 리포트를 빌드 화면에 게시
- Jenkins Pipeline: Checkout → 테스트/커버리지 → Docker 빌드 → DockerHub Push → 배포 → **배포된 서버 대상 API 자동 테스트**까지 한 번에 수행
- `httpx2` 기반 배포 후 API 스모크 테스트(`tests_deploy/`), Playwright 기반 브라우저 UI 테스트(`tests_ui/`) 추가
- 보안 패치가 반영된 fastapi/starlette/httpx2/pytest 최신 버전으로 의존성 갱신
- 앱 기능: 완료 항목 일괄삭제 (`DELETE /todos/completed`)

### Week 5 — 정적 분석: SonarQube & OWASP Top 10 (v5.0.0 / v5.1.0, 2026-10-07)
- Docker로 SonarQube 설치, Jenkins Pipeline에 "테스트 이후 → Docker 빌드 이전" 단계로 정적 분석 추가
- SonarQube Scanner 플러그인, Webhook 연동(Quality Gate 결과를 Jenkins 빌드에 반영)
- Claude Code로 OWASP Top 10(2021) 1차 분석 수행, 발견사항 9건 문서화 → [SECURITY_OWASP_REVIEW.md](SECURITY_OWASP_REVIEW.md)
- 1차 분석(3건: 테스트코드 이미지 포함, description 길이 무제한, 보안 헤더 부재) 수정 → v5.0.0
- SonarQube 1차 분석 발견 3건(Dockerfile COPY 패턴, 불필요한 yield, 404 미문서화) + 수정 중 새로 생긴 이슈 1건까지 수정, 2차 분석 확인 → v5.1.0
- 앱 기능: UI 전면 리디자인(카드형 레이아웃)

### Week 6 — 모니터링: Prometheus & Grafana (v6.0.0, 2026-11-07)
- `docker-compose.yml`에 Prometheus, Grafana, Node Exporter, cAdvisor 추가
- `/metrics` 엔드포인트 재노출, Grafana에 Node Exporter Full(ID 1860)·cAdvisor(ID 13946) 대시보드 연동
- 앱 기능: To-do 앱 고유의 Prometheus 비즈니스 지표 추가 (`todo_created_total`, `todo_completed_total`, `todo_deleted_total`, `todo_items_current`)

### Week 7 — 부하 테스트: JMeter & InfluxDB (v7.0.0, 2026-11-07)
- JMeter 테스트 플랜 작성(초기화면/조회/등록/수정/삭제 5개 엔드포인트), 전용 Docker 이미지로 패키징
- InfluxDB 추가 + JMeter Backend Listener로 부하테스트 결과를 실시간 전송, Grafana 대시보드(ID 4026 등)로 시각화
- Jenkins Pipeline에 JMeter 부하테스트 단계 통합 (배포 직후 자동 실행)
- `fastapi-app` 컨테이너에 메모리/CPU 제한을 걸어 한계점 테스트
- **부하 테스트로 실제 동시성 버그 발견**: 동시 요청이 몰리면 `todo.json`이 손상되어 에러율 67.79% 발생 → `threading.Lock` + 원자적 파일 교체(`os.replace`)로 수정, 같은 부하에서 에러율 0%로 확인 (회귀 테스트 추가)
- 앱 기능: `prompt()`/`confirm()` 기반 수정 UX를 인라인 편집 + 토스트 알림으로 교체

### Week 8 — 로그 수집: Grafana Loki & Alloy (v8.0.0, 2026-11-11)
- `docker-compose.yml`에 Grafana Loki + Grafana Alloy 추가 (Promtail은 EOL이라 공식 후속인 Alloy 사용)
- Alloy가 Docker 소켓으로 `fastapi-app` 컨테이너 로그를 읽어 Loki로 전송하도록 파이프라인 구성 (`alloy/config.alloy`)
- 요청 로그를 DEBUG/INFO/WARNING/ERROR 4단계로 남기도록 미들웨어 추가, 모든 로그에 `psutil` CPU/메모리 사용률 같이 기록 (메트릭-로그 상관 분석용)
- Grafana에 커스텀 대시보드("Counting Requests Per Path")와 커뮤니티 대시보드(ID 12611, "Logging Dashboard via Loki") 연동
- `fastapi-app` 컨테이너 이름이 Jenkins 배포 컨테이너와 충돌하던 문제 수정 (`fastapi-app-sogang017` → `fastapi-app-compose-sogang017`)
- 앱 기능: To-Do 목록에 제목/설명 키워드 검색 필터 추가

## 버전 현황

| 버전 | 날짜 | 주차 | 주요 내용 |
|---|---|---|---|
| [v8.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v8.0.0) | 2026-11-11 | 8주차 | Grafana Loki/Alloy 로그 수집, 컨테이너 이름 충돌 수정, 검색 필터 |
| [v7.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v7.0.0) | 2026-11-07 | 7주차 | JMeter 부하테스트, InfluxDB, 동시성 버그 수정, 인라인 편집 |
| [v6.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v6.0.0) | 2026-11-07 | 6주차 | Prometheus/Grafana 모니터링, 비즈니스 지표 |
| [v5.1.0](https://github.com/oh130/FastApi-Todos/releases/tag/v5.1.0) | 2026-10-07 | 5주차 | SonarQube 2차 분석, 발견사항 수정 |
| [v5.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v5.0.0) | 2026-10-07 | 5주차 | SonarQube 연동, OWASP Top 10 분석, UI 리디자인 |
| [v4.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v4.0.0) | 2026-09-30 | 4주차 | pytest/coverage, CI 테스트 게이트, 완료 항목 일괄삭제 |
| [v3.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v3.0.0) | 2026-09-23 | 3주차 | Docker/DockerHub 배포, 다크모드 |
| [v2.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v2.0.0) | 2026-09-16 | 2주차 | Jenkins CI/CD, 우선순위·마감일 |

## 프로젝트 구조

```
App/
├── CHANGELOG.md
├── README.md
├── SECURITY_OWASP_REVIEW.md     # Claude Code OWASP Top 10 / SonarQube 분석 결과
├── docker-compose.yml           # fastapi-app, jmeter, influxdb, sonarqube, prometheus, grafana, node-exporter, loki, alloy
├── .env.example                 # Grafana 관리자 비밀번호 등 (.env로 복사해서 사용, git에 안 올라감)
├── ci/                          # Jenkins Pipeline 스크립트 (참고용, 실제 설정은 Jenkins Job에 붙여넣음)
├── prometheus/prometheus.yml    # Prometheus 스크레이프 설정
├── jmeter/                      # JMeter Dockerfile + 부하테스트 시나리오(.jmx)
├── alloy/config.alloy           # Grafana Alloy 로그 수집 파이프라인 설정
└── fastapi-app/
    ├── main.py                  # FastAPI 앱
    ├── todo.json                # 데이터 저장 파일
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

`http://127.0.0.1:8000` 접속.

## 테스트 실행

```bash
cd fastapi-app
pip install -r requirements.txt pytest-playwright
pytest tests --html=pytest_report/report.html --self-contained-html --cov=. --cov-report=html:htmlcov
```
