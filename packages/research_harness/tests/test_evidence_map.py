"""Tests for v2 Step 3.3 — citation-sentence evidence coverage.

Covers:
- _extract_evidence_map produces one entry per citation-marked sentence
- _extract_evidence_map maps numeric [N] tokens to paper_ids via 1-based index
- _classify_relation picks inference/compression/quotation
- check_citation_sentence_evidence_coverage fires on missing entries
"""

from __future__ import annotations

import json

import pytest

from research_harness.execution.llm_primitives import (
    _classify_relation,
    _extract_evidence_map,
    _has_any_citation,
    _sentence_citations,
    _split_sentences,
)
from research_harness.orchestrator.invariants import InvariantChecker
from research_harness.storage.db import Database


# ---------------------------------------------------------------------------
# extractor helpers
# ---------------------------------------------------------------------------


def test_split_sentences_basic():
    text = "First sentence. Second one! Third? And a fourth."
    assert _split_sentences(text) == [
        "First sentence.",
        "Second one!",
        "Third?",
        "And a fourth.",
    ]


def test_has_citation_numeric():
    assert _has_any_citation("This claim [1] is supported.")
    assert _has_any_citation("Recent work [1, 2, 3] shows X.")
    assert not _has_any_citation("No citation here.")


def test_has_citation_latex_and_author_year():
    assert _has_any_citation("Per \\cite{foo2024} the approach works.")
    assert _has_any_citation("The idea (Smith, 2024) holds.")


def test_sentence_citations_numeric_mapping():
    paper_ids = [100, 200, 300]
    got = _sentence_citations("Multiple refs [1, 3] exist.", paper_ids)
    assert got == [100, 300]


def test_sentence_citations_out_of_range():
    paper_ids = [100]
    # [3] is out of range — must be ignored, not crash
    got = _sentence_citations("Ref [3] is bogus.", paper_ids)
    assert got == []


def test_classify_relation():
    assert _classify_relation('Smith writes "the gold standard is X"') == "quotation"
    assert _classify_relation("Results suggest improvement") == "inference"
    assert _classify_relation("Method M outperforms baseline B") == "compression"


def test_extract_evidence_map_end_to_end():
    content = (
        "Transformers are efficient [1]. "
        "They outperform RNNs on many tasks [1, 2]. "
        "No citation here. "
        "Results suggest further scaling helps [2]."
    )
    paper_ids = [42, 99]
    entries = _extract_evidence_map(content, paper_ids)
    # Sentence 0 -> [1] -> paper 42 : 1 entry
    # Sentence 1 -> [1,2] -> papers 42, 99 : 2 entries
    # Sentence 2 -> no citation : 0 entries
    # Sentence 3 -> [2] -> paper 99 : 1 entry
    assert len(entries) == 4
    assert entries[0].source_paper_id == 42
    assert entries[0].relation_type == "compression"
    assert entries[3].relation_type == "inference"
    assert sorted(e.sentence_index for e in entries) == [0, 1, 1, 3]


# ---------------------------------------------------------------------------
# invariant: check_citation_sentence_evidence_coverage
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


@pytest.fixture
def topic_id(db):
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)",
            ("test", "test"),
        )
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (tid, tid, "stub", "stub"),
        )
        conn.commit()
        return tid
    finally:
        conn.close()


def _insert_draft_pack(db, topic_id, sections, evidence_map):
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO project_artifacts
              (topic_id, stage, artifact_type, title, payload_json, status, version)
            VALUES (?, 'write', 'draft_pack', 'Test', ?, 'active', 1)
            """,
            (
                topic_id,
                json.dumps(
                    {
                        "sections": sections,
                        "evidence_map": evidence_map,
                    }
                ),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_coverage_check_passes_when_all_citations_covered(db, topic_id):
    sections = {"introduction": "Recent work [1] is strong. Nothing more."}
    evidence_map = [
        {"section": "introduction", "sentence_index": 0, "source_paper_id": 42}
    ]
    _insert_draft_pack(db, topic_id, sections, evidence_map)

    checker = InvariantChecker(db)
    violations = checker.check_citation_sentence_evidence_coverage(topic_id, "write")
    assert violations == []


def test_coverage_check_fires_on_missing_entry(db, topic_id):
    sections = {"introduction": "Claim one [1]. Claim two [2]. No-cite here."}
    # evidence_map only covers sentence 0 in introduction
    evidence_map = [
        {"section": "introduction", "sentence_index": 0, "source_paper_id": 42}
    ]
    _insert_draft_pack(db, topic_id, sections, evidence_map)

    checker = InvariantChecker(db)
    violations = checker.check_citation_sentence_evidence_coverage(topic_id, "write")
    assert len(violations) == 1
    assert violations[0].check == "citation_sentence_evidence_coverage"
    assert violations[0].severity == "medium"
    assert "introduction" in violations[0].message


def test_coverage_check_skipped_on_non_write_stage(db, topic_id):
    sections = {"introduction": "Uncited [1]."}
    _insert_draft_pack(db, topic_id, sections, [])

    checker = InvariantChecker(db)
    violations = checker.check_citation_sentence_evidence_coverage(topic_id, "analyze")
    assert violations == []


def test_coverage_check_ignores_abstract_conclusion(db, topic_id):
    sections = {
        "abstract": "We claim progress [1].",
        "conclusion": "We conclude [2].",
    }
    _insert_draft_pack(db, topic_id, sections, [])

    checker = InvariantChecker(db)
    violations = checker.check_citation_sentence_evidence_coverage(topic_id, "write")
    # abstract and conclusion are exempt; no violations expected
    assert violations == []
