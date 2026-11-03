# services/agent — UXight Agent (Python 3.12 · FastAPI · Playwright)

역할: **실행 전부** — Persona Agent 루프 · 행동 로그 · Friction 진단 · 개선안 · 재실험. api 는 `POST /runs` 한 번만 부른다.
LLM 은 OpenAI-compatible SDK + pydantic 만 (LangChain 없음, T15). LLM 이 낼 수 있는 행동은 `schemas.Action` 5종뿐 (D18).

```sh
uv sync                      # .venv 생성 (dev 포함)
uv run playwright install chromium   # 처음 한 번
uv run uvicorn uxight_agent.main:app --reload   # http://localhost:8000/health
uv run ruff check . && uv run pytest
```

환경변수는 `.env.example`. 실행 로그(JSON)는 `data/` — 커밋하지 않는다.

**LLM 호출은 `uxight_agent/llm.py` 의 `LLMClient.chat()` 으로만.** 호출마다 사용량(토큰 · 비용 · 시간 · 역할 · 실행 id)이 `data/llm-usage.jsonl` 에 한 줄씩 남는다 — 키 · 프롬프트 · 응답 본문은 남기지 않는다. 비용은:

```sh
uv run python -m uxight_agent.usage_report                  # 전체, 역할별
uv run python -m uxight_agent.usage_report --days 1 --by run  # 최근 하루, 실행별
uv run python -m uxight_agent.usage_report --log data/llm-usage.jsonl data/bench/*/usage.jsonl --by day  # 운영 + benchmark
```

단가는 OpenRouter 기준이고(`usage_report.py` 의 단가표), 호출마다 그때의 단가로 센 `cost_usd` 가 같이 남는다. 단가표가 나중에 바뀌어도 지난 비용은 안 바뀐다.

## Persona 종료 이유 (GACA-218)

`run_personas.status` 의 끝 값이다. Persona 진행 API(`GET /api/runs/{runId}/personas`)가 그대로 넘긴다.

| 값 | 뜻 |
| --- | --- |
| `done` | Agent 가 done 을 냈다 (성공, 메인 판정 기준) |
| `max_steps` | step 상한까지 돌았다 |
| `token_limit` | 토큰 상한으로 끝났다. 토큰 상한(회차 당)과 하루 토큰 예산 둘 다 이 값이다 (아래) |
| `stuck` | 같은 화면이 3번 이어져 끝냈다 (아래) |
| `timeout` | 시간 상한에 걸렸다 |
| `fail` | 실행 오류로 끝났거나, 행동을 얻지 못한 step 이 3번 이어졌다 |
| `cancelled` | 회차가 취소됐다 |

- `token_limit` 의 두 상한은 감사 로그 `agent.limit_reached` 의 `reason` 으로 가른다.
  - `max_tokens`: 토큰 상한(회차 당, 정책 `max_tokens`)이다. 회차 안 Persona 가 나눠 쓴다.
  - `daily_token_budget`: 하루 토큰 예산(`policies.daily_token_budget`)이다. 오늘 시작한 회차의 토큰 합으로 센다.
- `stuck` 은 같은 화면의 관측이 3번 이어지면, 세 번째 관측의 step 까지 마치고 끝낸다.
  - 같은 화면은 요소 줄(step 로그의 `elements_hash`)과 지금 화면 안의 본문 글이 둘 다 같은 것이다. 펼침처럼 누른 뒤 본문 글만 바뀌어도 다른 화면이다.
  - 본문 글은 step 로그에 없다. 그래서 stuck 은 step 로그만으로 다시 셀 수 없다.
  - 관측 사이의 행동마다 세는지 정하고, 세지 않는 행동 뒤에는 처음부터 다시 센다.
  - 브라우저에 보낸 click · back 은 센다. select 를 누른 것도 센다 — 이 드라이버에서는 select 를 눌러도 값이 바뀌지 않는다.
  - scroll 은 본문 글이 있으면 센다. 페이지 가운데에서는 본문 글이 바뀌어 같은 화면이 아니고, 페이지 끝에서 되풀이하면 같은 화면이다.
  - 본문 글이 비면(benchmark 의 본문 글 끔 변형 등) scroll 은 세지 않는다. 요소 줄에는 화면 아래 요소도 있어, scroll 이 화면을 바꿨는지 알 수 없다.
  - 본문이 안쪽 스크롤 상자에 든 페이지(SPA 등)는 드라이버의 scroll(창 스크롤)로 움직이지 않는다. 그래서 scroll 두 번이면 stuck 이 될 수 있다 — 사이트의 UX 문제가 아니라 드라이버의 한계다. 열린 모달은 예외다(아래 '관측 전 기다림 · 모달').
  - type 과 입력칸(input 의 텍스트 · 체크 계열, textarea) click 은 세지 않는다. 입력값 · 체크 상태는 요소 줄에도 본문 글에도 없어서, 세면 폼을 채우는 Persona 가 끝난다.
  - 가드 차단은 세지 않는다. 가드 끔(benchmark)에서 가드가 막았을 행동도 세지 않아, 가드 켬 · 끔에서 세는 규칙이 같다.
  - 행동을 얻지 못한 step 은 `fail` 규칙이 맡는다.
