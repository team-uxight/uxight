# apps/web — 에이전트 안내

- 스택: React 19 + TypeScript, Vite, oxlint. 상태 · 스타일 · 컴포넌트 라이브러리는 FE 리드가 정한다 (`docs/decisions.md` O23) — 정해지기 전에 새 라이브러리를 추가하지 않는다.
- 화면 목록 · 역할(운영자 / 리서처) · 라우트는 FE 리드가 Confluence 에 정리한 화면 구성 문서를 따른다. API 는 `docs/architecture.md` §8.
- 검사: `npm run lint && npm run typecheck && npm run build && npm test -- --run` (= `make web-check`).
- 환경변수는 `VITE_` 접두사만 클라이언트에 노출된다. 비밀은 여기에 없다.
- 실행 상태(run 진행률)는 `GET /api/runs/{id}` 폴링 3초 (architecture §3.2). SSE 는 S3 이후.
