"""Build stage rubric — literature retrieval and corpus construction quality."""

from __future__ import annotations

_ECONOMY = {
    "dimensions": [
        {
            "name": "corpus_coverage",
            "weight": 0.40,
            "rubric_prompt": "Score 1-10: Does the paper pool cover the key research threads? Check for missing seminal works, recent state-of-the-art papers, and competing approaches. 8+ requires no obvious gaps in top-venue publications from the last 3 years.",
        },
        {
            "name": "metadata_completeness",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Are paper metadata fields (title, authors, year, venue, abstract, citation count) populated? Penalize missing venues or years that prevent quality assessment.",
        },
        {
            "name": "retrieval_diversity",
            "weight": 0.30,
            "rubric_prompt": "Score 1-10: Were multiple retrieval strategies used (keyword, citation expansion, author tracking)? A single-strategy pool risks systematic blind spots.",
        },
    ],
}

_STANDARD = {
    "dimensions": [
        {
            "name": "corpus_coverage",
            "weight": 0.20,
            "rubric_prompt": "Score 1-10: Does the paper pool cover the key research threads? Check for missing seminal works, recent state-of-the-art papers, and competing approaches. 8+ requires no obvious gaps in top-venue publications from the last 3 years.",
        },
        {
            "name": "metadata_completeness",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Are paper metadata fields (title, authors, year, venue, abstract, citation count) populated? Penalize missing venues or years that prevent quality assessment.",
        },
        {
            "name": "retrieval_diversity",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: Were multiple retrieval strategies used (keyword, citation expansion, author tracking)? A single-strategy pool risks systematic blind spots.",
        },
        {
            "name": "relevance_precision",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: What fraction of papers are genuinely relevant to the topic? Penalize pools padded with tangentially related work. 8+ means >80% of papers directly address a facet of the research question.",
        },
        {
            "name": "temporal_distribution",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: Is the publication year distribution appropriate? Recent work (last 2 years) should dominate, but foundational papers must be present. Penalize pools that are entirely recent or entirely old.",
        },
        {
            "name": "venue_quality",
            "weight": 0.15,
            "rubric_prompt": "Score 1-10: What fraction of papers come from recognized venues (CCF-A/B, top workshops)? A pool dominated by preprints with no peer-reviewed anchor papers scores below 6.",
        },
        {
            "name": "pdf_availability",
            "weight": 0.10,
            "rubric_prompt": "Score 1-10: What fraction of relevant papers have accessible PDFs? Structured extraction depends on PDF access. 8+ means >70% of high-relevance papers have PDFs resolved.",
        },
    ],
}

_PREMIUM = {
    "dimensions": _STANDARD["dimensions"]
    + [
        {
            "name": "citation_network_density",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Is the citation graph well-connected? Isolated clusters suggest missing bridging papers. Check for papers that cite each other and identify any disconnected subgraphs.",
        },
        {
            "name": "baseline_identification",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Are the main baseline methods and their source papers clearly identified in the corpus? 8+ requires at least 3 competing approaches with their original papers present.",
        },
        {
            "name": "negative_result_coverage",
            "weight": 0.00,
            "rubric_prompt": "Score 1-10: Does the corpus include papers reporting negative results or failed approaches? These inform what not to try and are often missing from superficial searches.",
        },
    ],
}

RUBRICS = {
    "economy": _ECONOMY,
    "standard": _STANDARD,
    "premium": _PREMIUM,
}
