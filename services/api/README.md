# services/api — UXight API (Java 21 · Spring Boot · MySQL)

역할: CRUD · 인증 · 조회. **실행은 하지 않는다** — `POST /api/projects/{projectId}/runs` 는 runs 행을 만들고 `services/agent` 에 "시작" 한 번 호출한 뒤 끝. 이후 상태는 agent 가 MySQL 에 쓰고 여기서는 읽는다 (`docs/tech-stack.md` §4).

```sh
./gradlew build        # JDK 21 이 없으면 toolchain 이 받는다
./gradlew bootRun      # http://localhost:8080/api/health
```

환경변수는 `.env.example`.

## 스키마

- `src/main/resources/db/migration/` — Flyway. `V1` 은 최종 스키마(`schema_blueprint.sql`) 중 walking skeleton 이 쓰는 7개 테이블. 새 테이블 · 컬럼은 `V2__…` 부터.
- `src/main/resources/db/seed/R__seed_local.sql` — `local` 프로필(기본값)에서만 적용되는 테스트 데이터: 계정 `test@uxight.com`, 공용 Persona 1번.

## API 직접 호출해 보기

FE 화면이 붙기 전에는 curl 로 확인한다. 인증은 임시로 세션 쿠키(비밀번호는 아직 확인하지 않는다).

```sh
H='Content-Type: application/json'
curl -c /tmp/uxight.txt -H "$H" -d '{"email":"test@uxight.com","password":"x"}' localhost:8080/api/auth/login
curl -b /tmp/uxight.txt -H "$H" -d '{"title":"Example","targetUrl":"https://example.com","allowedDomains":["example.com"]}' localhost:8080/api/projects
curl -b /tmp/uxight.txt -H "$H" -d '{"goal":"IANA 문서 찾기","successUrl":"https://www.iana.org/help/example-domains","personaIds":[1],"mode":"diagnose"}' localhost:8080/api/projects/1/runs
curl -b /tmp/uxight.txt 'localhost:8080/api/runs?state=in_progress'   # 몇 초 뒤 state=completed
curl -b /tmp/uxight.txt -X POST localhost:8080/api/runs/1/cancel
```

FE(5173)에서 부를 때는 쿠키가 실리도록 `fetch(url, { credentials: 'include' })`.
