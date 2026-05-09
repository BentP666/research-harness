"""Tests for the DB-backed PaperLibrary store (no LLM required).

These sit OUTSIDE paperindex_tests/ (which skip without an LLM key) so
the store's pure persistence contract runs in every CI pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_harness.paperindex.cards.schema import PaperCard
from research_harness.paperindex.library.store import (
    INDEX_DB_FILENAME,
    PaperLibrary,
)
from research_harness.paperindex.types import (
    PaperRecord,
    SectionNode,
    SectionResult,
    StructureResult,
)


def _make_record(paper_id: str = "p1", title: str = "Alpha paper") -> PaperRecord:
    node = SectionNode(
        node_id="sec-1",
        title="Method",
        start_page=2,
        end_page=4,
        section_text="The method uses X",
        summary="Uses X method",
    )
    structure = StructureResult(
        doc_name="alpha.pdf",
        tree=[node],
        pdf_hash="hash-alpha",
        page_count=10,
        raw={"page_count": 10},
    )
    sections = {
        "summary": SectionResult(
            section="summary", content="Alpha summary", source_pdf_hash="hash-alpha"
        ),
    }
    card = PaperCard(paper_id=paper_id, title=title, core_idea="Alpha idea")
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        doc_name="alpha.pdf",
        pdf_hash="hash-alpha",
        page_count=10,
        structure=structure,
        sections=sections,
        card=card,
        source_path="/tmp/alpha.pdf",
    )


def test_save_creates_db_and_list_returns_record(tmp_path: Path) -> None:
    lib = PaperLibrary(tmp_path)
    rec = _make_record()
    lib.save(rec)

    assert (tmp_path / INDEX_DB_FILENAME).exists()
    records = lib.list()
    assert len(records) == 1
    assert records[0].paper_id == "p1"
    assert records[0].title == "Alpha paper"


def test_get_roundtrips_record(tmp_path: Path) -> None:
    lib = PaperLibrary(tmp_path)
    rec = _make_record()
    lib.save(rec)

    loaded = lib.get("p1")
    assert loaded.paper_id == "p1"
    assert loaded.sections["summary"].content == "Alpha summary"
    assert loaded.structure.tree[0].title == "Method"


def test_get_missing_raises(tmp_path: Path) -> None:
    lib = PaperLibrary(tmp_path)
    with pytest.raises(FileNotFoundError):
        lib.get("does-not-exist")


def test_list_catalog_has_node_titles(tmp_path: Path) -> None:
    lib = PaperLibrary(tmp_path)
    lib.save(_make_record())

    catalog = lib.list_catalog()
    assert len(catalog) == 1
    assert catalog[0].paper_id == "p1"
    assert "Method" in catalog[0].node_titles
    assert "summary" in catalog[0].section_names


def test_find_by_hash_returns_match(tmp_path: Path) -> None:
    lib = PaperLibrary(tmp_path)
    lib.save(_make_record())

    hit = lib.find_by_hash("hash-alpha")
    assert hit is not None
    assert hit.paper_id == "p1"

    miss = lib.find_by_hash("nope")
    assert miss is None


def test_save_is_upsert_and_sorted_by_title(tmp_path: Path) -> None:
    lib = PaperLibrary(tmp_path)
    lib.save(_make_record(paper_id="p1", title="Zeta paper"))
    lib.save(_make_record(paper_id="p2", title="Alpha paper"))
    # Re-save p1 with same id — should upsert, not duplicate
    lib.save(_make_record(paper_id="p1", title="Zeta paper v2"))

    records = lib.list()
    assert len(records) == 2
    # Sorted by LOWER(title): Alpha before Zeta
    assert records[0].paper_id == "p2"
    assert records[1].title == "Zeta paper v2"


def test_legacy_json_migration_runs_on_first_open(tmp_path: Path) -> None:
    """Drop a pre-0.4 JSON file into <root>/papers/ and confirm it loads."""
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    rec = _make_record(paper_id="legacy-1", title="Legacy paper")
    (papers_dir / "legacy-1.json").write_text(
        json.dumps(rec.to_dict(), ensure_ascii=False), encoding="utf-8"
    )

    lib = PaperLibrary(tmp_path)
    records = lib.list()
    assert len(records) == 1
    assert records[0].paper_id == "legacy-1"
    # DB file now exists and is authoritative
    assert (tmp_path / INDEX_DB_FILENAME).exists()


def test_legacy_migration_is_idempotent(tmp_path: Path) -> None:
    """Second construction must not re-import or duplicate legacy rows."""
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    rec = _make_record(paper_id="legacy-2", title="Once-migrated")
    (papers_dir / "legacy-2.json").write_text(
        json.dumps(rec.to_dict(), ensure_ascii=False), encoding="utf-8"
    )

    PaperLibrary(tmp_path).list()
    # Rewrite the legacy file with a different title — must be ignored
    # since the DB is now authoritative.
    rec2 = _make_record(paper_id="legacy-2", title="Should NOT reappear")
    (papers_dir / "legacy-2.json").write_text(
        json.dumps(rec2.to_dict(), ensure_ascii=False), encoding="utf-8"
    )
    records = PaperLibrary(tmp_path).list()
    assert len(records) == 1
    assert records[0].title == "Once-migrated"
