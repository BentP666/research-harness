"""Candidate seeding + persistence for the research_candidates recommendation engine.

Groups typed evidence (gaps, contradictions, claims) into CandidateDraft
objects without calling an LLM. The LLM is used LATER in the pipeline
(direction_ranking) to score the resulting drafts; scoring and
opportunity_angle are computed in primitives/recommend.py.

Deterministic structural atoms per draft:
- lineage_key: sha1(primary_signal_family + normalize(primary_evidence))
  Stable across re-seeding so a user-dismissed candidate stays dismissed.
- evidence_signature: sha1(sorted(all_evidence_ids))
  Changes whenever new evidence arrives, triggering re-scoring.

scope format: 'topic:N' (MVP) | 'research_area:N' | 'domain:N'
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..storage.db import Database
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec


# Severity weights when multiple gaps cluster under the same lineage
_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


@dataclass
class CandidateDraft:
    scope: str
    title: str
    pitch: str
    primary_signal_family: str  # 'gap' | 'contradiction' | 'claim'
    primary_signal_id: int
    evidence_gap_ids: list[int] = field(default_factory=list)
    evidence_contradiction_ids: list[int] = field(default_factory=list)
    evidence_claim_ids: list[int] = field(default_factory=list)
    seed_paper_ids: list[int] = field(default_factory=list)
    primary_domain_id: int | None = None
    research_area_ids: list[int] = field(default_factory=list)

    def lineage_key(self) -> str:
        normalized = _normalize_text(self.pitch or self.title)
        raw = f"{self.primary_signal_family}|{normalized}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def evidence_signature(self) -> str:
        parts = [
            f"g:{sorted(self.evidence_gap_ids)}",
            f"c:{sorted(self.evidence_contradiction_ids)}",
            f"cl:{sorted(self.evidence_claim_ids)}",
            f"p:{sorted(self.seed_paper_ids)}",
        ]
        return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _normalize_text(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip().lower())
    return s


CANDIDATE_SEED_SPEC = PrimitiveSpec(
    name="candidate_seed",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Group typed evidence in a scope into CandidateDraft objects. "
        "Deterministic; no LLM. One draft per gap/contradiction cluster."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "scope": {"type": "string", "description": "'topic:N' etc."},
            "min_gap_severity": {
                "type": "string",
                "default": "medium",
                "description": "Gaps below this severity are skipped.",
            },
        },
        "required": ["scope"],
    },
    output_type="list[CandidateDraft]",
    requires_llm=False,
    idempotent=True,
)


def _parse_scope(scope: str) -> tuple[str, int]:
    parts = scope.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid scope: {scope!r}")
    kind, idx = parts
    return kind, int(idx)


def _scope_paper_ids(conn, scope: str) -> list[int]:
    kind, idx = _parse_scope(scope)
    if kind == "topic":
        rows = conn.execute(
            "SELECT paper_id FROM paper_topics WHERE topic_id = ?", (idx,)
        ).fetchall()
    elif kind == "research_area":
        rows = conn.execute(
            "SELECT paper_id FROM paper_research_areas WHERE research_area_id = ?",
            (idx,),
        ).fetchall()
    elif kind == "domain":
        rows = conn.execute(
            "SELECT paper_id FROM paper_domains WHERE domain_id = ?", (idx,)
        ).fetchall()
    else:
        raise ValueError(f"Unknown scope kind: {kind!r}")
    return [int(r[0]) for r in rows]


def _topic_id_for_scope(conn, scope: str) -> int | None:
    """gaps/contradictions are topic-scoped. Return the topic id directly or
    None when a scope doesn't naturally map to one topic."""
    kind, idx = _parse_scope(scope)
    if kind == "topic":
        return idx
    return None


