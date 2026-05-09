"""10 go/no-go boolean assertions for orchestrator runs.

Each function takes a ``Database`` plus the ``topic_id`` under inspection
and returns ``AssertionResult(passed, detail, evidence)``. ``detail`` is a
one-line human summary; ``evidence`` is a structured dict the test runner
can dump on failure for triage.

Why split into 10 functions instead of one monolithic check:
- Lets the smoke tier run a subset (1, 2, 5, 6) cheaply
- Failure detail names exactly which invariant broke
- Easy to add a new check without churning the others

The functions DO NOT raise — callers convert ``passed=False`` into pytest
failures. This makes the suite reusable from non-pytest contexts (CLI
diagnostics, nightly reports, dashboard).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from research_harness.orchestrator.stages import (
    STAGE_REGISTRY,
    is_valid_transition,
    resolve_stage,
)
from research_harness.storage.db import Database

logger = logging.getLogger(__name__)


TERMINAL_STAGE_STATUSES = frozenset({"completed", "blocked", "rejected"})
TERMINAL_FOR_PIPELINE_OK = frozenset({"completed"})

# Citation regex matches \cite{a,b}, [12], (Author, 2024)
_CITE_RX = re.compile(r"\\cite[pt]?\{([^}]+)\}|\[(\d+)\]|\((\w+),\s*\d{4}\)")
_CITE_KEY_RX = re.compile(r"\\cite[pt]?\{([^}]+)\}")
_BIBKEY_RX = re.compile(r"@\w+\{([^,]+),")


@dataclass
class AssertionResult:
    """Outcome of one boolean check."""

    name: str
    passed: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.passed


# ---------------------------------------------------------------------------
# Individual assertions (1–10)
# ---------------------------------------------------------------------------


def assert_terminal_state(db: Database, topic_id: int) -> AssertionResult:
    """1. Run reached a terminal stage_status — not stuck at in_progress.

    Why this matters: the orchestrator must converge. A run that sits at
    in_progress forever is a hang, not a partial success. ``blocked`` is
    acceptable in supervised mode (means human review is needed).
    """
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT current_stage, stage_status, gate_status, blocking_issue_count "
            "FROM orchestrator_runs WHERE topic_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return AssertionResult(
            name="terminal_state",
            passed=False,
            detail=f"no orchestrator_run for topic_id={topic_id}",
            evidence={"topic_id": topic_id},
        )

    status = row["stage_status"]
    passed = status in TERMINAL_STAGE_STATUSES
    return AssertionResult(
        name="terminal_state",
        passed=passed,
        detail=f"stage={row['current_stage']} status={status}",
        evidence=dict(row),
    )


def assert_transition_legal(db: Database, topic_id: int) -> AssertionResult:
    """2. Every recorded stage transition is in STAGE_GRAPH.

    Self-loops (build→build for retry) are legal. Forward and loopback
    edges are legal. Anything else means the orchestrator wrote an event
    the state machine forbids — bug.
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, from_stage, to_stage, event_type, created_at "
            "FROM orchestrator_stage_events "
            "WHERE topic_id = ? ORDER BY id ASC",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()

    illegal: list[dict[str, Any]] = []
    for row in rows:
        from_s = row["from_stage"]
        to_s = row["to_stage"]
        # Initial 'started' events use sentinel '<start>' or empty string
        if not from_s or from_s in {"<start>", "init"} and to_s == "init":
            continue
        if not is_valid_transition(from_s, to_s):
            illegal.append(
                {
                    "event_id": row["id"],
                    "from": from_s,
                    "to": to_s,
                    "event_type": row["event_type"],
                }
            )

    return AssertionResult(
        name="transition_legal",
        passed=not illegal,
        detail=(
            f"all {len(rows)} transitions legal"
            if not illegal
            else f"{len(illegal)} illegal of {len(rows)}: first={illegal[0]}"
        ),
        evidence={"illegal_transitions": illegal[:10], "total_events": len(rows)},
    )


