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
