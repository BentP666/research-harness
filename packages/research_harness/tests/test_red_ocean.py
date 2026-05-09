"""Tests for red_ocean primitives — pure SQL + math, no LLM."""

from __future__ import annotations

import json

import pytest

from research_harness.primitives.red_ocean import (
    GAP_DENSITY_CAP,
    W_CONVERGE,
    W_GAP,
    W_LAB,
    W_VOLUME,
    RedOceanBreakdown,
    _compose,
    _gap_density,
    _lab_concentration,
    _method_convergence,
    _volume_pressure,
    compute_area_red_ocean,
    compute_method_red_ocean,
    compute_task_red_ocean,
    opportunity_angle,
)
from research_harness.storage.db import Database


# ---------------------------------------------------------------------------
# Unit tests for math helpers
# ---------------------------------------------------------------------------


def test_volume_pressure_at_peer_median_is_half():
    # ratio = 1 → log2 = 0 → tanh(0) = 0 → mapped to 0.5
    assert abs(_volume_pressure(10, 10) - 0.5) < 1e-9


def test_volume_pressure_double_is_above_half():
    v = _volume_pressure(20, 10)
    assert 0.5 < v < 1.0


def test_volume_pressure_half_is_below_half():
    v = _volume_pressure(5, 10)
    assert 0.0 < v < 0.5


def test_volume_pressure_zero_peer_median():
    assert _volume_pressure(5, 0) == 1.0
    assert _volume_pressure(0, 0) == 0.0


def test_method_convergence_empty():
    assert _method_convergence([]) == 0.0


def test_method_convergence_single_dominant_method():
    # One method with 9/10 papers → top3 = 9+0+0 / total=10 = 0.9 or close
    assert abs(_method_convergence([9, 1]) - 1.0) < 1e-9
    # top3 sum is 10 when only 2 entries; same as total
    assert _method_convergence([5, 3, 2, 1]) == (5 + 3 + 2) / 11


def test_lab_concentration_single_lab():
    assert _lab_concentration([1.0]) == 1.0


def test_lab_concentration_ten_equal_labs():
    shares = [0.1] * 10
    assert abs(_lab_concentration(shares) - 0.1) < 1e-9


def test_gap_density_capped():
    assert _gap_density(100, 10) == GAP_DENSITY_CAP  # should cap
    assert _gap_density(1, 100) == 0.01


def test_compose_weights_sum_correctly():
    bd = RedOceanBreakdown(
        volume_pressure=1.0,
        method_convergence=1.0,
        lab_concentration=1.0,
        gap_density_cap=0.0,
    )
    assert abs(_compose(bd) - (W_VOLUME + W_CONVERGE + W_LAB)) < 1e-9


def test_compose_subtracts_gap_density():
    bd = RedOceanBreakdown(
        volume_pressure=0.5,
        method_convergence=0.5,
        lab_concentration=0.5,
        gap_density_cap=0.2,
    )
    expected = W_VOLUME * 0.5 + W_CONVERGE * 0.5 + W_LAB * 0.5 - W_GAP * 0.2
    assert abs(_compose(bd) - expected) < 1e-9


def test_compose_clips_to_zero_one():
    bd_high = RedOceanBreakdown(
        volume_pressure=10.0,
        method_convergence=10.0,
        lab_concentration=10.0,
    )
    assert _compose(bd_high) == 1.0
    bd_low = RedOceanBreakdown(gap_density_cap=10.0)
    assert _compose(bd_low) == 0.0


# ---------------------------------------------------------------------------
# Integration tests against real SQLite
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_db(tmp_path):
    """A tiny synthetic topic: 1 domain, 1 research_area with 3 papers,
    one sibling research_area with 1 paper (so peer_median = 1)."""
    d = Database(tmp_path / "ro.db")
    d.migrate()
    conn = d.connect()
    try:
        conn.execute("INSERT INTO domains (name) VALUES ('cs.LG')")
        domain_id = conn.execute("SELECT id FROM domains").fetchone()[0]

        conn.execute("INSERT INTO topics (name) VALUES ('synth-topic')")
        topic_id = conn.execute("SELECT id FROM topics").fetchone()[0]

        conn.execute(
            "INSERT INTO research_areas (domain_id, name, slug, source) "
            "VALUES (?, 'gnn pretraining', 'gnn-pretraining', 'llm')",
            (domain_id,),
        )
        area_id = conn.execute(
            "SELECT id FROM research_areas WHERE slug='gnn-pretraining'"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO research_areas (domain_id, name, slug, source) "
            "VALUES (?, 'sibling', 'sibling', 'llm')",
            (domain_id,),
        )
        sibling_id = conn.execute(
            "SELECT id FROM research_areas WHERE slug='sibling'"
        ).fetchone()[0]

        # 3 papers in main area, 1 in sibling (for peer median calc)
        for pid, aff in [(1, "Stanford"), (2, "Stanford"), (3, "MIT")]:
            conn.execute(
                "INSERT INTO papers (id, title, authors, affiliations, year, "
                "venue, abstract, arxiv_id, s2_id, doi) "
                "VALUES (?, 'p', '[]', ?, 2024, 'nips', '', ?, ?, ?)",
                (pid, json.dumps([aff]), f"a{pid}", f"s{pid}", f"10.t/{pid}"),
            )
            conn.execute(
                "INSERT INTO paper_research_areas "
                "(paper_id, research_area_id, is_primary) VALUES (?, ?, 1)",
                (pid, area_id),
            )
            conn.execute(
                "INSERT INTO paper_domains (paper_id, domain_id, is_primary) "
                "VALUES (?, ?, 1)",
                (pid, domain_id),
            )
        # One paper in sibling
        conn.execute(
            "INSERT INTO papers (id, title, authors, affiliations, year, "
            "venue, abstract, arxiv_id, s2_id, doi) "
            "VALUES (4, 'q', '[]', '[]', 2024, 'nips', '', 'a4', 's4', '10.t/4')"
        )
        conn.execute(
            "INSERT INTO paper_research_areas "
            "(paper_id, research_area_id, is_primary) VALUES (4, ?, 1)",
            (sibling_id,),
        )
        # Method claims so convergence has signal
        for pid, method in [(1, "BERT"), (2, "BERT"), (3, "GPT")]:
            conn.execute(
                "INSERT INTO normalized_claims "
                "(topic_id, paper_id, claim_text, method) "
                "VALUES (?, ?, 'c', ?)",
                (topic_id, pid, method),
            )
        conn.commit()
        yield (
            d,
            {
                "domain_id": domain_id,
                "area_id": area_id,
                "sibling_id": sibling_id,
                "topic_id": topic_id,
            },
        )
    finally:
        conn.close()


