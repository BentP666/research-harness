"""Tests for the Codex app-server bridge used by Zotero chat."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness_mcp.codex_app_server import (
    CodexAppServerClient,
    CodexAppServerError,
    CodexStreamEvent,
    ZoteroCodexConversationStore,
)


class ScriptedTransport:
    def __init__(self, messages: list[dict]):
        self.messages = list(messages)
        self.sent: list[dict] = []
        self.closed = False

    def send(self, message: dict) -> None:
        self.sent.append(message)

    def read(self, timeout_seconds: float | None = None) -> dict:
        if not self.messages:
            raise TimeoutError("no scripted messages left")
        return self.messages.pop(0)

    def close(self) -> None:
        self.closed = True


def test_codex_client_starts_thread_and_streams_delta_events():
    transport = ScriptedTransport(
        [
            {"id": 1, "result": {"userAgent": "codex-test"}},
            {"id": 2, "result": {"thread": {"id": "thread-1"}}},
            {
                "method": "turn/started",
                "params": {"threadId": "thread-1", "turn": {"id": "turn-1"}},
            },
            {"id": 3, "result": {"turn": {"id": "turn-1"}}},
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "delta": "你好",
                },
            },
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "delta": "，RH",
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-1",
                    "turn": {"id": "turn-1", "status": "completed"},
                },
            },
        ]
    )
    client = CodexAppServerClient(transport_factory=lambda: transport)

    client.initialize()
    thread_id = client.start_thread(cwd="/repo", instructions="中文回答")
    events = list(client.stream_turn(thread_id, "请总结这篇论文"))

    assert thread_id == "thread-1"
    assert [event.event for event in events] == ["started", "delta", "delta", "done"]
    assert "".join(event.data.get("text", "") for event in events) == "你好，RH"
    assert transport.sent[0]["method"] == "initialize"
    assert transport.sent[1]["method"] == "initialized"
    assert transport.sent[2]["method"] == "thread/start"
    assert transport.sent[2]["params"]["sandbox"] == "read-only"
    assert transport.sent[2]["params"]["approvalPolicy"] == "never"
    assert transport.sent[3]["method"] == "turn/start"
    assert transport.sent[3]["params"]["input"][0]["text"] == "请总结这篇论文"


def test_codex_client_denies_server_approval_requests_before_completion():
    transport = ScriptedTransport(
        [
            {"id": 1, "result": {"userAgent": "codex-test"}},
            {
                "id": "approval-1",
                "method": "item/commandExecution/requestApproval",
                "params": {},
            },
            {"id": 2, "result": {"turn": {"id": "turn-1"}}},
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-1",
                    "turn": {"id": "turn-1", "status": "completed"},
                },
            },
        ]
    )
    client = CodexAppServerClient(transport_factory=lambda: transport)

    client.initialize()
    events = list(client.stream_turn("thread-1", "只读回答"))

    assert events[-1].event == "done"
    approval_reply = next(
        message for message in transport.sent if message.get("id") == "approval-1"
    )
    assert approval_reply["result"] == {"decision": "decline"}


def test_codex_client_raises_on_failed_turn():
    transport = ScriptedTransport(
        [
            {"id": 1, "result": {"userAgent": "codex-test"}},
            {"id": 2, "result": {"turn": {"id": "turn-1"}}},
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-1",
                    "turn": {"id": "turn-1", "status": "failed"},
                },
            },
        ]
    )
    client = CodexAppServerClient(transport_factory=lambda: transport)

    client.initialize()
    with pytest.raises(CodexAppServerError):
        list(client.stream_turn("thread-1", "会失败"))


def test_codex_client_treats_idle_status_as_turn_done():
    transport = ScriptedTransport(
        [
            {"id": 1, "result": {"userAgent": "codex-test"}},
            {"id": 2, "result": {"turn": {"id": "turn-1"}}},
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "delta": "收到",
                },
            },
            {
                "method": "thread/status/changed",
                "params": {"threadId": "thread-1", "status": {"type": "idle"}},
            },
        ]
    )
    client = CodexAppServerClient(transport_factory=lambda: transport)

    client.initialize()
    events = list(client.stream_turn("thread-1", "只回复收到"))

    assert [event.event for event in events] == ["delta", "status", "done"]
    assert events[-1].data["completion_source"] == "thread_idle"


def test_codex_client_can_send_image_urls_with_turn_input():
    transport = ScriptedTransport(
        [
            {"id": 1, "result": {"userAgent": "codex-test"}},
            {"id": 2, "result": {"turn": {"id": "turn-1"}}},
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thread-1",
                    "turn": {"id": "turn-1", "status": "completed"},
                },
            },
        ]
    )
    client = CodexAppServerClient(transport_factory=lambda: transport)

    client.initialize()
    events = list(
        client.stream_turn(
            "thread-1",
            "请结合截图回答",
            image_urls=["data:image/png;base64,abc"],
        )
    )

    assert events[-1].event == "done"
    turn_start = transport.sent[2]
    assert turn_start["method"] == "turn/start"
    assert turn_start["params"]["input"] == [
        {"type": "text", "text": "请结合截图回答", "text_elements": []},
        {"type": "image", "url": "data:image/png;base64,abc", "detail": "high"},
    ]


def test_codex_client_defaults_to_fast_zotero_model_and_low_effort():
    client = CodexAppServerClient(transport_factory=lambda: ScriptedTransport([]))

    assert client.model == "gpt-5.3-codex-spark"
    assert client.effort == "low"


def test_zotero_codex_conversation_store_persists_thread_mapping(tmp_path: Path):
    store = ZoteroCodexConversationStore(tmp_path / "threads.json")

    store.save_thread(
        conversation_id="conv-1",
        thread_id="thread-1",
        paper_id=7,
        topic_id=3,
        zotero_item_key="ABCD1234",
    )

    reloaded = ZoteroCodexConversationStore(tmp_path / "threads.json")
    assert reloaded.get_thread_id("conv-1") == "thread-1"
    assert reloaded.read_all()["conv-1"]["paper_id"] == 7


class FakePoolClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.initialized = 0
        self.closed = False
        self.started = 0
        self.resumed: list[str] = []
        self.turns: list[tuple[str, str]] = []

    def initialize(self):
        self.initialized += 1
        return {"userAgent": "fake"}

    def start_thread(self, *, cwd, instructions):
        self.started += 1
        return f"thread-{self.started}"

    def resume_thread(self, thread_id, *, cwd, instructions):
        self.resumed.append(thread_id)
        return thread_id

    def stream_turn(self, thread_id, prompt):
        self.turns.append((thread_id, prompt))
        yield CodexStreamEvent("delta", {"thread_id": thread_id, "text": "ok"})
        yield CodexStreamEvent("done", {"thread_id": thread_id})

    def close(self):
        self.closed = True


def test_codex_app_server_pool_reuses_initialized_client_for_same_model(tmp_path: Path):
    from research_harness_mcp.codex_app_server import CodexAppServerPool

    created: list[FakePoolClient] = []

    def factory(**kwargs):
        client = FakePoolClient(**kwargs)
        created.append(client)
        return client

    pool = CodexAppServerPool(client_factory=factory)

    first = list(
        pool.stream_turn(
            cwd=tmp_path,
            instructions="中文",
            existing_thread_id=None,
            prompt="第一轮",
            model="gpt-5.3-codex-spark",
            effort="low",
        )
    )
    second = list(
        pool.stream_turn(
            cwd=tmp_path,
            instructions="中文",
            existing_thread_id="thread-1",
            prompt="第二轮",
            model="gpt-5.3-codex-spark",
            effort="low",
        )
    )

    assert len(created) == 1
    assert created[0].initialized == 1
    assert created[0].started == 1
    assert created[0].resumed == ["thread-1"]
    assert first[-1].event == "done"
    assert second[-1].event == "done"


def test_codex_app_server_pool_prewarms_without_starting_thread(tmp_path: Path):
    from research_harness_mcp.codex_app_server import CodexAppServerPool

    created: list[FakePoolClient] = []

    def factory(**kwargs):
        client = FakePoolClient(**kwargs)
        created.append(client)
        return client

    pool = CodexAppServerPool(client_factory=factory)

    pool.prewarm(
        cwd=tmp_path,
        model="gpt-5.3-codex-spark",
        effort="low",
        service_tier=None,
    )
    events = list(
        pool.stream_turn(
            cwd=tmp_path,
            instructions="中文",
            existing_thread_id=None,
            prompt="第一轮",
            model="gpt-5.3-codex-spark",
            effort="low",
        )
    )

    assert len(created) == 1
    assert created[0].initialized == 1
    assert created[0].started == 1
    assert events[-1].event == "done"


def test_codex_app_server_pool_uses_separate_clients_per_model(tmp_path: Path):
    from research_harness_mcp.codex_app_server import CodexAppServerPool

    created: list[FakePoolClient] = []

    def factory(**kwargs):
        client = FakePoolClient(**kwargs)
        created.append(client)
        return client

    pool = CodexAppServerPool(client_factory=factory)

    list(
        pool.stream_turn(
            cwd=tmp_path,
            instructions="中文",
            existing_thread_id=None,
            prompt="fast",
            model="gpt-5.3-codex-spark",
            effort="low",
        )
    )
    list(
        pool.stream_turn(
            cwd=tmp_path,
            instructions="中文",
            existing_thread_id=None,
            prompt="strong",
            model="gpt-5.5",
            effort="low",
        )
    )

    assert [client.kwargs["model"] for client in created] == [
        "gpt-5.3-codex-spark",
        "gpt-5.5",
    ]
