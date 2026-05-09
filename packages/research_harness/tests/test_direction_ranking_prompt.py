"""Prompt-shape tests for direction_ranking.

These tests exercise the prompt builder directly (no LLM call). They
verify that red-ocean/opportunity_angle kwargs produce the expected
saturation-aware extension, and that omitting them keeps the baseline
prompt intact.
"""

from __future__ import annotations

from research_harness.execution.prompts import direction_ranking_prompt


def test_baseline_prompt_omits_saturation_block():
    p = direction_ranking_prompt("- gap A", "- claim A", "topic about X")
    assert "Market saturation" not in p
    assert "opportunity_angle" not in p
    assert "angle_fit" not in p
    # Must still include scoring template
    assert "novelty" in p
    assert "feasibility" in p
    assert "impact" in p


def test_saturation_block_appears_with_full_kwargs():
    p = direction_ranking_prompt(
        "- gap A",
        "- claim A",
        "topic about X",
        area_red_ocean=0.85,
        task_red_ocean=0.90,
        method_red_ocean=0.60,
        opportunity_angle="red_ocean",
    )
    assert "Market saturation" in p
    assert "area=0.85" in p
    assert "task=0.90" in p
    assert "method=0.60" in p
    assert "Opportunity angle: red_ocean" in p
    assert "angle_fit" in p


def test_partial_kwargs_do_not_emit_block():
    """All-or-none: if any required kwarg is missing, baseline prompt emitted."""
    p = direction_ranking_prompt(
        "- gap A",
        "- claim A",
        "topic",
        area_red_ocean=0.5,
        task_red_ocean=0.5,
        method_red_ocean=0.5,
        # opportunity_angle missing
    )
    assert "Market saturation" not in p


def test_frontier_angle_reward_instructions_present():
    p = direction_ranking_prompt(
        "- gap",
        "- claim",
        "topic",
        area_red_ocean=0.1,
        task_red_ocean=0.1,
        method_red_ocean=0.1,
        opportunity_angle="frontier",
    )
    assert "frontier" in p
    # The reward instruction must be present so the LLM biases toward novelty
    assert "reward novelty" in p
