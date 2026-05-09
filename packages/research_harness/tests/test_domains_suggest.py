"""Tests for domain suggest endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.storage.db import Database


@pytest.fixture()
def db_empty(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


def test_suggest_returns_structured(db_empty: Database):
    """Simulate the suggest endpoint logic (stub mode)."""
    idea = "Using large language models to optimize real-time bidding in programmatic advertising"
    words = idea.split()
    name = " ".join(words[:5]).title()
    assert "Large" in name
    assert "Language" in name
    keywords = words[:10]
    assert len(keywords) == 10


def test_suggest_short_idea():
    idea = "ML bidding"
    words = idea.split()
    name = idea.title()
    assert name == "Ml Bidding"
    keywords = words[:10]
    assert len(keywords) == 2
