"""CS yearly paper harvest — topicless bulk ingestion.

Harvests papers across 14 arxiv CS categories with a small set of seed
queries, deduplicates by doi/arxiv_id/title, ingests into the paper pool
with topic_id=None, then uses head_paper_rank to identify the top-N
"head" papers worth deep processing. Non-head papers remain in the pool
(not deleted) so Phase 2 classification can decide whether to tag or
ignore them.

No LLM. Network access via SearchAggregator. Idempotent — re-running
with the same year re-uses the existing paper pool entries rather than
creating duplicates (PaperPool.ingest is upsert-style).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.paper_pool import PaperPool
from ..paper_sources import PaperRecord, SearchAggregator, SearchQuery, SearchProvider
from ..storage.db import Database
from ..storage.models import Paper
from .head_paper import head_paper_rank
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

logger = logging.getLogger(__name__)


CS_CATEGORIES: list[str] = [
    "cs.AI",
    "cs.LG",
    "cs.CV",
    "cs.CL",
    "cs.IR",
    "cs.RO",
    "cs.CR",
    "cs.DB",
    "cs.DC",
    "cs.DS",
    "cs.HC",
    "cs.PL",
    "cs.SE",
    "cs.SY",
]

SEED_QUERIES: list[str] = [
    "machine learning",
    "deep learning",
    "neural network",
    "transformer",
    "large language model",
]


@dataclass
class HarvestResult:
    year: int
    ingested: int  # papers kept as head (or all, if below target)
    discovered: int  # unique papers returned by search (pre-rank)
    total_ingested: int  # all papers inserted into pool (pre-trim)
    categories_covered: list[str]
    seed_queries: list[str]
    head_paper_ids: list[int] = field(default_factory=list)
    classified: int = 0  # how many head papers got cs_classify'd
    areas_scored: int = 0  # how many research_areas had red-ocean computed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CS_HARVEST_SPEC = PrimitiveSpec(
    name="cs_harvest",
    category=PrimitiveCategory.RETRIEVAL,
    description=(
        "Harvest papers from 14 CS categories × seed queries for a given year, "
        "dedupe, ingest with topic_id=None, rank with head_paper_rank, "
        "return top-target as head papers. No LLM."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "year": {"type": "integer"},
            "target": {
                "type": "integer",
                "default": 1000,
                "description": "Keep top-N papers as 'head' after ranking.",
            },
            "per_provider_limit": {
                "type": "integer",
                "default": 50,
                "description": "Per-provider cap per (category, seed_query) call.",
            },
        },
        "required": ["year"],
    },
    output_type="HarvestResult",
    requires_llm=False,
    idempotent=True,
)


def _record_to_paper(rec: PaperRecord) -> Paper:
    return Paper(
        title=rec.title,
        authors=list(rec.authors),
        affiliations=list(rec.affiliations),
        year=rec.year,
        venue=rec.venue,
        abstract=rec.abstract,
        doi=rec.doi,
        arxiv_id=rec.arxiv_id,
        s2_id=rec.s2_id,
        url=rec.url,
    )


def _fingerprint(record: PaperRecord) -> str:
    return record.fingerprint()


@register_primitive(CS_HARVEST_SPEC)
def cs_harvest(
    *,
    db: Database,
    year: int,
    target: int = 1000,
    per_provider_limit: int = 50,
    aggregator: SearchAggregator | None = None,
    providers: list[SearchProvider] | None = None,
    categories: list[str] | None = None,
    seed_queries: list[str] | None = None,
    classify: bool = False,
    compute_red_ocean: bool = False,
    classify_client: Any = None,
    **_: Any,
) -> HarvestResult:
    cats = categories or CS_CATEGORIES
    queries = seed_queries or SEED_QUERIES

    # Build aggregator if not supplied (tests may pass a stub)
    if aggregator is None:
        if providers is None:
            from ..paper_source_clients import build_provider_suite

            providers = build_provider_suite()
        aggregator = SearchAggregator(providers)

    # Fan out — cross product of categories × seed queries
    seen: dict[str, PaperRecord] = {}
    for cat in cats:
        for q in queries:
            sq = SearchQuery(
                query=q,
                subject_categories=(cat,),
                year_from=year,
                year_to=year,
                limit=per_provider_limit,
                per_provider_limit=per_provider_limit,
            )
            try:
                outcome = aggregator.search(sq)
            except Exception as exc:
                logger.warning(
                    "cs_harvest: search failed for cat=%s q=%r: %s", cat, q, exc
                )
                continue
            # SearchAggregator.search returns SearchOutcome (with .results)
            records = outcome.results if hasattr(outcome, "results") else outcome
            for rec in records:
                fp = _fingerprint(rec)
                if fp and fp not in seen:
                    seen[fp] = rec

    deduped = list(seen.values())
    discovered = len(deduped)

    # Ingest — PaperPool.ingest is upsert-style (existing papers get merged)
    ingested_ids: list[int] = []
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        for rec in deduped:
            paper = _record_to_paper(rec)
            try:
                pid = pool.ingest(paper, topic_id=None)
                if rec.citation_count is not None:
                    conn.execute(
                        "UPDATE papers SET citation_count = ? WHERE id = ?",
                        (rec.citation_count, pid),
                    )
                ingested_ids.append(pid)
            except Exception as exc:
                logger.warning(
                    "cs_harvest: ingest failed for %r: %s", rec.title[:80], exc
                )
        conn.commit()
    finally:
        conn.close()

    total_ingested = len(ingested_ids)

    # Rank and trim to head set
    head_ids: list[int] = ingested_ids
    if total_ingested > target:
        ranked = head_paper_rank(
            db=db,
            year=year,
            paper_ids=ingested_ids,
            current_year=year,
            target=target,
        )
        head_ids = [r.paper_id for r in ranked.ranked]

    # Optional: classify head papers → research_areas, then score red-ocean
    classified_count = 0
    areas_scored = 0
    if classify and head_ids:
        from .cs_classify import cs_classify

        cls_out = cs_classify(db=db, paper_ids=head_ids, client=classify_client)
        classified_count = len(cls_out.classified)

        if compute_red_ocean and classified_count:
            from .red_ocean import compute_area_red_ocean

            conn = db.connect()
            try:
                placeholders = ",".join("?" * len(head_ids))
                area_rows = conn.execute(
                    f"SELECT DISTINCT research_area_id FROM paper_research_areas "
                    f"WHERE paper_id IN ({placeholders})",
                    head_ids,
                ).fetchall()
                area_ids = [int(r[0]) for r in area_rows]
            finally:
                conn.close()
            for aid in area_ids:
                try:
                    compute_area_red_ocean(db=db, research_area_id=aid)
                    areas_scored += 1
                except Exception as exc:
                    logger.warning(
                        "cs_harvest: red-ocean failed for area %d: %s", aid, exc
                    )

    return HarvestResult(
        year=year,
        ingested=len(head_ids),
        discovered=discovered,
        total_ingested=total_ingested,
        categories_covered=list(cats),
        seed_queries=list(queries),
        head_paper_ids=head_ids,
        classified=classified_count,
        areas_scored=areas_scored,
    )
