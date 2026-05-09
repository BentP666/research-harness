"""Field Brief primitive — distills a structured 6-dimension snapshot from the
paper pool for a given topic.

Produces: datasets, baselines, narrative_patterns, open_challenges,
compute_bands, venue_options, saturation_score.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema — LLM output MUST conform to this
# ---------------------------------------------------------------------------


class Dataset(BaseModel):
    name: str
    size: str | None = None
    license: str | None = None
    gpu_req: Literal["cpu", "low", "medium", "high"]


class Baseline(BaseModel):
    name: str
    paper_id: int | None = None
    metric_name: str
    metric_value: float


class Challenge(BaseModel):
    problem: str
    maturity: Literal["saturated", "hot", "niche"]


class VenueOption(BaseModel):
    name: str
    deadline: str | None = None
    acceptance_rate: float | None = None


class FieldBrief(BaseModel):
    datasets: list[Dataset]
    baselines: list[Baseline]
    narrative_patterns: list[str]
    open_challenges: list[Challenge]
    compute_bands: list[str]
    venue_options: list[VenueOption]
    saturation_score: float = Field(ge=0, le=1)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a research field analyst. Given a collection of paper summaries from a
specific research topic, produce a structured "Field Brief" that captures the
landscape in 6 dimensions.

Return ONLY valid JSON matching this exact schema (no markdown fences, no extra text):

{
  "datasets": [{"name": str, "size": str|null, "license": str|null, "gpu_req": "cpu"|"low"|"medium"|"high"}],
  "baselines": [{"name": str, "paper_id": int|null, "metric_name": str, "metric_value": float}],
  "narrative_patterns": [str],
  "open_challenges": [{"problem": str, "maturity": "saturated"|"hot"|"niche"}],
  "compute_bands": [str],
  "venue_options": [{"name": str, "deadline": str|null, "acceptance_rate": float|null}],
  "saturation_score": float  // 0.0 = blue ocean, 1.0 = fully saturated
}

Rules:
- datasets: list ALL datasets mentioned across papers. gpu_req = minimum GPU needed.
- baselines: list key methods with their best reported metric values.
- narrative_patterns: recurring themes / framings across papers (3-5 items).
- open_challenges: unsolved problems mentioned. maturity = field crowdedness for that problem.
- compute_bands: distinct compute tiers used across papers (e.g. "4×A100", "CPU-only", "1×V100").
- venue_options: conferences/journals where these papers were published, with deadlines if known.
- saturation_score: your estimate of how saturated this subfield is (0=wide open, 1=fully explored).
"""


