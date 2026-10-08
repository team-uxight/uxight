# services/api — 에이전트 안내

- 스택: Java 21 · Spring Boot 3.5 · Gradle 8.14 · MySQL 8. 패키지 루트 `com.uxight.api`.
- **역할: CRUD · 인증(JWT · 역할) · 조회 · 정책값 · 감사 로그. 실행은 하지 않는다.** `POST /api/projects/{projectId}/runs` 는 `runs` 행(`status=queued`) 을 만들고 커밋한 뒤 `services/agent` 에 `POST /runs {run_id}` 를 **한 번** 부르고 끝난다 (architecture §3.1).
- `runs.status` 는 **agent 만 UPDATE** 한다. api 는 `dispatch_state` 와 설정 컬럼만 쓴다 (§3.3). 이 경계를 넘는 코드는 리뷰에서 막힌다.
- 스키마는 **api 쪽 Flyway 마이그레이션이 유일한 소유자** (`src/main/resources/db/migration/V*.sql`, architecture §3.4). 최종 스키마는 `schema_blueprint.sql`(BE 리드 관리)이고, `V1` 은 그중 walking skeleton 이 쓰는 7개 테이블이다. **머지된 V 파일은 고치지 않는다** — 테이블 · 컬럼 추가는 기능 티켓에서 `V2__…` 부터 blueprint 를 그대로 옮긴다. 테이블 소유권은 §3.4 · §7. 스키마 PR 은 AI 리뷰어를 태운다 (CODEOWNERS).
- API 는 설계 문서(서비스 REST API 설계 · 오류 코드 8.4)를 따른다. 실패 응답은 `GlobalExceptionHandler` 가 공통 본문(`code` · `message` · `fieldErrors`)으로 만든다 — 서비스는 `ApiException(ErrorCode.…)` 를 던지고, 새 코드는 8.4 표에서 `ErrorCode` 로 옮긴다. 남의 자원은 404.
- 인증은 임시로 세션 쿠키다 (`SessionConst.LOGIN_USER_ID`). JWT 로 바꿀 때 `LoginCheckInterceptor` · `AuthController` 만 교체하고, 컨트롤러는 계속 userId 하나만 받는다.
- 검사: `./gradlew build` (= `make api-check`). 로컬: `./gradlew bootRun` → `http://localhost:8080/api/health`.
- 자격증명(`test_accounts.secret_enc`) 은 AES-GCM 으로 암호화 저장, 평문은 로그 · 응답에 없다 (§9.1, S3).
