"""Tests for Zotero HTTP API bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "zotero-api.db"
    from research_harness.storage.db import Database

    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO topics (name, description) VALUES ('demo-topic', '')")
        conn.execute(
            """
            INSERT INTO papers
                (title, authors, year, venue, doi, arxiv_id, url, abstract, status, deep_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Agentic Zotero API Sync",
                json.dumps(["Ada Lovelace"]),
                2026,
                "ICLR",
                "10.1234/zotero-api",
                "2602.99999",
                "https://arxiv.org/abs/2602.99999",
                "A paper for Zotero API sync tests.",
                "pdf_ready",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO paper_topics (paper_id, topic_id, relevance) VALUES (1, 1, 'high')"
        )
        conn.commit()
    finally:
        conn.close()

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


def test_topic_zotero_sync_push_dry_run(client: TestClient):
    response = client.post(
        "/api/topics/1/zotero-sync",
        json={"direction": "push", "dry_run": True, "limit": 1},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["output"]["direction"] == "push"
    assert payload["output"]["push"]["planned_count"] == 1
    assert payload["output"]["push"]["records"][0]["title"] == "Agentic Zotero API Sync"


def test_topic_zotero_sync_unknown_topic_404(client: TestClient):
    response = client.post(
        "/api/topics/999/zotero-sync",
        json={"direction": "push", "dry_run": True},
    )

    assert response.status_code == 404


def test_topic_zotero_sync_obeys_optional_token_gate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN", "secret-token")

    blocked = client.post(
        "/api/topics/1/zotero-sync",
        json={"direction": "push", "dry_run": True, "limit": 1},
    )
    assert blocked.status_code == 401

    allowed = client.post(
        "/api/topics/1/zotero-sync",
        headers={"X-RH-Zotero-Token": "secret-token"},
        json={"direction": "push", "dry_run": True, "limit": 1},
    )
    assert allowed.status_code == 200, allowed.text


def test_zotero_chat_resolves_rh_paper_from_tags(client: TestClient):
    response = client.post(
        "/api/zotero/chat",
        json={
            "message": "这篇论文接下来该怎么读？",
            "item": {
                "zotero_item_key": "ABCD1234",
                "library_id": 1,
                "title": "Agentic Zotero API Sync",
                "creators": ["Ada Lovelace"],
                "year": 2026,
                "doi": "10.1234/zotero-api",
                "tags": [
                    "rh",
                    "rh-paper-id:1",
                    "rh-topic:demo-topic",
                    "rh-deep-read",
                ],
                "abstract": "A paper for Zotero API sync tests.",
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["output"]["matched"]["paper"]["id"] == 1
    assert payload["output"]["matched"]["topic"]["id"] == 1
    assert "Agentic Zotero API Sync" in payload["output"]["assistant_message"]
    assert payload["output"]["codex_handoff"]["prompt"]
    assert payload["output"]["suggested_actions"][0]["kind"] == "codex_handoff"


def test_zotero_chat_prefers_existing_zotero_item_link(client: TestClient):
    from research_harness_mcp import http_api

    with http_api.get_db() as conn:
        conn.execute(
            """
            INSERT INTO zotero_item_links (
                paper_id, topic_id, zotero_library_id, zotero_library_type,
                zotero_collection_key, zotero_item_key, zotero_note_key,
                content_hash, last_synced_at
            )
            VALUES (1, 1, '1', 'user', 'COLL1234', 'LINK1234', 'NOTE1234', 'hash', '')
            """
        )
        conn.commit()

    response = client.post(
        "/api/zotero/chat",
        json={
            "message": "总结 RH 已知上下文",
            "item": {
                "zotero_item_key": "LINK1234",
                "library_id": 1,
                "title": "Different local title",
                "tags": [],
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()["output"]
    assert payload["matched"]["paper"]["id"] == 1
    assert payload["matched"]["topic"]["name"] == "demo-topic"
    assert payload["matched"]["zotero_link"]["zotero_item_key"] == "LINK1234"


def test_zotero_chat_link_match_filters_library_when_library_is_supplied(
    client: TestClient,
):
    from research_harness_mcp import http_api

    with http_api.get_db() as conn:
        conn.execute(
            """
            INSERT INTO zotero_item_links (
                paper_id, topic_id, zotero_library_id, zotero_library_type,
                zotero_collection_key, zotero_item_key, zotero_note_key,
                content_hash, last_synced_at
            )
            VALUES (1, 1, '2', 'group', 'GROUPCOLL', 'SAMEKEY', 'GROUPNOTE', 'hash', '')
            """
        )
        conn.commit()

    user_library = client.post(
        "/api/zotero/chat",
        json={
            "message": "这篇论文匹配到了什么？",
            "item": {
                "zotero_item_key": "SAMEKEY",
                "library_id": "1",
                "library_type": "user",
                "title": "Unrelated local title",
                "tags": [],
            },
        },
    )
    assert user_library.status_code == 200, user_library.text
    assert user_library.json()["output"]["matched"]["paper"] is None

    group_library = client.post(
        "/api/zotero/chat",
        json={
            "message": "这篇论文匹配到了什么？",
            "item": {
                "zotero_item_key": "SAMEKEY",
                "library_id": "2",
                "library_type": "group",
                "title": "Unrelated local title",
                "tags": [],
            },
        },
    )
    assert group_library.status_code == 200, group_library.text
    matched = group_library.json()["output"]["matched"]
    assert matched["paper"]["id"] == 1
    assert matched["zotero_link"]["zotero_library_type"] == "group"


def test_zotero_chat_optional_token_gate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN", "secret-token")

    blocked = client.post(
        "/api/zotero/chat",
        json={"message": "ping", "item": {"title": "Untitled"}},
    )
    assert blocked.status_code == 401

    allowed = client.post(
        "/api/zotero/chat",
        headers={"X-RH-Zotero-Token": "secret-token"},
        json={"message": "ping", "item": {"title": "Untitled"}},
    )
    assert allowed.status_code == 200


def test_zotero_chat_rejects_overlong_message(client: TestClient):
    response = client.post(
        "/api/zotero/chat",
        json={"message": "x" * 12001, "item": {"title": "Untitled"}},
    )

    assert response.status_code == 422


def test_zotero_chat_stream_uses_codex_app_server_and_persists_thread(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api
    from research_harness_mcp.codex_app_server import CodexStreamEvent

    calls: list[dict] = []

    def fake_stream_codex_turn(
        *,
        conversation_id,
        existing_thread_id,
        prompt,
        matched,
        model,
        image_urls=None,
    ):
        calls.append(
            {
                "conversation_id": conversation_id,
                "existing_thread_id": existing_thread_id,
                "prompt": prompt,
                "matched": matched,
                "model": model,
                "image_urls": image_urls,
            }
        )
        yield CodexStreamEvent(
            "started",
            {"thread_id": existing_thread_id or "thread-1", "turn_id": "turn-1"},
        )
        yield CodexStreamEvent("delta", {"text": "第一段"})
        yield CodexStreamEvent("delta", {"text": "，第二段"})
        yield CodexStreamEvent(
            "done", {"thread_id": existing_thread_id or "thread-1", "turn_id": "turn-1"}
        )

    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", fake_stream_codex_turn)

    first = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "这篇论文的 RH 贡献是什么？",
            "model": "gpt-5.4-mini",
            "item": {
                "zotero_item_key": "ABCD1234",
                "library_id": 1,
                "title": "Agentic Zotero API Sync",
                "tags": ["rh-paper-id:1"],
                "selected_text": "RH Zotero 选中的实验结果片段",
                "screenshots": ["data:image/png;base64,abc"],
            },
        },
    )

    assert first.status_code == 200, first.text
    assert first.headers["content-type"].startswith("text/event-stream")
    assert "event: ready" in first.text
    assert "event: delta" in first.text
    assert "第一段" in first.text
    assert "，第二段" in first.text
    assert "event: done" in first.text
    assert calls[0]["existing_thread_id"] is None
    assert "这篇论文的 RH 贡献是什么？" in calls[0]["prompt"]
    assert "RH Zotero 选中的实验结果片段" in calls[0]["prompt"]
    assert calls[0]["matched"]["paper"]["id"] == 1
    assert calls[0]["model"] == "gpt-5.4-mini"
    assert calls[0]["image_urls"] == ["data:image/png;base64,abc"]
    assert '"model":"gpt-5.4-mini"' in first.text

    second = client.post(
        "/api/zotero/chat/stream",
        json={
            "conversation_id": "zotero-chat-custom",
            "message": "继续上一轮",
            "item": {
                "zotero_item_key": "ABCD1234",
                "library_id": 1,
                "title": "Agentic Zotero API Sync",
                "tags": ["rh-paper-id:1"],
            },
        },
    )
    assert second.status_code == 200, second.text
    third = client.post(
        "/api/zotero/chat/stream",
        json={
            "conversation_id": "zotero-chat-custom",
            "message": "再继续",
            "item": {
                "zotero_item_key": "ABCD1234",
                "library_id": 1,
                "title": "Agentic Zotero API Sync",
                "tags": ["rh-paper-id:1"],
            },
        },
    )
    assert third.status_code == 200, third.text
    assert calls[-1]["existing_thread_id"] == "thread-1"


def test_zotero_chat_stream_token_gate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN", "secret-token")

    blocked = client.post(
        "/api/zotero/chat/stream",
        json={"message": "ping", "item": {"title": "Untitled"}},
    )
    assert blocked.status_code == 401


def test_zotero_chat_stream_rejects_unknown_model(client: TestClient):
    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "ping",
            "model": "not-a-real-model",
            "item": {"title": "Untitled"},
        },
    )

    assert response.status_code == 422


def test_zotero_warmup_prewarms_codex_pool(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api

    calls: list[dict] = []

    class FakePool:
        def prewarm(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(http_api, "_zotero_codex_pool", lambda: FakePool())

    response = client.post(
        "/api/zotero/warmup",
        json={"model": "gpt-5.3-codex-spark"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "warming"
    assert calls
    assert calls[0]["model"] == "gpt-5.3-codex-spark"
    assert calls[0]["effort"] == "low"


def test_zotero_chat_stream_returns_import_preview_for_current_collection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api

    def should_not_call_codex(**kwargs):
        raise AssertionError(
            "Codex stream should not run for current-collection import preview"
        )

    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", should_not_call_codex)

    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "把这个主题里精读过的 1 篇论文导入当前目录",
            "item": {
                "zotero_item_key": "ABCD1234",
                "library_id": 1,
                "title": "Agentic Zotero API Sync",
                "tags": ["rh-paper-id:1", "rh-topic:demo-topic", "rh-deep-read"],
                "current_directory_key": "CURRDIR1",
                "current_directory_name": "自动科研",
                "current_directory_path": "Research Harness / 自动科研",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert "event: ready" in response.text
    assert "event: action_preview" in response.text
    assert "event: done" in response.text
    assert '"topic_id":1' in response.text
    assert '"target_collection_key":"CURRDIR1"' in response.text
    assert '"library_id":"1"' in response.text
    assert '"library_type":"user"' in response.text
    assert '"paper_ids":[1]' in response.text
    assert "导入当前目录" in response.text
    assert '"action_type":"sync_rh_papers_to_collection"' in response.text
    assert '"type":"http_json"' in response.text
    assert '"label":"确认导入"' in response.text


def test_zotero_chat_stream_can_infer_import_topic_from_current_directory(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api

    def should_not_call_codex(**kwargs):
        raise AssertionError(
            "Codex stream should not run for current-directory import preview"
        )

    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", should_not_call_codex)

    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "把这个主题里精读过的 1 篇论文导入当前目录",
            "item": {
                "current_directory_key": "CURRDIR1",
                "current_directory_name": "demo-topic",
                "current_directory_path": "Research Harness / demo-topic",
                "library_id": "1",
                "library_type": "user",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert "event: action_preview" in response.text
    assert '"topic_id":1' in response.text
    assert '"paper_ids":[1]' in response.text


def test_zotero_import_preview_maps_local_user_library_to_web_user_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api

    def should_not_call_codex(**kwargs):
        raise AssertionError(
            "Codex stream should not run for current-directory import preview"
        )

    monkeypatch.setenv("ZOTERO_LIBRARY_ID", "16929158")
    monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "user")
    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", should_not_call_codex)

    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "把这个主题里 1 篇论文导入当前目录",
            "item": {
                "current_directory_key": "CURRDIR1",
                "current_directory_name": "demo-topic",
                "current_directory_path": "Research Harness / demo-topic",
                "library_id": "1",
                "library_type": "user",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert "event: action_preview" in response.text
    assert '"library_id":"16929158"' in response.text
    assert '"library_type":"user"' in response.text


def test_zotero_import_preview_counts_existing_links_in_current_library_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api

    def should_not_call_codex(**kwargs):
        raise AssertionError(
            "Codex stream should not run for current-directory import preview"
        )

    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", should_not_call_codex)

    with http_api.get_db() as conn:
        conn.execute(
            """
            INSERT INTO zotero_item_links (
                paper_id, topic_id, zotero_library_id, zotero_library_type,
                zotero_collection_key, zotero_item_key, zotero_note_key,
                content_hash, last_synced_at
            )
            VALUES (1, 1, '2', 'group', 'CURRDIR1', 'GROUPITEM', 'GROUPNOTE', 'hash', '')
            """
        )
        conn.commit()

    user_library = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "把这个主题里 1 篇论文导入当前目录",
            "item": {
                "current_directory_key": "CURRDIR1",
                "current_directory_name": "demo-topic",
                "current_directory_path": "Research Harness / demo-topic",
                "library_id": "1",
                "library_type": "user",
            },
        },
    )
    assert user_library.status_code == 200, user_library.text
    assert '"known_existing_count":0' in user_library.text

    group_library = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "把这个主题里 1 篇论文导入当前目录",
            "item": {
                "current_directory_key": "CURRDIR1",
                "current_directory_name": "demo-topic",
                "current_directory_path": "Research Harness / demo-topic",
                "library_id": "2",
                "library_type": "group",
            },
        },
    )
    assert group_library.status_code == 200, group_library.text
    assert '"known_existing_count":1' in group_library.text


def test_zotero_import_intent_classifier_avoids_generic_sync_chat():
    from research_harness_mcp import http_api

    assert not http_api._looks_like_zotero_import_request("同步这篇论文和 RH 的关系")
    assert not http_api._looks_like_zotero_import_request("请问这篇论文如何同步到 RH？")
    assert not http_api._looks_like_zotero_import_request("请帮我给 Zotero 添加标签")
    assert not http_api._looks_like_zotero_import_request("给这篇论文添加 Zotero 标签")
    assert http_api._looks_like_zotero_import_request("把这篇论文导入当前目录")


def test_zotero_chat_stream_returns_pdf_attach_action_preview_without_codex(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from research_harness_mcp import http_api

    def should_not_call_codex(**kwargs):
        raise AssertionError(
            "Codex stream should not run for PDF attachment action previews"
        )

    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", should_not_call_codex)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% RH test PDF\n")
    monkeypatch.setattr(http_api, "PDF_ROOTS", [tmp_path])
    with http_api.get_db() as conn:
        conn.execute("UPDATE papers SET pdf_path = ? WHERE id = 1", (str(pdf_path),))
        conn.commit()

    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "对当前条目触发同步，下载并附加 PDF，先 dry-run，确认后 apply",
            "item": {
                "zotero_item_key": "ABCD1234",
                "library_id": 1,
                "title": "Agentic Zotero API Sync",
                "arxiv_id": "2602.99999",
                "tags": ["rh-paper-id:1", "rh-topic:demo-topic"],
            },
        },
    )

    assert response.status_code == 200, response.text
    assert "event: ready" in response.text
    assert "event: done" in response.text
    assert "event: started" not in response.text
    assert "event: action_preview" in response.text
    assert '"action_type":"zotero_attach_pdf"' in response.text
    assert '"handler":"zotero_import_file_attachment"' in response.text
    assert f'"pdf_path":"{str(pdf_path)}"' in response.text
    assert '"parent_item_key":"ABCD1234"' in response.text
    assert "PDF 附件" in response.text


def test_zotero_unsupported_write_intent_classifier_catches_pdf_attachment():
    from research_harness_mcp import http_api

    assert http_api._looks_like_unsupported_zotero_write_request(
        "对当前条目 SG97W99P 同步，下载并附加 PDF"
    )
    assert http_api._looks_like_unsupported_zotero_write_request(
        "给这篇论文添加 Zotero 标签"
    )
    assert not http_api._looks_like_unsupported_zotero_write_request(
        "这篇论文为什么值得读？"
    )
    assert not http_api._looks_like_unsupported_zotero_write_request(
        "把这篇论文导入当前目录"
    )


def test_zotero_chat_ready_payload_reports_context_and_actions(client: TestClient):
    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "这个目录可以怎么推进？",
            "item": {
                "library_id": 1,
                "current_directory_key": "CURRDIR1",
                "current_directory_name": "demo-topic",
                "current_directory_path": "Research Harness / demo-topic",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert '"kind":"collection"' in response.text
    assert "init_topic_from_collection" in response.text
    assert "sync_rh_missing_papers_to_collection" in response.text


def test_zotero_chat_stream_returns_seed_paper_preview_for_empty_collection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from research_harness_mcp import http_api

    def fake_search(api, *, query, topic_id=None, max_results=50):
        assert topic_id == 1
        assert query == "demo-topic"
        assert max_results == 3
        return {
            "papers": [
                {
                    "title": "Seed Paper One",
                    "authors": ["Ada Lovelace"],
                    "year": 2026,
                    "venue": "ICLR",
                    "doi": "10.1234/seed-one",
                    "arxiv_id": "",
                    "url": "https://example.test/seed-one",
                    "snippet": "A seed paper.",
                    "citation_count": 12,
                },
                {
                    "title": "Seed Paper Two",
                    "authors": ["Grace Hopper"],
                    "year": 2025,
                    "venue": "NeurIPS",
                    "doi": "",
                    "arxiv_id": "2501.00002",
                    "url": "https://arxiv.org/abs/2501.00002",
                    "snippet": "Another seed paper.",
                    "citation_count": 24,
                },
            ],
            "provider_errors": [],
        }

    def should_not_call_codex(**kwargs):
        raise AssertionError(
            "Codex stream should not run for deterministic seed previews"
        )

    monkeypatch.setattr(http_api, "_search_papers_impl", fake_search)
    monkeypatch.setattr(http_api, "_stream_zotero_codex_turn", should_not_call_codex)

    response = client.post(
        "/api/zotero/chat/stream",
        json={
            "message": "帮我找到最开始的 3 篇种子论文",
            "item": {
                "current_directory_key": "EMPTYDIR",
                "current_directory_name": "demo-topic",
                "current_directory_path": "Research Harness / demo-topic",
                "library_id": "1",
                "library_type": "user",
            },
        },
    )

    assert response.status_code == 200, response.text
    assert "event: ready" in response.text
    assert "event: action_preview" in response.text
    assert "event: done" in response.text
    assert "event: started" not in response.text
    assert '"action_type":"zotero_seed_paper_search"' in response.text
    assert '"query":"demo-topic"' in response.text
    assert '"topic_id":1' in response.text
    assert '"target_collection_key":"EMPTYDIR"' in response.text
    assert '"candidate_sources":["10.1234/seed-one","2501.00002"]' in response.text
    assert '"path":"/api/zotero/seed-papers/apply"' in response.text
    assert "Seed Paper One" in response.text
    assert "入库并导入" in response.text


def test_zotero_seed_search_intent_classifier_catches_initial_folder_requests():
    from research_harness_mcp import http_api

    assert http_api._looks_like_zotero_seed_search_request("帮我找到最开始的几篇文章")
    assert http_api._looks_like_zotero_seed_search_request(
        "这个空目录先推荐 5 篇 seed papers"
    )
    assert not http_api._looks_like_zotero_seed_search_request(
        "把这个主题里精读过的 3 篇论文导入当前目录"
    )


def test_zotero_import_count_parses_multi_character_chinese_numbers():
    from research_harness_mcp import http_api

    assert http_api._extract_zotero_import_count("导入十二篇论文到当前目录") == 12
    assert http_api._extract_zotero_import_count("导入二十篇论文到当前目录") == 20
    assert http_api._extract_zotero_import_count("导入二十三篇论文到当前目录") == 23