- `max_steps` · `token_limit` · `stuck` · `timeout` 은 마지막 행동 뒤 화면을 `step-<n+1>.png` 로 남길 수 있다.
  - stuck 은 세 번째 행동을 보지 않으므로, 마지막 화면이 빠져나간 뒤의 화면일 수 있다(max_steps 와 같은 규칙).
- 진행률(`runs.progress`)은 `done` · `max_steps` · `token_limit` · `stuck` 을 센다.
- benchmark 의 `personas.jsonl` 에 있는 `outcome` 도 같은 값을 쓴다.

## 관측 전 기다림 · 모달 (GACA-157)

- 관측 전에 화면이 멎기를 기다린다. DOM · SoM 이 같은 기준이고, 최대 1.5초(`STILL_WAIT_MS`)다.
  - 주 창 문서가 보낸 fetch · XHR 이 끝나기를 기다린다. 받아 온 글을 나중에 넣는 페이지가 많다. iframe 의 요청은 세지 않는다. iframe 안 글은 관측에 들지 않는다.
  - 글이나 누를 것이 든 요소의 끝이 있는 애니메이션과 창의 부드러운 스크롤이 멎기를 기다린다. 처음엔 투명했다가 나타나는 글(결함 사본의 미끼 DST-ANIM)도 이것으로 첫 관측에 든다.
  - 상한을 넘기면 그대로 관측한다. 늦게 온 글은 다음 관측에 들어온다. 상한까지 끝나지 않은 요청은 버린다. 오래 열어 두는 요청(long poll) 하나로 관측마다 상한을 다 쓰지 않는다.
  - 주 창에 새 문서가 들어오면 앞 문서의 요청은 잊는다. 같은 문서 안 주소 변경(pushState · 해시)에는 계속 기다린다.
  - 허용 밖 페이지에서는 기다리지 않는다. 기다림 스크립트를 허용 밖 페이지에서 돌리지 않는다.
  - 학교 사본 71쪽에서 기다림은 0.6초 안팎이었다(11/03). 대부분 메뉴 링크의 글자색 전환(0.3~0.4초)이다.
- 모달이 열려 있으면 그 안만 관측한다. 요소 줄 · 클릭이 걸린 칸 · 본문 글 모두 그렇다.
  - 모달은 브라우저 모달 dialog(showModal), 또는 화면을 다 덮는 고정 위치 층이다. 층은 화면 가운데와 네 귀퉁이 근처 다섯 점의 맨 위 요소를 모두 품어야 한다. role · aria 표시가 없는 레이어 팝업도 잡는다.
  - 모달 dialog 가 여럿 열려 있으면 맨 위(화면 가운데 요소가 든 것)만 본다.
  - 화면 일부만 가리는 팝업은 모달이 아니다. 보이는 글도 누를 것도 없는 막(투명 막, 스크린 리더용 숨김 글만 든 dim)도 모달이 아니다.
  - 모달이 열려 있으면 scroll 은 창 대신 그 안의 스크롤 상자를 움직인다. 화면 가운데 요소에서 가장 가까운 상자다. 긴 모달의 아래쪽도 볼 수 있다.
  - 못 잡는 모양: dim 과 팝업이 형제이고 팝업이 dim 밖에 있는 레이어 팝업. 전처럼 뒤 요소도 관측에 든다.

## 성능 benchmark (GACA-179)

같은 사본 · Task · Persona 로 변형(관측 모드 등)만 바꿔 돌리고, 지표를 표 하나로 낸다.

- 운영과 같은 코드로 돈다: Persona 루프 · 드라이버 · 가드 · LLM 판단기 · step 로그와 성공 판정.
- **DB 를 쓰지 않는다.** 결과는 `--out` 폴더에만 남아, 운영자 화면에 벤치 회차가 섞이지 않는다.
- LLM 설정은 서버와 같은 env(`LLM_BASE_URL` · `LLM_API_KEY` · `LLM_MODEL`)다.

```sh
uv run python -m uxight_agent.bench ../../config/bench-school.json --out data/bench/<이름> \
  --serve original=<원본 사본 폴더> --serve seedA=<결함 사본 폴더>
```

