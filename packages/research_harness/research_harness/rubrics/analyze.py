"""Analyze stage rubric — evidence structuring, gap detection, direction quality."""

from __future__ import annotations

_ECONOMY = {
    "dimensions": [
        {
            "name": "evidence_coverage",
            "weight": 0.35,
            "rubric_prompt": "Score 1-10: Does the analysis cover the major evidence threads in the corpus? 8+ requires structured evidence from at least 70% of high-relevance papers with explicit support/contradict/neutral labels.",
        },
        {
            "name": "citation_grounding",
            "weight": 0.35,
            "rubric_prompt": "Score 1-10: Is every factual claim backed by a specific paper citation with a locatable quote or section reference? Score 0 for any claim with zero citations. Score 8+ only if all claims have precise evidence pointers.",
        },
        {
            "name": "gap_crispness",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Are identified research gaps specific and actionable? Vague gaps like 'more work is needed' score below 4. 8+ requires gaps that specify what is missing, why it matters, and what evidence suggests it is solvable.",
        },
    ],
}

_STANDARD = {
    "dimensions": [
        {
            "name": "evidence_coverage",
            "weight": 0.20,
            "rubric_prompt": "Score 1-10: Does the analysis cover the major evidence threads in the corpus? 8+ requires structured evidence from at least 70% of high-relevance papers with explicit support/contradict/neutral labels.",
        },
        {
            "name": "counter_evidence",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are contradictory findings and alternative explanations surfaced? Penalize one-sided analysis that ignores negative results or competing hypotheses. 8+ shows balanced treatment of conflicting evidence.",
        },
        {
            "name": "gap_crispness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are identified research gaps specific and actionable? Vague gaps like 'more work is needed' score below 4. 8+ requires gaps that specify what is missing, why it matters, and what evidence suggests it is solvable.",
        },
        {
            "name": "citation_grounding",
            "weight": 0.20,
            "rubric_prompt": "Score 1-10: Is every factual claim backed by a specific paper citation with a locatable quote or section reference? Score 0 for any claim with zero citations. Score 8+ only if all claims have precise evidence pointers.",
        },
        {
            "name": "novelty",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Does the analysis reveal non-obvious connections or underexplored angles? Restating known relationships scores below 5. 8+ requires at least one insight that goes beyond what individual papers state.",
        },
        {
            "name": "feasibility",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Are proposed directions feasible given typical academic resources? Penalize directions requiring massive compute, proprietary data, or unrealistic timelines without acknowledging constraints.",
        },
        {
            "name": "clarity",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Is the analysis well-structured and easy to follow? Check for logical flow from evidence to gaps to directions. Penalize disorganized presentation or unexplained jumps in reasoning.",
        },
    ],
}

_PREMIUM = {
    "dimensions": _STANDARD["dimensions"]
    + [
        {
            "name": "claim_graph_coherence",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Do the extracted claims form a coherent graph with clear support/contradict edges? Check for orphan claims, circular reasoning, and missing transitive relationships.",
        },
        {
            "name": "baseline_comparison_depth",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Are baselines compared on consistent metrics across papers? Penalize apples-to-oranges comparisons or missing normalization. 8+ requires a structured comparison matrix.",
        },
        {
            "name": "methodological_rigor",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the analysis critically assess the methodology of cited papers (sample sizes, statistical tests, reproducibility)? Surface-level citation without methodological critique scores below 5.",
        },
    ],
}

RUBRICS = {
    "economy": _ECONOMY,
    "standard": _STANDARD,
    "premium": _PREMIUM,
}