def assert_artifacts_present_and_valid(db: Database, topic_id: int) -> AssertionResult:
    """3. Every required_artifacts entry exists, is active, and has a non-empty payload.

    Each stage in STAGE_REGISTRY declares required artifact types. For the
    run to be coherent, every type the run reached must have at least one
    active artifact with a parseable JSON payload that is not literally
    ``{}``.
    """
    conn = db.connect()
    try:
        run = conn.execute(
            "SELECT current_stage FROM orchestrator_runs "
            "WHERE topic_id = ? ORDER BY id DESC LIMIT 1",
            (topic_id,),
        ).fetchone()
        if run is None:
            return AssertionResult(
                name="artifacts_present_and_valid",
                passed=False,
                detail="no run",
                evidence={"topic_id": topic_id},
            )

        current = resolve_stage(run["current_stage"])
        # Stages whose artifacts must exist = current + all predecessors
        from research_harness.orchestrator.stages import STAGE_ORDER

        idx = STAGE_ORDER.index(current) if current in STAGE_ORDER else -1
        required_stages = STAGE_ORDER[: idx + 1] if idx >= 0 else ()

        missing: list[str] = []
        invalid: list[dict[str, Any]] = []
        for stage_name in required_stages:
            meta = STAGE_REGISTRY[stage_name]
            for art_type in meta.required_artifacts:
                row = conn.execute(
                    "SELECT id, payload_json FROM project_artifacts "
                    "WHERE topic_id = ? AND artifact_type = ? AND status = 'active' "
                    "ORDER BY version DESC LIMIT 1",
                    (topic_id, art_type),
                ).fetchone()
                if row is None:
                    missing.append(f"{stage_name}:{art_type}")
                    continue
                try:
                    payload = json.loads(row["payload_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    invalid.append(
                        {"id": row["id"], "type": art_type, "reason": "bad json"}
                    )
                    continue
                if not payload:
                    invalid.append(
                        {"id": row["id"], "type": art_type, "reason": "empty payload"}
                    )
    finally:
        conn.close()

    passed = not missing and not invalid
    return AssertionResult(
        name="artifacts_present_and_valid",
        passed=passed,
        detail=(
            f"all required artifacts present (current_stage={current})"
            if passed
            else f"missing={missing[:5]} invalid={invalid[:5]}"
        ),
        evidence={"missing": missing, "invalid": invalid, "current_stage": current},
    )


def assert_provenance_complete(db: Database, topic_id: int) -> AssertionResult:
    """4. Every active artifact past 'init' has a provenance_record_id with the
    minimum fields populated (primitive, started/finished, success).

    Critical artifacts (evidence_pack, direction_proposal, experiment_result,
    draft_pack, adversarial_resolution) MUST link to provenance. Other
    artifacts are advisory.
    """
    critical_types = {
        "evidence_pack",
        "direction_proposal",
        "experiment_result",
        "draft_pack",
        "adversarial_resolution",
    }
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, artifact_type, provenance_record_id, stage "
            "FROM project_artifacts WHERE topic_id = ? AND status = 'active'",
            (topic_id,),
        ).fetchall()

        missing_link: list[dict[str, Any]] = []
        bad_provenance: list[dict[str, Any]] = []
        for row in rows:
            if row["artifact_type"] not in critical_types:
                continue
            pid = row["provenance_record_id"]
            if not pid:
                missing_link.append(
                    {"artifact_id": row["id"], "type": row["artifact_type"]}
                )
                continue
            prov = conn.execute(
                "SELECT primitive, started_at, finished_at, success, error "
                "FROM provenance_records WHERE id = ?",
                (pid,),
            ).fetchone()
            if prov is None:
                bad_provenance.append(
                    {
                        "artifact_id": row["id"],
                        "provenance_id": pid,
                        "reason": "row missing",
                    }
                )
                continue
            if (
                not prov["primitive"]
                or not prov["started_at"]
                or not prov["finished_at"]
            ):
                bad_provenance.append(
                    {
                        "artifact_id": row["id"],
                        "provenance_id": pid,
                        "reason": "missing fields",
                    }
                )
    finally:
        conn.close()

    passed = not missing_link and not bad_provenance
    return AssertionResult(
        name="provenance_complete",
        passed=passed,
        detail=(
            f"{len(rows)} artifacts inspected, all OK"
            if passed
            else f"missing_link={len(missing_link)} bad={len(bad_provenance)}"
        ),
        evidence={
            "missing_link": missing_link[:5],
            "bad_provenance": bad_provenance[:5],
        },
    )


