# services/api — UXight API (Java 21 · Spring Boot · MySQL)

역할: CRUD · 인증 · 조회. **실행은 하지 않는다** — `POST /api/runs` 는 runs 행을 만들고 `services/agent` 에 "시작" 한 번 호출한 뒤 끝. 이후 상태는 agent 가 MySQL 에 쓰고 여기서는 읽는다 (`docs/tech-stack.md` §4).

```sh
./gradlew build        # JDK 21 이 없으면 toolchain 이 받는다
./gradlew bootRun      # http://localhost:8080/api/health
```

환경변수는 `.env.example`.
