# Secrets 규약 (v1, 2026-09-12)

## 원칙 세 줄
1. **토큰·키는 절대 커밋하지 않는다.** `.env` 는 `.gitignore` 에 있고, 커밋되면 즉시 폐기·재발급
2. 로컬은 `.env`, CI/배포는 **GitHub Secrets**. 그 외 경로 없음
3. 각 서비스에 `.env.example` 을 두고 **키 이름만** 적는다. 값은 비운다

## 어디에 뭐가 있나

| 비밀 | 로컬 | CI · 배포 |
| --- | --- | --- |
| LLM API 키 (회사 API / OpenRouter) | `services/api/.env` → `LLM_API_KEY` | GitHub Secrets `LLM_API_KEY` |
| LLM base URL · 모델 ID | `.env` (비밀 아님, 환경별 값) | workflow env |
| Jira API 토큰 (PM 도구) | macOS Keychain (`scripts/mcp-atlassian-capstone.sh`) | 안 씀 |
| 배포 서버 SSH 키 | PM 로컬만 | GitHub Secrets `DEPLOY_SSH_KEY` |
| Expo 자격 (앱 있으면) | `apps/mobile/.env` | Secrets |

## 받는 법
LLM 키는 PM 이 1인 1키로 발급 (OpenRouter 는 키별 spend limit). Slack DM 으로만 전달, 채널에 붙이지 않는다.

## 사고 났을 때
1. 키 폐기 (제공자 콘솔) 2. 새 키 발급·배포 3. 커밋 이력에서 제거는 PM 이 4. Slack #general 에 한 줄 공지 — 탓하지 않는다
