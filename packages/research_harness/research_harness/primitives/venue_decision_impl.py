"""Venue Decision + Style Kit primitives.

venue_decision: selects best venue given intake constraints + field brief.
venue_style_kit: distills writing style from real papers at the decided venue.

3-tier degradation for style_kit:
1. Exact venue match >= 3 papers → use them
2. Venue family expansion (NLP/ML/time-series overlap) → source_venues recorded
3. Family still insufficient → 409 Conflict, front-end shows "Need more reference papers"
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class VenueDecision(BaseModel):
    decided_venue: str
    decision_basis: dict[str, Any]
    fit_risk: list[str] | None = None
    source_venues: list[str] = []


class VenueStyleKit(BaseModel):
    venue: str
    avg_section_lengths: dict[str, int]
    citation_density: float
    hedging_terms: list[str]
    source_paper_ids: list[int]
    source_venues: list[str]


# ---------------------------------------------------------------------------
# Venue family mapping
# ---------------------------------------------------------------------------

_VENUE_FAMILIES: dict[str, list[str]] = {
    "nlp": ["emnlp", "acl", "naacl", "eacl", "coling", "findings"],
    "ml": ["neurips", "icml", "iclr", "aaai", "ijcai", "aistats"],
    "cv": ["cvpr", "iccv", "eccv"],
    "ir": ["sigir", "wsdm", "cikm", "kdd"],
    "time_series": ["neurips", "icml", "iclr", "aaai", "kdd", "ieee", "ijf"],
}


def _find_venue_family(venue: str) -> list[str]:
    v_lower = venue.lower()
    for _family, members in _VENUE_FAMILIES.items():
        if any(m in v_lower for m in members):
            return members
    return []


# ---------------------------------------------------------------------------
# Transient retry
# ---------------------------------------------------------------------------

_TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)


def _call_with_transient_retry(chat_fn, prompt: str, *, retries: int = 1) -> str:
    last_err: BaseException | None = None
    for attempt in range(1 + retries):
        try:
            return chat_fn(prompt)
        except _TRANSIENT_ERRORS as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
        except Exception as exc:
            err_str = str(exc).lower()
            if any(
                k in err_str for k in ("timeout", "connection", "502", "503", "504")
            ):
                last_err = exc
                if attempt < retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
            raise
    raise RuntimeError(f"Failed after {1 + retries} attempts: {last_err}") from last_err


# ---------------------------------------------------------------------------
# venue_decision
# ---------------------------------------------------------------------------


def decide_venue(topic_id: int, db: Any) -> VenueDecision:
    conn = db.connect()
    try:
        intake = conn.execute(
            "SELECT * FROM topic_intake_profile WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    finally:
        conn.close()

    if not intake:
        raise RuntimeError("Intake profile not found.")

    from research_harness.primitives.field_brief_impl import get_latest_field_brief

    fb_result = get_latest_field_brief(topic_id, db)
    if not fb_result:
        raise RuntimeError("Field brief not found.")
    venue_options = fb_result["brief"].get("venue_options") or []

    constraint = intake["venue_constraint"]
    target = intake["target_venue"] or ""

    if constraint == "locked":
        decision = VenueDecision(
            decided_venue=target,
            decision_basis={"constraint": "locked", "target": target},
            fit_risk=[] if venue_options else ["No matching papers in pool"],
            source_venues=[target],
        )
    elif constraint == "preferred":
        matching = [
            v for v in venue_options if target.lower() in (v.get("name") or "").lower()
        ]
        if matching:
            decision = VenueDecision(
                decided_venue=target,
                decision_basis={
                    "constraint": "preferred",
                    "target": target,
                    "matched": True,
                },
                source_venues=[target],
            )
        else:
            best = venue_options[0] if venue_options else None
            decided = best["name"] if best else target
            decision = VenueDecision(
                decided_venue=decided,
                decision_basis={
                    "constraint": "preferred",
                    "target": target,
                    "matched": False,
                    "suggestion": decided,
                },
                fit_risk=[
                    f"Preferred venue '{target}' not found in field brief. Suggesting '{decided}' instead."
                ],
                source_venues=[decided],
            )
    else:
        if venue_options:
            best = venue_options[0]
            decided = best["name"]
        else:
            decided = "arXiv"
        decision = VenueDecision(
            decided_venue=decided,
            decision_basis={"constraint": "open", "selected": decided},
            source_venues=[decided],
        )

    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO venue_decision (topic_id, decided_venue, decision_basis, fit_risk, source_venues)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(topic_id) DO UPDATE SET
                 decided_venue = excluded.decided_venue,
                 decision_basis = excluded.decision_basis,
                 fit_risk = excluded.fit_risk,
                 source_venues = excluded.source_venues,
                 decided_at = CURRENT_TIMESTAMP""",
            (
                topic_id,
                decision.decided_venue,
                json.dumps(decision.decision_basis, ensure_ascii=False),
                json.dumps(decision.fit_risk, ensure_ascii=False)
                if decision.fit_risk
                else None,
                json.dumps(decision.source_venues, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return decision


# ---------------------------------------------------------------------------
# venue_style_kit — 3-tier degradation
# ---------------------------------------------------------------------------


def build_style_kit(topic_id: int, db: Any) -> VenueStyleKit:
    conn = db.connect()
    try:
        vd_row = conn.execute(
            "SELECT * FROM venue_decision WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    finally:
        conn.close()

    if not vd_row:
        raise RuntimeError("Venue decision not found. Decide venue first.")

    decided_venue = vd_row["decided_venue"]
    source_venues_used: list[str] = []

    # Tier 1: exact venue match
    conn = db.connect()
    try:
        papers = conn.execute(
            """SELECT p.id, p.title, p.compiled_summary, p.venue
               FROM papers p JOIN paper_topics pt ON pt.paper_id = p.id
               WHERE pt.topic_id = ? AND p.venue LIKE ?
               AND p.compiled_summary IS NOT NULL AND p.compiled_summary != ''
               LIMIT 5""",
            (topic_id, f"%{decided_venue}%"),
        ).fetchall()
    finally:
        conn.close()

    if len(papers) >= 3:
        source_venues_used = [decided_venue]
    else:
        # Tier 2: venue family expansion
        family = _find_venue_family(decided_venue)
        if family:
            conn = db.connect()
            try:
                like_clauses = " OR ".join(["p.venue LIKE ?" for _ in family])
                like_params = [f"%{v}%" for v in family]
                papers = conn.execute(
                    f"""SELECT p.id, p.title, p.compiled_summary, p.venue
                        FROM papers p JOIN paper_topics pt ON pt.paper_id = p.id
                        WHERE pt.topic_id = ? AND ({like_clauses})
                        AND p.compiled_summary IS NOT NULL AND p.compiled_summary != ''
                        LIMIT 5""",
                    [topic_id] + like_params,
                ).fetchall()
            finally:
                conn.close()
            source_venues_used = list({p["venue"] for p in papers if p["venue"]})

        if len(papers) < 3:
            # Tier 3: insufficient → 409
            raise RuntimeError(
                f"Need at least 3 reference papers for venue style analysis. "
                f"Found {len(papers)} for '{decided_venue}' and family {family}. "
                f"Please ingest more papers from this venue."
            )

    paper_ids = [p["id"] for p in papers]

    # LLM-based style extraction
    combined = "\n\n---\n\n".join(
        f"Paper: {p['title']}\nVenue: {p['venue']}\n{p['compiled_summary'][:1500]}"
        for p in papers
    )

    from research_harness.execution.llm_primitives import _get_client, _client_chat

    client = _get_client(None, tier="light", task_name="style_kit")

    prompt = (
        "Analyze these academic papers and extract writing style patterns.\n"
        "Return JSON:\n"
        '{"avg_section_lengths": {"introduction": int, "related_work": int, "method": int, '
        '"experiments": int, "conclusion": int}, '
        '"citation_density": float (citations per 100 words), '
        '"hedging_terms": [top 10 hedging phrases]}\n\n'
        f"{combined}"
    )

    raw = _call_with_transient_retry(lambda p: _client_chat(client, p), prompt)

    from research_harness.execution.llm_primitives import _parse_json

    parsed = _parse_json(raw, primitive="style_kit")

    try:
        kit = VenueStyleKit(
            venue=decided_venue,
            avg_section_lengths=parsed.get("avg_section_lengths", {}),
            citation_density=float(parsed.get("citation_density", 0.0)),
            hedging_terms=parsed.get("hedging_terms", []),
            source_paper_ids=paper_ids,
            source_venues=source_venues_used,
        )
    except (ValidationError, TypeError) as exc:
        raise RuntimeError(f"Style kit validation failed: {exc}") from exc

    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO venue_style_kit
               (topic_id, venue, avg_section_lengths, citation_density,
                hedging_terms, source_paper_ids, source_venues)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(topic_id) DO UPDATE SET
                 venue = excluded.venue,
                 avg_section_lengths = excluded.avg_section_lengths,
                 citation_density = excluded.citation_density,
                 hedging_terms = excluded.hedging_terms,
                 source_paper_ids = excluded.source_paper_ids,
                 source_venues = excluded.source_venues,
                 built_at = CURRENT_TIMESTAMP""",
            (
                topic_id,
                kit.venue,
                json.dumps(kit.avg_section_lengths, ensure_ascii=False),
                kit.citation_density,
                json.dumps(kit.hedging_terms, ensure_ascii=False),
                json.dumps(kit.source_paper_ids),
                json.dumps(kit.source_venues, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return kit
