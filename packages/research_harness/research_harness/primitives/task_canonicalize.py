"""LLM-driven canonicalization of normalized_claims.task labels.

The normalized_claims table stores per-claim (method, dataset, metric, task)
tuples extracted by evidence_matrix. Human-written tasks are noisy:
"sentiment classification" vs "sentiment analysis" vs "sentiment detection"
are the same conceptual task but split across rows, defeating cross-paper
aggregation for red-ocean scoring.

This primitive:
1. Queries DISTINCT task strings with task_canonical IS NULL (and task != '').
2. Asks an LLM to group near-duplicates under a single canonical label per
   cluster, preserving real distinctions (sentiment vs stance detection).
3. Updates every row in the cluster with the canonical label.

Idempotent: only touches rows whose task_canonical is NULL (re-running
processes only the newly-added noise). Callers can force a re-run by
NULL-ing task_canonical first.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from llm_router.client import LLMClient, resolve_llm_config

from ..storage.db import Database
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

logger = logging.getLogger(__name__)


CANONICALIZE_PROMPT = """You are deduplicating research-task labels from a
scientific-paper database. Given the raw task strings below, group those
that refer to the SAME underlying task under one canonical label.

Preserve real distinctions:
- "sentiment classification" and "sentiment analysis" and "sentiment
   detection" are the SAME task → group.
- "sentiment detection" and "stance detection" are DIFFERENT → separate.
- "image classification" and "image segmentation" are DIFFERENT → separate.

Output strict JSON array, no commentary:
[
  {{"canonical": "short 2-4 word label", "members": ["orig1", "orig2", ...]}},
  ...
]

Every input string must appear in exactly one group's members. Rules:
- "canonical" should be concise, lowercased, and the most common or
  most precise phrasing of the cluster.
- If a task is unique (no near-duplicate in the list), its group has
  exactly one member equal to itself, and canonical = the task string.
- Preserve all input strings verbatim in members; do not rephrase them.

Tasks ({n}):
{task_list}
"""


@dataclass
class CanonicalizeGroup:
    canonical: str
    members: list[str] = field(default_factory=list)


@dataclass
class CanonicalizeOutput:
    processed_rows: int
    group_count: int
    groups: list[CanonicalizeGroup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed_rows": self.processed_rows,
            "group_count": self.group_count,
            "groups": [asdict(g) for g in self.groups],
        }


TASK_CANONICALIZE_SPEC = PrimitiveSpec(
    name="task_canonicalize",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Group near-duplicate normalized_claims.task strings under canonical "
        "labels via LLM; UPDATE task_canonical for every clustered row."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "domain_id": {
                "type": "integer",
                "description": "Optional — only canonicalize tasks from papers "
                "in this domain. Default: all NULL rows.",
            },
            "batch_size": {"type": "integer", "default": 200},
        },
    },
    output_type="CanonicalizeOutput",
    requires_llm=True,
    idempotent=True,
)


def _parse_groups(raw: str) -> list[CanonicalizeGroup]:
    """Best-effort parse of LLM JSON-array output."""
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
        txt = txt.strip()
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    blob = m.group(0) if m else txt
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return []
    groups: list[CanonicalizeGroup] = []
    if not isinstance(data, list):
        return []
    for item in data:
        if not isinstance(item, dict):
            continue
        canonical = (item.get("canonical") or "").strip()
        members = item.get("members") or []
        if not canonical:
            continue
        clean_members = [
            str(m).strip() for m in members if isinstance(m, str) and str(m).strip()
        ]
        if not clean_members:
            continue
        groups.append(CanonicalizeGroup(canonical=canonical, members=clean_members))
    return groups


def _fetch_distinct_tasks(conn, *, domain_id: int | None, batch_size: int) -> list[str]:
    if domain_id is None:
        rows = conn.execute(
            "SELECT DISTINCT task FROM normalized_claims "
            "WHERE task_canonical IS NULL AND task IS NOT NULL AND task != '' "
            "ORDER BY task LIMIT ?",
            (batch_size,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT nc.task FROM normalized_claims nc "
            "JOIN paper_domains pd ON pd.paper_id = nc.paper_id "
            "WHERE pd.domain_id = ? AND nc.task_canonical IS NULL "
            "  AND nc.task IS NOT NULL AND nc.task != '' "
            "ORDER BY nc.task LIMIT ?",
            (domain_id, batch_size),
        ).fetchall()
    return [r[0] for r in rows]


@register_primitive(TASK_CANONICALIZE_SPEC)
def task_canonicalize(
    *,
    db: Database,
    domain_id: int | None = None,
    batch_size: int = 200,
    client: LLMClient | None = None,
    **_: Any,
) -> CanonicalizeOutput:
    conn = db.connect()
    try:
        tasks = _fetch_distinct_tasks(conn, domain_id=domain_id, batch_size=batch_size)
    finally:
        conn.close()

    if not tasks:
        return CanonicalizeOutput(processed_rows=0, group_count=0, groups=[])

    if client is None:
        client = LLMClient(resolve_llm_config())

    prompt = CANONICALIZE_PROMPT.format(
        n=len(tasks),
        task_list="\n".join(f"- {t}" for t in tasks),
    )
    try:
        raw = client.chat(prompt)
    except Exception as exc:
        logger.warning("task_canonicalize: LLM call failed: %s", exc)
        return CanonicalizeOutput(processed_rows=0, group_count=0, groups=[])

    groups = _parse_groups(raw)
    if not groups:
        logger.warning("task_canonicalize: LLM returned unparseable output")
        return CanonicalizeOutput(processed_rows=0, group_count=0, groups=[])

    # Write updates
    processed = 0
    conn = db.connect()
    try:
        for g in groups:
            if not g.members:
                continue
            placeholders = ",".join("?" * len(g.members))
            cur = conn.execute(
                f"UPDATE normalized_claims SET task_canonical = ? "
                f"WHERE task_canonical IS NULL AND task IN ({placeholders})",
                [g.canonical, *g.members],
            )
            processed += cur.rowcount or 0
        conn.commit()
    finally:
        conn.close()

    return CanonicalizeOutput(
        processed_rows=processed,
        group_count=len(groups),
        groups=groups,
    )
