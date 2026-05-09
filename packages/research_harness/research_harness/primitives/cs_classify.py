"""LLM-driven CS paper classifier.

Primary classification path post Phase 0 (CSO_MODE=llm_fallback decision).
Assigns a coarse domain (one of 15 arxiv CS categories, including
cs.OTHER) and 1–3 fine-grained research_areas per paper, persisting to:

- research_areas (upserted by (domain_id, slug))
- paper_research_areas (paper_id × research_area_id; is_primary=1 for first)
- paper_domains (paper_id × domain_id; is_primary=1 for first)

Design notes:
- Reads title + abstract; no PDF required (works for meta_only papers).
- CSO is retained as an optional supplementary signal when
  RESEARCH_HUB_CSO_MODE=cso is set, but the default is llm-only.
- Blocks generic, non-informative terms ("computer science",
  "artificial intelligence", "machine learning", …) from
  research_area names to force LLM to produce a specific label.
- Idempotent: re-running on the same paper replaces its
  paper_research_areas / paper_domains rows atomically.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from llm_router.client import LLMClient, resolve_llm_config

from ..storage.db import Database
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

logger = logging.getLogger(__name__)


VALID_DOMAINS: tuple[str, ...] = (
    "cs.AI",
    "cs.LG",
    "cs.CV",
    "cs.CL",
    "cs.IR",
    "cs.RO",
    "cs.CR",
    "cs.DB",
    "cs.DC",
    "cs.DS",
    "cs.HC",
    "cs.PL",
    "cs.SE",
    "cs.SY",
    "cs.OTHER",
)


GENERIC_BLOCKLIST: frozenset[str] = frozenset(
    {
        "computer science",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "algorithms",
        "mathematics",
        "engineering",
        "neural network",
        "neural networks",
        "research",
        "method",
        "methods",
    }
)


CLASSIFY_PROMPT = """You are a CS paper classifier. Given a title and abstract,
produce JSON with exactly these keys:

  "domain": one of {domains}
  "research_areas": array of 1-3 specific research-area names (2-5 words each)
  "rationale": one short sentence

Rules:
- "domain" must be drawn verbatim from the list above. Use "cs.OTHER" only
  when nothing else fits.
- "research_areas" must be SPECIFIC. Do NOT return generic labels like
  "machine learning", "deep learning", "artificial intelligence",
  "neural networks", or "algorithms". Examples of good labels:
  "reinforcement learning from human feedback",
  "graph neural network pretraining",
  "differential privacy for federated learning".
- Output strictly parseable JSON. No markdown, no commentary.

Title: {title}

