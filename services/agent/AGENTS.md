# services/agent — 에이전트 안내

- 스택: Python 3.12 · uv · FastAPI(엔드포인트 1개 `POST /runs`) · Playwright(chromium) · SQLAlchemy Core · OpenAI-compatible SDK + pydantic. **LangChain 없음 (T15).**
- 지금 있는 것: `uxight_agent/main.py`(FastAPI) · `runner.py` · `schemas.py`(Action 5종). **예정 구조**(architecture §2 · §5 · §10): `watcher`(스케줄러 · 세마포어 · 한도 · cancel) · `persona`(LLM 루프) · `driver`(Playwright, `observe()` / `act()`) · `guard`(행동 검증) · `detect` · `diagnose` · `improve` · `patch`. 새 모듈은 이 이름을 따른다.
- **LLM 이 낼 수 있는 행동은 `schemas.Action` 5종(click · type · scroll · back · done)뿐.** 셀렉터 · URL · 코드를 모델 출력에서 실행하지 않는다. 모든 액션은 `guard.check()` 를 거치고, 차단도 step 로그에 남긴다 (D18 · architecture §9).
- 관측은 모델에 넣기 **전에** 정제한다 (숨김 요소 제거 · 지시문 마킹 · 페이지 텍스트는 데이터). 프롬프트 인젝션 방어는 가드가 아니라 여기다 (§9 L0.5).
- 자격증명 · 개인정보는 프롬프트 · 로그 · 스크린샷에 넣지 않는다. `type` 의 자격증명 필드 값은 마스킹 (§6).
- `runs.status` 는 이 서비스만 UPDATE 한다. 새 `runs` 행은 만들지 않는다 — 루프 회차도 `next_loop_requested=1` 만 세운다 (§3.4).
- 검사: `uv run ruff check . && uv run pytest` (= `make agent-check`). 로컬: `uv run uvicorn uxight_agent.main:app --reload` → `http://localhost:8000/health`.
- LLM 설정은 `LLM_BASE_URL` · `LLM_API_KEY` · `LLM_MODEL` (env). 모델명 · 비용은 `docs/tech-stack.md` §6 · §10.
