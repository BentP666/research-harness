"""JSON-schema description for RH Discover OpportunityBrief payloads."""

from __future__ import annotations

from typing import Any


def opportunity_brief_schema() -> dict[str, Any]:
    """Return a lightweight JSON Schema for the Discover/Core boundary."""

    signal = {
        "type": "object",
        "required": ["type", "title", "url", "published_at", "importance", "reason"],
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "paper",
                    "blog",
                    "product",
                    "repo",
                    "model",
                    "benchmark",
                    "news",
                ],
            },
            "title": {"type": "string"},
            "url": {"type": "string"},
            "published_at": {"type": "string"},
            "importance": {
                "type": "string",
                "enum": ["act_now", "watch", "horizon"],
            },
            "reason": {"type": "string"},
        },
    }
    seed_paper = {
        "type": "object",
        "required": ["title", "doi", "arxiv_id", "url", "year"],
        "properties": {
            "title": {"type": "string"},
            "doi": {"type": ["string", "null"]},
            "arxiv_id": {"type": ["string", "null"]},
            "url": {"type": "string"},
            "year": {"type": ["integer", "null"]},
        },
    }
    goal_preview = {
        "type": "object",
        "required": [
            "title",
            "dataset",
            "baseline",
            "metric_name",
            "target_metric_delta",
            "time_window_days",
            "compute_need",
            "feasibility",
            "evidence_strength",
            "risk",
            "first_steps",
        ],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "dataset": {"type": ["string", "null"]},
            "baseline": {"type": ["string", "null"]},
            "metric_name": {"type": ["string", "null"]},
            "target_metric_delta": {"type": ["number", "null"]},
            "time_window_days": {"type": ["integer", "null"]},
            "compute_need": {"type": "string", "enum": ["low", "medium", "high"]},
            "feasibility": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "evidence_strength": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "risk": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "first_steps": {"type": "array", "items": {"type": "string"}},
            "goalability": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
    }
    readiness = {
        "type": "object",
        "required": [
            "evidence",
            "novelty",
            "feasibility",
            "goalability",
            "handoff_readiness",
        ],
        "properties": {
            key: {"type": "number", "minimum": 0.0, "maximum": 1.0}
            for key in [
                "evidence",
                "novelty",
                "feasibility",
                "goalability",
                "handoff_readiness",
            ]
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "RH Discover OpportunityBrief",
        "type": "object",
        "required": [
            "title",
            "summary",
            "why_now",
            "signals",
            "trend_context",
            "seed_papers",
            "fit_score",
            "goal_previews",
            "readiness",
            "risks",
            "recommended_next_steps",
            "rh_handoff",
        ],
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "why_now": {"type": "string"},
            "signals": {"type": "array", "items": signal, "minItems": 1},
            "trend_context": {
                "type": "object",
                "required": ["window", "growth_summary", "saturation"],
                "properties": {
                    "window": {
                        "type": "string",
                        "enum": ["24h", "7d", "1y", "3y", "5y"],
                    },
                    "growth_summary": {"type": "string"},
                    "saturation": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                },
            },
            "seed_papers": {"type": "array", "items": seed_paper},
            "fit_score": {
                "type": "object",
                "required": ["trend", "novelty", "feasibility", "user_fit", "risk"],
                "properties": {
                    key: {"type": "number", "minimum": 0.0, "maximum": 1.0}
                    for key in ["trend", "novelty", "feasibility", "user_fit", "risk"]
                },
            },
            "goal_previews": {"type": "array", "items": goal_preview},
            "readiness": readiness,
            "risks": {"type": "array", "items": {"type": "string"}},
            "recommended_next_steps": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "rh_handoff": {
                "type": "object",
                "required": [
                    "topic_name",
                    "initial_queries",
                    "suggested_primitives",
                ],
                "properties": {
                    "topic_name": {"type": "string"},
                    "initial_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "suggested_primitives": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    }
