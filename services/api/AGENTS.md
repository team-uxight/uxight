# services/api — 에이전트 안내

- 스택: Java 21 · Spring Boot 3.5 · Gradle 8.14 · MySQL 8. 패키지 루트 `com.uxight.api`.
- **역할: CRUD · 인증(JWT · 역할) · 조회 · 정책값 · 감사 로그. 실행은 하지 않는다.** `POST /api/runs` 는 `runs` 행(`status=queued`) 을 만들고 `services/agent` 에 `POST /runs` 를 **한 번** 부른 뒤 끝난다 (architecture §3.1).
- `runs.status` 는 **agent 만 UPDATE** 한다. api 는 `dispatch_state` 와 설정 컬럼만 쓴다 (§3.3). 이 경계를 넘는 코드는 리뷰에서 막힌다.
- 스키마는 **api 쪽 마이그레이션이 유일한 소유자** — 제안은 Flyway (`src/main/resources/db/migration/V*.sql`, architecture §3.4, BE 리드 확인 후 도입). 도입 전에는 어디에도 DDL 을 넣지 않는다. 테이블 소유권은 §3.4 · §7. 스키마 PR 은 AI 리뷰어를 태운다 (CODEOWNERS).
- 검사: `./gradlew build` (= `make api-check`). 로컬: `./gradlew bootRun` → `http://localhost:8080/api/health`.
- 자격증명(`test_accounts.secret_enc`) 은 AES-GCM 으로 암호화 저장, 평문은 로그 · 응답에 없다 (§9.1, S3).
