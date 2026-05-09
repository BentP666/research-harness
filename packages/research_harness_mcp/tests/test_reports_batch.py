"""Smoke tests for PR 3 advisor-report composer endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


def _seed_topic(db_path: Path) -> None:
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO topics (id, name, status) VALUES (1, 'T', 'active')")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "reports.db"
    _seed_topic(db_path)
    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


def _fake_generate_report(
    db, topic_id, *, template, title, draft_missing, extra_instructions
):
    from types import SimpleNamespace

    # Record that extra_instructions was forwarded so the test can assert it.
    _fake_generate_report.last_kwargs = {  # type: ignore[attr-defined]
        "topic_id": topic_id,
        "template": template,
        "extra_instructions": extra_instructions,
    }
    return SimpleNamespace(
        id=42,
        topic_id=topic_id,
        template=template,
        version_minor=1,
        word_count=123,
        metadata={"template": template},
    )


def test_single_report_forwards_extra_instructions(client: TestClient):
    with patch(
        "research_harness.reports.generate_report",
        side_effect=_fake_generate_report,
    ):
        r = client.post(
            "/api/topics/1/reports",
            json={
                "template": "abstract_intro",
                "extra_instructions": "focus on baseline contrast",
            },
        )
    assert r.status_code == 200, r.text
    # The mock recorded the forwarded kwarg:
    assert _fake_generate_report.last_kwargs["extra_instructions"] == (  # type: ignore[attr-defined]
        "focus on baseline contrast"
    )


def test_batch_runs_each_template_and_bubbles_failures(client: TestClient):
    calls: list[str] = []

    def fake(db, topic_id, *, template, title, draft_missing, extra_instructions):
        calls.append(template)
        if template == "full_review":
            raise ValueError(f"no draft yet for {template}")
        from types import SimpleNamespace

        return SimpleNamespace(
            id=100 + len(calls),
            topic_id=topic_id,
            template=template,
            version_minor=len(calls),
            word_count=500,
            metadata={},
        )

    with patch("research_harness.reports.generate_report", side_effect=fake):
        r = client.post(
            "/api/topics/1/reports:batch",
            json={
                "templates": ["abstract_only", "full_review"],
                "extra_instructions": "focus X",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    results: list[dict[str, Any]] = body["results"]
    assert [x["template"] for x in results] == ["abstract_only", "full_review"]
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False
    assert "no draft yet" in results[1]["error"]
    assert calls == ["abstract_only", "full_review"]


def test_batch_rejects_empty_templates(client: TestClient):
    r = client.post(
        "/api/topics/1/reports:batch",
        json={"templates": [], "extra_instructions": ""},
    )
    assert r.status_code == 400
