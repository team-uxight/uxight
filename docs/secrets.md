# Secrets 규약 (v1, 2026-09-12)

## 원칙 세 줄
1. **토큰·키는 절대 커밋하지 않는다.** `.env` 는 `.gitignore` 에 있다. **push 되면**(public 이라 바로 공개된다) 즉시 폐기·재발급. push 전이면 커밋을 취소하고 키를 빼면 된다
2. 로컬은 `.env`, CI/배포는 **GitHub Secrets**. 그 외 경로 없음
3. `.env.example` 에 변수 이름을 모두 적는다. **공개해도 되는 값(LLM 모델 이름 등)은 채워 두고, 비밀(키 · 비밀번호)과 public 에 올리지 않는 값(회사 LLM 주소)은 비운다**

## 어디에 뭐가 있나

| 비밀 | 로컬 | CI · 배포 |
| --- | --- | --- |
| LLM API 키 (엘리스 MLAPI) | 루트 `.env` → `LLM_API_KEY` — compose 가 agent 에 넣는다 (LLM 은 agent 만 부른다) | GitHub Secrets `LLM_API_KEY` |
| LLM 주소 · 모델 (`LLM_BASE_URL` · `LLM_MODEL`) | 모델은 **`.env.example` 에 채워져 있다.** 주소는 회사 배포 주소라 저장소에 안 올리고 PM 이 키와 함께 DM 으로 준다 | workflow env |
| Jira API 토큰 (PM 도구) | macOS Keychain (`scripts/mcp-atlassian-capstone.sh`) | 안 씀 |
| 배포 서버 SSH 키 | PM 로컬만 | GitHub Secrets `DEPLOY_SSH_KEY` |
| MySQL 계정 | 루트 `.env` (compose) · `services/api/.env` | Secrets `DB_PASSWORD` |

## 받는 법
LLM 키는 PM 이 1인 1키로 발급. Slack DM 으로만 전달, 채널에 붙이지 않는다. 받으면 저장소 루트에서 `cp .env.example .env` 후 `LLM_BASE_URL` · `LLM_API_KEY` 두 줄을 채운다 (모델은 이미 들어 있다).

## 사고 났을 때
1. 키 폐기 (제공자 콘솔) 2. 새 키 발급·배포 3. 커밋 이력에서 제거는 PM 이 4. Slack #general 에 한 줄 공지 — 탓하지 않는다
