"""Tests for rubric definitions."""

from __future__ import annotations

import pytest

from research_harness.rubrics import get_rubric, get_threshold


STAGES = ("init", "build", "analyze", "propose", "experiment", "write")
TIERS = ("economy", "standard", "premium")


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("tier", TIERS)
def test_rubric_exists(stage: str, tier: str):
    rubric = get_rubric(stage, tier)
    assert "dimensions" in rubric
    dims = rubric["dimensions"]
    assert len(dims) >= 3


@pytest.mark.parametrize("stage", STAGES)
def test_economy_has_3_dims(stage: str):
    rubric = get_rubric(stage, "economy")
    assert len(rubric["dimensions"]) == 3


@pytest.mark.parametrize("stage", STAGES)
def test_standard_has_7_dims(stage: str):
    rubric = get_rubric(stage, "standard")
    assert len(rubric["dimensions"]) == 7


@pytest.mark.parametrize("stage", STAGES)
def test_premium_has_10_plus_dims(stage: str):
    rubric = get_rubric(stage, "premium")
    assert len(rubric["dimensions"]) >= 10


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("tier", TIERS)
def test_weights_sum_correctly(stage: str, tier: str):
    rubric = get_rubric(stage, tier)
    dims = rubric["dimensions"]
    positive = [d for d in dims if d["weight"] > 0]
    total = sum(d["weight"] for d in positive)
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total} for {stage}/{tier}"


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("tier", TIERS)
def test_dimension_has_required_fields(stage: str, tier: str):
    rubric = get_rubric(stage, tier)
    for dim in rubric["dimensions"]:
        assert "name" in dim
        assert "weight" in dim
        assert "rubric_prompt" in dim
        assert isinstance(dim["rubric_prompt"], str)
        assert len(dim["rubric_prompt"]) > 20


def test_threshold_defaults():
    assert get_threshold("A") == 7.8
    assert get_threshold("B") == 6.8
    assert get_threshold("workshop") == 5.5
    assert get_threshold("unknown") == 6.8


def test_unknown_stage_raises():
    with pytest.raises(ValueError, match="Unknown stage"):
        get_rubric("nonexistent", "standard")


def test_unknown_tier_raises():
    with pytest.raises(ValueError, match="Unknown tier"):
        get_rubric("analyze", "mythical")
