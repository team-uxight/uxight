# apps/web — UXight 관리자 웹 (React + TypeScript, Vite)

```sh
npm ci && npm run dev        # http://localhost:5173
npm run lint && npm run typecheck && npm run build
```

환경변수는 `.env.example` 참고 (`VITE_API_BASE_URL`).
로컬 화면을 dev 서버 API 에 붙이려면 `.env.local` 에 `VITE_API_BASE_URL=` (빈 값) · `DEV_PROXY_TARGET` · `DEV_TEAM_COOKIE` 를 넣는다 (`.env.example` 끝 참고). 로그인 쿠키 때문에 Chrome 에서 확인한다.

운영자 계정·권한 화면에서 리서처 계정을 생성하면 초기 비밀번호는 생성 직후 한 번만 표시된다. 안전한 방법으로 사용자에게 전달한 뒤 확인해야 창을 닫을 수 있다.
