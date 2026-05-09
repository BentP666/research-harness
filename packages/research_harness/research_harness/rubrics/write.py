"""Write stage rubric — draft quality, review readiness, submission completeness."""

from __future__ import annotations

_ECONOMY = {
    "dimensions": [
        {
            "name": "argument_flow",
            "weight": 0.35,
            "rubric_prompt": "Score 1-10: Does the paper tell a coherent story from problem to contribution to evidence? Check that each section logically follows from the previous one. Disconnected sections score below 5.",
        },
        {
            "name": "citation_integrity",
            "weight": 0.35,
            "rubric_prompt": "Score 1-10: Are all factual claims properly cited? Check for uncited statistics, unreferenced comparisons, and missing self-citations. Any fabricated citation is an automatic 0.",
        },
        {
            "name": "completeness",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Does the paper include all required sections for the target venue (abstract, intro, related work, method, experiments, conclusion)? Missing sections or placeholder text scores below 3.",
        },
    ],
}

_STANDARD = {
    "dimensions": [
        {
            "name": "argument_flow",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Does the paper tell a coherent story from problem to contribution to evidence? Check that each section logically follows from the previous one. Disconnected sections score below 5.",
        },
        {
            "name": "citation_integrity",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are all factual claims properly cited? Check for uncited statistics, unreferenced comparisons, and missing self-citations. Any fabricated citation is an automatic 0.",
        },
        {
            "name": "completeness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Does the paper include all required sections for the target venue (abstract, intro, related work, method, experiments, conclusion)? Missing sections or placeholder text scores below 3.",
        },
        {
            "name": "technical_precision",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are mathematical formulations, algorithm descriptions, and technical terms used correctly and consistently? Notation inconsistencies and informal descriptions score below 6.",
        },
        {
            "name": "figure_table_quality",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Are figures and tables clear, properly labeled, and referenced in the text? Check for missing captions, illegible labels, and unreferenced figures. 8+ means every figure is essential and well-designed.",
        },
        {
            "name": "related_work_positioning",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Does the related work section accurately position this paper relative to prior art? Check for straw-man comparisons, missing key references, and failure to discuss closely related concurrent work.",
        },
        {
            "name": "writing_quality",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Is the writing clear, concise, and appropriate for a top-venue audience? Check for grammar errors, overly informal language, and unclear pronouns. 8+ reads like a polished top-venue submission.",
        },
    ],
}

_PREMIUM = {
    "dimensions": _STANDARD["dimensions"]
    + [
        {
            "name": "abstract_standalone",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the abstract stand alone as a compelling summary? It should convey the problem, approach, key results, and significance without requiring the full paper. Vague abstracts score below 5.",
        },
        {
            "name": "conclusion_strength",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the conclusion go beyond summarizing? Check for insightful limitations, honest future work, and broader impact discussion. Rote summaries score below 6.",
        },
        {
            "name": "venue_format_compliance",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the paper comply with the target venue's formatting requirements (page limit, citation style, anonymity, supplementary material guidelines)? Any violation is a potential desk reject.",
        },
    ],
}

RUBRICS = {
    "economy": _ECONOMY,
    "standard": _STANDARD,
    "premium": _PREMIUM,
}
