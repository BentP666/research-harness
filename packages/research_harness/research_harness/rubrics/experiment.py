"""Experiment stage rubric — execution quality, result validity, reproducibility."""

from __future__ import annotations

_ECONOMY = {
    "dimensions": [
        {
            "name": "result_validity",
            "weight": 0.40,
            "rubric_prompt": "Score 1-10: Are the experimental results statistically valid? Check for appropriate significance tests, confidence intervals, and sufficient runs. Single-run results on stochastic tasks score below 5.",
        },
        {
            "name": "baseline_fairness",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Are baselines given a fair comparison? Same data splits, hyperparameter tuning budget, and compute allocation. Using baselines with default settings while tuning your method scores below 4.",
        },
        {
            "name": "metric_appropriateness",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Are the chosen metrics standard for the task and do they actually measure what matters? Penalize cherry-picked metrics or missing widely-used benchmarks for the domain.",
        },
    ],
}

_STANDARD = {
    "dimensions": [
        {
            "name": "result_validity",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are the experimental results statistically valid? Check for appropriate significance tests, confidence intervals, and sufficient runs. Single-run results on stochastic tasks score below 5.",
        },
        {
            "name": "baseline_fairness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are baselines given a fair comparison? Same data splits, hyperparameter tuning budget, and compute allocation. Using baselines with default settings while tuning your method scores below 4.",
        },
        {
            "name": "metric_appropriateness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are the chosen metrics standard for the task and do they actually measure what matters? Penalize cherry-picked metrics or missing widely-used benchmarks for the domain.",
        },
        {
            "name": "reproducibility",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Could another researcher reproduce these results? Check for specified random seeds, hardware description, library versions, and data preprocessing steps. Missing any of these lowers the score.",
        },
        {
            "name": "ablation_completeness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Does the ablation study isolate the contribution of each proposed component? Missing ablations for claimed contributions score below 5. 8+ shows clean, interpretable ablation tables.",
        },
        {
            "name": "error_analysis",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Is there meaningful analysis of failure cases? Reporting only aggregate metrics without examining where the method fails scores below 6. 8+ includes qualitative examples of errors.",
        },
        {
            "name": "code_quality",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Is the experiment code well-organized and executable? Check for hardcoded paths, missing dependencies, and unclear entry points. 8+ means the code runs with minimal setup.",
        },
    ],
}

_PREMIUM = {
    "dimensions": _STANDARD["dimensions"]
    + [
        {
            "name": "scaling_analysis",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Is there analysis of how performance scales with data size, model size, or compute? Missing scaling curves for methods that claim efficiency score below 5.",
        },
        {
            "name": "cross_domain_evaluation",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Is the method evaluated on multiple datasets or domains to test generalization? Single-dataset evaluation scores below 6 for methods claiming generality.",
        },
        {
            "name": "resource_accounting",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Are computational costs (GPU hours, memory, training time) reported and compared to baselines? Hidden costs make fair comparison impossible.",
        },
    ],
}

RUBRICS = {
    "economy": _ECONOMY,
    "standard": _STANDARD,
    "premium": _PREMIUM,
}
