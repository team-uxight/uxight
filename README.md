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
| [`docs/git-workflow.md`](docs/git-workflow.md) | **첫 PR 전에.** 브랜치 · 커밋 · PR 규칙 |
| [`docs/secrets.md`](docs/secrets.md) | 키를 어디에 두나 |
| [`docs/jira.md`](docs/jira.md) | Jira 기한(soft) · Hard due 의미 |
| [`docs/schedule.md`](docs/schedule.md) | 학사 마감 |

기획·회의록·비용 등 나머지 문서는 Confluence(`gachoncaps`)에 있다. 이 저장소의 `docs/` 는 PM 작업공간에서 동기화된다 — **여기서 직접 고치지 말고 Slack 으로 PM 에게.**

## 구조 (예정)

```
apps/web        관리자 웹 — React + TypeScript (Vite)
apps/mobile     모바일 앱 — Expo (앱 필수 여부 확인 후)
services/api    API + 오케스트레이터 + Agent (BE 언어 확정 후)
  └ agent/      Persona Agent · Friction 진단 · 개선안 · DOM 패처
docs/           위 문서
```

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
