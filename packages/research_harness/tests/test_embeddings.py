"""Tests for v2 Step 7 — embedding service with SQLite content-hash cache."""

from __future__ import annotations

import pytest

from research_harness.embeddings import (
    clear_cache,
    embed_texts,
    read_cached,
    write_cached,
)
from research_harness.embeddings.cache import content_hash, normalize
from research_harness.embeddings.service import cosine_similarity
from research_harness.storage.db import Database


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Force deterministic fake provider so tests never hit network.
    monkeypatch.setenv("RESEARCH_HARNESS_EMBEDDING_PROVIDER", "fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


def test_normalize_collapses_whitespace():
    assert normalize("  hello   world  ") == "hello world"
    assert normalize("foo\nbar") == "foo bar"


def test_content_hash_is_whitespace_invariant():
    assert content_hash("foo bar") == content_hash("foo  bar")
    assert content_hash("foo bar") == content_hash("  foo\tbar  ")


def test_embed_fake_is_deterministic(db):
    a = embed_texts(db, ["hello world"])
    b = embed_texts(db, ["hello world"])
    assert a.vectors == b.vectors
    assert a.dim > 0


def test_embed_cache_hits_second_call(db):
    # First call populates cache.
    first = embed_texts(db, ["sample text"])
    assert first.cache_hits == 0
    assert first.cache_misses == 1

    # Second call should hit cache for the same text.
    second = embed_texts(db, ["sample text"])
    assert second.cache_hits == 1
    assert second.cache_misses == 0
    assert second.vectors == first.vectors


def test_embed_mixed_cache_behavior(db):
    embed_texts(db, ["first"])
    mixed = embed_texts(db, ["first", "second"])
    assert mixed.cache_hits == 1
    assert mixed.cache_misses == 1
    assert len(mixed.vectors) == 2


def test_clear_cache_by_provider(db):
    embed_texts(db, ["foo"])
    cleared = clear_cache(db, provider="fake")
    assert cleared >= 1
    after = embed_texts(db, ["foo"])
    assert after.cache_hits == 0


def test_cosine_similarity_basic():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0, 2.0]) == 0.0


def test_read_write_cached_roundtrip(db):
    write_cached(
        db,
        provider="fake",
        model="test-v1",
        pairs=[("abc", [0.1, 0.2, 0.3])],
    )
    out = read_cached(db, provider="fake", model="test-v1", texts=["abc"])
    assert out[content_hash("abc")] == [0.1, 0.2, 0.3]


def test_empty_input_returns_empty(db):
    result = embed_texts(db, [])
    assert result.vectors == []
    assert result.dim == 0
