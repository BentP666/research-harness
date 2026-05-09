"""Tests for v2 Step 5.2 — adversarial section review.

The adversarial pass is stubbed by monkeypatching the internal
_client_chat so tests do not hit any LLM API.
"""

from __future__ import annotations

import json

import pytest

from research_harness.execution import llm_primitives
from research_harness.execution.llm_primitives import adversarial_section_review
from research_harness.storage.db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


def _stub_chat_with(response_json: dict):
    """Returns a fake _client_chat that ignores the prompt and returns JSON."""
    payload = json.dumps(response_json)

    def fake_chat(client, prompt: str) -> str:
        return payload

    return fake_chat


def test_adversarial_review_structured_output(db, monkeypatch):
    monkeypatch.setattr(
        llm_primitives,
        "_client_chat",
        _stub_chat_with(
            {
                "weaknesses": [
                    {
                        "category": "experimental_design",
                        "description": "Only one seed reported",
                        "evidence": "Table 1 shows a single run per config",
                        "severity": "critical",
                    },
                    {
                        "category": "baseline_fairness",
                        "description": "Strongest baseline missing",
                        "evidence": "No comparison against method X (2024)",
                        "severity": "major",
                    },
                    {
                        "category": "minor",  # will be normalized
                        "description": "Typo",
                        "evidence": "Page 4 line 12",
                        "severity": "trivial",  # will normalize to minor
                    },
                ]
            }
        ),
    )
    # _get_client itself is wrapped in a try/except that builds a stub client,
    # but to be extra safe monkeypatch it too.
    monkeypatch.setattr(
        llm_primitives,
        "_get_client",
        lambda *a, **k: type("C", (), {"model": "stub-model"})(),
    )

    result = adversarial_section_review(
        db=db,
        section="introduction",
        content="A sentence. Another sentence.",
        target_words=500,
    )

    assert result["section"] == "introduction"
    assert len(result["weaknesses"]) == 3
    assert result["critical_count"] == 1
    assert result["major_count"] == 1
    # severity 'trivial' was normalized to 'minor'
    assert result["minor_count"] == 1


def test_adversarial_review_drops_items_without_evidence(db, monkeypatch):
    monkeypatch.setattr(
        llm_primitives,
        "_client_chat",
        _stub_chat_with(
            {
                "weaknesses": [
                    {
                        "category": "statistical_significance",
                        "description": "No CI reported",
                        "evidence": "",  # empty -> dropped per contract
                        "severity": "major",
                    },
                    {
                        "category": "statistical_significance",
                        "description": "Missing error bars",
                        "evidence": "Figure 3 has only point estimates",
                        "severity": "major",
                    },
                ]
            }
        ),
    )
    monkeypatch.setattr(
        llm_primitives,
        "_get_client",
        lambda *a, **k: type("C", (), {"model": "stub-model"})(),
    )

    result = adversarial_section_review(db=db, section="results", content="body")
    assert len(result["weaknesses"]) == 1
    assert result["weaknesses"][0]["description"] == "Missing error bars"


def test_adversarial_review_handles_empty_response(db, monkeypatch):
    monkeypatch.setattr(
        llm_primitives, "_client_chat", _stub_chat_with({"weaknesses": []})
    )
    monkeypatch.setattr(
        llm_primitives,
        "_get_client",
        lambda *a, **k: type("C", (), {"model": "stub-model"})(),
    )

    result = adversarial_section_review(db=db, section="discussion", content="body")
    assert result["weaknesses"] == []
    assert result["critical_count"] == 0