**설정 파일** (JSON, 예: `config/bench-school.json`). 칸의 모양은 `uxight_agent/bench.py` 의 `BenchConfig` 이고, 상대 경로는 설정 파일 폴더 기준이다.

| 칸 | 뜻 |
| --- | --- |
| `personas_file` · `personas` | Persona 파일과 돌릴 Persona id |
| `tasks` | `goal` · `success_rule` · `success_url`. 성공 URL 은 `/` 로 시작하는 경로(`/kor/3126/subview.do`)이고, 사이트마다 그 주소에 붙는다 |
| `sites` | `name` · `url`(시작 URL). `--serve 이름=폴더` 로 띄우는 사이트는 경로만, 아니면 주소 전체를 쓴다 |
| `sites[].original` | 원본 사본(심은 결함 0)이면 `true`. 여기서 나온 진단은 모두 오탐으로 센다 |
| `sites[].answers` | 결함 사본의 정답 파일 |
| `sites[].findings` | `{변형 이름: 진단 결과 파일}`. 진단 결과는 findings 표의 행을 담은 JSON 배열이다. 원본 사본이나 정답 파일이 있는 사이트에만 쓴다 |
| `sites[].allowed_domains` | 회차의 허용 도메인과 같다. 시작 URL 의 호스트는 늘 허용한다. 하위 요청(글꼴 · 스크립트)도 이 목록으로 거른다 |
| `variants` | 변형 이름 → 바꿀 값. `observation` 은 `dom` 또는 `som`, `body_text` 는 `false` 면 관측에서 본문 글을 뺀다(기본 `true`), `guard` 는 `on`(가드 켬, 기본) 또는 `off`(가드 끔 — 판단만 기록, 아래) |
| `variants` 의 자리만 있는 칸 | `diagnosis` 는 `single` 만 받는다. 다중 진단(GACA-181)이 생기면 값을 더한다 |
| `repeat` · `concurrency` | 반복 수 · 동시에 도는 Persona 수 |
| `max_steps` · `max_seconds` · `max_tokens` | 한도. 토큰 상한은 Persona 실행 하나마다 센다 |

**결과** (`--out` 폴더)

- `summary.md`: 머리(날짜 · 커밋 · 모델 · 조건 · 합계), 변형 × 사이트마다 한 행인 표, 설정 파일 전문
- `summary.csv`: 같은 표. 행마다 설정 이름 · 커밋 · 모델 · 날짜를 붙인다
- `personas.jsonl`: Persona 실행 하나에 한 줄
- `steps.jsonl`: step 하나에 한 줄. 행동 로그 명세의 14칸 그대로다
- `guard-log.jsonl`: 가드 끔 변형에서 가드가 걸린 것 하나에 한 줄 (아래)
- `usage.jsonl`: LLM 사용량. 서버의 사용량 기록과 섞지 않는다

**지표**

- 정의는 `uxight_agent/bench_metrics.py` 맨 위 한 곳에 있다.
- 재현율과 오탐은 정답 · 진단 파일을 줬을 때만 낸다. 안 주면 `—` 다.
- 정답과 진단을 맞추는 규칙(`matches`)은 시작값이다.

**가드 켬 · 끔 A/B test** (GACA-180, 예: `config/bench-guard.json`)

- `guard: "off"` 변형은 가드 셋이 막을지 판단만 기록하고 막지 않는다. 시스템 프롬프트는 두 조건이 같다.
  - 파괴적 행동 차단 · 링크 도메인 검사: 막을 행동도 실행하고, 막았을 결과를 남긴다.
  - 페이지 글 지시문 표시: 프롬프트에 `[[지시문 의심: …]]` 을 붙이지 않고, 붙였을 조각 수를 남긴다. 페이지가 쓴 `[[ ]]` 는 그때도 하나로 줄인다.
