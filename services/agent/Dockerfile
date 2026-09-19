FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Chromium + 시스템 의존성. S2 (GACA-78) 에서 복원한다 — 지금 runner 는 스텁이라 브라우저를 열지 않는다.
# 복원 시 주의: compose 의 read_only:true 때문에 HOME 을 tmpfs 로 주어야 Chromium 이 뜬다.
# RUN uv run --no-sync playwright install --with-deps chromium
COPY uxight_agent ./uxight_agent
RUN uv sync --frozen --no-dev
# 비root 실행 (agent-safety §2.2). uid 1000 = compose 바인드마운트 data/ 의 소유자와 맞춘다.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /app/data && chown -R app:app /app
USER app
EXPOSE 8000
# uv 를 런타임에서 쓰지 않는다 — read_only 컨테이너에서 uv 가 캐시를 만들려다 EROFS 로 죽는다.
CMD ["/app/.venv/bin/uvicorn", "uxight_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
