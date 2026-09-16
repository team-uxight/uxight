FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Chromium + 시스템 의존성 — 첫 빌드가 느리다 (수 분). 로컬에선 `uv run playwright install chromium` 으로 대체 가능
RUN uv run --no-sync playwright install --with-deps chromium
COPY uxight_agent ./uxight_agent
RUN uv sync --frozen --no-dev
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "uxight_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
