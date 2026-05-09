"""Advisor reports — sharable section bundles for PhD→PI workflow.

One of the core v2 product insights: PhDs don't ship finished papers to
advisors, they ship *partial* documents (abstract-only, abstract+intro,
deep pitch). This module persists those bundles with version history and
a share-token so the advisor can read without logging in.
"""

from __future__ import annotations

from .service import (
    REPORT_TEMPLATES,
    ReportSummary,
    create_share_token,
    generate_report,
    get_report,
    list_reports,
    render_markdown,
)

__all__ = [
    "REPORT_TEMPLATES",
    "ReportSummary",
    "create_share_token",
    "generate_report",
    "get_report",
    "list_reports",
    "render_markdown",
]
