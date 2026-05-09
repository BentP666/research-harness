"""Tests for v2 Step 5 — ADR-001 Decision 1 wiring of run_section_loop
into the auto_runner/tool_dispatch.py write-stage path.

The loop itself is stubbed via monkeypatch so we don't hit an LLM. We only
verify that the integration correctly bypasses the draft/review/revise triad
when RESEARCH_HARNESS_SECTION_LOOP=1 and populates context as expected.
"""

from __future__ import annotations

import pytest

from research_harness.auto_runner import tool_dispatch
from research_harness.execution.loops import LoopIteration, LoopResult
from research_harness.orchestrator.service import OrchestratorService
from research_harness.storage.db import Database


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
            ("t", "t"),
        )
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (tid, tid, "stub", "stub"),
        )
        conn.commit()
    finally:
        conn.close()
    return tid


def _fake_loop_result(content: str, converged: bool = True) -> LoopResult:
    return LoopResult(
        converged=converged,
        final_score=0.85 if converged else 0.4,
        total_rounds=1,
        iterations=[
            LoopIteration(round=1, score=0.85, passed=converged, feedback="ok")
        ],
        final_output=content,
        decision="CONCLUDE" if converged else "DEEPEN",
    )


def test_section_loop_enabled_bypasses_triad(db, topic_id, monkeypatch):
    monkeypatch.setenv("RESEARCH_HARNESS_SECTION_LOOP", "1")

    calls: list[str] = []

    def fake_run(**kwargs):
        calls.append(kwargs["section"])
        return _fake_loop_result(f"draft of {kwargs['section']}")

    # Patch where tool_dispatch imports it
    from research_harness.execution import loops

    monkeypatch.setattr(loops, "run_section_loop", fake_run)

    svc = OrchestratorService(db)
    context = {
        "sections_to_draft": ["introduction", "methods"],
        "outline": "outline text",
    }
    tools = (
        "outline_generate",
        "section_draft",
        "section_review",
        "section_revise",
    )

    summary = tool_dispatch.dispatch_stage_tools(
        db=db,
        svc=svc,
        topic_id=topic_id,
        stage="write",
        tools=tools,
        context=context,
    )

    # run_section_loop was called once per section
    assert calls == ["introduction", "methods"]
    # section_draft/review/revise tools were skipped (no direct execution)
    tool_results = [r["tool"] for r in summary["tool_results"]]
    # section_draft appears from the loop (not the legacy tool call)
    assert tool_results.count("section_draft") == 2
    # No section_review or section_revise tool calls occurred
    assert "section_review" not in tool_results
    assert "section_revise" not in tool_results
    # Context populated with outputs
    assert context["_drafted_sections"] == ["introduction", "methods"]
    assert (
        context["_output_section_draft_introduction"]["text"] == "draft of introduction"
    )
    assert context["_output_section_draft_methods"]["text"] == "draft of methods"


def test_section_loop_disabled_falls_back_to_triad(db, topic_id, monkeypatch):
    monkeypatch.delenv("RESEARCH_HARNESS_SECTION_LOOP", raising=False)

    called = {"run": 0}

    def fake_run(**kwargs):
        called["run"] += 1
        return _fake_loop_result("should not be called")

    from research_harness.execution import loops

    monkeypatch.setattr(loops, "run_section_loop", fake_run)

    svc = OrchestratorService(db)
    context = {
        "sections_to_draft": ["introduction"],
        "outline": "outline",
    }
    # Only draft; legacy path will also dispatch, but since we don't have a
    # real backend configured, it just fails gracefully. The important
    # assertion: run_section_loop was NOT called.
    tool_dispatch.dispatch_stage_tools(
        db=db,
        svc=svc,
        topic_id=topic_id,
        stage="write",
        tools=("section_draft",),
        context=context,
    )
    assert called["run"] == 0


def test_section_loop_skipped_for_non_write_stage(db, topic_id, monkeypatch):
    monkeypatch.setenv("RESEARCH_HARNESS_SECTION_LOOP", "1")
    called = {"run": 0}

    from research_harness.execution import loops

    def fake_run(**kwargs):
        called["run"] += 1
        return _fake_loop_result("x")

    monkeypatch.setattr(loops, "run_section_loop", fake_run)

    svc = OrchestratorService(db)
    context = {"sections_to_draft": ["introduction"]}
    tool_dispatch.dispatch_stage_tools(
        db=db,
        svc=svc,
        topic_id=topic_id,
        stage="analyze",
        tools=("section_draft",),
        context=context,
    )
    assert called["run"] == 0, "loop should only fire for stage=='write'"
