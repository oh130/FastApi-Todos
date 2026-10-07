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

## SonarQube 1차 분석 결과 (2026-10-07, 커밋 `b80c1b9`)

Quality Gate: Passed · Lines of Code 221 · Coverage 73.4% · Duplications 0.0% · 총 3건 (Security 1 / Reliability 0 / Maintainability 2)

| # | 룰 | 분류 | 심각도 | 발견사항 | Claude 분석과의 관계 | 검토의견 / 수정여부 |
|---|---|---|---|---|---|---|
| S1 | docker:S6470 | Security | High | `Dockerfile`에서 `COPY --chown=appuser:appuser . .`로 빌드 컨텍스트 전체를 재귀 복사 — 민감 파일이 실수로 이미지에 들어갈 위험 | Claude 1차 분석 #1(테스트 코드가 이미지에 포함되는 문제)과 같은 근본 원인(`COPY . .`)을 다른 각도에서 지적 | **수정**. `.dockerignore`로 막는 것보다 확실하게, 필요한 파일(`main.py`, `todo.json`, `templates/`)만 명시적으로 복사하도록 Dockerfile 자체를 변경 |
| S2 | python:S9100 | Maintainability | Medium | `tests/test_main.py`의 `setup_and_teardown` fixture가 teardown 코드 없이 `yield`만 사용 | 새 발견 (테스트 코드 스타일) | **수정**. `yield` 제거, 함수명도 `setup_todo_file`로 변경 (teardown이 없으니 이름도 맞게) |
| S3 | python:S8415 | Maintainability | High | `HTTPException(status_code=404)`를 던지는 `update_todo`/`delete_todo` 엔드포인트가 OpenAPI 문서(`responses=`)에 404를 명시하지 않음 | 새 발견 (API 문서화) | **수정**. 두 엔드포인트에 `responses={404: {"description": "To-Do item not found"}}` 추가 |

**SonarQube Community Edition의 한계**: 대시보드 자체에 "SQL Injection, XSS 등 심각한 인젝션 취약점은 스캔하지 않는다"는 경고가 표시됨 — 유료 에디션 기능. 즉 Claude Code의 OWASP Top 10 분석(인증 부재, Swagger 노출 등)과 SonarQube의 코드 품질 분석은 **서로 겹치지 않고 보완하는 관계**였다. SonarQube는 코드 스멜/버그/문서화 미비 같은 유지보수성 이슈를, Claude Code는 설계·구성 수준의 보안 이슈를 각각 잡아냈다.

이번 차수에 Claude 1차 분석 3건 + SonarQube 3건, 총 6건 중 수정 가능한 6건을 모두 반영했다 (인증 부재·Swagger 공개·의존성 정책 3건은 과제 요구사항과 상충하거나 의도된 설계라 보류).

## SonarQube 2차 분석에서 새로 발견된 항목 (수정의 부작용)

| # | 룰 | 분류 | 심각도 | 발견사항 | 검토의견 / 수정여부 |
|---|---|---|---|---|---|
| S4 | docker:S6504 | Security | Low | S1을 고치면서 `COPY --chown=appuser:appuser main.py todo.json ./`로 바꿨는데, 이게 "민감한 리소스를 non-root 유저가 쓰기 가능하게 복사하면 안 된다"는 규칙에 새로 걸림 | **수정**. 실행 중 고칠 필요가 없는 `main.py`/`templates/`는 root 소유·읽기전용으로 복사하고, 앱이 실제로 쓰기를 하는 `todo.json`만 `appuser` 소유로 분리 |

실제 쓰기가 필요한 `todo.json`에 대해서는 이 규칙이 다시 뜰 수 있는데, 그 경우엔 "데이터 파일이라 쓰기 권한이 실제로 필요함"을 근거로 보류(수용) 처리했다.

## Claude Code 활용 방법과 소감

이번 주 과제에서 Claude Code를 아래와 같이 활용했다.

1. **OWASP Top 10 1차 분석**: SonarQube 설치 전에, Claude Code에게 `main.py`, `templates/index.html`, `Dockerfile`, CI 스크립트, `requirements.txt` 전체를 OWASP Top 10(2021) 기준으로 검토하게 했다. 코드가 작아서(약 220줄) 전체를 한 번에 훑으며 "인증 부재", "Swagger UI 공개", "의존성 버전 정책", "description 길이 제한 없음" 같은 항목들을 근거(파일·라인)와 함께 표로 정리해줬고, 그중 과제 요구사항과 충돌하지 않는 3건을 바로 코드로 고치고 테스트까지 추가해 검증했다.
2. **SonarQube 연동 및 발견사항 대응**: SonarQube 1차 분석에서 Dockerfile `COPY` 패턴(S6470), pytest fixture의 불필요한 `yield`(S9100), API 응답 미문서화(S8415) 3건이 나왔는데, 이슈 설명을 Claude Code에 그대로 붙여넣자 각각의 원인과 고치는 방법을 설명해주고 바로 수정해줬다.
3. **수정의 부작용 디버깅**: Dockerfile을 고치는 과정에서 `--chown`을 그대로 옮기는 바람에 새로운 보안 이슈(S6504, 앱 코드가 non-root 유저 소유로 쓰기 가능한 상태)가 생겼는데, 이것도 Claude Code가 "실행 중 고칠 필요 없는 파일은 root 소유로, 실제 쓰기가 필요한 `todo.json`만 appuser 소유로" 분리하는 방식으로 바로 잡아줬다.
4. **인프라 트러블슈팅**: SonarQube(Docker 컨테이너)와 Jenkins(호스트 설치) 사이에서 Webhook이 전달되지 않는 문제가 있었는데, "컨테이너 내부망과 호스트 방화벽 대역이 다르다"는 원인을 Claude Code가 짚어줘서 `docker network inspect`로 서브넷을 확인하고 방화벽 규칙을 추가해 해결했다.

**소감**: SonarQube는 코드 스멜·버그·문서화 미비 같은 "품질" 관점의 정적 분석에 강했고, Claude Code는 인증·설정 노출 같은 "설계" 수준의 보안 분석과 인프라 트러블슈팅에 강했다. 한쪽이 못 보는 부분을 다른 쪽이 메워주는 느낌이라, 둘을 같이 쓰니 혼자 코드를 볼 때보다 훨씬 꼼꼼하게 점검이 됐다. 특히 "수정하다가 새 이슈가 생기는" 상황을 Claude Code와 함께 바로바로 재분석하면서 잡아나갈 수 있었던 게 가장 체감되는 장점이었다.
