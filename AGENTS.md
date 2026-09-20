# AGENTS.md — 코딩 에이전트 · 새 팀원 공용 안내

이 파일은 Claude Code · Codex · Cursor · Copilot 이 읽는 **팀 공용 컨텍스트**다. 사람이 읽어도 같은 내용이어야 한다.
`CLAUDE.md` 는 이 파일을 가리키기만 한다 — 규칙은 **여기 한 곳**에만 적는다. 서비스별 세부는 `apps/web/AGENTS.md` · `services/api/AGENTS.md` · `services/agent/AGENTS.md`.

## 먼저 읽을 것 (순서대로)

1. `README.md` — 구조 · 처음 한 번 · 로컬 실행
2. `docs/architecture.md` — **코드 짜기 전에.** 컴포넌트 경계 · Spring↔Python 계약 · 스키마 · Agent 권한 구조
3. `docs/agent-safety.md` — Agent 가 할 수 있는 것 / 없는 것 (D17 · D18)
4. `docs/decisions.md` — "왜" 가 궁금하면. 결정을 뒤집으려면 여기에 줄을 추가하고 PR 에 적는다
5. `docs/git-workflow.md` · `docs/secrets.md` — 첫 PR 전에

## 하지 말 것

- `docs/` 를 직접 고치지 않는다 — PM 작업공간에서 동기화된다. 틀린 게 있으면 Slack `#pm`.
- `main` · `develop` 직접 push 금지. 머지는 Squash (`docs/git-workflow.md`).
- `.env` · 키 · 토큰 · 계정을 코드 · 로그 · 프롬프트 · 커밋에 넣지 않는다 (`docs/secrets.md`). 이름은 `.env.example` 에만.
- LangChain 류 프레임워크를 추가하지 않는다 (T15). LLM 은 OpenAI-compatible SDK + pydantic.
- `services/agent` 에서 LLM 출력으로 코드 · 셸 · 임의 URL 을 실행하지 않는다. 행동은 `schemas.Action` 5종뿐이고 Runner 가드를 거친다 (D18).
- 새 서비스 · 새 큐 · 새 DB 를 만들지 않는다. 서비스는 web · api · agent 셋, 상태의 단일 진실은 MySQL (`docs/tech-stack.md` §4).

## 원칙 하나 — 가장 단순한 해 (Occam's Razor)

같은 문제를 푸는 안이 둘이면 **구성 요소 · 상태 · 예외가 적은 쪽**을 고른다. "나중에 필요할지도" 로 서비스 · 테이블 · 옵션 · 추상화를 미리 만들지 않는다 — 지금 티켓이 요구하는 것만. 복잡한 쪽을 골라야 하면 PR 본문에 이유 한 줄. 예외: Agent 안전 통제(`docs/agent-safety.md` §2.2)는 줄이지 않는다.

## 할 것

- 브랜치 이름과 커밋 제목에 Jira 키 (`GACA-nn`). PR 본문에 무엇을 · 왜 · 어떻게 확인했나.
- 커밋 전 `make check` (CI 와 같은 검사) 또는 서비스별 명령 (각 `AGENTS.md`).
- 스키마 변경은 Flyway 마이그레이션 (`services/api`) 으로만. `services/agent` 는 DDL 을 하지 않는다 (architecture §3.4).
- 모르는 것은 추측하지 말고 `docs/architecture.md` §12 (미결) 를 본 뒤 PR 에 "[확인 필요]" 로 남긴다.

## 명령

```sh
make up        # mysql · api · agent (compose). FE 는 호스트에서 npm run dev
make check     # web(lint · typecheck · build · test) · api(gradlew build) · agent(ruff · pytest)
make fmt
```

## 언어

문서 · 커밋 · PR · 코드 주석은 한국어. 식별자 · 로그 메시지 · API 필드는 영어.