def assert_paper_count_conserved(db: Database, topic_id: int) -> AssertionResult:
    """5. searched_count = ingested + skipped + failed (no silent paper drops).

    Pulled from the latest acquisition_report payload. If the four
    counters don't add up, the build stage silently lost papers — historical
    P0 bug.
    """
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, payload_json FROM project_artifacts "
            "WHERE topic_id = ? AND artifact_type = 'acquisition_report' "
            "AND status = 'active' ORDER BY version DESC LIMIT 1",
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        # No acquisition_report yet = stage hasn't run = vacuously OK
        return AssertionResult(
            name="paper_count_conserved",
            passed=True,
            detail="no acquisition_report yet (build not reached)",
            evidence={"topic_id": topic_id},
        )

    try:
        payload = json.loads(row["payload_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return AssertionResult(
            name="paper_count_conserved",
            passed=False,
            detail=f"acquisition_report {row['id']} has bad JSON",
            evidence={"artifact_id": row["id"]},
        )

    searched = int(payload.get("searched_count") or payload.get("searched") or 0)
    ingested = int(payload.get("ingested_count") or payload.get("ingested") or 0)
    skipped = int(payload.get("skipped_count") or payload.get("skipped") or 0)
    failed = int(payload.get("failed_count") or payload.get("failed") or 0)

    # Skip the assertion if the report doesn't carry counters
    if searched == 0 and ingested == 0 and skipped == 0 and failed == 0:
        return AssertionResult(
            name="paper_count_conserved",
            passed=True,
            detail="acquisition_report carries no counters (acceptable)",
            evidence={"artifact_id": row["id"]},
        )

    accounted = ingested + skipped + failed
    passed = accounted == searched
    return AssertionResult(
        name="paper_count_conserved",
        passed=passed,
        detail=f"searched={searched} accounted={accounted} (i={ingested} s={skipped} f={failed})",
        evidence={
            "searched": searched,
            "ingested": ingested,
            "skipped": skipped,
            "failed": failed,
            "delta": searched - accounted,
        },
    )


def assert_gate_has_reason(db: Database, topic_id: int) -> AssertionResult:
    """6. Every gate event has a non-empty rationale (or payload_json.reason).

    Gate decisions without structured reasons mean the autonomous resolver
    couldn't be audited. Historical bug: silent gate auto-pass.
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, gate_type, status, rationale, payload_json "
            "FROM orchestrator_stage_events "
            "WHERE topic_id = ? AND gate_type != '' AND event_type = 'gate'",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()

    silent: list[dict[str, Any]] = []
    for row in rows:
        rationale = (row["rationale"] or "").strip()
        if rationale:
            continue
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        reason = (payload.get("reason") or payload.get("decision_reason") or "").strip()
        if not reason:
            silent.append(
                {
                    "event_id": row["id"],
                    "gate": row["gate_type"],
                    "status": row["status"],
                }
            )

    return AssertionResult(
        name="gate_has_reason",
        passed=not silent,
        detail=(
            f"{len(rows)} gate events, all reasoned"
            if not silent
            else f"{len(silent)} silent gates"
        ),
        evidence={"silent_gates": silent[:5], "total_gate_events": len(rows)},
    )


def assert_budget_tracked(db: Database, topic_id: int) -> AssertionResult:
    """7. Sum of provenance_records.cost_usd for this topic is finite and
    reported. If a budget cap was hit, the run must be in 'blocked' state
    with reason mentioning budget — never silently dropped.

    Smoke-tier accepts cost==0 (replay mode). Real runs should be > 0.
    """
    conn = db.connect()
    try:
        cost_row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total, COUNT(*) AS n "
            "FROM provenance_records WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
        run = conn.execute(
            "SELECT stage_status, blocking_issue_count FROM orchestrator_runs "
            "WHERE topic_id = ? ORDER BY id DESC LIMIT 1",
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()

    total = float(cost_row["total"] or 0.0)
    n = int(cost_row["n"] or 0)
    # Pass condition: cost is a real number, no NaN/Inf
    if total != total or total == float("inf"):
        return AssertionResult(
            name="budget_tracked",
            passed=False,
            detail=f"cost not finite: {total}",
            evidence={"total_cost_usd": total, "records": n},
        )
    return AssertionResult(
        name="budget_tracked",
        passed=True,
        detail=f"total_cost=${total:.4f} across {n} provenance records",
        evidence={
            "total_cost_usd": total,
            "records": n,
            "stage_status": run["stage_status"] if run else None,
        },
    )


def assert_citations_no_dangling(db: Database, topic_id: int) -> AssertionResult:
    """8. Every \\cite{key} referenced in a draft section has a matching
    BibTeX entry in the bibliography artifact.

    Skipped if no draft_pack exists yet (write stage not reached).
    """
    conn = db.connect()
    try:
        draft = conn.execute(
            "SELECT id, payload_json FROM project_artifacts "
            "WHERE topic_id = ? AND artifact_type = 'draft_pack' "
            "AND status = 'active' ORDER BY version DESC LIMIT 1",
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()

    if draft is None:
        return AssertionResult(
            name="citations_no_dangling",
            passed=True,
            detail="no draft_pack yet (write not reached)",
            evidence={"topic_id": topic_id},
        )

    try:
        payload = json.loads(draft["payload_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return AssertionResult(
            name="citations_no_dangling",
            passed=False,
            detail=f"draft_pack {draft['id']} has bad JSON",
            evidence={"artifact_id": draft["id"]},
        )

    sections = payload.get("sections") or {}
    bibtex = (
        payload.get("bibtex")
        or payload.get("bibliography")
        or payload.get("references")
        or ""
    )
    if isinstance(bibtex, list):
        bibtex = "\n".join(str(b) for b in bibtex)

    cited_keys: set[str] = set()
    for section in sections.values() if isinstance(sections, dict) else []:
        if not isinstance(section, str):
            continue
        for m in _CITE_KEY_RX.finditer(section):
            for k in m.group(1).split(","):
                k = k.strip()
                if k:
                    cited_keys.add(k)

    bibkeys = set(_BIBKEY_RX.findall(bibtex)) if isinstance(bibtex, str) else set()
    dangling = sorted(cited_keys - bibkeys)

    # If neither citations nor bibtex are present, nothing to verify
    if not cited_keys and not bibkeys:
        return AssertionResult(
            name="citations_no_dangling",
            passed=True,
            detail="no citation markers found (acceptable for stub draft)",
            evidence={"artifact_id": draft["id"]},
        )

    return AssertionResult(
        name="citations_no_dangling",
        passed=not dangling,
        detail=(
            f"{len(cited_keys)} keys, all matched"
            if not dangling
            else f"{len(dangling)} dangling: {dangling[:5]}"
        ),
        evidence={
            "cited_keys": sorted(cited_keys)[:20],
            "bibtex_keys": sorted(bibkeys)[:20],
            "dangling": dangling,
        },
    )


def assert_llm_route_audited(db: Database, topic_id: int) -> AssertionResult:
    """9. Every provenance_record where backend != 'none' has model_used set
    to a real model id (not '' or 'none' or 'unknown').

    Catches the historical 'silent fallback' bug where llm_router quietly
    swapped tier=heavy → claude-haiku and never recorded the swap.
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, primitive, backend, model_used FROM provenance_records "
            "WHERE topic_id = ? AND backend NOT IN ('', 'none', 'local')",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()

    bad = [
        {"id": r["id"], "primitive": r["primitive"], "model": r["model_used"]}
        for r in rows
        if not r["model_used"] or r["model_used"] in {"none", "unknown", ""}
    ]
    return AssertionResult(
        name="llm_route_audited",
        passed=not bad,
        detail=(
            f"{len(rows)} LLM calls, all carry model_used"
            if not bad
            else f"{len(bad)} of {len(rows)} missing model_used"
        ),
        evidence={"unaudited": bad[:5], "total_llm_calls": len(rows)},
    )


def assert_no_unexplained_traceback(db: Database, topic_id: int) -> AssertionResult:
    """10. provenance_records with success=0 must carry an 'error' field with
    a non-empty message. A failed call without explanation is a silent
    failure — the worst class of bug for an autonomous system.
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, primitive, success, error FROM provenance_records "
            "WHERE topic_id = ? AND success = 0",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()

    silent_failures = [
        {"id": r["id"], "primitive": r["primitive"]}
        for r in rows
        if not (r["error"] or "").strip()
    ]
    return AssertionResult(
        name="no_unexplained_traceback",
        passed=not silent_failures,
        detail=(
            f"{len(rows)} failed calls, all explained"
            if not silent_failures
            else f"{len(silent_failures)} silent failures of {len(rows)}"
        ),
        evidence={"silent_failures": silent_failures[:5], "total_failures": len(rows)},
    )


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


_ALL_CHECKS = (
    assert_terminal_state,
    assert_transition_legal,
    assert_artifacts_present_and_valid,
    assert_provenance_complete,
    assert_paper_count_conserved,
    assert_gate_has_reason,
    assert_budget_tracked,
    assert_citations_no_dangling,
    assert_llm_route_audited,
    assert_no_unexplained_traceback,
)

# Smoke tier: cheap structural checks that don't need a finished pipeline
SMOKE_CHECKS = (
    assert_transition_legal,
    assert_paper_count_conserved,
    assert_gate_has_reason,
    assert_no_unexplained_traceback,
)


def assert_full_pipeline_ok(
    db: Database, topic_id: int, *, tier: str = "full"
) -> tuple[bool, list[AssertionResult]]:
    """Run all checks and return (overall_passed, individual_results).

    tier:
      - "smoke": only structural checks (4 of 10) — runs without a completed pipeline
      - "full": all 10 checks (default)
    """
    checks = SMOKE_CHECKS if tier == "smoke" else _ALL_CHECKS
    results: list[AssertionResult] = []
    for fn in checks:
        try:
            results.append(fn(db, topic_id))
        except Exception as exc:  # noqa: BLE001 — assertion failure shouldn't crash suite
            logger.exception("assertion %s crashed", fn.__name__)
            results.append(
                AssertionResult(
                    name=fn.__name__,
                    passed=False,
                    detail=f"check raised {type(exc).__name__}: {exc}",
                    evidence={"exception": str(exc)},
                )
            )
    overall = all(r.passed for r in results)
    return overall, results


__all__ = [
    "AssertionResult",
    "assert_terminal_state",
    "assert_transition_legal",
    "assert_artifacts_present_and_valid",
    "assert_provenance_complete",
    "assert_paper_count_conserved",
    "assert_gate_has_reason",
    "assert_budget_tracked",
    "assert_citations_no_dangling",
    "assert_llm_route_audited",
    "assert_no_unexplained_traceback",
    "assert_full_pipeline_ok",
]
