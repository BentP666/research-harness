"""Programmable Anthropic-compatible mock server (proxy stub).

Why we need this:
- Real proxies are per-user gateways. Backend tests can't depend on
  them. We replicate the surface (POST /v1/messages, returns
  ``{content: [{type: "text", text: "..."}], usage: {...}}``).
- The replay recorder (replay/recorder.py) covers the *happy path* with
  cached responses. This mock covers the *pathological* path: rate
  limits, refusals, truncated bodies, latency spikes, request shape
  inspection.
- Stays in-process via ``http.server`` so no extra deps or daemons.

Usage::

    with FakeProxyMock(scenario="rate_limit_then_ok") as mock:
        os.environ["ANTHROPIC_BASE_URL"] = mock.base_url
        os.environ["ANTHROPIC_API_KEY"] = "sk-fake"
        # ... run code that hits anthropic ...
        assert mock.request_count >= 1
        assert mock.scenarios_triggered == ["rate_limit_then_ok"]

Scenarios:
- "ok"                  : returns a stub assistant response
- "rate_limit"          : every call returns 429 with Retry-After: 1
- "rate_limit_then_ok"  : first call 429, second call 200 (retry path)
- "refusal"             : returns content "I can't help with that."
- "truncated_json"      : returns Content-Length lying body that ends mid-token
- "slow"                : sleeps 2s before responding 200
- "5xx"                 : returns 503 every time
- "unicode_garbage"     : returns high-codepoint noise as text content

The scenario can also be a callable ``(request_dict) -> (status, body)``
for custom logic (e.g. "reject any prompt over 8k tokens").
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional


_RECORDED_REQUESTS: list[dict[str, Any]] = []


@dataclass
class CapturedRequest:
    """One captured POST body for assertions in tests."""

    path: str
    headers: dict[str, str]
    body: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


def _ok_response(prompt_len: int) -> dict[str, Any]:
    """Stub Anthropic Messages API response."""
    return {
        "id": "msg_fake_001",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": '{"ok": true, "stub": "fake_proxy"}'}],
        "model": "claude-fake",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": prompt_len // 4,
            "output_tokens": 16,
        },
    }


# Built-in scenarios: take (request_count, body) -> (status_code, response_dict, sleep_s)
ScenarioFn = Callable[[int, dict[str, Any]], tuple[int, Any, float]]


def _scenario_ok(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    prompt_len = len(json.dumps(body.get("messages", [])))
    return 200, _ok_response(prompt_len), 0.0


def _scenario_rate_limit(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    return (
        429,
        {
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "Rate limit"},
        },
        0.0,
    )


def _scenario_rate_limit_then_ok(
    n: int, body: dict[str, Any]
) -> tuple[int, Any, float]:
    if n == 1:
        return _scenario_rate_limit(n, body)
    return _scenario_ok(n, body)


def _scenario_refusal(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    return (
        200,
        {
            "id": "msg_refusal",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "I'm sorry, but I can't help with that request.",
                }
            ],
            "model": "claude-fake",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 4, "output_tokens": 11},
        },
        0.0,
    )


def _scenario_truncated_json(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    # Sentinel -- the handler intercepts and writes a partial body manually.
    return 200, "__TRUNCATED__", 0.0


def _scenario_slow(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    return _scenario_ok(n, body)[:2] + (2.0,)


def _scenario_5xx(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    return 503, {"type": "error", "error": {"type": "overloaded_error"}}, 0.0


def _scenario_unicode_garbage(n: int, body: dict[str, Any]) -> tuple[int, Any, float]:
    garbage = "\u202e\u200d\U0001f4a9\u0000\uffff" * 30
    return (
        200,
        {
            "id": "msg_garbage",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": garbage}],
            "model": "claude-fake",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        0.0,
    )


_BUILTIN_SCENARIOS: dict[str, ScenarioFn] = {
    "ok": _scenario_ok,
    "rate_limit": _scenario_rate_limit,
    "rate_limit_then_ok": _scenario_rate_limit_then_ok,
    "refusal": _scenario_refusal,
    "truncated_json": _scenario_truncated_json,
    "slow": _scenario_slow,
    "5xx": _scenario_5xx,
    "unicode_garbage": _scenario_unicode_garbage,
}


class _Handler(BaseHTTPRequestHandler):
    # type: ignore[misc]
    server_version = "FakeProxy/0.1"
    mock: "FakeProxyMock"  # set on the class by the server before serving

    def log_message(self, *_args: Any, **_kw: Any) -> None:  # silence
        return

    def do_POST(self) -> None:  # noqa: N802 -- http.server signature
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"_raw": raw[:200].decode("utf-8", errors="replace")}

        captured = CapturedRequest(
            path=self.path,
            headers={k: v for k, v in self.headers.items()},
            body=body,
        )
        self.mock._capture(captured)

        scenario = self.mock._resolve_scenario(captured)
        n = self.mock.request_count
        status, payload, sleep_s = scenario(n, body)
        if sleep_s > 0:
            time.sleep(sleep_s)

        if payload == "__TRUNCATED__":
            # Lie about content-length and write half the body
            full = json.dumps(_ok_response(0)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(full)))
            self.end_headers()
            self.wfile.write(full[: len(full) // 2])
            try:
                self.wfile.flush()
            except Exception:
                pass
            return

        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if status == 429:
            self.send_header("Retry-After", "1")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


class FakeProxyMock:
    """Context-manager wrapper around an in-process HTTP server.

    Bind to localhost on an OS-assigned port so concurrent tests don't
    collide. Captures every request for later inspection.
    """

    def __init__(
        self,
        scenario: str | ScenarioFn = "ok",
        port: int = 0,
    ):
        self._scenario_input = scenario
        self._scenario: ScenarioFn = self._resolve_input(scenario)
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._captured: list[CapturedRequest] = []
        self._lock = threading.Lock()
        self._port = port

    @staticmethod
    def _resolve_input(scenario: str | ScenarioFn) -> ScenarioFn:
        if callable(scenario):
            return scenario
        if scenario not in _BUILTIN_SCENARIOS:
            raise ValueError(
                f"unknown scenario {scenario!r}; valid: {sorted(_BUILTIN_SCENARIOS)}"
            )
        return _BUILTIN_SCENARIOS[scenario]

    def _resolve_scenario(self, request: CapturedRequest) -> ScenarioFn:
        return self._scenario

    def _capture(self, request: CapturedRequest) -> None:
        with self._lock:
            self._captured.append(request)

    @property
    def request_count(self) -> int:
        with self._lock:
            return len(self._captured)

    @property
    def captured_requests(self) -> list[CapturedRequest]:
        with self._lock:
            return list(self._captured)

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("mock server not started")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def set_scenario(self, scenario: str | ScenarioFn) -> None:
        """Switch scenario mid-flight (useful for multi-stage tests)."""
        self._scenario = self._resolve_input(scenario)

    def __enter__(self) -> "FakeProxyMock":
        handler = type("BoundHandler", (_Handler,), {"mock": self})
        self._server = HTTPServer(("127.0.0.1", self._port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="fake-proxy-mock"
        )
        self._thread.start()
        # Tiny startup delay so accept() is ready
        time.sleep(0.01)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)


__all__ = ["FakeProxyMock", "CapturedRequest", "ScenarioFn"]
