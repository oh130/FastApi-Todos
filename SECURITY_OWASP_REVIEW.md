# OWASP Top 10 (2021) 분석 — 1차 (Claude Code)

대상 커밋: `76e4ac5` (v5.0.0, UI 리디자인 직후)
대상 파일: `fastapi-app/main.py`, `fastapi-app/templates/index.html`, `fastapi-app/Dockerfile`, `fastapi-app/.dockerignore`, `fastapi-app/requirements.txt`, `docker-compose.yml`, `ci/*.groovy`

| # | OWASP 분류 | 발견사항 | 근거(위치) | 심각도 | 검토의견 / 수정여부 |
|---|---|---|---|---|---|
| 1 | A05:2021 Security Misconfiguration | 테스트 코드·개발용 의존성(`tests/`, `tests_deploy/`, `tests_ui/`, `requirements-dev.txt`)이 `.dockerignore`에서 제외되지 않아 운영 이미지에 그대로 포함됨 | `fastapi-app/.dockerignore` | 낮음 | **수정**. 운영에 필요 없는 코드가 이미지에 들어가면 공격 표면과 이미지 크기만 늘어남. 바로 고칠 수 있는 안전한 변경이라 반영 |
| 2 | A04:2021 Insecure Design | `TodoIn.description`에 길이 제한이 없어, 매우 큰 문자열을 계속 추가하면 `todo.json` 파일과 메모리를 무한정 키울 수 있음(리소스 고갈) | `fastapi-app/main.py:22` | 낮음 | **수정**. `title`처럼 `max_length`만 추가하면 되는 저비용·무위험 변경 |
| 3 | A05:2021 Security Misconfiguration | 응답에 `X-Content-Type-Options`, `X-Frame-Options` 같은 기본 보안 헤더가 없어 MIME 스니핑·클릭재킹에 대한 방어가 한 겹 빠져 있음 | `fastapi-app/main.py` (미들웨어 없음) | 낮음 | **수정**. 소규모 미들웨어 추가로 해결되고 기존 동작에 영향 없음 |
| 4 | A01:2021 Broken Access Control | 모든 `/todos` 엔드포인트에 인증·인가가 전혀 없음 — 네트워크에 접근 가능한 누구나 전체 CRUD 가능 | `fastapi-app/main.py` 전체 | 중간 | **보류(수용)**. 과제 특성상 "개인용 Todo 앱, 별도 로그인 없음"이 전제라 지금 인증을 넣는 건 과제 범위를 벗어남. 다만 실제 서비스라면 반드시 추가해야 할 항목이라 보고서에는 남겨둠 |
| 5 | A05:2021 Security Misconfiguration | `/docs`, `/openapi.json`(Swagger UI)이 운영 서버에 그대로 공개되어 API 구조가 노출됨 | FastAPI 기본 설정 (`docs_url` 미지정) | 낮음 | **보류(수용)**. 4주차 과제에서 Swagger UI로 수동 테스트하는 것이 요구사항이라 지금 닫으면 과제 진행이 막힘. 민감 데이터가 없는 데모 앱이라 리스크도 낮다고 판단, 지금은 열어둠 |
| 6 | A06:2021 Vulnerable and Outdated Components | 의존성이 `==` 정확한 버전이 아니라 `>=` 하한선으로만 고정되어 있어, 빌드 시점마다 설치되는 실제 버전이 달라질 수 있음(재현성 저하) | `fastapi-app/requirements.txt` | 낮음 | **의도된 설계로 판단, 수정 보류**. 4주차 가이드가 의도적으로 "알려진 취약점이 패치된 최소 버전" 정책을 쓰라고 안내했음 — 오래된 취약 버전이 조용히 깔리는 걸 막기 위한 트레이드오프. `pip-audit`을 CI에 추가해 실제 설치된 버전의 취약점만 별도로 점검하는 쪽을 권장 |
| 7 | — (양호) | Starlette `>=1.7.0`로 이미 Host 헤더 관련 CVE(CVE-2026-48710 계열)가 패치된 버전을 쓰고 있음 | `fastapi-app/requirements.txt` | — | 해당 없음 — 이미 올바르게 조치됨 |
| 8 | — (양호) | 프론트엔드가 `innerHTML` 대신 `textContent`로 사용자 입력(title/description)을 렌더링해 저장형 XSS(A03:2021 Injection)를 원천 차단함 | `fastapi-app/templates/index.html` | — | 해당 없음 — 이미 올바르게 설계됨 |
| 9 | — (양호) | 컨테이너가 root가 아닌 `appuser`(UID 10001)로 실행되고, `docker-compose.yml`에 `cap_drop: ALL`, `no-new-privileges:true`가 설정되어 있음 | `fastapi-app/Dockerfile`, `docker-compose.yml` | — | 해당 없음 — 이미 올바르게 조치됨 |

## 이번 차수에서 실제로 수정한 항목 (3건)
1. `.dockerignore`에 `tests/`, `tests_deploy/`, `tests_ui/`, `requirements-dev.txt`, 각종 리포트 산출물 디렉터리 추가
2. `TodoIn.description`에 `max_length=1000` 추가
3. 모든 응답에 `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` 헤더를 추가하는 미들웨어 도입

## 보류(수용)한 항목과 근거 요약
- **인증 부재(#4)**, **Swagger UI 공개(#5)**: 과제 설계(로그인 없는 개인용 데모 앱, 수동 테스트용 Swagger UI 요구)와 충돌하고, 다루는 데이터가 민감하지 않아 현재 리스크가 낮다고 판단해 지금 단계에서는 고치지 않음
- **의존성 버전 고정 방식(#6)**: 가이드가 요구한 정책(`>=` 최소 버전)과 상충하지 않게, 고치는 대신 `pip-audit`으로 보완하는 방향 제안

## SonarQube 비교 (추후 채워 넣을 섹션)
SonarQube 1차 분석 결과가 나오면 아래에 두 도구의 발견사항을 교차 비교해 기록합니다.

| SonarQube 발견사항 | Claude 분석과 겹치는 항목 | 비고 |
|---|---|---|
| (분석 후 채움) | | |
