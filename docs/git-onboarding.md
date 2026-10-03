# Git 협업 가이드 (v1, 2026-10-04)

**git 으로 여럿이 일해 본 적이 별로 없다면 이것부터.** 규칙과 이유는 [`git-workflow.md`](git-workflow.md) 에 있고, 이 문서는 그 규칙대로 **손을 움직이는 순서**다.

- 예시는 `fe` 기준이다. 자기 파트(`be` · `ai`)로 바꿔 읽는다. `GACA-번호` 는 내 Jira 티켓 번호로.
- 명령은 터미널 기준이다. VS Code · IntelliJ 의 Git 버튼으로 해도 순서만 같으면 된다.
- 막히면 **아무것도 지우지 말고 멈춘 뒤** `git status` 결과를 Slack 에 붙여 PM 에게.

## 0. 한눈에

| 언제 | 무엇을 | 리뷰 |
| --- | --- | --- |
| 매일 | 내 파트 브랜치(`fe` · `be` · `ai`)에 커밋 · push | 없음 |
| 여럿이 동시에 작업할 때 | `feat/` 브랜치에서 작업 → 파트 브랜치로 PR | 없음 (바로 병합해도 된다) |
| 기능 하나가 끝나면 | 파트 브랜치 → `develop` 으로 PR | 권장. 자동 검사(CI)는 통과해야 병합된다 |
| 진도표 제출 때 | `develop` → `main` | PM 이 한다 |

- 흐름은 **`feat/` → 파트 브랜치 → `develop` → `main`**. GitHub 기본 브랜치는 `develop` 이다.
- **PR**(Pull Request) = "내 브랜치를 저 브랜치에 합쳐 주세요" 하는 요청. 리뷰와 자동 검사가 여기서 돈다.
- `main` · `develop` 에는 직접 push 가 안 된다. 강제 push(`--force`)는 어디서도 쓰지 않는다 — `main` · `develop` · 파트 브랜치는 GitHub 가 막지만, `feat/` 는 안 막혀 있어서 팀원 커밋이 날아간다.
- 남의 파트 브랜치에는 push 하지 않는다 (막혀 있진 않다). `docs/` 는 PM 이 관리한다 — 고칠 게 보이면 Slack 으로.

## 1. 처음 한 번

```sh
git clone https://github.com/team-uxight/uxight.git
cd uxight
git switch fe                          # 받은 직후엔 develop 에 있다 → 내 파트 브랜치로

# 이름 · 이메일 (이 저장소에만). public 이라 커밋 이메일이 공개된다 → GitHub → Settings → Emails 에서
# "Keep my email addresses private" 를 켜고 거기 나온 noreply 주소를 쓴다 (병합 버튼 커밋도 noreply 가 된다)
git config user.name "홍길동"
git config user.email "숫자+아이디@users.noreply.github.com"
git config pull.rebase false           # pull 은 merge 로. 안 하면 둘이 같은 브랜치에 push 했을 때 pull 이 멈춘다
```

