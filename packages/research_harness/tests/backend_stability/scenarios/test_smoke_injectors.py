"""Self-tests for fault injectors.

These tests verify the injectors do what they claim, NOT that the
orchestrator handles them gracefully (that's Phase 1's main work).
Keeps the injector library trustworthy so later scenarios can rely on it.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ..fixtures import load_topic
from ..injectors import llm as llm_inj
from ..injectors import storage as storage_inj


# ---------------------------------------------------------------------------
# LLM injectors
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_llm_rate_limit_raises_then_succeeds():
    from llm_router import client as llm_client

    with llm_inj.llm_rate_limit(fail_n=2):
        provider = llm_client.get_provider("anthropic")
        with pytest.raises(llm_inj.RateLimitError):
            provider("hello", "claude-haiku")
        with pytest.raises(llm_inj.RateLimitError):
            provider("hello", "claude-haiku")
        result = provider("hello", "claude-haiku")
        assert "after_rate_limit" in result


@pytest.mark.smoke
def test_llm_empty_response_returns_empty_string():
    from llm_router import client as llm_client

    with llm_inj.llm_empty_response():
        provider = llm_client.get_provider("anthropic")
        assert provider("hi", "claude-haiku") == ""


@pytest.mark.smoke
def test_llm_truncated_json_breaks_json_parse():
    from llm_router import client as llm_client

    with llm_inj.llm_truncated_json():
        provider = llm_client.get_provider("anthropic")
        out = provider("hi", "claude-haiku")
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)


@pytest.mark.smoke
def test_llm_refusal_does_not_parse_as_json():
    from llm_router import client as llm_client

    with llm_inj.llm_refusal():
        provider = llm_client.get_provider("anthropic")
        out = provider("hi", "claude-haiku")
        assert "can't help" in out
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)


@pytest.mark.smoke
def test_llm_unicode_garbage_returns_high_codepoints():
    from llm_router import client as llm_client

    with llm_inj.llm_unicode_garbage():
        provider = llm_client.get_provider("anthropic")
        out = provider("hi", "claude-haiku")
        assert any(ord(c) > 0x10000 for c in out)


# ---------------------------------------------------------------------------
# Storage injectors
# ---------------------------------------------------------------------------


@pytest.mark.smoke
def test_corrupt_paper_row_isolates_change(db):
    loaded = load_topic(db, "small_tfr")
    paper_id = loaded.paper_ids[0]
    with storage_inj.corrupt_paper_row(db, paper_id):
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT authors FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
            assert row["authors"] == "<<<NOT JSON>>>{{"
            with pytest.raises(json.JSONDecodeError):
                json.loads(row["authors"])
        finally:
            conn.close()
    # After exit, the row is restored
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT authors FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        json.loads(row["authors"])  # must parse — restored
    finally:
        conn.close()


@pytest.mark.smoke
def test_sqlite_writer_lock_blocks_concurrent_write(db):
    load_topic(db, "small_tfr")
    with storage_inj.sqlite_writer_lock(db, hold_seconds=0.3):
        with pytest.raises(sqlite3.OperationalError):
            conn = sqlite3.connect(str(db.db_path), timeout=0.1)
            try:
                conn.execute("INSERT INTO topics (name) VALUES ('blocked-write')")
                conn.commit()
            finally:
                conn.close()


@pytest.mark.smoke
def test_drop_index_no_op_when_index_missing(db):
    """Should silently no-op rather than raise."""
    with storage_inj.drop_index(db, "idx_does_not_exist_xyz"):
        pass  # no exception
