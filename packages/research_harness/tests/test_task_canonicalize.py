"""Tests for task_canonicalize primitive (LLMClient mocked)."""

from __future__ import annotations

import json

import pytest

from research_harness.primitives.task_canonicalize import (
    _parse_groups,
    task_canonicalize,
)
from research_harness.storage.db import Database


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "tc.db")
    d.migrate()
    conn = d.connect()
    try:
        conn.execute("INSERT INTO topics (name) VALUES ('test-topic')")
        conn.execute(
            "INSERT INTO papers (id, title, authors, abstract, arxiv_id, s2_id, doi) "
            "VALUES (1, 't', '[]', '', 'ax1', 's1', '10.test/1')"
        )
        conn.execute(
            "INSERT INTO papers (id, title, authors, abstract, arxiv_id, s2_id, doi) "
            "VALUES (2, 't', '[]', '', 'ax2', 's2', '10.test/2')"
        )
        conn.commit()
    finally:
        conn.close()
    return d


def _seed_claim(conn, topic_id: int, paper_id: int, task: str, claim_text: str = "x"):
    conn.execute(
        "INSERT INTO normalized_claims "
        "(topic_id, paper_id, claim_text, method, task) "
        "VALUES (?, ?, ?, 'mX', ?)",
        (topic_id, paper_id, claim_text, task),
    )


class _StubClient:
    def __init__(self, payload):
        self._payload = payload

    def chat(self, prompt: str, **_kw) -> str:
        if isinstance(self._payload, Exception):
            raise self._payload
        return json.dumps(self._payload)


def test_parse_groups_valid():
    raw = json.dumps(
        [
            {
                "canonical": "sentiment analysis",
                "members": ["sentiment classification", "sentiment detection"],
            },
            {"canonical": "stance detection", "members": ["stance detection"]},
        ]
    )
    groups = _parse_groups(raw)
    assert len(groups) == 2
    assert groups[0].canonical == "sentiment analysis"
    assert "sentiment classification" in groups[0].members


def test_parse_groups_strips_fences():
    raw = '```json\n[{"canonical": "c", "members": ["m"]}]\n```'
    groups = _parse_groups(raw)
    assert len(groups) == 1
    assert groups[0].canonical == "c"


def test_parse_groups_malformed_returns_empty():
    assert _parse_groups("gibberish") == []
    assert _parse_groups("[{bad json}]") == []


def test_parse_groups_filters_missing_canonical():
    raw = json.dumps(
        [
            {"canonical": "", "members": ["a"]},
            {"canonical": "ok", "members": ["b"]},
        ]
    )
    groups = _parse_groups(raw)
    assert len(groups) == 1
    assert groups[0].canonical == "ok"


def test_empty_input_short_circuits(db):
    out = task_canonicalize(db=db, client=_StubClient([]))
    assert out.processed_rows == 0
    assert out.group_count == 0


def test_canonicalize_updates_all_cluster_members(db):
    conn = db.connect()
    try:
        topic_id = conn.execute("SELECT id FROM topics LIMIT 1").fetchone()[0]
        _seed_claim(conn, topic_id, 1, "sentiment classification")
        _seed_claim(conn, topic_id, 1, "sentiment detection")
        _seed_claim(conn, topic_id, 2, "sentiment classification")  # dup task
        _seed_claim(conn, topic_id, 2, "stance detection")  # separate cluster
        conn.commit()
    finally:
        conn.close()

    client = _StubClient(
        [
            {
                "canonical": "sentiment analysis",
                "members": ["sentiment classification", "sentiment detection"],
            },
            {"canonical": "stance detection", "members": ["stance detection"]},
        ]
    )
    out = task_canonicalize(db=db, client=client)
    assert out.group_count == 2
    # 3 sentiment rows + 1 stance row = 4 rows updated
    assert out.processed_rows == 4

    conn = db.connect()
    try:
        sent = conn.execute(
            "SELECT COUNT(*) FROM normalized_claims "
            "WHERE task_canonical = 'sentiment analysis'"
        ).fetchone()[0]
        stance = conn.execute(
            "SELECT COUNT(*) FROM normalized_claims "
            "WHERE task_canonical = 'stance detection'"
        ).fetchone()[0]
        untouched = conn.execute(
            "SELECT COUNT(*) FROM normalized_claims WHERE task_canonical IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    assert sent == 3
    assert stance == 1
    assert untouched == 0


def test_canonicalize_idempotent(db):
    """Running twice should not touch rows already canonicalized."""
    conn = db.connect()
    try:
        topic_id = conn.execute("SELECT id FROM topics LIMIT 1").fetchone()[0]
        _seed_claim(conn, topic_id, 1, "task_one")
        conn.commit()
    finally:
        conn.close()

    client = _StubClient([{"canonical": "canonical_one", "members": ["task_one"]}])
    first = task_canonicalize(db=db, client=client)
    assert first.processed_rows == 1

    # Second run: fetch returns nothing because task_canonical IS NOT NULL
    second = task_canonicalize(db=db, client=_StubClient([]))
    assert second.processed_rows == 0


def test_canonicalize_llm_failure_returns_empty(db):
    conn = db.connect()
    try:
        topic_id = conn.execute("SELECT id FROM topics LIMIT 1").fetchone()[0]
        _seed_claim(conn, topic_id, 1, "task_X")
        conn.commit()
    finally:
        conn.close()

    out = task_canonicalize(db=db, client=_StubClient(RuntimeError("LLM down")))
    assert out.processed_rows == 0
    # Row still has task_canonical IS NULL
    conn = db.connect()
    try:
        assert (
            conn.execute(
                "SELECT task_canonical FROM normalized_claims WHERE task = 'task_X'"
            ).fetchone()[0]
            is None
        )
    finally:
        conn.close()
