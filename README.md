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

## 버전 현황

| 버전 | 날짜 | 주차 | 주요 내용 |
|---|---|---|---|
| [v4.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v4.0.0) | 2026-09-30 | 4주차 | pytest/coverage, CI 테스트 게이트, 완료 항목 일괄삭제 |
| [v3.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v3.0.0) | 2026-09-23 | 3주차 | Docker/DockerHub 배포, 다크모드 |
| [v2.0.0](https://github.com/oh130/FastApi-Todos/releases/tag/v2.0.0) | 2026-09-16 | 2주차 | Jenkins CI/CD, 우선순위·마감일 |

## 프로젝트 구조

```
App/
├── CHANGELOG.md
├── README.md
├── docker-compose.yml
├── ci/                          # Jenkins Pipeline 스크립트 (참고용, 실제 설정은 Jenkins Job에 붙여넣음)
└── fastapi-app/
    ├── main.py                  # FastAPI 앱
    ├── todo.json                # 데이터 저장 파일
    ├── requirements.txt         # 운영 의존성
    ├── requirements-dev.txt     # UI 테스트 전용 의존성 (playwright)
    ├── pyproject.toml           # pytest 설정
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