- 이어서 런타임(Node · Java · uv)과 pre-commit 을 설치한다 — 명령은 [README "처음 한 번"](../README.md#처음-한-번). pre-commit 은 커밋할 때 비밀 키가 섞였는지 먼저 잡아 준다 — 꼭 켠다.
- push 때 로그인이 안 되면 GitHub CLI 로 한 번: `gh auth login` (설치는 `brew install gh`). GitHub 비밀번호로는 push 가 안 된다.
- 이미 받아 둔 사람은 `git fetch origin` → `git switch fe` → 위 `git config` 세 줄.

## 2. 매일 — 내 파트 브랜치에서

```sh
git switch fe && git pull              # 시작 전에 최신으로
# … 작업 …
git status                             # 바뀐 파일 목록
git add apps/web/src/pages/Login.tsx   # 올릴 파일만 담는다
git commit -m "GACA-번호 로그인 화면 레이아웃"
git push                               # 파트 브랜치엔 바로 올라간다
```

- **작게 자주.** 하루치를 커밋 하나에 몰지 않는다.
- 커밋 첫 줄은 `GACA-번호 무엇을 했나`. 이 번호가 Jira 티켓과 코드를 잇는다.
- `git add .` 은 `git status` 로 목록을 확인한 뒤에만 — 키가 든 설정 파일 · 큰 데이터가 같이 들어가기 쉽다.
- push 하면 자동 검사(CI)가 돈다. GitHub **Actions** 탭에 빨간 ✗ 가 뜨면 눌러서 로그를 본다. 로컬에서는 자기 파트만: `make web-check` · `make api-check` · `make agent-check`.

**여럿이 동시에 작업할 때**는 `feat/` 브랜치를 자유롭게 만들어 쓴다.

```sh
git switch fe && git pull
git switch -c feat/GACA-번호-login-layout       # 파트 브랜치에서 딴다
# … 커밋 …
git push -u origin feat/GACA-번호-login-layout  # -u 는 처음 한 번만
```

GitHub 에서 PR 을 열 때 **base 를 `fe` 로** 바꾼다 (기본값은 `develop`). 리뷰 없이 바로 **Squash and merge** 해도 된다. 병합된 `feat/` 는 지워지지 않고 남는다 — Jira 티켓에서 찾아갈 수 있게. **다시 쓰지 말고** 다음 작업은 새 `feat/` 로 (이미 합쳐진 변경이 PR 에 또 보이고 충돌하기 쉽다).

## 3. develop 받아 오기 — 주 1회 이상, PR 올리기 전엔 꼭

다른 파트가 develop 에 올린 것을 내 파트 브랜치로 가져온다.

```sh
git switch fe && git pull
git fetch origin                       # GitHub 의 최신 상태를 받아 온다
git merge origin/develop --no-edit     # origin/develop = GitHub 에 있는 develop
git push
```

- **rebase 는 쓰지 않는다.** 이미 올린 이력을 고쳐 쓰게 되고, 그걸 올리려면 강제 push 가 필요한데 막혀 있다.
- `CONFLICT` 가 뜨면 아래 "6. 충돌이 났을 때".

## 4. 기능 하나가 끝나면 — develop 으로 PR

1. 위 "3. develop 받아 오기" 대로 develop 을 먼저 받는다. 충돌은 PR 화면이 아니라 **내 브랜치에서** 푼다.
2. 자기 코딩 에이전트(Codex · Claude 등)로 셀프 리뷰를 한 번.
3. GitHub → **Pull requests → New pull request** → 위쪽을 **`base: develop` ← `compare: fe`** 로 맞춘다. base 는 기본값이 `develop` 이니 compare 만 내 파트 브랜치로 고르면 된다.
4. 제목은 `[FE] GACA-번호 로그인 화면`. 본문은 템플릿 칸을 채운다 — **어떻게 확인했나**는 필수, 화면이 바뀌었으면 스크린샷.
5. 리뷰어는 자동으로 요청된다 — BE · AI 코드는 상대 파트 사람과 PM, FE 코드는 다른 FE 한 명과 PM. **리뷰는 권장**이다 — 다른 파트와 맞물리는 변경(API 요청 · 응답, DB, 화면이 쓰는 값)이면 승인을 받고 병합한다. PR 에 적은 Jira 티켓은 **QA** 로 옮긴다.
6. **자동 검사가 통과**하면 올린 사람이 **Create a merge commit** 으로 병합한다 (develop 은 이 방식만 열려 있다). 티켓은 **완료** 로.

- 병합 버튼이 회색(**Merging is blocked**)이면 자동 검사가 아직 돌고 있거나 실패한 것이다. 버튼 위 목록에 뭐가 남았는지 나온다.
- PR 이 열려 있는 동안 파트 브랜치에 push 한 커밋은 팀원 것이라도 **그 PR 에 같이 들어간다** (받아 둔 승인도 풀린다). 리뷰를 기다리는 동안 다른 작업은 push 를 미루거나 `feat/` 에서.
- 병합해도 파트 브랜치는 지워지지 않는다. 그대로 이어서 쓴다.
- PR 은 기능 하나 크기. 1,000줄이 넘으면 나눈다.

## 5. 리뷰를 부탁받으면

- **24시간 안에.** PR → **Files changed** → 줄 옆 `+` 로 코멘트 → **Review changes** → *Approve*(승인) 또는 *Request changes*(수정 요청).
- 볼 곳은 **내 파트와 맞물리는 부분** — API 요청 · 응답 모양, DB 컬럼, 화면에 띄우는 값. 형식 · 스타일은 짚지 않는다 (셀프 리뷰 몫).
- 이 PR 에서 안 고칠 문제는 Jira 버그로 남기고 승인해도 된다.

## 6. 충돌이 났을 때

`git merge` · `git pull` 뒤 `CONFLICT` 가 뜨면:

1. `git status` → **both modified** 로 나오는 파일이 충돌 난 파일이다.
2. 파일을 열면 아래 표시가 있다. 남길 내용만 남기고 표시 세 줄(`<<<<<<<` · `=======` · `>>>>>>>`)을 지운다. VS Code 는 그 위에 버튼을 띄워 준다 — **Current** = 내 것, **Incoming** = 들어온 것, **Both** = 둘 다.

   ```
   <<<<<<< HEAD
   내 브랜치의 내용
   =======
   들어온 내용
   >>>>>>> origin/develop
   ```

3. `git add 그파일` → `git commit --no-edit` → `git push`.

- **남의 파트 코드가 걸리면 혼자 고르지 말고 그 사람과 같이.**
- 모르겠으면 `git merge --abort` — merge 하기 전으로 그대로 돌아간다. 그다음 PM 호출.
- `git stash pop` · `git cherry-pick` 에서 난 CONFLICT 는 위 방법이 안 맞는다 — 그대로 두고 PM 호출 (stash 는 지워지지 않고 남아 있다).

## 7. 실수했을 때

| 상황 | 이렇게 |
| --- | --- |
| push 가 `[rejected]` (fetch first · non-fast-forward) | GitHub 쪽이 앞서 있다 (팀원이 올렸거나 GitHub 에서 병합함). `git pull` → `git push` |
| push 가 `GH006` · `GH013` 으로 거부 | `main` · `develop` 에 올리려 한 것. 바로 아래 "커밋 후에 브랜치가 틀린 걸 알았다" 대로 옮긴다 |
| 커밋 **후**에 브랜치가 틀린 걸 알았다 | `git log --oneline -3` 으로 커밋번호 확인 → `git switch fe` → `git cherry-pick 커밋번호` → `git push`. 틀린 쪽은 `git branch -f main origin/main` (develop 이면 develop) 으로 원래대로 |
| 커밋 **전**에 브랜치가 틀린 걸 알았다 | `git switch fe` — 고친 파일은 따라온다. 안 되면 `git stash` → `git switch fe` → `git stash pop` |
| `git pull` 이 `local changes … would be overwritten` | 먼저 커밋하거나, `git stash` → `git pull` → `git stash pop` |
| push 전, 커밋 메시지를 고치고 싶다 | `git commit --amend -m "GACA-번호 고친 메시지"` |
| push 전, 마지막 커밋을 취소 (고친 내용은 남김) | `git reset --soft HEAD~1` |
| push 한 커밋을 되돌리고 싶다 | `git revert --no-edit 커밋번호` → `git push` (되돌리는 커밋이 새로 생긴다. 병합 커밋이면 PM 호출) |
| **비밀 키 · `.env` 를 커밋했다** | push 전: `git reset --soft HEAD~1` → `git restore --staged 그파일` (파일째 뺀다. 키만 지웠으면 `git add 그파일`) → 다시 커밋. **push 했으면 지워도 이미 공개됐다** → 바로 PM 에게, 키 폐기 · 재발급 ([secrets.md "사고 났을 때"](secrets.md)) |
| `git pull` · `git revert` 뒤 낯선 편집 화면(vim)이 떴다 | 커밋 메시지 확인 화면이다. `Esc` → `:wq` → Enter |
| PR base 를 잘못 골랐다 | PR 제목 옆 **Edit** → base 를 바꾼다 |
