from __future__ import annotations

from research_harness.storage.db import Database
from research_harness.verification.citation_registry import (
    CitationSource,
    SourceRegistry,
    sanitize_citations,
)


def test_sanitizer_removes_hallucinated_reference_and_renumbers() -> None:
    registry = SourceRegistry()
    registry.add(
        CitationSource(
            source_id="paper:1",
            title="Verified Paper",
            url="https://example.org/papers/verified",
            doi="10.1234/verified",
            paper_id=1,
        )
    )
    registry.add(
        CitationSource(
            source_id="paper:2",
            title="Second Paper",
            url="https://arxiv.org/abs/2501.12345",
            arxiv_id="2501.12345",
            paper_id=2,
        )
    )

    text = """The core claim is supported [1], but this one is not [2].
The second valid claim appears later [3].

## References
[1] Verified Paper. https://example.org/papers/verified?utm_source=news
[2] Fabricated Paper. https://malicious.example/fake
[3] Second Paper. arXiv:2501.12345
"""

    result = sanitize_citations(text, registry)

    assert result.removed_count == 1
    assert result.valid_count == 2
    assert "[2] Fabricated Paper" not in result.sanitized_text
    assert "this one is not [2]" not in result.sanitized_text
    assert "supported [1]" in result.sanitized_text
    assert "later [2]" in result.sanitized_text
    assert "[1] Verified Paper. https://example.org/papers/verified" in result.sanitized_text
    assert "[2] Second Paper. arXiv:2501.12345" in result.sanitized_text


def test_sanitizer_repairs_truncated_url_when_unique() -> None:
    registry = SourceRegistry()
    registry.add(
        CitationSource(
            source_id="paper:10",
            title="Long URL Paper",
            url="https://example.org/papers/very-long-slug",
            paper_id=10,
        )
    )

    text = """A claim cites a clipped source [1].

References
[1] Long URL Paper. https://example.org/papers/very-long
"""

    result = sanitize_citations(text, registry)

    assert result.repaired_count == 1
    assert result.removed_count == 0
    assert "https://example.org/papers/very-long-slug" in result.sanitized_text


def test_source_registry_can_be_built_from_topic_papers(tmp_path) -> None:
    db = Database(tmp_path / "topic.db")
    db.migrate()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO topics (id, name) VALUES (1, 'citation-topic')")
        conn.execute(
            """
            INSERT INTO papers (id, title, doi, arxiv_id, s2_id, url)
            VALUES (7, 'Topic Paper', '10.9999/topic', '2601.00001', 's2-topic',
                    'https://example.org/topic-paper')
            """
        )
        conn.execute(
            "INSERT INTO paper_topics (paper_id, topic_id, relevance) VALUES (7, 1, 'high')"
        )
        conn.commit()
    finally:
        conn.close()

    registry = SourceRegistry.from_topic(db, 1)

    assert registry.resolve_url("https://example.org/topic-paper?utm_campaign=x")
    assert registry.resolve_doi("https://doi.org/10.9999/topic")
    assert registry.resolve_arxiv("arXiv:2601.00001")


def test_citation_sanitize_primitive_records_hallucinated_rows_when_project_exists(
    tmp_path,
) -> None:
    from research_harness.primitives.verification_impls import citation_sanitize

    db = Database(tmp_path / "primitive.db")
    db.migrate()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO topics (id, name) VALUES (1, 'primitive-topic')")
        conn.execute(
            "INSERT INTO projects (id, topic_id, name) VALUES (1, 1, 'primitive-topic')"
        )
        conn.execute(
            """
            INSERT INTO papers (id, title, doi, arxiv_id, s2_id, url)
            VALUES (1, 'Real Paper', '10.1111/real', '', '', 'https://example.org/real')
            """
        )
        conn.execute(
            "INSERT INTO paper_topics (paper_id, topic_id, relevance) VALUES (1, 1, 'high')"
        )
        conn.commit()
    finally:
        conn.close()

    result = citation_sanitize(
        db=db,
        topic_id=1,
        text="""Supported [1], unsupported [2].

## References
[1] Real Paper. https://example.org/real
[2] Ghost Paper. https://ghost.example/nope
""",
    )

    assert result.removed_count == 1
    assert result.hallucinated_recorded == 1

    conn = db.connect()
    try:
        row = conn.execute(
            """
            SELECT status, title, source FROM citation_verifications
            WHERE topic_id = 1 AND status = 'hallucinated'
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["title"] == "Ghost Paper. https://ghost.example/nope"
    assert row["source"] == "citation_sanitize"
