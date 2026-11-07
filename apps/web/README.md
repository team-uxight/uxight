# apps/web — UXight 관리자 웹 (React + TypeScript, Vite)

```sh
npm ci && npm run dev        # http://localhost:5173
npm run lint && npm run typecheck && npm run build
```

환경변수는 `.env.example` 참고 (`VITE_API_BASE_URL`).
로컬 화면을 dev 서버 API 에 붙이려면 `.env.local` 에 `VITE_API_BASE_URL=` (빈 값) · `DEV_PROXY_TARGET` · `DEV_TEAM_COOKIE` 를 넣는다 (`.env.example` 끝 참고). 로그인 쿠키 때문에 Chrome 에서 확인한다.
