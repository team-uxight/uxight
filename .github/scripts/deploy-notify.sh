#!/usr/bin/env bash
# deploy-dev 의 Slack 알림 — 배포 결과를 Block Kit 메시지(머리글 · PR · 바뀐 곳 · 서버 상태 · 버튼)로 보낸다.
# 입력은 워크플로가 env 로 넘긴다(deploy-dev.yml 의 notify 잡). PR 정보는 GitHub API 로 읽는다.
# 로컬 시험: DRY_RUN=1 GH=../../scripts/gh-uxight.sh REPO=team-uxight/uxight SHA=<커밋> … bash deploy-notify.sh
set -euo pipefail
GH=${GH:-gh}
RESULT=${RESULT:-}; EVENT=${EVENT:-}

# 어떤 경우인가: CI 실패 · 배포 실패 · 반영 · 그대로(서버가 다른 브랜치를 따름)
if [ -n "${CI:-}" ] && [ "$CI" != success ]; then case=ci_fail
elif [ "${DEPLOY:-}" != success ]; then case=deploy_fail
else case=${RESULT%% *}; fi                  # RESULT = "deployed fe <sha>" | "unchanged fe <sha>"
srv_branch=""; srv_full=""
if [ "$RESULT" != "${RESULT#* }" ]; then srv=${RESULT#* }; srv_branch=${srv%% *}; srv_full=${srv##* }; fi
srv_sha=${srv_full:0:7}
# 손 배포는 서버가 따르는 브랜치의 커밋을 보여 준다(실행한 브랜치가 아니라)
if [ "$EVENT" = workflow_dispatch ] && [ -n "$srv_full" ]; then BRANCH=$srv_branch; SHA=$srv_full; fi

# 이 커밋을 만든 PR (병합 커밋이면 그 PR, 직접 push 면 없음)
pr='{}'; files=''; failed=''
n=$($GH api "repos/$REPO/commits/$SHA/pulls" --jq '[.[] | select(.merged_at != null)][0].number // empty' 2>/dev/null || true)
[[ "$n" =~ ^[0-9]+$ ]] || n=""             # 커밋을 못 찾으면 API 가 오류 본문을 내놓는다
if [ -n "$n" ]; then
  pr=$($GH api "repos/$REPO/pulls/$n")
  files=$($GH api --paginate "repos/$REPO/pulls/$n/files?per_page=100" --jq '.[].filename')
fi
if [ "$case" = ci_fail ] && [ -n "${CI_RUN_ID:-}" ]; then
  failed=$($GH api "repos/$REPO/actions/runs/$CI_RUN_ID/jobs?per_page=50" \
    --jq '[.jobs[] | select(.conclusion == "failure" or .conclusion == "timed_out") | .name] | join(" · ")' 2>/dev/null || true)
fi

# 바뀐 파일을 파트별로 센다
areas=$(printf '%s\n' "$files" | awk 'NF {
  if ($0 ~ /^apps\/web\//) a = "FE"; else if ($0 ~ /^services\/api\//) a = "BE"; else if ($0 ~ /^services\/agent\//) a = "AI";
  else if ($0 ~ /^docs\//) a = "문서"; else if ($0 ~ /^(\.github\/|docker-compose|infra\/)/) a = "인프라"; else a = "기타";
  c[a]++ } END { for (k in c) printf "%s %d파일\n", k, c[k] }' | sort | paste -sd '|' - | sed 's/|/ · /g')

payload=$(jq -n \
  --arg case "$case" --arg event "${EVENT:-}" --arg actor "${ACTOR:-}" \
  --arg branch "$BRANCH" --arg sha "$SHA" --arg commit_msg "${COMMIT_MSG:-}" --arg commit_author "${COMMIT_AUTHOR:-}" \
  --arg repo_url "${SERVER_URL:-https://github.com}/$REPO" --arg run_url "${RUN_URL:-}" --arg ci_url "${CI_URL:-}" \
  --arg srv_branch "$srv_branch" --arg srv_sha "$srv_sha" --arg services "${SERVICES:-}" --arg seconds "${SECONDS_TAKEN:-}" \
  --arg areas "$areas" --arg failed "$failed" --argjson pr "$pr" '
  def esc: gsub("&"; "&amp;") | gsub("<"; "&lt;") | gsub(">"; "&gt;");
  def link($u; $t): "<" + $u + "|" + ($t | esc | gsub("\\|"; "/")) + ">";
  def btn($t; $u; $s): {type: "button", text: {type: "plain_text", text: $t[0:75], emoji: true}, url: $u}
                       + (if $s == "" then {} else {style: $s} end);
  def dur: ($seconds | tonumber) as $s | (if $s >= 60 then "\($s / 60 | floor)분 " else "" end) + "\($s % 60)초";

  ($pr.number // null) as $num |
  ([($pr.title // ""), ($pr.head.ref // ""), $commit_msg] | map(select(test("GACA-[0-9]+")) | capture("(?<k>GACA-[0-9]+)").k) | first // "") as $jira |
  ($commit_msg | split("\n")[0]) as $commit_title |
  ($sha[0:7]) as $short |
  ($pr.body // "" | split("\n")
     | (map(test("^## 무엇을")) | index(true)) as $i
     | if $i == null then "" else .[$i + 1:] | (map(test("^## ")) | index(true)) as $j | (if $j == null then . else .[:$j] end)
         | map(select(test("\\S") and (test("^\\s*<!--") | not))) | first // "" end) as $summary |

  (if $case == "ci_fail" then ":x: CI 실패 · \($branch)"
   elif $case == "deploy_fail" then ":warning: dev 서버 배포 실패 · \($branch)"
   elif $case == "deployed" and $event == "workflow_dispatch" then ":hammer_and_wrench: dev 서버 다시 배포 · \($srv_branch)"
   elif $case == "deployed" then ":white_check_mark: dev 서버 반영 · \($branch)"
   elif $case == "unchanged" then ":large_blue_circle: \($branch) 갱신 · dev 서버는 그대로"
   else ":grey_question: 확인 필요 · \($branch)" end) as $header |

  (if $num then "*" + link($pr.html_url; "#\($num) \($pr.title)") + "*"
   elif $event == "workflow_dispatch" then "*Actions 탭에서 손으로 실행*"
   else "*" + ($commit_title | esc) + "*" end) as $title |

  ([ {type: "mrkdwn", text: ("*브랜치*\n" + ($branch | esc) + (if ($pr.head.ref // "") != "" then " ← " + ($pr.head.ref | esc) else "" end))},
     {type: "mrkdwn", text: ("*커밋*\n" + link("\($repo_url)/commit/\($sha)"; $short)
        + (if $num then " · 작성 " + ($pr.user.login | esc)
             + (if ($pr.merged_by.login // "") != "" and $pr.merged_by.login != $pr.user.login then " · 병합 " + ($pr.merged_by.login | esc) else "" end)
           elif $event == "workflow_dispatch" then " · 실행 " + ($actor | esc)
           elif $commit_author != "" then " · " + ($commit_author | esc) else "" end))},
     {type: "mrkdwn", text: ("*바뀐 곳*\n" + (if $num then (if $areas != "" then $areas else "파일 없음" end)
        + "\n커밋 \($pr.commits)개 · +\($pr.additions) −\($pr.deletions)" else "직접 push (PR 없음)" end))},
     {type: "mrkdwn", text: ("*dev 서버*\n" +
        (if $case == "deployed" then "\($srv_branch)@\($srv_sha) 반영"
         elif $case == "unchanged" then "\($srv_branch)@\($srv_sha) 그대로\n(서버는 \($srv_branch) 를 따름)"
         elif $case == "ci_fail" then "배포 안 함"
         else "배포 실패 — 실행 로그 확인" end)
        + (if $services != "" and ($case == "deployed" or $case == "unchanged") then "\n서비스 \($services) 실행 중" else "" end)
        + (if $seconds != "" and $case == "deployed" then " · \(dur)" else "" end))}
   ] + (if $failed != "" then [{type: "mrkdwn", text: ("*실패한 검사*\n" + ($failed | esc))}] else [] end)) as $fields |

  ((if $num then [btn("PR #\($num) 보기"; $pr.html_url; (if ($case == "deployed" or $case == "unchanged") then "primary" else "" end))] else [] end)) as $pr_btn |
  ((if $jira != "" then [btn("Jira \($jira)"; "https://proj-uxight.atlassian.net/browse/\($jira)"; "")] else [] end)) as $jira_btn |
  (if $case == "ci_fail" then [btn("CI 로그"; $ci_url; "danger")] + $pr_btn + $jira_btn
   elif $case == "deploy_fail" then [btn("실행 로그"; $run_url; "danger")] + $pr_btn + $jira_btn
   else $pr_btn + $jira_btn + [btn("dev 서버 열기"; "https://dev.uxight.duckdns.org"; ""), btn("실행 로그"; $run_url; "")] end) as $buttons |

  {
    text: (($header | sub("^:[a-z_]+: "; "")) + " — " + (if $num then "#\($num) \($pr.title)" else $commit_title end)),
    blocks: (
      [ {type: "header", text: {type: "plain_text", text: $header[0:150], emoji: true}},
        {type: "section", text: {type: "mrkdwn", text: ($title + (if $summary != "" then "\n>" + ($summary | esc)[0:280] else "" end))}},
        {type: "section", fields: $fields} ]
      + (if $branch == "develop" and ($case == "deployed" or $case == "unchanged")
         then [{type: "context", elements: [{type: "mrkdwn", text: "develop 이 바뀌었어요. 작업 브랜치에서 `git pull origin develop` 으로 받아 주세요."}]}]
         else [] end)
      + [{type: "actions", elements: $buttons}] )
  }')

if [ -n "${DRY_RUN:-}" ]; then printf '%s\n' "$payload"; exit 0; fi
[ -n "${SLACK_WEBHOOK_URL:-}" ] || { echo "SLACK_WEBHOOK_URL 없음 — 알림 건너뜀"; exit 0; }
printf '%s' "$payload" | curl -fsS -X POST -H 'Content-Type: application/json' --data @- "$SLACK_WEBHOOK_URL" > /dev/null
echo "Slack 알림 보냄: $case"
