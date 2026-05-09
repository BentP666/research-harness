"""Self-tests for FakeProxyMock.

Each test spins up the mock, hits it with a raw requests.post, and asserts
the expected status/body shape. This keeps the mock trustworthy so later
scenarios can drive the real anthropic provider through it by just setting
ANTHROPIC_BASE_URL.
"""

from __future__ import annotations

import json

import pytest

from ..injectors.fake_proxy import FakeProxyMock


def _post(url: str) -> tuple[int, bytes]:
    try:
        import requests
    except ImportError:  # pragma: no cover -- requests is a hard dep in practice
        pytest.skip("requests not installed")
    r = requests.post(
        f"{url}/v1/messages",
        json={"messages": [{"role": "user", "content": "hi"}]},
        timeout=10,
    )
    return r.status_code, r.content


@pytest.mark.smoke
def test_fake_proxy_ok_scenario_returns_200():
    with FakeProxyMock("ok") as mock:
        status, body = _post(mock.base_url)
        assert status == 200
        parsed = json.loads(body)
        assert parsed["type"] == "message"
        assert parsed["content"][0]["type"] == "text"
        assert mock.request_count == 1


@pytest.mark.smoke
def test_fake_proxy_rate_limit_then_ok():
    with FakeProxyMock("rate_limit_then_ok") as mock:
        s1, _ = _post(mock.base_url)
        s2, body2 = _post(mock.base_url)
        assert s1 == 429
        assert s2 == 200
        assert mock.request_count == 2


@pytest.mark.smoke
def test_fake_proxy_refusal_returns_safety_message():
    with FakeProxyMock("refusal") as mock:
        status, body = _post(mock.base_url)
        assert status == 200
        text = json.loads(body)["content"][0]["text"]
        assert "can't help" in text


@pytest.mark.smoke
def test_fake_proxy_captures_request_body():
    with FakeProxyMock("ok") as mock:
        import requests

        requests.post(
            f"{mock.base_url}/v1/messages",
            json={"messages": [{"role": "user", "content": "hello world"}]},
            headers={"x-api-key": "sk-test"},
            timeout=10,
        )
        assert mock.request_count == 1
        req = mock.captured_requests[0]
        assert req.path == "/v1/messages"
        assert req.headers.get("x-api-key") == "sk-test"
        assert req.body["messages"][0]["content"] == "hello world"


@pytest.mark.smoke
def test_fake_proxy_scenario_can_switch_midflight():
    with FakeProxyMock("ok") as mock:
        s1, _ = _post(mock.base_url)
        mock.set_scenario("5xx")
        s2, _ = _post(mock.base_url)
        assert s1 == 200
        assert s2 == 503
