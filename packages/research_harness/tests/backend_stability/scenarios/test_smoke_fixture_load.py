"""Smoke-tier scenario: load fixture + run structural assertions.

This is the simplest end-to-end exercise that proves the Phase 0
plumbing works:

    fixtures.load_topic(db, "small_tfr")
        → topic + 5 papers in DB
    boolean_suite assertions
        → cheap structural checks must all pass on this minimal state

If this test goes red, something fundamental is broken: either the
fixture loader, the boolean suite, or the DB migration. Every later
fault-injection scenario assumes this works.
"""

from __future__ import annotations

import pytest

from ..assertions import boolean_suite as bs
from ..fixtures import load_topic


@pytest.mark.smoke
def test_smoke_fixture_loads_and_passes_structural_checks(db):
    """Minimal pipeline state must satisfy structural-only assertions."""
    loaded = load_topic(db, "small_tfr")

    assert loaded.topic_id > 0
    assert len(loaded.paper_ids) == 5

    # No orchestrator_run yet → terminal_state and artifact checks would
    # fail (correctly!). We only verify the structural checks that don't
    # need a run.
    transition = bs.assert_transition_legal(db, loaded.topic_id)
    paper_count = bs.assert_paper_count_conserved(db, loaded.topic_id)
    gate_reason = bs.assert_gate_has_reason(db, loaded.topic_id)
    no_traceback = bs.assert_no_unexplained_traceback(db, loaded.topic_id)

    # All four are vacuously true on a fresh DB with no events
    assert transition.passed, transition.detail
    assert paper_count.passed, paper_count.detail
    assert gate_reason.passed, gate_reason.detail
    assert no_traceback.passed, no_traceback.detail


@pytest.mark.smoke
def test_smoke_loader_idempotent(db):
    """Loading the same fixture twice must not duplicate papers."""
    a = load_topic(db, "small_tfr")
    b = load_topic(db, "small_tfr")
    assert a.topic_id == b.topic_id
    assert a.paper_ids == b.paper_ids


@pytest.mark.smoke
def test_smoke_loopback_fixture_marks_stale_paper(db):
    """The lb-005 seed must land with status='stale' so loopback tests
    can detect it without doing analysis themselves."""
    load_topic(db, "loopback_evidence")
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT arxiv_id, status FROM papers WHERE arxiv_id LIKE 'fixture-lb-%'"
        ).fetchall()
    finally:
        conn.close()

    by_id = {r["arxiv_id"]: r["status"] for r in rows}
    assert by_id.get("fixture-lb-005-stale") == "stale", by_id
    assert by_id.get("fixture-lb-001") == "meta_only", by_id
