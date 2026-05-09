"""Tests for cs_classify primitive (LLMClient mocked)."""

from __future__ import annotations

import json

import pytest

from research_harness.cli import CS_DOMAIN_SEED
from research_harness.primitives.cs_classify import (
    GENERIC_BLOCKLIST,
    VALID_DOMAINS,
    _parse_response,
    _slugify,
    cs_classify,
)
from research_harness.storage.db import Database


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "cls.db")
    d.migrate()
    conn = d.connect()
    try:
        for name, description in CS_DOMAIN_SEED:
            conn.execute(
                "INSERT OR IGNORE INTO domains (name, description) VALUES (?, ?)",
                (name, description),
            )
        conn.commit()
    finally:
        conn.close()
    return d


def _seed_paper(conn, pid: int, title: str, abstract: str) -> None:
    conn.execute(
        "INSERT INTO papers (id, title, authors, year, venue, abstract, "
        "arxiv_id, s2_id, doi) "
        "VALUES (?, ?, '[]', 2024, 'nips', ?, ?, ?, ?)",
        (pid, title, abstract, f"arxiv_{pid}", f"s2_{pid}", f"10.test/{pid}"),
    )


class _StubClient:
    """Minimal LLMClient stand-in whose .chat(...) returns a fixed JSON."""

    def __init__(self, payload: dict | list[dict]):
        self._payload = payload
        self._i = 0

    def chat(self, prompt: str, **_kw) -> str:
        if isinstance(self._payload, list):
            p = self._payload[min(self._i, len(self._payload) - 1)]
            self._i += 1
        else:
            p = self._payload
        return json.dumps(p)


def test_slugify():
    assert _slugify("Reinforcement Learning from Human Feedback") == (
        "reinforcement-learning-from-human-feedback"
    )
    assert _slugify("") == "unknown"
    assert _slugify("   ") == "unknown"


def test_parse_response_valid_json():
    raw = json.dumps(
        {
            "domain": "cs.LG",
            "research_areas": ["graph neural networks", "contrastive learning"],
            "rationale": "paper is about GNN pretraining",
        }
    )
    d, areas, rat = _parse_response(raw)
    assert d == "cs.LG"
    assert "graph neural networks" in areas
    assert rat.startswith("paper")


def test_parse_response_strips_markdown_fences():
    raw = '```json\n{"domain": "cs.CV", "research_areas": ["diffusion models"], "rationale": "x"}\n```'
    d, areas, rat = _parse_response(raw)
    assert d == "cs.CV"
    assert areas == ["diffusion models"]


def test_parse_response_filters_generic_terms():
    raw = json.dumps(
        {
            "domain": "cs.LG",
            "research_areas": ["machine learning", "graph neural networks", "research"],
            "rationale": "x",
        }
    )
    _, areas, _ = _parse_response(raw)
    # "machine learning" and "research" filtered
    assert areas == ["graph neural networks"]


def test_parse_response_invalid_domain_coerces_to_other():
    raw = json.dumps(
        {"domain": "cs.SOMETHING_NEW", "research_areas": ["foo"], "rationale": "x"}
    )
    d, _, _ = _parse_response(raw)
    assert d == "cs.OTHER"


def test_parse_response_malformed_falls_back():
    d, areas, rat = _parse_response("not a json at all")
    assert d == "cs.OTHER"
    assert areas == []
    assert rat == "parse_error"


def test_classify_single_paper_writes_all_rows(db):
    conn = db.connect()
    try:
        _seed_paper(conn, 1, "Attention Is All You Need", "Transformer architecture")
        conn.commit()
    finally:
        conn.close()

    client = _StubClient(
        {
            "domain": "cs.LG",
            "research_areas": ["transformer architecture"],
            "rationale": "transformers",
        }
    )
    out = cs_classify(db=db, paper_ids=[1], client=client)
    assert len(out.classified) == 1
    assert out.skipped == []

    conn = db.connect()
    try:
        # Domain row
        pd = conn.execute(
            "SELECT d.name, pd.is_primary FROM paper_domains pd "
            "JOIN domains d ON d.id = pd.domain_id WHERE pd.paper_id = 1"
        ).fetchone()
        assert pd["name"] == "cs.LG"
        assert pd["is_primary"] == 1

        # Research area row
        pra = conn.execute(
            "SELECT ra.name, pra.is_primary FROM paper_research_areas pra "
            "JOIN research_areas ra ON ra.id = pra.research_area_id "
            "WHERE pra.paper_id = 1"
        ).fetchall()
        assert len(pra) == 1
        assert pra[0]["name"] == "transformer architecture"
        assert pra[0]["is_primary"] == 1
    finally:
        conn.close()


