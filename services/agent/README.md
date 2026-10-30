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

**LLM 호출은 `uxight_agent/llm.py` 의 `LLMClient.chat()` 으로만.** 호출마다 사용량(토큰 · 시간 · 역할 · 실행 id)이 `data/llm-usage.jsonl` 에 한 줄씩 남는다 — 키 · 프롬프트 · 응답 본문은 남기지 않는다. 비용은:

```sh
uv run python -m uxight_agent.usage_report                  # 전체, 역할별
uv run python -m uxight_agent.usage_report --days 1 --by run  # 최근 하루, 실행별
```

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
| `sites[].allowed_domains` | 회차의 허용 도메인과 같다. 시작 URL 의 호스트는 늘 허용한다 |
| `variants` | 변형 이름 → 바꿀 값. `observation` 은 `dom` 또는 `som`, `body_text` 는 `false` 면 관측에서 본문 글을 뺀다(기본 `true`) |
| `variants` 의 자리만 있는 칸 | `guard` 는 `on`, `diagnosis` 는 `single` 만 받는다. 가드 끄기(GACA-180) · 다중 진단(GACA-181)이 생기면 값을 더한다 |
| `repeat` · `concurrency` | 반복 수 · 동시에 도는 Persona 수 |
| `max_steps` · `max_seconds` · `max_tokens` | 한도. 토큰 상한은 Persona 실행 하나마다 센다 |

**결과** (`--out` 폴더)

- `summary.md`: 머리(날짜 · 커밋 · 모델 · 조건 · 합계), 변형 × 사이트마다 한 행인 표, 설정 파일 전문
- `summary.csv`: 같은 표. 행마다 설정 이름 · 커밋 · 모델 · 날짜를 붙인다
- `personas.jsonl`: Persona 실행 하나에 한 줄
- `steps.jsonl`: step 하나에 한 줄. 행동 로그 명세의 14칸 그대로다
- `usage.jsonl`: LLM 사용량. 서버의 사용량 기록과 섞지 않는다

**지표**

- 정의는 `uxight_agent/bench_metrics.py` 맨 위 한 곳에 있다.
- 재현율과 오탐은 정답 · 진단 파일을 줬을 때만 낸다. 안 주면 `—` 다.
- 정답과 진단을 맞추는 규칙(`matches`)은 시작값이다.

**알아 둘 것**

- `som` 변형은 지금 드라이버만 바뀐다(번호 박스 그림, 화면이 멎기를 기다림). Persona 프롬프트에 그림을 넣지 않으므로 모델이 받는 글은 `dom` 과 같다.
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
