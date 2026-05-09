"""Method Atoms primitive — extracts reusable method components from papers.

Each atom represents a discrete technique (loss function, data augmentation,
training schedule, etc.) that can be recombined in the experiment matrix.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------


class MethodAtom(BaseModel):
    atom_type: Literal[
        "loss",
        "data_trick",
        "augmentation",
        "training_schedule",
        "inference_heuristic",
        "micro_block",
    ]
    name: str
    description: str
    deps: list[str] = []
    reported_gain: str | None = None
    reuse_risk: Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Transient retry (shared pattern)
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
    raise RuntimeError(
        f"LLM call failed after {1 + retries} attempts: {last_err}"
    ) from last_err


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_HARVEST_PROMPT = """\
You are a method decomposition expert. Given a paper's title and content,
extract all discrete method components ("atoms") that could be reused in
other experiments.

Return ONLY valid JSON — a list of objects:
[
  {{
    "atom_type": "loss" | "data_trick" | "augmentation" | "training_schedule" | "inference_heuristic" | "micro_block",
    "name": str,
    "description": str (1-2 sentences),
    "deps": [str] (names of other atoms this depends on, or empty),
    "reported_gain": str or null (e.g. "+2.3 BLEU", "-5% MAPE"),
    "reuse_risk": "low" | "medium" | "high"
  }}
]

Rules:
- atom_type categories:
  - loss: novel loss functions or regularization terms
  - data_trick: data preprocessing, feature engineering, normalization
  - augmentation: data augmentation strategies
  - training_schedule: learning rate schedules, curriculum learning, etc.
  - inference_heuristic: post-processing, ensemble, calibration
  - micro_block: architectural components (attention variants, etc.)
- reuse_risk: low = drop-in reusable, medium = needs adaptation, high = tightly coupled to paper's setup
- Extract 2-8 atoms per paper. Skip trivial atoms (e.g. "use Adam optimizer").

Paper: {title}

Content:
{content}
"""


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def harvest_atoms_from_paper(
    topic_id: int,
    paper_id: int,
    db: Any,
) -> list[MethodAtom]:
    """Extract method atoms from a single paper.

    Args:
        topic_id: Topic context
        paper_id: Paper to analyze
        db: Database instance

    Returns:
        List of validated MethodAtom objects

    Raises:
        RuntimeError: if paper not found, LLM fails, or all atoms fail validation
    """
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT title, abstract, compiled_summary FROM papers WHERE id = ?",
            (paper_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise RuntimeError(f"Paper {paper_id} not found")

    title = row["title"] or "Untitled"
    content = row["compiled_summary"] or row["abstract"] or ""
    if not content:
        raise RuntimeError(f"Paper {paper_id} has no summary or abstract to analyze")

    if len(content) > 3000:
        content = content[:3000] + "..."

    prompt = _HARVEST_PROMPT.format(title=title, content=content)

    from research_harness.execution.llm_primitives import _get_client, _client_chat

    client = _get_client(None, tier="light", task_name="harvest_atoms")
    raw = _call_with_transient_retry(lambda p: _client_chat(client, p), prompt)

    from research_harness.execution.llm_primitives import _parse_json

    parsed = _parse_json(raw, primitive="harvest_atoms")

    if isinstance(parsed, dict) and "atoms" in parsed:
        candidates = parsed["atoms"]
    elif isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict):
        candidates = [parsed]
    else:
        raise RuntimeError(f"LLM returned unexpected format: {type(parsed)}")

    validated: list[MethodAtom] = []
    for c in candidates:
        try:
            atom = MethodAtom.model_validate(c)
            validated.append(atom)
        except ValidationError:
            logger.warning("Skipping invalid atom: %s", c)

    if not validated:
        raise RuntimeError(f"LLM returned 0 valid atoms for paper {paper_id}")

    # Write to DB
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for atom in validated:
            conn.execute(
                """INSERT INTO method_atoms
                   (topic_id, source_paper_id, atom_type, name, description,
                    deps, reported_gain, reuse_risk)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    topic_id,
                    paper_id,
                    atom.atom_type,
                    atom.name,
                    atom.description,
                    json.dumps(atom.deps, ensure_ascii=False),
                    atom.reported_gain,
                    atom.reuse_risk,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return validated


def harvest_atoms_batch(
    topic_id: int,
    paper_ids: list[int],
    db: Any,
) -> dict[str, Any]:
    """Harvest atoms from multiple papers. Returns summary."""
    results: dict[str, Any] = {"total_atoms": 0, "papers_processed": 0, "errors": []}
    for pid in paper_ids:
        try:
            atoms = harvest_atoms_from_paper(topic_id, pid, db)
            results["total_atoms"] += len(atoms)
            results["papers_processed"] += 1
        except RuntimeError as exc:
            results["errors"].append({"paper_id": pid, "error": str(exc)})
    return results
