# Release notes

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
