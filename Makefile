.PHONY: up down logs check fmt web-check api-check agent-check

up:            ## 로컬 기동 (mysql · api · agent). FE 는 호스트에서 npm run dev
	docker compose up -d --build

down:          ## 중지 (볼륨 유지). 초기화는 docker compose down -v
	docker compose down

logs:
	docker compose logs -f --tail=100

check: web-check api-check agent-check   ## CI 와 같은 검사

web-check:
	cd apps/web && npm ci && npm run lint && npm run typecheck && npm run build

api-check:
	cd services/api && ./gradlew build --no-daemon

agent-check:
	cd services/agent && uv sync --frozen && uv run ruff check . && uv run ruff format --check . && uv run pytest

fmt:
	cd services/agent && uv run ruff format . && uv run ruff check --fix .
