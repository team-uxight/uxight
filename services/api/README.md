# services/api — UXight API (Java 21 · Spring Boot · MySQL)

역할: CRUD · 인증 · 조회. **실행은 하지 않는다** — `POST /api/runs` 는 runs 행을 만들고 `services/agent` 에 "시작" 한 번 호출한 뒤 끝. 이후 상태는 agent 가 MySQL 에 쓰고 여기서는 읽는다 (`docs/tech-stack.md` §4).

```sh
./gradlew build        # JDK 21 이 없으면 toolchain 이 받는다
./gradlew bootRun      # http://localhost:8080/api/health
```

환경변수는 `.env.example`.

## 이메일 인증

- `POST /api/auth/signup` — `{ "email", "password", "name" }`; 비밀번호는 영어 소문자와 숫자를 포함한 8~12자
- `POST /api/auth/login` — `{ "email", "password" }`; 응답 본문의 `accessToken`을 보호 API의 `Authorization: Bearer ...` 헤더에 사용
- `POST /api/auth/refresh` — 로그인 응답의 HttpOnly `refreshToken` 쿠키로 access token 재발급
- `POST /api/auth/logout` — refresh token 폐기 및 쿠키 삭제
- `GET /api/users/me` — 현재 로그인 계정 조회

웹 앱에서 로그인하려면 API와 MySQL을 먼저 실행한다. 로컬 웹 주소는 `http://localhost:5173`, API 주소는 `http://localhost:8080`이다. 로컬 `JWT_SECRET`이 비어 있으면 API가 임의 키를 사용하므로 재시작 시 access token은 다시 발급받아야 한다.
