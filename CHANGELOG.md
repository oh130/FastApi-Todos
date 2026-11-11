# Release notes

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
