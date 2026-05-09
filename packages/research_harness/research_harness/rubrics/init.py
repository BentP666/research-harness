"""Init stage rubric — topic framing and scope definition quality."""

from __future__ import annotations

_ECONOMY = {
    "dimensions": [
        {
            "name": "scope_clarity",
            "weight": 0.40,
            "rubric_prompt": "Score 1-10: Is the research scope precisely bounded with clear in/out criteria? A score of 8+ requires explicit inclusion and exclusion boundaries for methods, domains, and time ranges.",
        },
        {
            "name": "venue_alignment",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Does the framing match the target venue's typical scope, contribution style, and novelty bar? Check call-for-papers alignment if venue is specified.",
        },
        {
            "name": "feasibility",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Given stated resources (time, compute, data access), is the topic achievable? Penalize topics that implicitly require unavailable resources.",
        },
    ],
}

_STANDARD = {
    "dimensions": [
        {
            "name": "scope_clarity",
            "weight": 0.20,
            "rubric_prompt": "Score 1-10: Is the research scope precisely bounded with clear in/out criteria? A score of 8+ requires explicit inclusion and exclusion boundaries for methods, domains, and time ranges.",
        },
        {
            "name": "venue_alignment",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Does the framing match the target venue's typical scope, contribution style, and novelty bar? Check call-for-papers alignment if venue is specified.",
        },
        {
            "name": "feasibility",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Given stated resources (time, compute, data access), is the topic achievable? Penalize topics that implicitly require unavailable resources.",
        },
        {
            "name": "seed_paper_quality",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are the seed papers representative of the research area? Penalize if seed set is too narrow (single group) or too broad (unrelated subfields).",
        },
        {
            "name": "query_coverage",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Do the generated search queries cover the key facets of the topic? Check for synonym coverage, acronym variants, and related concept terms.",
        },
        {
            "name": "constraint_completeness",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Are all research constraints (ethical, legal, data licensing, compute budget) explicitly stated? Implicit assumptions lower the score.",
        },
        {
            "name": "motivation_strength",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Is there a compelling argument for why this research matters? Score 8+ requires connecting to real-world impact or a recognized open problem.",
        },
    ],
}

_PREMIUM = {
    "dimensions": _STANDARD["dimensions"]
    + [
        {
            "name": "interdisciplinary_awareness",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the framing acknowledge relevant work from adjacent fields? Penalize tunnel vision that misses established solutions from other disciplines.",
        },
        {
            "name": "timeline_realism",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Is the implied timeline (from seed to submission) realistic given the scope? Cross-check against typical timelines for similar publications.",
        },
        {
            "name": "reproducibility_setup",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the framing set up for reproducible research? Check for dataset specification, metric definitions, and baseline identification.",
        },
    ],
}

RUBRICS = {
    "economy": _ECONOMY,
    "standard": _STANDARD,
    "premium": _PREMIUM,
}
