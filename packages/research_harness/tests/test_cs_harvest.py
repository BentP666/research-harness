"""Tests for cs_harvest primitive (mocked aggregator — no network)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from research_harness.paper_sources import PaperRecord, SearchOutcome, SearchQuery
from research_harness.primitives.cs_harvest import (
    CS_CATEGORIES,
    SEED_QUERIES,
    cs_harvest,
)
from research_harness.storage.db import Database


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "harvest.db")
    d.migrate()
    return d


@dataclass
class _StubAggregator:
    """Returns N synthetic PaperRecords per query; records the call count."""

    per_query: int = 2
    calls: list[SearchQuery] = field(default_factory=list)

    def search(self, query: SearchQuery, **_kw) -> SearchOutcome:
        self.calls.append(query)
        cat = (query.subject_categories or ("unknown",))[0]
        records = [
            PaperRecord(
                title=f"{cat} paper {i} {query.query}",
                authors=["Author A"],
                year=query.year_from,
                venue="nips",
                arxiv_id=f"{cat}_{query.query}_{i}".replace(" ", "_"),
                citation_count=i * 5,
                provider="arxiv",
            )
            for i in range(self.per_query)
        ]
        return SearchOutcome(results=records, provider_errors=[])


def test_harvest_covers_all_categories_and_queries(db):
    agg = _StubAggregator(per_query=1)
    result = cs_harvest(db=db, year=2024, target=10, aggregator=agg)
    assert len(agg.calls) == len(CS_CATEGORIES) * len(SEED_QUERIES)
    assert result.categories_covered == CS_CATEGORIES
    assert result.seed_queries == SEED_QUERIES


def test_harvest_dedupes_by_fingerprint(db):
    """Identical arxiv_id across categories should dedupe to one paper."""

    @dataclass
    class _SameRecordAgg:
        calls: int = 0

        def search(self, query: SearchQuery, **_kw) -> SearchOutcome:
            self.calls += 1
            return SearchOutcome(
                results=[
                    PaperRecord(
                        title="The Same Paper",
                        authors=["A"],
                        year=2024,
                        venue="nips",
                        arxiv_id="2024.00001",
                        provider="arxiv",
                    )
                ],
                provider_errors=[],
            )

    agg = _SameRecordAgg()
    result = cs_harvest(db=db, year=2024, target=10, aggregator=agg)
    assert result.discovered == 1
    assert result.total_ingested == 1
    # No trim needed since below target
    assert result.ingested == 1


def test_harvest_ingests_with_topic_id_none(db):
    agg = _StubAggregator(per_query=1)
    cs_harvest(db=db, year=2024, target=100, aggregator=agg)
    # Verify no paper_topics rows created
    conn = db.connect()
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM paper_topics").fetchone()[0]
        p_cnt = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    finally:
        conn.close()
    assert cnt == 0
    assert p_cnt > 0


def test_harvest_trims_to_target_when_over(db):
    # 2 cats × 2 queries × 5 records = 20 unique
    agg = _StubAggregator(per_query=5)
    result = cs_harvest(
        db=db,
        year=2024,
        target=3,
        aggregator=agg,
        categories=["cs.LG", "cs.CV"],
        seed_queries=["q1", "q2"],
    )
    assert result.total_ingested == 20
    assert result.ingested == 3
    assert len(result.head_paper_ids) == 3


def test_harvest_passes_categories_to_search(db):
    agg = _StubAggregator(per_query=1)
    cs_harvest(
        db=db,
        year=2024,
        target=10,
        aggregator=agg,
        categories=["cs.LG"],
        seed_queries=["attention"],
    )
    # Should have exactly 1 call; categories=("cs.LG",), year_from=year_to=2024
    assert len(agg.calls) == 1
    call = agg.calls[0]
    assert call.subject_categories == ("cs.LG",)
    assert call.year_from == 2024 and call.year_to == 2024
    assert call.query == "attention"


def test_harvest_with_classify_wires_research_areas(db):
    """--classify path seeds domains, then LLM-stubs classify the head papers."""
    # Seed CS domains first
    from research_harness.cli import CS_DOMAIN_SEED

    conn = db.connect()
    try:
        for name, description in CS_DOMAIN_SEED:
            conn.execute(
                "INSERT OR IGNORE INTO domains (name, description) VALUES (?, ?)",
                (name, description),
            )
        conn.commit()
    finally:
        conn.close()

    import json as _json

    class _StubLLM:
        def chat(self, prompt: str, **_kw) -> str:
            return _json.dumps(
                {
                    "domain": "cs.LG",
                    "research_areas": ["attention mechanism"],
                    "rationale": "ok",
                }
            )

    agg = _StubAggregator(per_query=1)
    result = cs_harvest(
        db=db,
        year=2024,
        target=5,
        aggregator=agg,
        classify=True,
        compute_red_ocean=True,
        classify_client=_StubLLM(),
        categories=["cs.LG"],
        seed_queries=["attention"],
    )
    # head_paper_ids should all be classified
    assert result.classified == len(result.head_paper_ids)
    assert result.areas_scored >= 1

    conn = db.connect()
    try:
        # Every head paper got a paper_domains row
        pd_cnt = conn.execute(
            "SELECT COUNT(*) FROM paper_domains WHERE paper_id IN "
            f"({','.join('?' * len(result.head_paper_ids))})",
            result.head_paper_ids,
        ).fetchone()[0]
        # Red-ocean score populated on at least one area
        scored = conn.execute(
            "SELECT COUNT(*) FROM research_areas WHERE red_ocean_score IS NOT NULL"
        ).fetchone()[0]
    finally:
        conn.close()
    assert pd_cnt == len(result.head_paper_ids)
    assert scored >= 1


def test_harvest_tolerates_provider_error(db):
    """A failing provider call should not abort the whole harvest."""

    class _FlakyAgg:
        def __init__(self):
            self.calls = 0

        def search(self, query: SearchQuery, **_kw) -> SearchOutcome:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated provider outage")
            return SearchOutcome(
                results=[
                    PaperRecord(
                        title="survivor",
                        year=2024,
                        venue="nips",
                        arxiv_id=f"survivor_{self.calls}",
                    )
                ],
                provider_errors=[],
            )

    agg = _FlakyAgg()
    result = cs_harvest(
        db=db,
        year=2024,
        target=10,
        aggregator=agg,
        categories=["cs.LG", "cs.CV"],
        seed_queries=["q1"],
    )
    # One call failed, one succeeded
    assert result.discovered == 1
    assert agg.calls == 2