@register_primitive(CANDIDATE_SEED_SPEC)
def seed_candidates(
    *,
    db: Database,
    scope: str,
    min_gap_severity: str = "medium",
    **_: Any,
) -> list[CandidateDraft]:
    drafts: list[CandidateDraft] = []
    topic_id = None
    paper_ids: list[int] = []

    conn = db.connect()
    try:
        topic_id = _topic_id_for_scope(conn, scope)
        paper_ids = _scope_paper_ids(conn, scope)

        # Pass 1 — gap-driven candidates
        if topic_id is not None:
            allowed = {
                "low": {"low", "medium", "high"},
                "medium": {"medium", "high"},
                "high": {"high"},
            }[min_gap_severity]
            severity_filter = ",".join("?" * len(allowed))
            gap_rows = conn.execute(
                f"SELECT id, description, severity, gap_type, related_paper_ids "
                f"FROM gaps WHERE topic_id = ? AND severity IN ({severity_filter}) "
                f"ORDER BY CASE severity "
                f"  WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC, id",
                [topic_id, *allowed],
            ).fetchall()
            for g in gap_rows:
                gap_related = _safe_json_list(g["related_paper_ids"])
                title = _title_from_description(g["description"])
                drafts.append(
                    CandidateDraft(
                        scope=scope,
                        title=title,
                        pitch=g["description"],
                        primary_signal_family="gap",
                        primary_signal_id=int(g["id"]),
                        evidence_gap_ids=[int(g["id"])],
                        seed_paper_ids=[int(p) for p in gap_related if _is_int(p)],
                    )
                )

        # Pass 2 — contradiction-driven candidates
        if topic_id is not None:
            con_rows = conn.execute(
                "SELECT id, claim_a_id, claim_b_id, conflict_reason "
                "FROM contradictions WHERE topic_id = ? AND status = 'candidate'",
                (topic_id,),
            ).fetchall()
            for c in con_rows:
                # Pull papers + claim text for context
                claims = conn.execute(
                    "SELECT nc.id, nc.paper_id, nc.claim_text FROM normalized_claims nc "
                    "WHERE nc.id IN (?, ?)",
                    (c["claim_a_id"], c["claim_b_id"]),
                ).fetchall()
                paper_refs = [int(row[1]) for row in claims]
                claim_ids = [int(row[0]) for row in claims]
                claim_snippet = " vs ".join((row[2] or "")[:80] for row in claims)
                pitch = f"Contradiction: {claim_snippet}" + (
                    f" — {c['conflict_reason']}" if c["conflict_reason"] else ""
                )
                drafts.append(
                    CandidateDraft(
                        scope=scope,
                        title=f"Resolve contradiction #{int(c['id'])}",
                        pitch=pitch,
                        primary_signal_family="contradiction",
                        primary_signal_id=int(c["id"]),
                        evidence_contradiction_ids=[int(c["id"])],
                        evidence_claim_ids=claim_ids,
                        seed_paper_ids=paper_refs,
                    )
                )

        # Attach dominant domain + research_areas from the scope's papers
        if paper_ids:
            primary_domain, area_ids = _dominant_taxonomy(conn, paper_ids)
            for d in drafts:
                if d.primary_domain_id is None:
                    d.primary_domain_id = primary_domain
                if not d.research_area_ids:
                    d.research_area_ids = area_ids
    finally:
        conn.close()

    return drafts


def _safe_json_list(blob: Any) -> list:
    if not blob:
        return []
    try:
        data = json.loads(blob)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _is_int(v: Any) -> bool:
    try:
        int(v)
        return True
    except (TypeError, ValueError):
        return False


def _title_from_description(desc: str) -> str:
    """Use first clause of the gap description as a concise candidate title."""
    first = re.split(r"[.\n]", (desc or "").strip(), maxsplit=1)[0]
    first = first.strip()
    if len(first) > 120:
        first = first[:117] + "..."
    return first or "Untitled candidate"


def _dominant_taxonomy(conn, paper_ids: list[int]) -> tuple[int | None, list[int]]:
    if not paper_ids:
        return None, []
    ph = ",".join("?" * len(paper_ids))
    # Most common domain
    dom_row = conn.execute(
        f"SELECT domain_id, COUNT(*) AS c FROM paper_domains "
        f"WHERE paper_id IN ({ph}) GROUP BY domain_id ORDER BY c DESC LIMIT 1",
        paper_ids,
    ).fetchone()
    primary_domain = int(dom_row[0]) if dom_row else None

    area_rows = conn.execute(
        f"SELECT DISTINCT research_area_id FROM paper_research_areas "
        f"WHERE paper_id IN ({ph}) ORDER BY research_area_id",
        paper_ids,
    ).fetchall()
    area_ids = [int(r[0]) for r in area_rows]
    return primary_domain, area_ids


# ---------------------------------------------------------------------------
# Persistence (upsert) — preserves user status across re-seeding.
# ---------------------------------------------------------------------------


CANDIDATE_UPSERT_SPEC = PrimitiveSpec(
    name="candidate_upsert",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Upsert a research_candidate by (scope, lineage_key). If evidence "
        "signature unchanged and row exists, no-op. Preserves status column."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "scope": {"type": "string"},
            "draft": {"type": "object"},
            "llm_score": {"type": "number"},
            "llm_score_breakdown": {"type": "object"},
            "area_red_ocean": {"type": "number"},
            "task_red_ocean": {"type": "number"},
            "method_red_ocean": {"type": "number"},
            "opportunity_angle": {"type": "string"},
        },
        "required": ["scope", "draft"],
    },
    output_type="int",
    requires_llm=False,
    idempotent=True,
)


