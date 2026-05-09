"""Claim tracking and citation grounding enforcement."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any


class UngroundedClaimError(Exception):
    def __init__(self, claim_text: str):
        self.claim_text = claim_text
        super().__init__(f"Ungrounded claim (0 citations): {claim_text[:100]}")


def _derive_uuid(text: str) -> str:
    """Deterministic claim_uuid from content."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"claim_{digest}"


def write_claim(
    conn: sqlite3.Connection,
    artifact_id: int,
    topic_id: int,
    text: str,
    claim_type: str | None = None,
    citation_paper_ids: list[int] | None = None,
    evidence_quotes: list[str] | None = None,
    *,
    modality: str = "text",
    evidence_spans: list[dict[str, Any]] | None = None,
    confidence: float = 0.0,
    claim_uuid: str | None = None,
) -> int:
    """Persist a grounded claim with migration 050 columns.

    Extra kwargs (modality, evidence_spans, confidence, claim_uuid) are the
    new migration-050 columns. Legacy callers that pass only positional/old
    kwargs still work because of defaults. See ADR-001 Decision 3.
    """
    if not citation_paper_ids:
        raise UngroundedClaimError(text)

    uuid_val = claim_uuid or _derive_uuid(text)
    modality_val = (
        modality
        if modality in {"text", "figure", "table", "equation", "mixed"}
        else "text"
    )
    paper_ids_json = json.dumps(list(citation_paper_ids))
    evidence_spans_json = json.dumps(evidence_spans or [])

    cur = conn.execute(
        """
        INSERT INTO claims (
            artifact_id, topic_id, text, claim_type,
            modality, claim_uuid, paper_ids_json, evidence_spans_json, confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            topic_id,
            text,
            claim_type,
            modality_val,
            uuid_val,
            paper_ids_json,
            evidence_spans_json,
            float(confidence),
        ),
    )
    claim_id = cur.lastrowid
    assert claim_id is not None

    quotes = evidence_quotes or [None] * len(citation_paper_ids)
    for paper_id, quote in zip(citation_paper_ids, quotes):
        conn.execute(
            "INSERT INTO claim_citations (claim_id, paper_id, evidence_quote) VALUES (?, ?, ?)",
            (claim_id, paper_id, quote),
        )

    return claim_id