def test_compute_area_red_ocean_writes_to_db(seeded_db):
    db, ids = seeded_db
    score = compute_area_red_ocean(db=db, research_area_id=ids["area_id"])
    assert 0.0 <= score.score <= 1.0
    assert score.breakdown.papers == 3

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT red_ocean_score, red_ocean_breakdown FROM research_areas "
            "WHERE id = ?",
            (ids["area_id"],),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] is not None
    bd = json.loads(row[1])
    assert bd["papers"] == 3


def test_compute_area_red_ocean_peer_median(seeded_db):
    """Main area has 3 papers, sibling has 1 → peer_median = 1."""
    db, ids = seeded_db
    score = compute_area_red_ocean(db=db, research_area_id=ids["area_id"])
    assert score.breakdown.peer_median == 1
    # 3 papers vs peer median 1 = 3x the peers → volume_pressure > 0.5
    assert score.breakdown.volume_pressure > 0.5


def test_compute_area_red_ocean_method_convergence(seeded_db):
    """2/3 papers use BERT, 1 uses GPT → convergence = (2+1)/3 = 1.0."""
    db, ids = seeded_db
    score = compute_area_red_ocean(db=db, research_area_id=ids["area_id"])
    # 2 BERT + 1 GPT = all methods in top-3, convergence = 1.0
    assert abs(score.breakdown.method_convergence - 1.0) < 1e-9


def test_compute_area_red_ocean_lab_hhi(seeded_db):
    """2/3 papers at Stanford, 1 at MIT → HHI = (2/3)² + (1/3)² = 4/9 + 1/9 = 5/9."""
    db, ids = seeded_db
    score = compute_area_red_ocean(db=db, research_area_id=ids["area_id"])
    expected_hhi = (2 / 3) ** 2 + (1 / 3) ** 2
    assert abs(score.breakdown.lab_concentration - expected_hhi) < 1e-9


def test_compute_task_red_ocean_no_claims(seeded_db):
    """Non-existent task → score = 0.0 (no papers in scope)."""
    db, ids = seeded_db
    score = compute_task_red_ocean(
        db=db, task_canonical="nonexistent_task", domain_id=ids["domain_id"]
    )
    assert score.breakdown.papers == 0
    assert score.score == 0.0


def test_compute_method_red_ocean_returns_score(seeded_db):
    db, ids = seeded_db
    score = compute_method_red_ocean(
        db=db, method="BERT", research_area_id=ids["area_id"]
    )
    assert 0.0 <= score.score <= 1.0
    assert score.breakdown.papers == 2  # BERT used by papers 1 & 2


# ---------------------------------------------------------------------------
# opportunity_angle — deterministic 2x2x1 partitioning
# ---------------------------------------------------------------------------


def test_opportunity_angle_new_task_mature_method():
    # task cool, method hot
    assert opportunity_angle(0.5, 0.2, 0.9) == "new_task_mature_method"


def test_opportunity_angle_novel_method_known_task():
    # task hot, method cool
    assert opportunity_angle(0.5, 0.9, 0.2) == "novel_method_known_task"


def test_opportunity_angle_frontier():
    # neither red
    assert opportunity_angle(0.2, 0.2, 0.2) == "frontier"


def test_opportunity_angle_red_ocean():
    # both red
    assert opportunity_angle(0.8, 0.9, 0.85) == "red_ocean"


def test_opportunity_angle_at_threshold():
    # 0.7 exactly = red (>=, not >)
    assert opportunity_angle(0.5, 0.7, 0.2) == "novel_method_known_task"
    assert opportunity_angle(0.5, 0.2, 0.7) == "new_task_mature_method"
