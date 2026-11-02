import functools
import http.server
import json
import threading
from pathlib import Path

import httpx
import pytest
from openai import AsyncOpenAI

from uxight_agent.llm import LLMClient

NO_CHOICES = "<no choices>"


@pytest.fixture
def scripted_llm(tmp_path, monkeypatch):
    """정해 둔 답을 차례로 내는 LLMClient 를 만든다. 네트워크 없이 진짜 openai SDK 를 거친다.

    답 하나는 모델이 낸 글(content) 문자열이다. None 이면 HTTP 500 (호출 실패),
    (글, "length") 처럼 주면 그 finish_reason 으로 끝난 답, NO_CHOICES 면 choices 가 빈 답이다.
    돌려주는 requests 에 SDK 가 보낸 요청 본문이 쌓인다.
    """
    monkeypatch.setenv("LLM_USAGE_LOG", str(tmp_path / "llm-usage.jsonl"))

    def make(*replies) -> tuple[LLMClient, list[dict]]:
        queue = list(replies)
        requests: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            reply = queue.pop(0)
            if reply is None:
                return httpx.Response(500, json={"error": {"message": "boom"}})
            content, finish = reply if isinstance(reply, tuple) else (reply, "stop")
            choice = {
                "index": 0,
                "finish_reason": finish,
                "message": {"role": "assistant", "content": content},
            }
            return httpx.Response(
                200,
                json={
                    "id": "c",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "test-model",
                    "choices": [] if reply == NO_CHOICES else [choice],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                },
            )

        client = AsyncOpenAI(
            base_url="http://llm.test/v1",
            api_key="test",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        return LLMClient(client=client, model="test-model"), requests

    return make


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_server():
    """tests/fixtures 를 http://127.0.0.1:<port>/ 로 띄운다 (도메인 가드는 http 주소로 본다)."""
    handler = functools.partial(_QuietHandler, directory=str(FIXTURES))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass
