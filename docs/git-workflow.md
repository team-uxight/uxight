# Git 워크플로 (v3, 2026-10-04)

흐름은 **`feat/*` → 파트 브랜치(`be` · `ai` · `fe`) → `develop` → `main`**. 파트 브랜치까지는 자유롭게 올리고, `develop` · `main` 은 PR 과 자동 검사(CI)를 거친다. 리뷰는 **권장**이고 필수는 아니다. 모르면 PM 에게.

**git 협업이 처음이면 [`git-onboarding.md`](git-onboarding.md) 부터** — 이 규칙을 명령 순서와 "실수했을 때" 로 풀어 뒀다.

10/04 에 바뀐 것: develop PR 리뷰 필수 → 권장 · GitHub 기본 브랜치 main → develop · `feat/*` 는 동시 작업용으로 자유 · 병합된 브랜치를 자동으로 지우지 않음.

## 1. 브랜치

| 브랜치 | 무엇 | push | 병합 |
| --- | --- | --- | --- |
| `main` | 진도표 · 발표 때 찍는 스냅샷. 태그 `v0.x` | 금지 | develop → main PR, PM 이. merge commit |
| `develop` | 통합 · 배포 서버가 받는 브랜치. **GitHub 기본 브랜치** | 금지 | **PR + CI 통과**, **merge commit**. 리뷰 권장 |
| `be` · `ai` · `fe` | 파트 작업 브랜치 | **파트원 직접 push** (강제 push 금지) | 기능 하나가 끝나면 develop 으로 PR |
| `feat/GACA-번호-짧은설명` | 동시 작업용 — 필요하면 자유롭게 만든다. 파트 브랜치에서 딴다 | 자유 (강제 push 는 쓰지 않는다) | 파트 브랜치로 PR — 리뷰 없이 바로 병합해도 된다. squash |
| `docs/주제` | PM 문서 | 자유 | develop 으로 PR |

**왜 develop 병합만 merge commit 인가:** squash 로 합치면 파트 브랜치가 develop 과 갈라져서 **두 번째 PR 부터 이미 올린 파일이 다시 충돌한다.** merge commit 은 파트 브랜치를 그대로 이어 가게 해 준다. GitHub 가 develop 에서는 merge commit 만 허용하도록 막아 둔다.

**병합된 브랜치는 지워지지 않는다** — Jira 티켓에서 브랜치를 찾아갈 수 있게 남겨 둔다. 병합된 `feat/` 는 다시 쓰지 않는다 (이미 합쳐진 변경이 PR 에 또 보이고 충돌하기 쉽다). 다음 작업은 새 `feat/` 로.

## 2. 하루 흐름

```sh
git switch be && git pull                 # 내 파트 브랜치 최신화
# … 작업 · 작게 자주 커밋 …
git commit -m "GACA-101 runs 테이블 Flyway V1 추가"
git push                                  # 파트 브랜치에 바로 올린다 (CI 가 돈다)
# 기능 하나가 끝나면: GitHub 에서 PR  be → develop
```

**다른 파트 변경 · 최신 문서 받기 (주 1회 이상, PR 올리기 전엔 꼭):**

```sh
git switch be && git pull
git fetch origin && git merge origin/develop --no-edit   # rebase 말고 merge — 파트 브랜치는 여럿이 쓴다
git push
```

## 3. 이름 규칙

| 대상 | 형식 | 예 |
| --- | --- | --- |
| 커밋 첫 줄 | `GACA-번호 무엇을 했나` (Jira 키 필수) | `GACA-107 관측 결과에서 숨은 요소 제거` |
| PR 제목 | `[파트] GACA-번호 기능 이름` | `[AI] GACA-107 Persona Agent 루프 1차` |
| PR 본문 | 템플릿 그대로 — 무엇을 · 왜 · **어떻게 확인했나** | 화면 변경이면 스크린샷 |
| 태그 | `v0.진척률` | `v0.2`(10/11) `v0.3`(10/18) … `v1.0`(11/15) |

Jira 키를 넣어 두면 GitHub ↔ Jira 연동 후 커밋 · PR 이 티켓에 자동으로 붙는다.

## 4. 리뷰

- **develop · main 으로 가는 PR 은 리뷰를 권장한다 (필수 아님).** 병합 조건은 CI 통과뿐이다. 다른 파트와 맞물리는 변경(API 요청 · 응답, DB, 화면이 쓰는 값)이면 리뷰를 받고 병합한다 — 서로 맞물리는 곳이 가장 잘 깨진다.
- `feat/` → 파트 브랜치 PR 은 리뷰 없이 병합해도 된다.
- PR 을 열면 아래 사람이 리뷰어로 자동 요청된다.

| PR | 리뷰어 (먼저 적힌 사람) |
| --- | --- |
| BE (`services/api`) | 박소영 → PM |
| AI (`services/agent`) | 한재완 → PM |
| FE (`apps/web`) | 이수훈 ↔ 이유진 서로 → PM |
| 문서 · compose · CI | 한재완 또는 박소영 |

- **PR 올리기 전에 자기 코딩 에이전트(Codex · Claude 등)로 한 번 셀프 리뷰.** 사람 리뷰는 설계 · 계약 위주로 본다.
- 리뷰를 부탁받으면 **24시간 안에**. 막히면 Slack 에서 멘션.
- PR 은 기능 하나 크기. 1,000줄이 넘으면 나눈다.
- 리뷰 중 이 PR 에서 안 고칠 문제는 Jira 버그로 남기고 넘어간다.

## 5. 충돌

1. 파트 브랜치에서 `git merge origin/develop` → 충돌 파일의 `<<<<<<<` 정리 → `git add` → `git commit`
2. 남의 파트 코드가 걸린 충돌이면 **그 파트 사람과 같이** 푼다.
3. 모르겠으면 멈추고 PM 호출.

## 6. 하지 말 것

- `main` · `develop` 직접 push, 어느 브랜치든 강제 push
- develop PR 을 squash 로 병합 (GitHub 가 막지만 우회하지 않는다)
- 병합된 `feat/` 브랜치를 다시 쓰기 — 새로 판다
- 토큰 · API 키 · `.env` 커밋 (`docs/secrets.md`), 빌드 산출물 · `node_modules` 커밋
- 남의 파트 브랜치에 직접 push — 필요하면 PR 로

## 7. 릴리스 (PM)

진도표 제출 금요일에 develop → main PR(merge commit) → 태그 `v0.x` → 진도표에 태그 링크를 적는다.
