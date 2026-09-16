# UXight

**AI Agent 기반 UI/UX 개선 플랫폼** — 가천대학교 2026-2 심화전공프로젝트, 팀 UXight.

LLM 가상 사용자로 웹 사용성 테스트를 대신 돌리고, 행동 로그에서 UX 문제를 진단해 개선안을 제안하며,
승인된 개선안을 자동 적용해 재실험으로 효과를 검증한다. 사용자는 UX 리서처 한 명이다.

## 문서 — 코드보다 먼저

| 읽을 것 | 언제 |
| --- | --- |
| [`docs/product-direction.md`](docs/product-direction.md) | **범위가 궁금할 때.** In / Out / Phase 2, 유저 플로우, 성공 기준 |
| [`docs/decisions.md`](docs/decisions.md) | "왜 이렇게 정했지?" — 결정 한 줄씩, 근거·날짜 |
| [`docs/tech-stack.md`](docs/tech-stack.md) | 스택과 그 근거 |
| [`docs/architecture.md`](docs/architecture.md) | **코드 짜기 전에.** 컴포넌트 경계 · Spring↔Python 계약 · 스키마 초안 · Agent 권한 구조 · 09/27 walking skeleton |
| [`docs/agent-safety.md`](docs/agent-safety.md) | Agent 계정 · 격리 · 행동 제한 요구사항 (교수님 Q1·Q2) |
| [`docs/git-workflow.md`](docs/git-workflow.md) | **첫 PR 전에.** 브랜치 · 커밋 · PR 규칙 |
| [`docs/secrets.md`](docs/secrets.md) | 키를 어디에 두나 |
| [`docs/jira.md`](docs/jira.md) | Jira 기한(soft) · Hard due 의미 |
| [`docs/schedule.md`](docs/schedule.md) | 학사 마감 |

기획·회의록·비용 등 나머지 문서는 Confluence(`gachoncaps`)에 있다. 이 저장소의 `docs/` 는 PM 작업공간에서 동기화된다 — **여기서 직접 고치지 말고 Slack 으로 PM 에게.**

## 구조

```
apps/web          관리자 웹 — React + TypeScript (Vite)            → @team-uxight/fe
services/api      API — Java 21 · Spring Boot 3.5 (Gradle 8.14) · MySQL (CRUD · 인증 · 조회) → @team-uxight/be
services/agent    Agent — Python 3.12 · FastAPI · Playwright (실행 전부)     → @team-uxight/ai
docs/             위 문서
docker-compose.yml  로컬 3 서비스 (mysql · api · agent) + web 프로필
```

경계: `api` 는 실행하지 않는다. `POST /api/runs` → runs 행 생성 → `agent` 에 `POST /runs` 한 번(fire-and-forget).
이후 상태·로그는 `agent` 가 MySQL 에 쓰고 `api` 가 읽는다. 09/27 walking skeleton 게이트(GACA-69)가 이 경로를 검증한다.

## 처음 한 번

```sh
# 런타임 — 버전은 .tool-versions (mise/asdf) · .nvmrc (CI setup-node) · services/agent/.python-version (uv)
nvm install 22 && nvm use            # 또는 fnm
sdk install java 21-tem              # 없어도 됨: gradle toolchain 이 JDK 21 을 받는다
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install pre-commit && pre-commit install   # 커밋 전 검사 (secrets · ruff)
```

## 로컬 실행

백엔드 3종은 compose 로, **FE 는 호스트에서** 돌린다 — 컨테이너 web 은 up 마다 `npm ci` 를 해서 느리다.

```sh
cp .env.example .env                 # 값 채우기 (docs/secrets.md)
make up                              # mysql · api · agent — 첫 빌드는 느리다
make logs

cd apps/web && npm install && npm run dev    # FE 는 호스트에서
```

| 서비스 | 주소 | 어디서 |
| --- | --- | --- |
| web | http://localhost:5173 | 호스트 (`npm run dev`) |
| api | http://localhost:8080/api/health | compose |
| agent | http://localhost:8000/health | compose |
| mysql | 127.0.0.1:3306 (`uxight`) | compose |

포트는 전부 `127.0.0.1` 에만 바인딩된다 — 같은 네트워크의 다른 기기에서 보이지 않는다.
web 까지 컨테이너로 돌려야 하면 `docker compose --profile web up -d`.

서비스 하나만 돌릴 땐 각 디렉터리의 README (`npm run dev` · `./gradlew bootRun` · `uv run uvicorn …`).
`make check` 가 CI 와 같은 검사를 돌린다.

## 브랜치

`main` ← `develop` ← `fe` / `be` / `ai` ← `feat/GACA-123-…`. 자세한 건 `docs/git-workflow.md`.

## 팀

| | 역할 |
| --- | --- |
| 안준석 | PM · 인프라 |
| 이수훈 | FE Lead |
| 한재완 | BE Lead · AI |
| 박소영 | AI Lead |
| 이유진 | FE · BE |