- **가드 끔은 막을 행동을 실제로 실행한다.** 그래서 가드 끔 변형이 하나라도 있으면 모든 사이트가 `--serve` 로 띄운 사본이어야 하고, `allowed_domains` 는 비워야 한다. 아니면 브라우저를 띄우기 전에 멈춘다.
- 드라이버의 요청 단계 차단은 주 창 · 새 창 이동만 끊는다. 실행된 클릭이 낸 하위 요청(fetch · 이미지 · beacon · ping) · iframe 이동 · WebSocket 은 그것만으로는 밖에 닿는다.
  - 그래서 운영 Watcher 와 benchmark 의 모든 변형이 **허용 밖 하위 요청 차단**을 켠다(GACA-227). 두 조건이 같고, 운영과도 같다.
  - 허용 밖 하위 요청 차단은 두 겹이다. route 에서 허용 밖 하위 요청 · iframe 이동을 끊고, 허용 밖 WebSocket 은 가짜로 받는다.
  - route 를 거치지 않는 연결(worker · service worker 안의 요청, 떠날 때의 beacon · keepalive fetch, 추측 prefetch · prerender)은 브라우저 설정이 막는다. 허용 호스트:포트 말고는 모두 막힌 프록시로 보내고, WebRTC 의 UDP 와 QUIC 를 끄고, service worker 를 막는다.
  - 사본이 허용 밖에서 받는 글꼴 · 스크립트도 끊긴다. 학교 사본은 홈의 CDN 스크립트 1개가 끊기고, 홈과 Task 페이지 화면은 그대로였다(10/31). 그래도 이 차단을 켜기 전의 결과(GACA-179 benchmark)와는 바로 비교하지 않는다.
- 새 창 규칙 · 늦은 이동 되돌리기 · 자동 요청의 파괴적 경로 검사와 한도는 두 조건 모두 그대로다.
- `guard-log.jsonl` 한 줄: `run_id` · `persona_id` · `step`, `guard`(`domain` · `destructive` · `page_text`), `reason`, `action`(step 로그 모양), `destination`(계정 · 쿼리 뺀 목적지), `marks`(지시문 표시 조각 수).
  - `reason`: 행동 가드는 가드 켬이었다면 step 로그 `result.error` 에 남았을 문구, 지시문 표시는 걸린 패턴 이름이다. 페이지 글 원문은 남기지 않는다.
  - http(s) 가 아닌 목적지는 `destination` · `reason` 모두 scheme 만 남긴다(`data:` · `javascript:` · `mailto:`). 그 주소에 페이지 글 · 코드 · 메일 주소가 그대로 있어서다.
- 표의 가드 칸은 행의 합계다. 가드 `on` 은 실제로 막은 수 · 붙인 표시 수, `off` 는 막지 않고 기록한 수다.
  - 도메인 가드 · 파괴 가드: 가드가 걸린 행동 수.
  - 지시문 표시: 프롬프트 페이지 글의 표시 조각 수.
  - 요청 끊김: 드라이버가 요청 단계에서 끊은 허용 밖 이동 요청 수(주 창 · 새 창).
  - 하위 요청 끊김: 허용 밖 하위 요청 차단이 route 에서 끊은 수. 막힌 프록시가 막은 연결은 세지 못한다.
  - CuP: 성공했고 행동 가드가 한 번도 걸리지 않은 실행의 비율. 지시문 표시는 넣지 않는다.
- 가드 끔은 bench 에서만 쓴다. 운영 Watcher · 정책 · env 로는 켤 수 없다.

**알아 둘 것**

- `som` 변형은 지금 드라이버만 바뀐다(번호 박스 그림). 화면이 멎기를 기다리는 것은 `dom` 도 같다(GACA-157). Persona 프롬프트에 그림을 넣지 않으므로 모델이 받는 글은 `dom` 과 같다.
- 비교할 사이트는 같은 방식으로 띄운다. 학교 사본 홈은 스크립트가 메뉴 링크를 바꾼다. 그래서 첫 관측이 바뀌기 전인지 뒤인지가 로딩 속도에 따라 달라진다. 공개 주소와 `--serve` 를 섞으면 사이트 차이에 속도 차이가 섞인다.
- `--serve` 는 서버 nginx 설정 중 두 가지만 따른다. `.do` 를 HTML 로 내고, POST 에도 같은 파일을 준다. 사본에 없는 경로는 404 다(서버는 안내 페이지).
- 결함 사본과 정답 파일은 저장소에 넣지 않는다.

**dev 서버에서 돌리기** (PM)

- agent 이미지에는 git 과 `config/` 가 없다. 그래서 `config/` 와 사본 폴더를 붙이고, 커밋은 env 로 넘긴다.
- 컨테이너가 읽기 전용이라 `uv` 대신 venv 의 python 을 쓴다.

```sh
docker compose run --rm --no-deps \
  -e BENCH_COMMIT=<이미지를 만든 커밋> \
  -v "$PWD/config:/bench/config:ro" \
  -v <원본 사본 폴더>:/bench/original:ro -v <결함 사본 폴더>:/bench/seedA:ro \
  agent /app/.venv/bin/python -m uxight_agent.bench /bench/config/bench-school.json \
    --out /app/data/bench/$(date +%m%d-%H%M) \
    --serve original=/bench/original --serve seedA=/bench/seedA
```

결과는 호스트의 `services/agent/data/bench/<시각>/` 에 남는다.
