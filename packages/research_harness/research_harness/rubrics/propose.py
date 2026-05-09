"""Propose stage rubric — proposal quality, adversarial robustness, study design."""

from __future__ import annotations

_ECONOMY = {
    "dimensions": [
        {
            "name": "contribution_clarity",
            "weight": 0.40,
            "rubric_prompt": "Score 1-10: Are the claimed contributions specific and distinct? Each contribution should be independently verifiable. 8+ requires contributions that are non-overlapping and each advances the state of the art in a measurable way.",
        },
        {
            "name": "adversarial_robustness",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Has the proposal survived meaningful challenge? Check that key objections (novelty doubts, scalability concerns, comparison fairness) have been addressed with evidence, not hand-waving.",
        },
        {
            "name": "experiment_design",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Is the experiment plan concrete enough to execute? 8+ requires specified datasets, metrics, baselines, and success criteria. Vague plans ('we will evaluate on benchmarks') score below 5.",
        },
    ],
}

_STANDARD = {
    "dimensions": [
        {
            "name": "contribution_clarity",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are the claimed contributions specific and distinct? Each contribution should be independently verifiable. 8+ requires contributions that are non-overlapping and each advances the state of the art in a measurable way.",
        },
        {
            "name": "adversarial_robustness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Has the proposal survived meaningful challenge? Check that key objections (novelty doubts, scalability concerns, comparison fairness) have been addressed with evidence, not hand-waving.",
        },
        {
            "name": "experiment_design",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Is the experiment plan concrete enough to execute? 8+ requires specified datasets, metrics, baselines, and success criteria. Vague plans ('we will evaluate on benchmarks') score below 5.",
        },
        {
            "name": "novelty_argument",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Is the novelty claim well-supported by comparison to prior work? Simply being different is not novel. 8+ requires explicit positioning against the closest 3+ related methods with clear differentiation.",
        },
        {
            "name": "method_soundness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Is the proposed method technically sound? Check for logical consistency, valid assumptions, and correct use of mathematical formalism. Penalize hand-wavy justifications.",
        },
        {
            "name": "scalability_awareness",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Does the proposal acknowledge computational and data scale requirements? 8+ discusses complexity, memory footprint, and practical deployment constraints.",
        },
        {
            "name": "risk_mitigation",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are risks (negative results, baseline outperformance, data issues) identified with fallback plans? Ignoring risks entirely scores below 4.",
        },
    ],
}

_PREMIUM = {
    "dimensions": _STANDARD["dimensions"]
    + [
        {
            "name": "ablation_plan",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Is there a clear ablation study plan that isolates each contribution's effect? 8+ specifies which components to remove/replace and what metrics will show their value.",
        },
        {
            "name": "ethical_consideration",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Are ethical implications of the proposed research addressed? Consider bias, dual-use potential, environmental impact (compute), and data privacy.",
        },
        {
            "name": "generalization_argument",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the proposal argue why the method should generalize beyond the specific evaluation setting? Transfer learning claims, domain adaptation, or theoretical guarantees score higher.",
        },
    ],
}

RUBRICS = {
    "economy": _ECONOMY,
    "standard": _STANDARD,
    "premium": _PREMIUM,
}