def _build_user_prompt(paper_summaries: list[dict[str, Any]]) -> str:
    parts = [f"Topic paper pool ({len(paper_summaries)} papers):\n"]
    for i, p in enumerate(paper_summaries, 1):
        title = p.get("title") or "Untitled"
        summary = p.get("compiled_summary") or p.get("abstract") or "(no summary)"
        if len(summary) > 1500:
            summary = summary[:1500] + "..."
        parts.append(f"--- Paper {i}: {title} ---\n{summary}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Transient retry helper (per Q3 modification — 1 retry for network errors)
# ---------------------------------------------------------------------------

_TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def _call_with_transient_retry(chat_fn, prompt: str, *, retries: int = 1) -> str:
    last_err: BaseException | None = None
    for attempt in range(1 + retries):
        try:
            return chat_fn(prompt)
        except _TRANSIENT_ERRORS as exc:
            last_err = exc
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Transient error on attempt %d, retrying in %ds: %s",
                    attempt + 1,
                    wait,
                    exc,
                )
                time.sleep(wait)
            continue
        except Exception as exc:
            err_str = str(exc).lower()
            if any(
                k in err_str for k in ("timeout", "connection", "502", "503", "504")
            ):
                last_err = exc
                if attempt < retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Provider error on attempt %d, retrying in %ds: %s",
                        attempt + 1,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                    continue
            raise
    raise RuntimeError(
        f"LLM call failed after {1 + retries} attempts: {last_err}"
    ) from last_err


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def build_field_brief(
    topic_id: int,
    db: Any,
) -> FieldBrief:
    """Build a FieldBrief from the topic's paper pool.

    Args:
        topic_id: Topic to analyze
        db: Database instance (research_harness.storage.db.Database)

    Returns:
        Validated FieldBrief

    Raises:
        RuntimeError: if no papers, LLM fails, or schema validation fails
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.title, p.abstract, p.compiled_summary
            FROM papers p
            JOIN paper_topics pt ON pt.paper_id = p.id
            WHERE pt.topic_id = ?
            ORDER BY p.id
            """,
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise RuntimeError(
            f"No papers found for topic {topic_id}. Ingest papers first."
        )

    paper_summaries = [dict(r) for r in rows]
    user_prompt = _build_user_prompt(paper_summaries)
    full_prompt = _SYSTEM_PROMPT + "\n\n" + user_prompt

    from research_harness.execution.llm_primitives import _get_client, _client_chat

    client = _get_client(None, tier="medium", task_name="field_brief")

    raw_text = _call_with_transient_retry(
        lambda p: _client_chat(client, p),
        full_prompt,
    )

    # Parse JSON from LLM output
    from research_harness.execution.llm_primitives import _parse_json

    parsed = _parse_json(raw_text, primitive="field_brief")
    if not parsed:
        raise RuntimeError(
            f"LLM returned empty or unparseable output for field_brief. "
            f"Raw (first 500 chars): {raw_text[:500]}"
        )

    try:
        brief = FieldBrief.model_validate(parsed)
    except ValidationError as exc:
        raise RuntimeError(
            f"LLM output failed schema validation: {exc.errors()}"
        ) from exc

    # Record artifact + meta
    from research_harness.orchestrator import OrchestratorService

    svc = OrchestratorService(db)
    artifact = svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="field_brief",
        title="Field Brief",
        payload=brief.model_dump(),
    )

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        paper_count = conn.execute(
            "SELECT COUNT(*) FROM paper_topics WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO field_brief_meta (topic_id, artifact_id, paper_count_at_build, built_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(topic_id) DO UPDATE SET
                 artifact_id = excluded.artifact_id,
                 paper_count_at_build = excluded.paper_count_at_build,
                 built_at = excluded.built_at,
                 stale = 0""",
            (
                topic_id,
                artifact.id,
                paper_count,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return brief


def get_latest_field_brief(
    topic_id: int,
    db: Any,
) -> dict[str, Any] | None:
    """Return the latest field_brief artifact content + meta, or None."""
    conn = db.connect()
    try:
        meta_row = conn.execute(
            "SELECT * FROM field_brief_meta WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
        if not meta_row:
            return None

        meta = dict(meta_row)

        # Check time-based staleness (>21 days)
        built_at_str = meta.get("built_at") or ""
        if built_at_str:
            try:
                built_at = datetime.fromisoformat(built_at_str.replace("Z", "+00:00"))
                if built_at.tzinfo is None:
                    built_at = built_at.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - built_at).days
                if age_days > 21 and not meta["stale"]:
                    conn.execute(
                        "UPDATE field_brief_meta SET stale = 1 WHERE topic_id = ?",
                        (topic_id,),
                    )
                    conn.commit()
                    meta["stale"] = 1
            except (ValueError, TypeError):
                pass

        artifact_row = conn.execute(
            "SELECT payload_json FROM project_artifacts WHERE id = ?",
            (meta["artifact_id"],),
        ).fetchone()
        if not artifact_row:
            return None

        brief_data = json.loads(artifact_row["payload_json"])
        return {
            "brief": brief_data,
            "meta": {
                "stale": bool(meta["stale"]),
                "built_at": meta["built_at"],
                "paper_count_at_build": meta["paper_count_at_build"],
            },
        }
    finally:
        conn.close()
