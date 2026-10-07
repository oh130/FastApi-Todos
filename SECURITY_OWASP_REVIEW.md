# OWASP Top 10 분석 및 SonarQube 연동 결과

대상 커밋: `56173ee` (v5.1.0)

## 1. Claude Code를 이용한 OWASP Top 10 1차 분석

`main.py`, `templates/index.html`, `Dockerfile`, CI 스크립트, `requirements.txt` 전체를 OWASP Top 10(2021) 기준으로 Claude Code가 검토했다. 발견사항과 검토의견은 다음과 같다.

**수정한 항목**

1. **테스트 코드가 운영 이미지에 그대로 포함됨 (A05 Security Misconfiguration)** — `tests/`, `tests_deploy/`, `tests_ui/`, `requirements-dev.txt`가 `.dockerignore`에서 빠져 있어서 운영에 필요 없는 코드가 이미지에 들어가고 있었다. 공격 표면과 이미지 크기만 늘리는 요소라 바로 `.dockerignore`에 추가해 제외했다.
2. **설명(description) 필드에 길이 제한이 없음 (A04 Insecure Design)** — 아주 긴 문자열을 계속 넣으면 `todo.json`과 메모리를 무한정 키울 수 있는 구조였다. `title`과 마찬가지로 `max_length=1000`을 추가해 막았다.
3. **기본 보안 응답 헤더가 없음 (A05 Security Misconfiguration)** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` 같은 헤더가 전혀 없어서 MIME 스니핑·클릭재킹에 대한 방어가 한 겹 빠져 있었다. 미들웨어 하나로 세 헤더를 모두 추가했다.

**보류(수용)한 항목**

4. **모든 `/todos` 엔드포인트에 인증이 없음 (A01 Broken Access Control)** — 네트워크에 접근 가능한 누구나 전체 CRUD를 쓸 수 있는 구조다. 다만 이 과제는 "로그인 없는 개인용 Todo 앱"이 전제이고 인증을 넣는 건 이번 과제 범위를 벗어나므로, 지금은 고치지 않고 리스크로만 기록해뒀다. 실제 서비스로 간다면 반드시 추가해야 할 항목이다.
5. **Swagger UI(`/docs`)가 운영 서버에 그대로 공개됨 (A05 Security Misconfiguration)** — 과거 주차 과제에서 Swagger UI로 수동 테스트하는 것을 요구했기 때문에 지금 닫으면 과제 진행 자체가 막힌다. 다루는 데이터도 민감하지 않은 데모 앱이라 리스크가 낮다고 판단해 열어둔 채로 뒀다.
6. **의존성이 `==`가 아니라 `>=`로만 고정되어 있음 (A06 Vulnerable and Outdated Components)** — 빌드할 때마다 실제 설치되는 버전이 달라질 수 있다. 다만 이건 가이드가 "알려진 취약점이 패치된 최소 버전을 쓰라"고 의도적으로 안내한 정책이라 수정 대상이 아니라고 판단했고, 대신 `pip-audit`을 CI에 추가해서 보완하는 쪽을 제안했다.

**이미 잘 되어 있던 부분**: Starlette를 `>=1.7.0`로 써서 Host 헤더 관련 CVE가 이미 패치되어 있었고, 프론트엔드가 `innerHTML`이 아니라 `textContent`로 사용자 입력을 렌더링해 저장형 XSS를 원천 차단하고 있었으며, 컨테이너도 root가 아닌 `appuser`로 실행되고 `cap_drop: ALL`·`no-new-privileges:true`가 이미 설정되어 있었다.

## 2. SonarQube 1차 분석 (커밋 `b80c1b9`)

Quality Gate: Passed · 코드 221줄 · 커버리지 73.4% · 중복 0.0% · 총 3건(Security 1, Maintainability 2) 발견.

1. **Dockerfile에서 `COPY . .`로 빌드 컨텍스트를 통째로 복사함 (docker:S6470, Security, High)** — 민감한 파일이 실수로 이미지에 들어갈 위험이 있다는 지적으로, Claude 1차 분석 1번과 같은 근본 원인(`COPY . .`)을 다른 각도에서 짚은 것이었다. `.dockerignore`로 막는 것보다 확실하게, 필요한 파일(`main.py`, `todo.json`, `templates/`)만 명시적으로 복사하도록 Dockerfile을 고쳤다.
2. **pytest fixture가 teardown 코드 없이 `yield`를 사용함 (python:S9100, Maintainability, Medium)** — 정리할 게 없으면 `yield`를 쓸 이유가 없다는 지적이라, `yield`를 빼고 함수 이름도 `setup_todo_file`로 바꿨다.
3. **404 응답이 API 문서에 명시되지 않음 (python:S8415, Maintainability, High)** — `update_todo`/`delete_todo`가 404를 던질 수 있는데 OpenAPI 문서에는 안 나와 있었다. 두 엔드포인트에 `responses={404: {"description": "To-Do item not found"}}`를 추가했다.

SonarQube Community Edition은 대시보드에 "SQL Injection, XSS 같은 심각한 인젝션 취약점은 스캔하지 않는다"는 경고를 직접 띄운다. 즉 SonarQube는 코드 스멜·버그·문서화 미비 같은 품질 이슈를, Claude Code는 인증·설정 노출 같은 설계 수준의 보안 이슈를 잡아내는 식으로 서로 겹치지 않고 역할이 나뉘었다.

## 3. SonarQube 2차 분석에서 새로 생긴 이슈 (수정의 부작용)

1번을 고치면서 `COPY --chown=appuser:appuser main.py todo.json ./`로 바꿨는데, 이게 "민감한 리소스를 non-root 유저가 쓰기 가능하게 복사하면 안 된다"는 규칙(docker:S6504, Security, Low)에 새로 걸렸다. 생각해보면 타당한 지적이라, 실행 중 고칠 필요가 없는 `main.py`/`templates/`는 root 소유·읽기전용으로 복사하고, 앱이 실제로 쓰기(저장)를 해야 하는 `todo.json`만 `appuser` 소유로 분리해서 다시 고쳤다. 이 규칙이 `todo.json`에 대해서는 다시 뜰 수도 있는데, 그 경우엔 "데이터 파일이라 쓰기 권한이 실제로 필요함"을 근거로 보류(수용)할 계획이다.

정리하면 Claude 1차 분석 3건 + SonarQube 1·2차 분석 4건, 총 7건 중 6건을 실제로 수정했고, 인증 부재·Swagger 공개·의존성 버전 정책 3건은 과제 요구사항과 상충하거나 의도된 설계라 근거를 남기고 보류했다.

## 4. Claude Code 활용 방법과 소감

이번 주 과제에서 Claude Code를 네 가지 방식으로 활용했다. 먼저 SonarQube를 설치하기 전에 코드 전체(약 220줄)를 OWASP Top 10 기준으로 검토하게 해서, 인증 부재나 Swagger UI 공개 같은 설계 수준의 이슈를 근거와 함께 정리받고 그중 과제와 충돌하지 않는 것들을 바로 코드로 고쳤다. 다음으로 SonarQube 1차 분석에서 나온 이슈 설명을 그대로 붙여넣었더니 원인과 고치는 방법을 설명해주고 바로 수정해줬다. 그 과정에서 Dockerfile을 고치다가 `--chown`을 그대로 옮기는 바람에 새로운 보안 이슈가 생겼는데, 이것도 "실행 중 고칠 필요 없는 파일은 root 소유로, 실제 쓰기가 필요한 파일만 appuser 소유로" 나누는 방식으로 바로 잡아줬다. 마지막으로 SonarQube(Docker 컨테이너)와 Jenkins(호스트 설치) 사이에서 Webhook이 안 가는 인프라 문제도, "컨테이너 내부망과 호스트 방화벽 대역이 다르다"는 원인을 짚어줘서 해결했다.

소감은, SonarQube와 Claude Code가 서로 다른 층위를 본다는 걸 체감했다는 것이다. SonarQube는 코드 스멜·버그·문서화 미비 같은 "품질" 관점에 강했고, Claude Code는 인증·설정 노출 같은 "설계" 수준의 보안 분석과 인프라 트러블슈팅에 강했다. 한쪽이 못 보는 부분을 다른 쪽이 메워주는 느낌이라 혼자 코드를 볼 때보다 훨씬 꼼꼼하게 점검할 수 있었고, 특히 수정하다가 새 이슈가 생기는 상황을 바로바로 같이 재분석하면서 잡아나갈 수 있었던 게 가장 크게 느껴진 장점이었다.