def test_classify_is_idempotent(db):
    conn = db.connect()
    try:
        _seed_paper(conn, 1, "Title", "Abstract")
        conn.commit()
    finally:
        conn.close()

    client = _StubClient(
        {
            "domain": "cs.LG",
            "research_areas": ["graph neural networks"],
            "rationale": "gnn",
        }
    )
    cs_classify(db=db, paper_ids=[1], client=client)
    # Second run with DIFFERENT result should replace, not duplicate
    client2 = _StubClient(
        {
            "domain": "cs.CV",
            "research_areas": ["diffusion models"],
            "rationale": "diff",
        }
    )
    cs_classify(db=db, paper_ids=[1], client=client2)

    conn = db.connect()
    try:
        domains = conn.execute(
            "SELECT d.name FROM paper_domains pd "
            "JOIN domains d ON d.id = pd.domain_id WHERE pd.paper_id = 1"
        ).fetchall()
        areas = conn.execute(
            "SELECT ra.name FROM paper_research_areas pra "
            "JOIN research_areas ra ON ra.id = pra.research_area_id "
            "WHERE pra.paper_id = 1"
        ).fetchall()
    finally:
        conn.close()
    # Should be replaced with latest classification
    assert [d[0] for d in domains] == ["cs.CV"]
    assert [a[0] for a in areas] == ["diffusion models"]


def test_classify_skips_empty_papers(db):
    conn = db.connect()
    try:
        _seed_paper(conn, 1, "", "")
        _seed_paper(conn, 2, "Valid Title", "Valid abstract")
        conn.commit()
    finally:
        conn.close()

    client = _StubClient(
        {
            "domain": "cs.LG",
            "research_areas": ["an area"],
            "rationale": "x",
        }
    )
    out = cs_classify(db=db, paper_ids=[1, 2], client=client)
    assert out.skipped == [1]
    assert [c.paper_id for c in out.classified] == [2]


def test_classify_handles_llm_failure_gracefully(db):
    conn = db.connect()
    try:
        _seed_paper(conn, 1, "Title", "Abstract")
        _seed_paper(conn, 2, "Title2", "Abstract2")
        conn.commit()
    finally:
        conn.close()

    class _FlakyClient:
        def __init__(self):
            self.calls = 0

        def chat(self, prompt: str, **_kw) -> str:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("LLM outage")
            return json.dumps(
                {"domain": "cs.LG", "research_areas": ["ok area"], "rationale": "ok"}
            )

    out = cs_classify(db=db, paper_ids=[1, 2], client=_FlakyClient())
    assert out.skipped == [1]
    assert len(out.classified) == 1
    assert out.classified[0].paper_id == 2


def test_invalid_domain_falls_back_to_other(db):
    conn = db.connect()
    try:
        _seed_paper(conn, 1, "Quantum Title", "Quantum abstract")
        conn.commit()
    finally:
        conn.close()

    # LLM returns an unrecognized domain; classifier coerces to cs.OTHER
    client = _StubClient(
        {
            "domain": "cs.QU",  # not in VALID_DOMAINS
            "research_areas": ["quantum algorithms"],
            "rationale": "quantum",
        }
    )
    out = cs_classify(db=db, paper_ids=[1], client=client)
    assert out.classified[0].domain == "cs.OTHER"

    conn = db.connect()
    try:
        pd = conn.execute(
            "SELECT d.name FROM paper_domains pd "
            "JOIN domains d ON d.id = pd.domain_id WHERE pd.paper_id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert pd["name"] == "cs.OTHER"


def test_generic_blocklist_is_nonempty():
    # Sanity — we want the blocklist to actually filter something
    assert "machine learning" in GENERIC_BLOCKLIST
    assert "deep learning" in GENERIC_BLOCKLIST


def test_valid_domains_includes_other():
    assert "cs.OTHER" in VALID_DOMAINS
    assert len(VALID_DOMAINS) == 15
