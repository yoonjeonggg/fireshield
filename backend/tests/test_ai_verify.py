"""ai_verify._call_ollama 단위 테스트.

실제 Ollama 없이 httpx.MockTransport로 응답을 흉내 내서, prefill로 받은
숫자 조각을 가드레일이 파싱할 수 있는 JSON으로 복원하는지와 실패 시
None(규칙 점수 폴백)을 돌려주는지 검증한다.
"""

import asyncio
import json

import httpx
import pytest

import app.services.ai_verify as ai_verify
from app.services.ai_guardrail import extract_probability


def _patch_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(ai_verify.httpx, "AsyncClient", client_factory)


def test_prefilled_number_is_returned_as_json(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["url"] = str(request.url)
        sent["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "0.85"}})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(ai_verify.settings, "ollama_num_thread", 8)

    raw = asyncio.run(ai_verify._call_ollama("프롬프트"))

    assert raw == '{"scam_probability": 0.85}'
    value, is_invalid, _ = extract_probability(raw)
    assert not is_invalid and value == pytest.approx(85.0)

    assert sent["url"].endswith("/api/chat")
    assert sent["body"]["messages"][-1] == {"role": "assistant", "content": '{"scam_probability": '}
    assert sent["body"]["options"]["num_thread"] == 8
    assert sent["body"]["options"]["stop"] == ["}"]


def test_num_thread_omitted_when_unset(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "0.1"}})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(ai_verify.settings, "ollama_num_thread", None)

    asyncio.run(ai_verify._call_ollama("프롬프트"))
    assert "num_thread" not in sent["body"]["options"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="model not found"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"error": "unexpected shape"}),
    ],
)
def test_failures_fall_back_to_none(monkeypatch, response):
    _patch_transport(monkeypatch, lambda request: response)
    assert asyncio.run(ai_verify._call_ollama("프롬프트")) is None