Abstract: {abstract}
"""


@dataclass
class PaperClassification:
    paper_id: int
    domain: str
    research_areas: list[str] = field(default_factory=list)
    rationale: str = ""
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClassifyOutput:
    classified: list[PaperClassification]
    skipped: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classified": [c.to_dict() for c in self.classified],
            "skipped": list(self.skipped),
        }


CS_CLASSIFY_SPEC = PrimitiveSpec(
    name="cs_classify",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Classify papers into a CS domain (cs.AI/.LG/…) + 1-3 fine-grained "
        "research_areas via LLM. Writes paper_research_areas and paper_domains."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "paper_ids": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["paper_ids"],
    },
    output_type="ClassifyOutput",
    requires_llm=True,
    idempotent=True,
)


def _slugify(s: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return slug or "unknown"


def _filter_areas(candidates: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for c in candidates:
        if not isinstance(c, str):
            continue
        txt = c.strip()
        if not txt:
            continue
        if txt.lower() in GENERIC_BLOCKLIST:
            continue
        if txt in out:
            continue
        out.append(txt)
    return out[:3]


def _parse_response(raw: str) -> tuple[str, list[str], str]:
    """Best-effort JSON parse. Returns (domain, areas, rationale).

    Falls back to ("cs.OTHER", [], "parse_error") when the LLM returns
    unusable output — the caller records this as source='parse_error' and
    the paper still gets its coarse bucket, so downstream joins work.
    """
    txt = raw.strip()
    # Some providers wrap JSON in ```json fences
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
        txt = txt.strip()
    # Take the largest JSON-looking substring
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    blob = m.group(0) if m else txt
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return "cs.OTHER", [], "parse_error"
    domain = parsed.get("domain") if isinstance(parsed, dict) else ""
    if domain not in VALID_DOMAINS:
        domain = "cs.OTHER"
    areas = _filter_areas(parsed.get("research_areas") or [])
    rationale = (parsed.get("rationale") or "").strip()
    return domain, areas, rationale


def _get_or_create_research_area(conn, domain_id: int, name: str, source: str) -> int:
    slug = _slugify(name)
    row = conn.execute(
        "SELECT id FROM research_areas WHERE domain_id = ? AND slug = ?",
        (domain_id, slug),
    ).fetchone()
    if row:
        return int(row["id"])
    conn.execute(
        "INSERT INTO research_areas (domain_id, name, slug, source) "
        "VALUES (?, ?, ?, ?)",
        (domain_id, name, slug, source),
    )
    row = conn.execute(
        "SELECT id FROM research_areas WHERE domain_id = ? AND slug = ?",
        (domain_id, slug),
    ).fetchone()
    return int(row["id"])


def _domain_id_for(conn, name: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM domains WHERE name = ? LIMIT 1", (name,)
    ).fetchone()
    if row:
        return int(row["id"])
    # cs.OTHER must exist after `rh domain seed cs`; if missing, caller
    # forgot to seed — surface this by returning None and logging.
    if name == "cs.OTHER":
        logger.warning(
            "cs_classify: cs.OTHER domain not found. Run `rh domain seed cs`."
        )
    return None


def _classify_with_client(
    *, client: LLMClient, title: str, abstract: str
) -> tuple[str, list[str], str]:
    prompt = CLASSIFY_PROMPT.format(
        domains=", ".join(VALID_DOMAINS),
        title=(title or "").strip(),
        abstract=(abstract or "").strip(),
    )
    raw = client.chat(prompt)
    return _parse_response(raw)


@register_primitive(CS_CLASSIFY_SPEC)
def cs_classify(
    *,
    db: Database,
    paper_ids: list[int],
    client: LLMClient | None = None,
    **_: Any,
) -> ClassifyOutput:
    if not paper_ids:
        return ClassifyOutput(classified=[], skipped=[])

    own_client = client is None
    if own_client:
        client = LLMClient(resolve_llm_config())

    out_classified: list[PaperClassification] = []
    skipped: list[int] = []

    conn = db.connect()
    try:
        placeholders = ",".join("?" * len(paper_ids))
        rows = conn.execute(
            f"SELECT id, title, abstract FROM papers WHERE id IN ({placeholders})",
            list(paper_ids),
        ).fetchall()

        for r in rows:
            pid = int(r["id"])
            title = r["title"] or ""
            abstract = r["abstract"] or ""
            if not title and not abstract:
                skipped.append(pid)
                continue

            try:
                domain, areas, rationale = _classify_with_client(
                    client=client, title=title, abstract=abstract
                )
            except Exception as exc:
                logger.warning(
                    "cs_classify: LLM call failed for paper %d: %s", pid, exc
                )
                skipped.append(pid)
                continue

            domain_id = _domain_id_for(conn, domain)
            if domain_id is None:
                # Fallback to cs.OTHER if primary domain row missing
                domain_id = _domain_id_for(conn, "cs.OTHER")
            if domain_id is None:
                skipped.append(pid)
                continue

            # Replace existing paper_domains rows for this paper
            conn.execute("DELETE FROM paper_domains WHERE paper_id = ?", (pid,))
            conn.execute(
                "INSERT INTO paper_domains (paper_id, domain_id, is_primary) "
                "VALUES (?, ?, 1)",
                (pid, domain_id),
            )

            # Replace existing paper_research_areas for this paper
            conn.execute("DELETE FROM paper_research_areas WHERE paper_id = ?", (pid,))
            source = "llm" if not _is_parse_error(rationale) else "llm_parse_error"
            for i, area in enumerate(areas):
                area_id = _get_or_create_research_area(conn, domain_id, area, source)
                conn.execute(
                    "INSERT OR IGNORE INTO paper_research_areas "
                    "(paper_id, research_area_id, is_primary, match_type) "
                    "VALUES (?, ?, ?, 'llm')",
                    (pid, area_id, 1 if i == 0 else 0),
                )

            out_classified.append(
                PaperClassification(
                    paper_id=pid,
                    domain=domain,
                    research_areas=areas,
                    rationale=rationale,
                    source=source,
                )
            )
        conn.commit()
    finally:
        conn.close()

    return ClassifyOutput(classified=out_classified, skipped=skipped)


def _is_parse_error(rationale: str) -> bool:
    return rationale.strip() == "parse_error"