@register_primitive(CANDIDATE_UPSERT_SPEC)
def upsert_candidate(
    *,
    db: Database,
    scope: str,
    draft: CandidateDraft | dict[str, Any],
    llm_score: float = 0.0,
    llm_score_breakdown: dict[str, Any] | None = None,
    area_red_ocean: float = 0.0,
    task_red_ocean: float = 0.0,
    method_red_ocean: float = 0.0,
    opportunity_angle: str | None = None,
    confidence_level: str = "normal",
    why: list[str] | None = None,
    risks: list[str] | None = None,
    narration_model: str | None = None,
    **_: Any,
) -> int:
    d = draft if isinstance(draft, CandidateDraft) else _dict_to_draft(draft)
    lineage = d.lineage_key()
    sig = d.evidence_signature()

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, evidence_signature, status FROM research_candidates "
            "WHERE scope = ? AND lineage_key = ?",
            (scope, lineage),
        ).fetchone()

        payload = (
            scope,
            d.primary_domain_id,
            json.dumps(d.research_area_ids),
            d.title,
            d.pitch,
            float(llm_score),
            json.dumps(llm_score_breakdown or {}),
            float(area_red_ocean),
            float(task_red_ocean),
            float(method_red_ocean),
            opportunity_angle,
            confidence_level,
            json.dumps(d.evidence_gap_ids),
            json.dumps(d.evidence_contradiction_ids),
            json.dumps(d.evidence_claim_ids),
            json.dumps(d.seed_paper_ids),
            json.dumps(why or []),
            json.dumps(risks or []),
            lineage,
            sig,
            narration_model,
        )

        if row is None:
            cur = conn.execute(
                "INSERT INTO research_candidates "
                "(scope, primary_domain_id, research_area_ids, title, pitch, "
                " llm_score, llm_score_breakdown, area_red_ocean, task_red_ocean, "
                " method_red_ocean, opportunity_angle, confidence_level, "
                " evidence_gap_ids, evidence_contradiction_ids, evidence_claim_ids, "
                " seed_paper_ids, why, risks, lineage_key, evidence_signature, "
                " narration_model) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                payload,
            )
            conn.commit()
            return int(cur.lastrowid)
        # evidence unchanged → no-op (but return id)
        if row["evidence_signature"] == sig:
            return int(row["id"])
        # Evidence changed → UPDATE; preserve user status
        conn.execute(
            "UPDATE research_candidates SET "
            "primary_domain_id = ?, research_area_ids = ?, title = ?, pitch = ?, "
            "llm_score = ?, llm_score_breakdown = ?, area_red_ocean = ?, "
            "task_red_ocean = ?, method_red_ocean = ?, opportunity_angle = ?, "
            "confidence_level = ?, evidence_gap_ids = ?, "
            "evidence_contradiction_ids = ?, evidence_claim_ids = ?, "
            "seed_paper_ids = ?, why = ?, risks = ?, evidence_signature = ?, "
            "narration_model = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (
                d.primary_domain_id,
                json.dumps(d.research_area_ids),
                d.title,
                d.pitch,
                float(llm_score),
                json.dumps(llm_score_breakdown or {}),
                float(area_red_ocean),
                float(task_red_ocean),
                float(method_red_ocean),
                opportunity_angle,
                confidence_level,
                json.dumps(d.evidence_gap_ids),
                json.dumps(d.evidence_contradiction_ids),
                json.dumps(d.evidence_claim_ids),
                json.dumps(d.seed_paper_ids),
                json.dumps(why or []),
                json.dumps(risks or []),
                sig,
                narration_model,
                int(row["id"]),
            ),
        )
        conn.commit()
        return int(row["id"])
    finally:
        conn.close()


def _dict_to_draft(data: dict[str, Any]) -> CandidateDraft:
    return CandidateDraft(
        scope=data["scope"],
        title=data.get("title", ""),
        pitch=data.get("pitch", ""),
        primary_signal_family=data.get("primary_signal_family", "gap"),
        primary_signal_id=int(data.get("primary_signal_id", 0)),
        evidence_gap_ids=list(data.get("evidence_gap_ids") or []),
        evidence_contradiction_ids=list(data.get("evidence_contradiction_ids") or []),
        evidence_claim_ids=list(data.get("evidence_claim_ids") or []),
        seed_paper_ids=list(data.get("seed_paper_ids") or []),
        primary_domain_id=data.get("primary_domain_id"),
        research_area_ids=list(data.get("research_area_ids") or []),
    )
