from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_harness.discover.evidence import (
    EvidenceRecord,
    build_evidence_manifest,
    default_evidence_problem_specs,
    validate_evidence_manifest,
)


def _record(
    problem_id: str, index: int, *, route: str, provider: str
) -> EvidenceRecord:
    return EvidenceRecord(
        problem_id=problem_id,
        evidence_type="paper",
        title=f"{problem_id} evidence paper {index}",
        url=f"https://example.com/{problem_id}/{provider}/{index}",
        source_route=route,
        provider=provider,
        published_at="2026-05-01",
        year=2026,
        query=f"{problem_id} query",
        reason="Relevant recent evidence for the Discovery problem.",
    )


def test_default_evidence_plan_covers_ten_problem_spaces():
    specs = default_evidence_problem_specs()

    assert len(specs) == 10
    assert {spec.problem_id for spec in specs} == {
        "agentic-systems",
        "ai-for-research",
        "evaluation-benchmarks",
        "safety-governance",
        "enterprise-ai-workflow",
        "multimodal-intelligence",
        "ai-infrastructure",
        "retrieval-knowledge-data",
        "domain-science-ai",
        "robotics-embodied-ai",
    }
    for spec in specs:
        assert len(spec.queries) >= 4
        assert "rh_paper_search" in spec.required_routes
        assert "provider_fanout" in spec.required_routes


def test_evidence_manifest_validates_hundred_scale_recent_multi_route():
    specs = default_evidence_problem_specs()
    records: list[EvidenceRecord] = []
    for spec in specs:
        records.extend(
            _record(spec.problem_id, index, route="rh_paper_search", provider="rh")
            for index in range(60)
        )
        records.extend(
            _record(
                spec.problem_id,
                index + 60,
                route="provider_fanout",
                provider="semantic_scholar",
            )
            for index in range(60)
        )

    manifest = build_evidence_manifest(
        problem_specs=specs,
        records=records,
        min_per_problem=100,
        freshness_year_from=2025,
        min_recent_per_problem=100,
    )
    validation = validate_evidence_manifest(manifest)

    assert validation["ok"] is True
    assert all(item["evidence_count"] >= 100 for item in validation["problems"])
    assert all(item["recent_count"] >= 100 for item in validation["problems"])
    assert all(item["route_count"] >= 2 for item in validation["problems"])


def test_evidence_manifest_rejects_undercovered_problem():
    specs = default_evidence_problem_specs()
    undercovered = specs[0]
    records = [
        _record(
            undercovered.problem_id,
            index,
            route="rh_paper_search" if index % 2 == 0 else "provider_fanout",
            provider="rh" if index % 2 == 0 else "semantic_scholar",
        )
        for index in range(99)
    ]

    manifest = build_evidence_manifest(
        problem_specs=specs,
        records=records,
        min_per_problem=100,
        freshness_year_from=2025,
        min_recent_per_problem=100,
    )

    with pytest.raises(ValueError, match="agentic-systems"):
        validate_evidence_manifest(manifest, raise_on_error=True)


def test_cli_discover_evidence_plan_and_validate(runner, tmp_path):
    from research_harness.cli import main

    plan_result = runner.invoke(main, ["--json", "discover", "evidence", "plan"])
    assert plan_result.exit_code == 0, plan_result.output
    plan_payload = json.loads(plan_result.output)
    assert len(plan_payload["problems"]) == 10

    specs = default_evidence_problem_specs()
    records: list[EvidenceRecord] = []
    for spec in specs:
        records.extend(
            _record(spec.problem_id, index, route="rh_paper_search", provider="rh")
            for index in range(50)
        )
        records.extend(
            _record(
                spec.problem_id,
                index + 50,
                route="provider_fanout",
                provider="arxiv",
            )
            for index in range(50)
        )

    manifest = build_evidence_manifest(
        problem_specs=specs,
        records=records,
        min_per_problem=100,
        freshness_year_from=2025,
        min_recent_per_problem=100,
    )
    manifest_path = tmp_path / "evidence.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))

    validate_result = runner.invoke(
        main,
        ["discover", "evidence", "validate", str(manifest_path)],
    )

    assert validate_result.exit_code == 0, validate_result.output
    assert "10/10 problems passed" in validate_result.output


def test_public_repo_does_not_commit_generated_latest_evidence_manifest():
    manifest_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "discover"
        / "evidence"
        / "latest.json"
    )

    assert not manifest_path.exists()
