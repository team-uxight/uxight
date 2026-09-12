# 연동 세팅 절차 (UI 필요 — PM 이 직접)

API 로 못 하는 것들. 순서대로, 각 10분 내.

## 1. GitHub for Jira (GACA-37) — 브랜치·PR·커밋에 Jira 키 자동 연결

1. Jira → 앱 → **GitHub for Jira** 설치 (Atlassian Marketplace)
2. "Connect GitHub organization" → `team-uxight` 선택 → GitHub App 설치 승인
3. 확인: 브랜치 `feat/GACA-51-…` 을 push 하면 GACA-51 이슈 개발 패널에 브랜치가 뜬다
4. 스마트 커밋(`GACA-51 #done` 으로 상태 전이)은 **초반엔 끈다** — 팀원이 실수로 닫는다

## 2. Slack ↔ GitHub (GACA-38)

1. Slack 에 **GitHub** 앱 설치
2. 개발 채널: `/github subscribe team-uxight/<repo> pulls reviews comments` — `commits` 는 구독 안 함(소음)
3. `/github subscribe team-uxight/<repo> workflows:{event:"pull_request" branch:"develop"}` — CI 실패만
4. 각자 `/github signin` — 리뷰 요청 DM

## 3. Jira ↔ Slack (GACA-39)

1. Slack 에 **Jira Cloud** 앱 설치 → `proj-uxight` 연결
2. 공지 채널: `/jira subscribe` → `project = GACA AND labels = submission`
3. 개발 채널: `/jira subscribe` → `project = GACA AND issuetype = 버그` (전체 상태 변경은 시끄러움)
4. 개인 알림은 각자 `/jira notifications on`

## 4. Branch protection — 저장소 확정 후 API 로 (PM)
`main`·`develop`: PR 필수 · 리뷰 1 · CI 통과 · 강제 push 금지 · 삭제 금지. `fe`·`be`·`ai`: PR 필수 · 강제 push 금지.
