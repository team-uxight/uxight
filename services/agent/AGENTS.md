# services/agent — 에이전트 안내

- 스택: Python 3.12 · uv · FastAPI(엔드포인트 1개 `POST /runs`) · Playwright(chromium) · SQLAlchemy Core · OpenAI-compatible SDK + pydantic. **LangChain 없음 (T15).**
- 지금 있는 것: `main.py`(FastAPI) · `routers/runs.py`(`POST /runs`) · `watcher/`(회차 실행 · 취소 감시 · step 로그) · `persona/`(`LLMDecider` — 프롬프트 · LLM 1회 · 행동 검증) · `driver/`(`DomDriver`) · `repositories/`(SQL) · `schemas.py`(Action 5종). **예정 구조**(architecture §2 · §5 · §10): `watcher`(스케줄러 · 세마포어 · 한도 · cancel) · `persona`(LLM 루프) · `driver`(Playwright, `observe()` / `act()`) · `guard`(행동 검증) · `detect` · `diagnose` · `improve` · `patch`. 새 모듈은 이 이름을 따른다.
- **LLM 이 낼 수 있는 행동은 `schemas.Action` 5종(click · type · scroll · back · done)뿐.** 셀렉터 · URL · 코드를 모델 출력에서 실행하지 않는다. 모든 액션은 `guard.check()` 를 거치고, 차단도 step 로그에 남긴다 (D18 · architecture §9).
- LLM 호출은 `LLMClient` 하나를 통해서만 (`uxight_agent/llm.py` — 호출마다 사용량을 `data/llm-usage.jsonl` 에 남긴다. 직접 `openai` 를 부르면 비용 추적에서 빠진다). 단가표와 비용 계산은 `usage_report.py` 한 곳이고, Persona step 은 step 마다 그 비용을 `runs` · `run_personas` 의 `cost_usd` 에 더한다. 단가 없는 모델이면 토큰만 세고 비용 칸은 NULL 로 둔다. 출력 채널은 `response_format`(기본) 또는 `emit_action` function tool **하나**(대안) — `tools` 목록에 다른 도구를 넣지 않는다. 제공사 서버 실행 도구(web_search · computer use · code interpreter)는 어떤 제공자에서도 요청하지 않는다 (`docs/agent-safety.md` §2.4). 제공자 전환은 `LLM_PROVIDER` env 로.
- `cost_usd` 칸은 소수 4자리다. Persona 행은 그 Persona 사용량 합계의 4자리 반올림이고, `runs` 는 Persona 행의 합이다. 따라서 Persona 가 여럿이면 `runs` 값이 사용량 기록 전체 합의 반올림과 0.0001~0.0002 다를 수 있다.
- 서버(agent 컨테이너)는 코드의 기본 단가표만 쓴다. `LLM_PRICES` 는 CLI(`usage_report`) · bakeoff · bench 용이다.
- 성능 benchmark(`bench.py` · `bench_metrics.py`, GACA-179)는 운영 코드로 돌되 DB 를 불러오지 않는다. Watcher 와 같이 쓰는 step 규칙(로그 14칸 · 성공 판정 · 비용 · Persona 를 끝낼지)은 `watcher/step_rules.py` 에 있고, 이 파일도 DB 를 불러오지 않는다.
- 끊긴 step(LLM 응답 뒤 시간 상한 · 취소 · 행동 오류)의 토큰 · 비용은 사용량 기록(`llm-usage.jsonl`)에만 남고 DB 에서는 빠진다. 토큰은 이번 변경 전부터 같은 방식으로 빠졌다.
- 한도(step · 토큰 · 하루 예산 · 시간)로 끝난 Persona 는 마지막 행동 뒤 화면을 `step-(n+1).png` 로 남길 수 있다 (n = step 로그 줄 수). 이 화면의 로그 줄은 없다.
- 관측은 모델에 넣기 **전에** 정제한다 (숨김 요소 제거 · 지시문 마킹 · 페이지 텍스트는 데이터). 프롬프트 인젝션 방어는 가드가 아니라 여기다 (§9 L0.5).
- 자격증명 · 개인정보는 프롬프트 · 로그 · 스크린샷에 넣지 않는다. `type` 의 자격증명 필드 값은 마스킹 (§6).
- `runs.status` 는 이 서비스만 UPDATE 한다. 새 `runs` 행은 만들지 않는다 — 다음 회차는 리서처 승인 시 Spring 이 만든다. 회차의 입력(대상 URL · Task · Persona · 정책)은 `POST /runs` 본문이 아니라 `runs` 행의 스냅샷 컬럼에서 읽는다.
- 검사: `uv run ruff check . && uv run pytest` (= `make agent-check`). 로컬: `uv run uvicorn uxight_agent.main:app --reload` → `http://localhost:8000/health`.
- LLM 설정은 `LLM_BASE_URL` · `LLM_MODEL` · `LLM_API_KEY` (env) 하나씩 — 엘리스 MLAPI 배포 하나(`openai/gpt-5.6-luna`)를 step 과 진단이 같이 쓴다. 주소 하나에 모델 하나가 묶이고 모델명은 `provider/model` 형식 — base URL · 모델명을 코드에 박지 않는다. Luna 는 추론 모델이라 생각 토큰도 출력 한도에 들어간다 — 한도를 너무 작게 잡으면 답이 비어 온다. 한도는 `LLMClient.chat(max_tokens=…)` 로 주고, API 에는 `max_completion_tokens` 로 간다(Luna 는 `max_tokens` 를 400 으로 거절). Persona step 호출은 non-streaming · 짧게. 관측에 원시 HTML · 셀렉터를 그대로 넣지 않는다 (코드성 프롬프트는 프록시에서 막힐 수 있다, `docs/tech-stack.md` §6 T19).
