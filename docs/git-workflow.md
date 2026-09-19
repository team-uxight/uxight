# Git 워크플로 가이드 (v1, 2026-09-12)

09/10 위클리 M8 합의를 문서화한 것. **처음 협업하는 사람 기준**으로 쓴다. 모르면 PM 에게 묻는다.

## 1. 브랜치

```
main      배포 가능한 것만. 직접 push 금지. develop → main 은 PM 이 릴리스 때
develop   통합 브랜치. 파트 브랜치의 PR 이 여기로 머지된다
fe / be / ai   파트 작업 브랜치. 각 파트 리드가 관리
feat/…    실제 작업은 여기서. 파트 브랜치에서 따고, 파트 브랜치로 PR
```

**피처 브랜치 이름:** `feat/GACA-123-short-desc` — Jira 키를 넣으면 이슈에 자동 연결된다 (GitHub for Jira).
버그면 `fix/GACA-123-…`, 문서면 `docs/…`.

파트 브랜치(`fe`·`be`·`ai`)를 두는 이유: 파트 안에서 자주 합치고, develop 엔 파트 단위로 안정된 것만 올리기 위해서다.
파트가 작아 부담이면 리드 판단으로 피처 → develop 직행도 된다.

## 2. 하루 흐름

```sh
git switch fe                    # 내 파트 브랜치로
git pull                         # 최신화
git switch -c feat/GACA-51-approval-screen
# … 작업 …
git add -A && git commit -m "GACA-51 승인 화면 레이아웃"
git push -u origin feat/GACA-51-approval-screen
# GitHub 에서 PR: feat/… → fe
```

- **커밋 메시지 첫 줄에 Jira 키.** `GACA-51 승인 화면 레이아웃`. 형식 강제는 안 하되 키는 필수
- 작게 자주 커밋. 하루 끝에 한 번 몰아서 올리지 않는다
- `main` · `develop` 에 직접 push 하면 protection 이 막는다

## 3. PR

- 제목에 Jira 키. 본문은 템플릿(`.github/PULL_REQUEST_TEMPLATE.md`) 따라 — **무엇을 · 왜 · 어떻게 확인했나**
- **리뷰어 1명 필수** (파트 리드 또는 PM). CODEOWNERS 가 자동 지정한다
- CI 통과 전 머지 불가
- 머지는 **Squash** — develop 이력이 PR 단위로 남는다
- 리뷰는 24시간 안에. 막히면 Slack 파트 채널에 멘션
- 리뷰 중 **이 PR 에서 안 고칠 결함**을 찾으면 GitHub Issue 를 만들고 Jira 에 버그로 짝을 만든다 (`docs/jira.md` 역할 분담)

## 4. 충돌

1. `git switch fe && git pull` 후 내 피처 브랜치에서 `git rebase fe` (또는 `git merge fe` — 둘 다 OK, 편한 걸로)
2. 충돌 파일 열어 `<<<<<<<` 정리 → `git add` → `git rebase --continue`
3. 모르겠으면 **멈추고 PM 호출.** 강제 push 는 자기 피처 브랜치에만

## 5. 하지 말 것

- `main`/`develop` 직접 push · 강제 push
- 토큰·API 키 커밋 (`docs/secrets.md`)
- 남의 피처 브랜치에 커밋 (필요하면 PR 로)
- 빌드 산출물 · `node_modules` · `.env` 커밋 (`.gitignore` 가 막지만 확인)

## 6. 릴리스 (PM)

develop → main PR. 태그 `v0.x`. 중간발표(10/20) · 최종(11/22) 전에 각 1회.
