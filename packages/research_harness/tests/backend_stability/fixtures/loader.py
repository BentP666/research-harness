"""Offline fixture loader for backend-stability tests.

Reads ``fixtures/topics/*.json`` and ``fixtures/papers/*.json`` and
inserts them into a fresh ``Database`` directly via SQL — bypasses the
real ``paper_ingest`` primitive (which requires network) and any
``research_init`` dialogue. Tests that want to exercise the real
ingest path should use the per-test fixtures, not this loader.

Loader contract:
- idempotent: re-running on the same DB is a no-op (uses INSERT OR IGNORE)
- side-effect-free outside the DB: no PDF downloads, no provenance writes
- returns a ``LoadedTopic`` so tests can grab the topic_id and seed paper_ids
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_harness.storage.db import Database

FIXTURE_ROOT = Path(__file__).parent
TOPICS_DIR = FIXTURE_ROOT / "topics"
PAPERS_DIR = FIXTURE_ROOT / "papers"


@dataclass(frozen=True)
class LoadedTopic:
    name: str
    topic_id: int
    paper_ids: tuple[int, ...]
    spec: dict[str, Any]


def _read_topic_spec(name: str) -> dict[str, Any]:
    path = TOPICS_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_paper_spec(arxiv_id: str) -> dict[str, Any] | None:
    path = PAPERS_DIR / f"{arxiv_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_topic_specs() -> list[str]:
    """Return all available topic spec names (without .json suffix)."""
    return sorted(p.stem for p in TOPICS_DIR.glob("*.json"))


def load_topic(db: Database, spec_name: str) -> LoadedTopic:
    """Load a topic + its seed papers into ``db``. Idempotent.

    Reads ``topics/<spec_name>.json`` and ingests each seed listed in
    ``spec.seeds`` from ``papers/<seed>.json``. If a paper has
    ``fixture_flags`` containing ``mark_stale_after_ingest``, it is
    inserted with status ``stale`` (drives loopback tests).
    """
    spec = _read_topic_spec(spec_name)
    conn = db.connect()
    try:
        # 1. topic
        conn.execute(
            """
            INSERT OR IGNORE INTO topics (name, description, target_venue, deadline)
            VALUES (?, ?, ?, ?)
            """,
            (
                spec["name"],
                spec.get("direction", ""),
                spec.get("venue_target", ""),
                spec.get("deadline", ""),
            ),
        )
        topic_row = conn.execute(
            "SELECT id FROM topics WHERE name = ?", (spec["name"],)
        ).fetchone()
        topic_id = int(topic_row["id"])

        # 1b. project — orchestrator_runs.project_id has a FK to projects(id);
        # service code passes (topic_id, topic_id, mode) so project_id matches
        # the topic's id. Create a project row whose id equals topic_id so
        # the FK resolves.
        conn.execute(
            "INSERT OR IGNORE INTO projects (id, topic_id, name, description) "
            "VALUES (?, ?, ?, ?)",
            (
                topic_id,
                topic_id,
                f"fixture-project-{spec['name']}",
                spec.get("direction", ""),
            ),
        )

        # 2. papers + topic linkage
        paper_ids: list[int] = []
        for seed in spec.get("seeds", []):
            pspec = _read_paper_spec(seed)
            if pspec is None:
                # Test may want to detect missing-fixture cases — just skip
                continue
            flags = set(pspec.get("fixture_flags") or [])
            status = "stale" if "mark_stale_after_ingest" in flags else "meta_only"
            # doi, arxiv_id, s2_id are now nullable UNIQUE (migration 064).
            # Pass None for missing ids so multiple fixture rows can coexist
            # without the old '' vs '' UNIQUE collision.
            arxiv_id = pspec.get("arxiv_id") or None
            doi = pspec.get("doi") or None
            s2_id = pspec.get("s2_id") or None
            conn.execute(
                """
                INSERT OR IGNORE INTO papers
                  (title, authors, year, venue, doi, arxiv_id, s2_id, status, abstract)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pspec.get("title", ""),
                    json.dumps(pspec.get("authors", [])),
                    pspec.get("year"),
                    pspec.get("venue", ""),
                    doi,
                    arxiv_id,
                    s2_id,
                    status,
                    pspec.get("abstract", ""),
                ),
            )
            paper_row = conn.execute(
                "SELECT id FROM papers WHERE arxiv_id = ?",
                (arxiv_id,),
            ).fetchone()
            if paper_row is None:
                continue
            pid = int(paper_row["id"])
            paper_ids.append(pid)
            conn.execute(
                """
                INSERT OR IGNORE INTO paper_topics (paper_id, topic_id, relevance)
                VALUES (?, ?, ?)
                """,
                (pid, topic_id, "high"),
            )
        conn.commit()
    finally:
        conn.close()

    return LoadedTopic(
        name=spec["name"],
        topic_id=topic_id,
        paper_ids=tuple(paper_ids),
        spec=spec,
    )
