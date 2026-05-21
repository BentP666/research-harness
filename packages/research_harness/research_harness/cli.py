"""hub CLI entrypoint."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import logging
import os
import platform
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import click

from .config import find_workspace_root, init_project_config, load_runtime_config
from .storage.db import Database
from .storage.models import Paper, TopicPaperNote

REQUIRED_ANNOTATION_SECTIONS = ("summary", "methodology", "experiments", "limitations")
NOTE_TYPES = ("relevance", "comparison", "usage_plan", "critique")
BACKEND_CHOICES = ("local", "claude_code", "research_harness")
logger = logging.getLogger(__name__)


def get_runtime_config(ctx: click.Context):
    runtime_config = ctx.obj.get("runtime_config")
    if runtime_config is None:
        runtime_config = load_runtime_config(
            ctx.obj.get("db_path"),
            explicit_backend=ctx.obj.get("backend_override"),
        )
        ctx.obj["runtime_config"] = runtime_config
    return runtime_config


def get_db(ctx: click.Context) -> Database:
    db = ctx.obj.get("db")
    if db is None:
        runtime_config = get_runtime_config(ctx)
        db = Database(runtime_config.db_path)
        db.migrate()
        ctx.obj["db"] = db
    return db


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _count_records(conn: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"] if row is not None else 0)


def _create_backend(ctx: click.Context):
    from .execution import create_backend

    return create_backend(ctx.obj["backend_name"], db=get_db(ctx))


def _echo(ctx: click.Context, result: object, text: str | None = None) -> None:
    if ctx.obj.get("json"):
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
    elif text is not None:
        click.echo(text)


def _write_text_output(output: str | None, content: str) -> None:
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        return
    sys.stdout.write(content)


def _serialize_provenance_export(records: list[object], fmt: str) -> str:
    payload = [dataclasses.asdict(record) for record in records]
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, default=str)

    fieldnames = [
        "timestamp",
        "primitive_name",
        "backend",
        "model",
        "cost_usd",
        "success",
        "duration_ms",
    ]
    rows: list[dict[str, object]] = []
    for item in payload:
        duration_ms = 0
        started_at = item.get("started_at")
        finished_at = item.get("finished_at")
        if (
            isinstance(started_at, str)
            and isinstance(finished_at, str)
            and started_at
            and finished_at
        ):
            try:
                started = datetime.fromisoformat(started_at)
                finished = datetime.fromisoformat(finished_at)
                duration_ms = int((finished - started).total_seconds() * 1000)
            except ValueError:
                duration_ms = 0
        rows.append(
            {
                "timestamp": item.get("started_at", ""),
                "primitive_name": item.get("primitive", ""),
                "backend": item.get("backend", ""),
                "model": item.get("model_used", ""),
                "cost_usd": item.get("cost_usd", 0.0),
                "success": item.get("success", False),
                "duration_ms": duration_ms,
            }
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _topic_id_or_exit(conn: sqlite3.Connection, topic_name: str) -> int:
    row = conn.execute("SELECT id FROM topics WHERE name = ?", (topic_name,)).fetchone()
    if not row:
        raise click.ClickException(f"topic '{topic_name}' not found")
    return int(row[0])


def _decode_artifact_metadata(metadata: object) -> object:
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except json.JSONDecodeError:
            return {"raw": metadata}
    return metadata


def _paper_artifact_or_exit(
    conn: sqlite3.Connection, paper_id: int, artifact_type: str
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT artifact_type, path, metadata, created_at
        FROM paper_artifacts
        WHERE paper_id = ? AND artifact_type = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (paper_id, artifact_type),
    ).fetchone()
    if row is not None:
        return row
    if artifact_type == "paperindex_card":
        raise click.ClickException(
            f"paper {paper_id} has no paper card artifact; run 'paper annotate {paper_id}' first"
        )
    raise click.ClickException(
        f"artifact '{artifact_type}' for paper {paper_id} not found"
    )


def _load_json_artifact_or_exit(path: str | Path, artifact_label: str) -> object:
    artifact_path = Path(path)
    if not artifact_path.exists():
        raise click.ClickException(
            f"{artifact_label} artifact file not found: {artifact_path}"
        )
    try:
        return json.loads(artifact_path.read_text())
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"{artifact_label} artifact at {artifact_path} is not valid JSON"
        ) from exc


def _card_text(card: dict[str, object], key: str) -> str:
    value = card.get(key, "")
    if isinstance(value, str):
        return value.strip()
    return ""


def _card_items(card: dict[str, object], key: str) -> list[str]:
    value = card.get(key, [])
    if isinstance(value, list):
        return [text for text in (str(item).strip() for item in value) if text]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return []


def _join_or_fallback(values: list[str], fallback: str, limit: int = 3) -> str:
    selected = [item for item in values if item][:limit]
    return "; ".join(selected) if selected else fallback


def _topic_note_next_action(artifact_status: dict[str, object]) -> str:
    return (
        "draft_topic_note_from_card"
        if artifact_status["has_card"]
        else "write_topic_note"
    )


def _draft_topic_note_from_card(
    paper_obj: Paper,
    topic_name: str,
    note_type: str,
    card: dict[str, object],
    topic_relevance: str = "",
) -> str:
    title = paper_obj.title or _card_text(card, "title") or f"Paper {paper_obj.id}"
    core_idea = (
        _card_text(card, "core_idea")
        or "No summary extracted yet. Review the PDF and card manually."
    )
    method_summary = (
        _card_text(card, "method_summary") or "Method details were not extracted yet."
    )
    key_results = _card_items(card, "key_results")
    limitations = _card_items(card, "limitations")
    evidence_sections = [
        str(item.get("section")).strip()
        for item in card.get("evidence", [])
        if isinstance(item, dict) and str(item.get("section", "")).strip()
    ]
    results_line = _join_or_fallback(key_results, "No key results were extracted yet.")
    limitations_line = _join_or_fallback(
        limitations, "No explicit limitations were extracted yet."
    )
    evidence_line = _join_or_fallback(
        evidence_sections, "No evidence sections were extracted.", limit=4
    )
    relevance_line = topic_relevance or "not specified"

    if note_type == "relevance":
        lines = [
            f"Topic: {topic_name}",
            f"Paper: {title}",
            f"Linked relevance: {relevance_line}",
            f"Why it matters: {core_idea}",
            f"Method signal: {method_summary}",
            f"Evidence worth citing: {results_line}",
            f"Watch-outs: {limitations_line}",
        ]
    elif note_type == "comparison":
        lines = [
            f"Topic: {topic_name}",
            f"Paper: {title}",
            f"Comparison focus: {core_idea}",
            f"Method to compare against our work: {method_summary}",
            f"Reported outcomes: {results_line}",
            f"Sections to inspect manually: {evidence_line}",
        ]
    elif note_type == "usage_plan":
        lines = [
            f"Topic: {topic_name}",
            f"Paper: {title}",
            f"Planned use: Reuse or verify the following idea for this topic: {core_idea}",
            f"Implementation angle: {method_summary}",
            f"What to extract next: {results_line}",
            f"Validation checklist: {limitations_line}",
        ]
    else:
        lines = [
            f"Topic: {topic_name}",
            f"Paper: {title}",
            f"Main claim to scrutinize: {core_idea}",
            f"Method risk: {method_summary}",
            f"Evidence coverage: {results_line}",
            f"Potential weaknesses: {limitations_line}",
        ]
    return "\n".join(lines)


def _paper_status_payload(
    conn: sqlite3.Connection, paper_obj: Paper
) -> dict[str, object]:
    from .core.paper_pool import PaperPool

    pool = PaperPool(conn)
    annotations = pool.get_annotations(paper_obj.id or 0)
    topics = conn.execute(
        """
        SELECT t.id AS topic_id, t.name, pt.relevance
        FROM paper_topics pt
        JOIN topics t ON pt.topic_id = t.id
        WHERE pt.paper_id = ?
        ORDER BY t.name, t.id
        """,
        (paper_obj.id,),
    ).fetchall()
    artifacts = conn.execute(
        "SELECT artifact_type, path, metadata, created_at FROM paper_artifacts WHERE paper_id = ? ORDER BY created_at DESC, id DESC",
        (paper_obj.id,),
    ).fetchall()
    notes = conn.execute(
        """
        SELECT t.name AS topic_name, n.topic_id, n.note_type, n.source, n.created_at
        FROM topic_paper_notes n
        JOIN topics t ON n.topic_id = t.id
        WHERE n.paper_id = ?
        ORDER BY t.name, n.note_type
        """,
        (paper_obj.id,),
    ).fetchall()

    current_hash = paper_obj.pdf_hash
    completed_sections = sorted(
        item.section
        for item in annotations
        if item.content
        and (not current_hash or item.pdf_hash_at_extraction == current_hash)
    )
    stale_sections = sorted(
        item.section
        for item in annotations
        if current_hash
        and item.pdf_hash_at_extraction
        and item.pdf_hash_at_extraction != current_hash
    )
    missing_sections = sorted(
        section
        for section in REQUIRED_ANNOTATION_SECTIONS
        if section not in completed_sections
    )
    artifact_rows = [dict(row) for row in artifacts]
    artifact_types = sorted({item["artifact_type"] for item in artifact_rows})
    artifact_details = [
        {
            "artifact_type": item["artifact_type"],
            "path": item["path"],
            "created_at": item["created_at"],
            "metadata": _decode_artifact_metadata(item["metadata"]),
        }
        for item in artifact_rows
    ]
    notes_by_topic: dict[str, list[str]] = {}
    for row in notes:
        notes_by_topic.setdefault(row["topic_name"], []).append(row["note_type"])
    for topic_name in list(notes_by_topic):
        notes_by_topic[topic_name] = sorted(notes_by_topic[topic_name])

    return {
        "paper": dataclasses.asdict(paper_obj),
        "linked_topics": [dict(row) for row in topics],
        "annotation_status": {
            "completed_sections": completed_sections,
            "missing_sections": missing_sections,
            "stale_sections": stale_sections,
            "count": len(completed_sections),
            "total_expected": len(REQUIRED_ANNOTATION_SECTIONS),
        },
        "artifact_status": {
            "count": len(artifact_details),
            "types": artifact_types,
            "has_structure": "paperindex_structure" in artifact_types,
            "has_card": "paperindex_card" in artifact_types,
            "items": artifact_details,
        },
        "topic_note_status": {
            "count": len(notes),
            "by_topic": notes_by_topic,
        },
        "ready": {
            "has_pdf": bool(paper_obj.pdf_path),
            "needs_annotation": bool(missing_sections),
            "can_export_card": "paperindex_card" in artifact_types,
        },
    }


def _paper_queue_entry(
    topic_name: str,
    status_payload: dict[str, object],
    conn: sqlite3.Connection | None = None,
    topic_id: int | None = None,
) -> dict[str, object]:
    paper = status_payload["paper"]
    annotation_status = status_payload["annotation_status"]
    artifact_status = status_payload["artifact_status"]
    topic_note_status = status_payload["topic_note_status"]
    ready = status_payload["ready"]
    topic_notes = sorted(topic_note_status["by_topic"].get(topic_name, []))

    next_actions: list[str] = []
    if not ready["has_pdf"]:
        bucket = "missing_pdf"
        next_actions.append("attach_pdf")
    elif annotation_status["stale_sections"]:
        bucket = "stale_annotations"
        next_actions.append("refresh_stale_annotations")
    elif annotation_status["missing_sections"]:
        bucket = "missing_sections"
        next_actions.append("annotate_sections")
    elif not topic_notes:
        bucket = "missing_topic_note"
        next_actions.append(_topic_note_next_action(artifact_status))
    else:
        bucket = "ready"
        next_actions.append("ready")

    if ready["has_pdf"] and not topic_notes and bucket != "missing_topic_note":
        next_actions.append(_topic_note_next_action(artifact_status))

    priority_rank = {
        "missing_pdf": 0,
        "stale_annotations": 1,
        "missing_sections": 2,
        "missing_card": 3,
        "missing_topic_note": 4,
        "ready": 5,
    }[bucket]

    has_pending_task = False
    if conn is not None and topic_id is not None:
        pending_row = conn.execute(
            "SELECT 1 FROM tasks WHERE topic_id = ? AND paper_id = ? AND status IN ('pending', 'in_progress') LIMIT 1",
            (topic_id, paper["id"]),
        ).fetchone()
        has_pending_task = pending_row is not None

    return {
        "paper_id": paper["id"],
        "title": paper["title"],
        "status": paper["status"],
        "queue_bucket": bucket,
        "priority_rank": priority_rank,
        "has_pdf": ready["has_pdf"],
        "completed_sections": annotation_status["completed_sections"],
        "missing_sections": annotation_status["missing_sections"],
        "stale_sections": annotation_status["stale_sections"],
        "artifact_types": artifact_status["types"],
        "topic_notes": topic_notes,
        "next_actions": next_actions,
        "has_pending_task": has_pending_task,
    }


@click.group()
@click.option(
    "--db", "db_path", default=None, help="SQLite database path (explicit override)"
)
@click.option("--json", "json_output", is_flag=True, default=False, help="JSON output")
@click.option(
    "--backend",
    type=click.Choice(BACKEND_CHOICES),
    default=None,
    help="Execution backend",
)
@click.pass_context
def main(
    ctx: click.Context, db_path: str | None, json_output: bool, backend: str | None
) -> None:
    """Research Hub - agent-first research workflow platform."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path
    ctx.obj["backend_override"] = backend
    ctx.obj["json"] = json_output
    ctx.obj["runtime_config"] = load_runtime_config(db_path, explicit_backend=backend)
    ctx.obj["backend_name"] = ctx.obj["runtime_config"].execution_backend


# Skill subcommands live in research_harness/skill/cli.py to keep this file
# from growing further. Registered after `main` is defined.
from .skill.cli import register as _register_skill_cli  # noqa: E402

_register_skill_cli(main)

# RH Discover is an incubation surface with a deliberately small CLI module.
from .discover.cli import register as _register_discover_cli  # noqa: E402

_register_discover_cli(main)


@main.group()
def config() -> None:
    """Manage runtime config."""


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    runtime_config = get_runtime_config(ctx)
    payload = {
        "db_path": str(runtime_config.db_path),
        "source": runtime_config.source,
        "workspace_root": str(runtime_config.workspace_root)
        if runtime_config.workspace_root
        else None,
        "config_path": str(runtime_config.config_path)
        if runtime_config.config_path
        else None,
        "execution_backend": runtime_config.execution_backend,
    }
    _echo(ctx, payload, f"DB: {payload['db_path']} ({payload['source']})")


@config.command("init")
@click.option(
    "--db-path",
    default=None,
    help="Store a project-local DB path in .research-harness/config.json",
)
@click.pass_context
def config_init(ctx: click.Context, db_path: str | None) -> None:
    workspace_root = find_workspace_root() or Path.cwd()
    config_path = init_project_config(workspace_root, db_path=db_path)
    ctx.obj["runtime_config"] = load_runtime_config(
        ctx.obj.get("db_path"), cwd=workspace_root
    )
    payload = {
        "config_path": str(config_path),
        "workspace_root": str(workspace_root),
        "db_path": str(get_runtime_config(ctx).db_path),
        "source": get_runtime_config(ctx).source,
        "execution_backend": get_runtime_config(ctx).execution_backend,
    }
    _echo(ctx, payload, f"Initialized project config at {config_path}")


@main.group()
def backend() -> None:
    """Execution backend management."""


@backend.command("list")
@click.pass_context
def backend_list(ctx: click.Context) -> None:
    """List available backends."""
    from .execution import get_backend_names

    names = get_backend_names()
    if ctx.obj.get("json"):
        click.echo(json.dumps(names, ensure_ascii=False))
        return
    for name in names:
        click.echo(name)


@backend.command("info")
@click.pass_context
def backend_info(ctx: click.Context) -> None:
    """Show current backend info and capabilities."""
    info = _create_backend(ctx).get_info()
    payload = dataclasses.asdict(info)
    _echo(ctx, payload, f"{info.name}: {info.description}")


@backend.command("primitives")
@click.pass_context
def backend_primitives(ctx: click.Context) -> None:
    """List primitives supported by current backend."""
    info = _create_backend(ctx).get_info()
    if ctx.obj.get("json"):
        click.echo(json.dumps(info.supported_primitives, ensure_ascii=False))
        return
    for primitive_name in info.supported_primitives:
        click.echo(primitive_name)


@main.group()
def domain() -> None:
    """Manage research domains."""


CS_DOMAIN_SEED: list[tuple[str, str]] = [
    ("cs.AI", "Artificial Intelligence"),
    ("cs.LG", "Machine Learning"),
    ("cs.CV", "Computer Vision"),
    ("cs.CL", "Computation and Language / NLP"),
    ("cs.IR", "Information Retrieval"),
    ("cs.RO", "Robotics"),
    ("cs.CR", "Cryptography and Security"),
    ("cs.DB", "Databases"),
    ("cs.DC", "Distributed Computing"),
    ("cs.DS", "Data Structures and Algorithms"),
    ("cs.HC", "Human-Computer Interaction"),
    ("cs.PL", "Programming Languages"),
    ("cs.SE", "Software Engineering"),
    ("cs.SY", "Systems and Control"),
    ("cs.OTHER", "Other Computer Science"),
]


@domain.command("seed")
@click.argument("kind", type=click.Choice(["cs"]))
@click.pass_context
def domain_seed(ctx: click.Context, kind: str) -> None:
    """Seed a pre-defined set of domains (currently: cs → 15 arxiv CS cats)."""
    db = get_db(ctx)
    if kind != "cs":
        raise click.ClickException(f"Unknown seed kind: {kind}")
    inserted: list[str] = []
    updated: list[str] = []
    conn = db.connect()
    try:
        for name, description in CS_DOMAIN_SEED:
            existing = conn.execute(
                "SELECT id, description FROM domains WHERE name = ?", (name,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO domains (name, description) VALUES (?, ?)",
                    (name, description),
                )
                inserted.append(name)
            elif not existing[1]:
                conn.execute(
                    "UPDATE domains SET description = ? WHERE name = ?",
                    (description, name),
                )
                updated.append(name)
        conn.commit()
    finally:
        conn.close()
    payload = {
        "kind": kind,
        "inserted": inserted,
        "updated": updated,
        "skipped": [
            n for n, _ in CS_DOMAIN_SEED if n not in inserted and n not in updated
        ],
    }
    _echo(
        ctx,
        payload,
        f"Seeded CS domains — {len(inserted)} inserted, {len(updated)} updated, "
        f"{len(payload['skipped'])} already present.",
    )


@domain.command("init")
@click.argument("name")
@click.option("--description", "-d", default="")
@click.pass_context
def domain_init(ctx: click.Context, name: str, description: str) -> None:
    """Create a new domain."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO domains (name, description) VALUES (?, ?)",
            (name, description),
        )
        conn.commit()
        domain_id = conn.execute(
            "SELECT id FROM domains WHERE name = ?", (name,)
        ).fetchone()[0]
    finally:
        conn.close()
    _echo(
        ctx,
        {"id": domain_id, "name": name, "status": "active"},
        f"Domain '{name}' created (id={domain_id})",
    )


@domain.command("list")
@click.pass_context
def domain_list(ctx: click.Context) -> None:
    """List all domains with topic counts."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT d.*, COALESCE(tc.cnt, 0) AS topic_count
            FROM domains d
            LEFT JOIN (
                SELECT domain_id, COUNT(*) AS cnt FROM topics WHERE domain_id IS NOT NULL GROUP BY domain_id
            ) tc ON tc.domain_id = d.id
            ORDER BY d.created_at DESC, d.id DESC
            """
        ).fetchall()
    finally:
        conn.close()
    if ctx.obj.get("json"):
        click.echo(
            json.dumps([dict(row) for row in rows], ensure_ascii=False, default=str)
        )
        return
    for row in rows:
        click.echo(
            f"[{row['id']}] {row['name']} ({row['status']}) topics={row['topic_count']}"
        )


@domain.command("show")
@click.argument("domain_name")
@click.pass_context
def domain_show(ctx: click.Context, domain_name: str) -> None:
    """Show domain details with its topics."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM domains WHERE name = ?", (domain_name,)
        ).fetchone()
        if row is None:
            raise click.ClickException(f"domain '{domain_name}' not found")
        domain_id = row["id"]
        topics = conn.execute(
            "SELECT id, name, status FROM topics WHERE domain_id = ? ORDER BY created_at",
            (domain_id,),
        ).fetchall()
    finally:
        conn.close()

    topic_list = [dict(t) for t in topics]
    payload = {**dict(row), "topics": topic_list}
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    click.echo(f"Domain: {row['name']} (id={domain_id})")
    click.echo(f"Description: {row['description'] or '-'}")
    click.echo(f"Status: {row['status']}  Topics: {len(topic_list)}")
    for t in topic_list:
        click.echo(f"  [{t['id']}] {t['name']} ({t['status']})")


@main.group()
def cs() -> None:
    """CS-workflow bulk operations (harvest, classify, red-ocean)."""


@cs.command("harvest")
@click.option("--year", type=int, required=True, help="Publication year to harvest.")
@click.option(
    "--target",
    type=int,
    default=1000,
    show_default=True,
    help="Keep top-N head papers after deterministic ranking.",
)
@click.option(
    "--per-provider-limit",
    type=int,
    default=50,
    show_default=True,
    help="Per-provider cap per (category × seed_query) call.",
)
@click.option(
    "--classify/--no-classify",
    default=False,
    show_default=True,
    help="After harvest, LLM-classify head papers into research_areas.",
)
@click.option(
    "--red-ocean/--no-red-ocean",
    "red_ocean",
    default=False,
    show_default=True,
    help="After classify, compute red-ocean score for affected areas. "
    "No-op without --classify.",
)
@click.pass_context
def cs_harvest_cmd(
    ctx: click.Context,
    year: int,
    target: int,
    per_provider_limit: int,
    classify: bool,
    red_ocean: bool,
) -> None:
    """Harvest CS papers across 14 arxiv categories × seed queries.

    Ingests with topic_id=NULL (pool-only), dedupes, ranks with
    head_paper_rank. With --classify, runs cs_classify on the head set
    (LLM cost ≈ N * 1 call). With --red-ocean, scores all touched
    research_areas (deterministic).
    """
    from .primitives.cs_harvest import cs_harvest as _cs_harvest

    db = get_db(ctx)
    result = _cs_harvest(
        db=db,
        year=year,
        target=target,
        per_provider_limit=per_provider_limit,
        classify=classify,
        compute_red_ocean=red_ocean,
    )
    payload = result.to_dict()
    summary_parts = [
        f"Harvested year={result.year}: {result.ingested} kept as head,",
        f"{result.discovered} unique discovered,",
        f"{result.total_ingested} total ingested across",
        f"{len(result.categories_covered)} categories.",
    ]
    if classify:
        summary_parts.append(f"Classified {result.classified} papers.")
    if red_ocean:
        summary_parts.append(f"Scored {result.areas_scored} research_areas.")
    _echo(ctx, payload, " ".join(summary_parts))


@main.group()
def topic() -> None:
    """Manage research topics."""


@topic.command("init")
@click.argument("name")
@click.option("--description", "-d", default="")
@click.option("--venue", default="")
@click.option("--deadline", default="")
@click.option("--domain", "domain_name", default=None, help="Assign to a domain")
@click.pass_context
def topic_init(
    ctx: click.Context,
    name: str,
    description: str,
    venue: str,
    deadline: str,
    domain_name: str | None,
) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        domain_id: int | None = None
        if domain_name:
            row = conn.execute(
                "SELECT id FROM domains WHERE name = ?", (domain_name,)
            ).fetchone()
            if not row:
                raise click.ClickException(f"domain '{domain_name}' not found")
            domain_id = int(row[0])
        conn.execute(
            "INSERT INTO topics (name, description, target_venue, deadline, domain_id) VALUES (?, ?, ?, ?, ?)",
            (name, description, venue, deadline, domain_id),
        )
        conn.commit()
        topic_id = conn.execute(
            "SELECT id FROM topics WHERE name = ?", (name,)
        ).fetchone()[0]
    finally:
        conn.close()
    _echo(
        ctx,
        {"id": topic_id, "name": name, "status": "created", "domain_id": domain_id},
        f"Topic '{name}' created (id={topic_id})",
    )


@topic.command("list")
@click.pass_context
def topic_list(ctx: click.Context) -> None:
    db = get_db(ctx)
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM topics ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    if ctx.obj.get("json"):
        click.echo(
            json.dumps([dict(row) for row in rows], ensure_ascii=False, default=str)
        )
        return
    for row in rows:
        click.echo(f"[{row['id']}] {row['name']} ({row['status']})")


@topic.command("show")
@click.argument("topic_name")
@click.pass_context
def topic_show(ctx: click.Context, topic_name: str) -> None:
    """Show topic details."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM topics WHERE name = ?", (topic_name,)
        ).fetchone()
        if row is None:
            raise click.ClickException(f"topic '{topic_name}' not found")
        topic_id = row["id"]
        paper_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM paper_topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()["cnt"]
    finally:
        conn.close()

    payload = {**dict(row), "paper_count": paper_count}
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    click.echo(f"Topic: {row['name']} (id={topic_id})")
    click.echo(f"Description: {row['description'] or '-'}")
    click.echo(
        f"Venue: {row['target_venue'] or '-'}  Deadline: {row['deadline'] or '-'}"
    )
    click.echo(f"Status: {row['status']}  Papers: {paper_count}")


@topic.command("update")
@click.argument("topic_name")
@click.option("--new-name", default=None)
@click.option("--description", "description", default=None)
@click.option("--venue", default=None)
@click.option("--deadline", default=None)
@click.option("--status", type=click.Choice(["active", "paused", "archived"]))
@click.pass_context
def topic_update(
    ctx: click.Context,
    topic_name: str,
    new_name: str | None,
    description: str | None,
    venue: str | None,
    deadline: str | None,
    status: str | None,
) -> None:
    """Update topic metadata."""
    if all(value is None for value in (new_name, description, venue, deadline, status)):
        raise click.ClickException("Nothing to update")

    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, name FROM topics WHERE name = ?", (topic_name,)
        ).fetchone()
        if row is None:
            raise click.ClickException(f"topic '{topic_name}' not found")

        updates: list[str] = []
        params: list[object] = []
        if new_name is not None:
            updates.append("name = ?")
            params.append(new_name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if venue is not None:
            updates.append("target_venue = ?")
            params.append(venue)
        if deadline is not None:
            updates.append("deadline = ?")
            params.append(deadline)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        params.append(row["id"])
        conn.execute(f"UPDATE topics SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        updated_name = new_name or row["name"]
    finally:
        conn.close()

    _echo(
        ctx,
        {"topic": updated_name, "previous_name": topic_name, "updated": True},
        f"Topic '{topic_name}' updated",
    )


@topic.command("overview")
@click.argument("topic_name")
@click.pass_context
def topic_overview(ctx: click.Context, topic_name: str) -> None:
    """Show a summary of topic progress: papers, queue, tasks, orchestrator."""
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        papers = PaperPool(conn).list_papers(topic_id=topic_id)
        queue_items = []
        for paper_obj in papers:
            status_payload = _paper_status_payload(conn, paper_obj)
            queue_items.append(
                _paper_queue_entry(
                    topic_name, status_payload, conn=conn, topic_id=topic_id
                )
            )

        bucket_counts: dict[str, int] = {}
        for item in queue_items:
            bucket_counts[item["queue_bucket"]] = (
                bucket_counts.get(item["queue_bucket"], 0) + 1
            )

        tasks = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE topic_id = ? GROUP BY status",
            (topic_id,),
        ).fetchall()
        task_summary = {row["status"]: row["cnt"] for row in tasks}
        task_total = sum(task_summary.values())

        orchestrator_run = conn.execute(
            "SELECT id, current_stage, stage_status, mode, created_at FROM orchestrator_runs WHERE topic_id = ? ORDER BY created_at DESC LIMIT 1",
            (topic_id,),
        ).fetchone()
        orchestrator_info = dict(orchestrator_run) if orchestrator_run else None

        review_ready = _check_review_ready(conn, topic_id)
    finally:
        conn.close()

    payload = {
        "topic": topic_name,
        "topic_id": topic_id,
        "paper_count": len(papers),
        "queue_summary": {
            "by_bucket": bucket_counts,
            "actionable": sum(v for k, v in bucket_counts.items() if k != "ready"),
            "ready": bucket_counts.get("ready", 0),
        },
        "task_summary": {
            "total": task_total,
            "by_status": task_summary,
        },
        "orchestrator": orchestrator_info,
        "review_ready": review_ready,
    }

    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return

    click.echo(f"Topic: {topic_name}")
    click.echo(
        f"Papers: {len(papers)} total, {payload['queue_summary']['actionable']} actionable, {payload['queue_summary']['ready']} ready"
    )
    if bucket_counts:
        parts = [f"{k}={v}" for k, v in sorted(bucket_counts.items())]
        click.echo(f"  Queue: {', '.join(parts)}")
    click.echo(
        f"Tasks: {task_total} total ({', '.join(f'{k}={v}' for k, v in sorted(task_summary.items()))})"
        if task_summary
        else "Tasks: 0"
    )
    if orchestrator_info:
        click.echo(
            f"Orchestrator: stage={orchestrator_info['current_stage']} status={orchestrator_info['stage_status']} mode={orchestrator_info['mode']}"
        )
    else:
        click.echo("Orchestrator: no run")
    if payload["review_ready"]:
        click.echo("All tasks done. Ready for gate review.")


@topic.command("export")
@click.argument("name")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def topic_export(ctx: click.Context, name: str, output: str | None) -> None:
    """Export a topic's full state (papers, claims, tasks, orchestrator, provenance) as JSON."""
    from .core.paper_pool import PaperPool
    from .provenance import ProvenanceRecorder

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_row = conn.execute(
            "SELECT * FROM topics WHERE name = ?", (name,)
        ).fetchone()
        if topic_row is None:
            raise click.ClickException(f"topic '{name}' not found")
        topic_id = int(topic_row["id"])

        pool = PaperPool(conn)
        papers = [
            dataclasses.asdict(item) for item in pool.list_papers(topic_id=topic_id)
        ]
        tasks = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM tasks WHERE topic_id = ? ORDER BY created_at, id",
                (topic_id,),
            ).fetchall()
        ]

        orchestrator_runs = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM orchestrator_runs WHERE topic_id = ? ORDER BY created_at",
                (topic_id,),
            ).fetchall()
        ]

        orchestrator_artifacts = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM project_artifacts WHERE topic_id = ? ORDER BY created_at",
                (topic_id,),
            ).fetchall()
        ]

        provenance = [
            dataclasses.asdict(item)
            for item in ProvenanceRecorder(db).list_records(
                topic_id=topic_id, limit=10000
            )
        ]
    finally:
        conn.close()

    payload = {
        "topic": dict(topic_row),
        "papers": papers,
        "claims": [],
        "tasks": tasks,
        "orchestrator_runs": orchestrator_runs,
        "orchestrator_artifacts": orchestrator_artifacts,
        "provenance": provenance,
    }
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    if output:
        _write_text_output(output, serialized)
        if not ctx.obj.get("json"):
            click.echo(f"Exported topic '{name}' to {output}")
        return
    click.echo(serialized)


@main.group()
def search() -> None:
    """Manage search history."""


@search.command("log")
@click.option("--topic", "topic_name", default=None)
@click.option("--query", "-q", required=True)
@click.option("--provider", required=True, help="semantic-scholar|arxiv|dblp|refcheck")
@click.option("--result-count", type=int, default=0)
@click.option("--ingested-count", type=int, default=0)
@click.pass_context
def search_log(
    ctx: click.Context,
    topic_name: str | None,
    query: str,
    provider: str,
    result_count: int,
    ingested_count: int,
) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name) if topic_name else None
        conn.execute(
            "INSERT INTO search_runs (topic_id, query, provider, result_count, ingested_count) VALUES (?, ?, ?, ?, ?)",
            (topic_id, query, provider, result_count, ingested_count),
        )
        conn.commit()
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    _echo(
        ctx,
        {
            "id": run_id,
            "query": query,
            "provider": provider,
            "result_count": result_count,
            "ingested_count": ingested_count,
        },
        f"Search logged: '{query}' via {provider}",
    )


@search.command("list")
@click.option("--topic", "topic_name", default=None)
@click.option("--provider", default=None)
@click.option("--limit", type=int, default=20, show_default=True)
@click.pass_context
def search_list(
    ctx: click.Context, topic_name: str | None, provider: str | None, limit: int
) -> None:
    """List logged search runs."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        query = """
            SELECT s.*, t.name AS topic_name
            FROM search_runs s
            LEFT JOIN topics t ON s.topic_id = t.id
        """
        conditions: list[str] = []
        params: list[object] = []
        if topic_name:
            conditions.append("t.name = ?")
            params.append(topic_name)
        if provider:
            conditions.append("s.provider = ?")
            params.append(provider)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY s.created_at DESC, s.id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    payload = [dict(row) for row in rows]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    for row in payload:
        scope = row["topic_name"] or "global"
        click.echo(
            f"[{row['id']}] {row['provider']} [{scope}] {row['query']} -> {row['result_count']} results, {row['ingested_count']} ingested"
        )


@search.command("providers")
@click.pass_context
def search_providers(ctx: click.Context) -> None:
    from .paper_source_clients import available_provider_specs

    payload = [dataclasses.asdict(item) for item in available_provider_specs()]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    for item in payload:
        state = "enabled" if item["enabled"] else "disabled"
        click.echo(f"{item['name']}: {state} ({item['reason']})")


@search.command("papers")
@click.option("--query", "query_text", required=True)
@click.option("--topic", "topic_name", default=None)
@click.option("--limit", type=int, default=10, show_default=True)
@click.option("--year-from", type=int, default=None)
@click.option("--year-to", type=int, default=None)
@click.option(
    "--log-run",
    is_flag=True,
    default=False,
    help="Record this multi-source search in search_runs",
)
@click.pass_context
def search_papers(
    ctx: click.Context,
    query_text: str,
    topic_name: str | None,
    limit: int,
    year_from: int | None,
    year_to: int | None,
    log_run: bool,
) -> None:
    from .paper_source_clients import available_provider_specs, build_provider_suite
    from .paper_sources import PDFResolver, SearchAggregator, SearchQuery

    providers = build_provider_suite()
    if not providers:
        raise click.ClickException("no search providers are configured")

    aggregator = SearchAggregator(providers)
    resolver = PDFResolver()
    query = SearchQuery(
        query=query_text,
        topic=topic_name or "",
        year_from=year_from,
        year_to=year_to,
        limit=limit,
    )
    outcome = aggregator.search(query)
    results = outcome.results

    payload = {
        "query": query_text,
        "topic": topic_name or "",
        "provider_specs": [
            dataclasses.asdict(item) for item in available_provider_specs()
        ],
        "provider_errors": [
            dataclasses.asdict(item) for item in outcome.provider_errors
        ],
        "result_count": len(results),
        "results": [
            {
                "title": item.title,
                "authors": item.authors,
                "year": item.year,
                "venue": item.venue,
                "abstract": item.abstract,
                "doi": item.doi,
                "arxiv_id": item.arxiv_id,
                "s2_id": item.s2_id,
                "openalex_id": item.openalex_id,
                "openreview_id": item.openreview_id,
                "url": item.url,
                "provider": item.provider,
                "citation_count": item.citation_count,
                "pdf_candidates": [
                    dataclasses.asdict(candidate) for candidate in resolver.plan(item)
                ],
            }
            for item in results
        ],
    }

    if log_run:
        db = get_db(ctx)
        conn = db.connect()
        try:
            topic_id = _topic_id_or_exit(conn, topic_name) if topic_name else None
            conn.execute(
                "INSERT INTO search_runs (topic_id, query, provider, result_count, ingested_count) VALUES (?, ?, ?, ?, ?)",
                (topic_id, query_text, "multi-source", len(results), 0),
            )
            conn.commit()
        finally:
            conn.close()

    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return

    click.echo(f"query={query_text} results={len(results)}")
    for row in payload["results"]:
        best_pdf = (
            row["pdf_candidates"][0]["source_type"] if row["pdf_candidates"] else "none"
        )
        click.echo(f"- {row['title']} ({row['provider']}) pdf={best_pdf}")


@main.group()
def paper() -> None:
    """Manage papers."""


@paper.command("ingest")
@click.option("--arxiv-id", default=None)
@click.option("--doi", default=None)
@click.option("--s2-id", default=None)
@click.option("--title", default=None)
@click.option("--authors", default=None, help="Comma-separated author names")
@click.option("--year", type=int, default=None)
@click.option("--venue", default=None)
@click.option("--pdf-path", default=None, help="Path to local PDF")
@click.option("--url", default=None, help="URL to paper PDF or landing page")
@click.option("--topic", "topic_name", default=None)
@click.option(
    "--relevance", type=click.Choice(["high", "medium", "low"]), default="medium"
)
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def paper_ingest(
    ctx: click.Context,
    arxiv_id: str | None,
    doi: str | None,
    s2_id: str | None,
    title: str | None,
    authors: str | None,
    year: int | None,
    venue: str | None,
    pdf_path: str | None,
    url: str | None,
    topic_name: str | None,
    relevance: str,
    dry_run: bool,
) -> None:
    from .core.paper_pool import PaperPool

    if not any([arxiv_id, doi, s2_id, title, url, pdf_path]):
        raise click.ClickException(
            "provide at least one of --arxiv-id, --doi, --s2-id, --title, --url, --pdf-path"
        )

    paper_obj = Paper(
        title=title or "",
        authors=[item.strip() for item in authors.split(",")] if authors else [],
        year=year,
        venue=venue or "",
        url=url or "",
        pdf_path=pdf_path or "",
        doi=doi or "",
        arxiv_id=arxiv_id or "",
        s2_id=s2_id or "",
    )
    if dry_run:
        click.echo(
            json.dumps(
                {"action": "ingest", "paper": dataclasses.asdict(paper_obj)},
                ensure_ascii=False,
            )
        )
        return

    db = get_db(ctx)
    conn = db.connect()
    html_ingest_summary: dict[str, object] = {}
    try:
        topic_id = _topic_id_or_exit(conn, topic_name) if topic_name else None
        paper_id = PaperPool(conn).ingest(
            paper_obj, topic_id=topic_id, relevance=relevance
        )
        # URL-only ingest: fetch HTML so downstream claim_extract /
        # paper_summarize have text to read instead of silently landing
        # meta_only. See tool-gaps.md [2026-04-27].
        if (
            url
            and (url.startswith("http://") or url.startswith("https://"))
            and not pdf_path
        ):
            from .acquisition.html_ingest import fetch_html_as_markdown
            from .storage.models import PaperAnnotation

            page = fetch_html_as_markdown(url)
            if page.ok:
                PaperPool(conn).upsert_annotation(
                    PaperAnnotation(
                        paper_id=paper_id,
                        section="summary",
                        content=page.markdown,
                        source=f"html_ingest:{url}",
                        confidence=0.9,
                        extractor_version="html_ingest.v1",
                    )
                )
                conn.execute(
                    "UPDATE papers SET status = ?, abstract = COALESCE(NULLIF(abstract, ''), ?) WHERE id = ?",
                    ("text_only", page.markdown[:2000], paper_id),
                )
                if page.title and not (paper_obj.title or "").strip():
                    conn.execute(
                        "UPDATE papers SET title = ? WHERE id = ?",
                        (page.title, paper_id),
                    )
                    paper_obj.title = page.title
                conn.commit()
                html_ingest_summary = {
                    "fetched": True,
                    "chars": len(page.markdown),
                    "http_status": page.http_status,
                }
            else:
                html_ingest_summary = {
                    "fetched": False,
                    "reason": page.error or "no body",
                }
    finally:
        conn.close()
    _echo(
        ctx,
        {
            "paper_id": paper_id,
            "title": paper_obj.title,
            "status": "ingested",
            "html_ingest": html_ingest_summary,
        },
        f"Paper ingested: id={paper_id}, title='{paper_obj.title[:60]}'"
        + (
            f" [html: {html_ingest_summary.get('chars', 0)} chars]"
            if html_ingest_summary.get("fetched")
            else ""
        ),
    )


@paper.command("list")
@click.option("--topic", "topic_name", default=None)
@click.option("--status", default=None)
@click.pass_context
def paper_list(ctx: click.Context, topic_name: str | None, status: str | None) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name) if topic_name else None
        papers = PaperPool(conn).list_papers(topic_id=topic_id, status=status)
    finally:
        conn.close()
    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                [dataclasses.asdict(p) for p in papers], ensure_ascii=False, default=str
            )
        )
        return
    for paper_obj in papers:
        click.echo(
            f"[{paper_obj.id}] ({paper_obj.year or '?'}) [{paper_obj.status}] {paper_obj.title[:70]}"
        )


@paper.command("show")
@click.argument("paper_id", type=int)
@click.pass_context
def paper_show(ctx: click.Context, paper_id: int) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        annotations = pool.get_annotations(paper_id)
        notes = conn.execute(
            "SELECT * FROM topic_paper_notes WHERE paper_id = ? ORDER BY created_at DESC",
            (paper_id,),
        ).fetchall()
        artifacts = conn.execute(
            "SELECT artifact_type, path, metadata, created_at FROM paper_artifacts WHERE paper_id = ? ORDER BY created_at DESC, id DESC",
            (paper_id,),
        ).fetchall()
    finally:
        conn.close()

    result = {
        "paper": dataclasses.asdict(paper_obj),
        "annotations": [dataclasses.asdict(item) for item in annotations],
        "topic_notes": [dict(row) for row in notes],
        "artifacts": [dict(row) for row in artifacts],
    }
    if ctx.obj.get("json"):
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
        return
    click.echo(f"# {paper_obj.title}")
    click.echo(f"Authors: {', '.join(paper_obj.authors)}")
    click.echo(f"Year: {paper_obj.year}  Venue: {paper_obj.venue}")
    click.echo(f"Status: {paper_obj.status}")
    click.echo(f"Annotations: {len(annotations)}")
    click.echo(f"Artifacts: {len(artifacts)}")
    for item in annotations:
        preview = item.content[:120].replace("\n", " ")
        click.echo(f"- {item.section}: {preview}")


@paper.command("update")
@click.argument("paper_id", type=int)
@click.option("--title", default=None)
@click.option("--year", type=int, default=None)
@click.option("--venue", default=None)
@click.option("--pdf-path", default=None)
@click.option("--url", default=None)
@click.option("--status", "new_status", default=None)
@click.pass_context
def paper_update(
    ctx: click.Context,
    paper_id: int,
    title: str | None,
    year: int | None,
    venue: str | None,
    pdf_path: str | None,
    url: str | None,
    new_status: str | None,
) -> None:
    """Update fields on an existing paper."""
    updates: list[str] = []
    params: list[object] = []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if year is not None:
        updates.append("year = ?")
        params.append(year)
    if venue is not None:
        updates.append("venue = ?")
        params.append(venue)
    if pdf_path is not None:
        updates.append("pdf_path = ?")
        params.append(pdf_path)
    if url is not None:
        updates.append("url = ?")
        params.append(url)
    if new_status is not None:
        updates.append("status = ?")
        params.append(new_status)
    if not updates:
        raise click.ClickException("nothing to update; provide at least one option")

    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise click.ClickException(f"paper {paper_id} not found")
        params.append(paper_id)
        conn.execute(f"UPDATE papers SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()
    _echo(ctx, {"paper_id": paper_id, "updated": True}, f"Paper {paper_id} updated")


@paper.command("enrich")
@click.argument("paper_id", type=int, required=False)
@click.option("--topic", "topic_name", default=None, help="Enrich all papers in topic")
@click.option(
    "--with-s2/--no-s2",
    default=True,
    help="Call Semantic Scholar API for venue/citation/abstract (default: on)",
)
@click.option(
    "--limit", "max_papers", type=int, default=None, help="Max papers to enrich"
)
@click.option(
    "--missing",
    "missing_fields",
    default=None,
    help="Comma-separated fields to target, e.g. venue,citation_count",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Preview changes without applying"
)
@click.pass_context
def paper_enrich(
    ctx: click.Context,
    paper_id: int | None,
    topic_name: str | None,
    with_s2: bool,
    max_papers: int | None,
    missing_fields: str | None,
    dry_run: bool,
) -> None:
    """Enrich paper metadata via Semantic Scholar API.

    Fills missing venue, citation_count, abstract, authors, affiliations,
    and cross-links (DOI, arXiv ID, S2 ID).  Also builds arXiv URL when absent.

    Examples:
        rh paper enrich 5                         # Enrich paper 5 via S2
        rh paper enrich --topic my-topic          # Enrich all in topic
        rh paper enrich --topic my-topic --missing venue,citation_count
        rh paper enrich --topic my-topic --limit 50 --dry-run
        rh paper enrich --no-s2 --topic my-topic  # URL-only (legacy mode)
    """
    import time

    from .core.paper_pool import PaperPool

    target_fields = set()
    if missing_fields:
        target_fields = {f.strip() for f in missing_fields.split(",") if f.strip()}

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        papers_raw: list = []

        if paper_id is not None:
            p = pool.get(paper_id)
            if p is None:
                raise click.ClickException(f"paper {paper_id} not found")
            papers_raw = [p]
        elif topic_name:
            topic_id = _topic_id_or_exit(conn, topic_name)
            papers_raw = pool.list_papers(topic_id=topic_id)
        else:
            raise click.ClickException("provide either paper_id or --topic")

        candidates: list[tuple[int, str, str | None]] = []
        for p in papers_raw:
            pid = p.id or 0
            title = p.title or ""
            has_id = bool(p.arxiv_id or p.doi or getattr(p, "s2_id", None))
            if not has_id:
                continue
            if target_fields:
                row = conn.execute(
                    "SELECT * FROM papers WHERE id = ?", (pid,)
                ).fetchone()
                if row is None:
                    continue
                needs = False
                for f in target_fields:
                    val = row[f] if f in row.keys() else None
                    if not val or (
                        f == "venue"
                        and str(val).strip().lower()
                        in ("", "arxiv", "arxiv.org", "arxiv preprint")
                    ):
                        needs = True
                        break
                if not needs:
                    continue
            candidates.append((pid, title, p.arxiv_id))
            if max_papers and len(candidates) >= max_papers:
                break

        updated: list[dict] = []
        skipped: list[dict] = []
        s2_enriched = 0

        for pid, title, arxiv_id in candidates:
            result_info: dict = {"paper_id": pid, "title": title[:50]}

            if with_s2:
                if dry_run:
                    result_info["action"] = "would_enrich_s2"
                    updated.append(result_info)
                    continue
                try:
                    s2_result = pool.enrich_metadata(pid)
                    if s2_result and "error" not in s2_result:
                        result_info["s2_fields"] = list(s2_result.keys())
                        s2_enriched += 1
                        updated.append(result_info)
                    else:
                        err = (
                            s2_result.get("error", "unknown") if s2_result else "empty"
                        )
                        skipped.append({**result_info, "reason": f"s2: {err}"})
                    time.sleep(1.05)
                except Exception as exc:
                    skipped.append({**result_info, "reason": str(exc)[:80]})
            else:
                if not arxiv_id:
                    skipped.append({**result_info, "reason": "no arxiv_id"})
                    continue
                arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
                if dry_run:
                    result_info.update(
                        {
                            "arxiv_id": arxiv_id,
                            "url": arxiv_url,
                            "action": "would_update",
                        }
                    )
                    updated.append(result_info)
                else:
                    conn.execute(
                        "UPDATE papers SET url = ? WHERE id = ?", (arxiv_url, pid)
                    )
                    result_info.update({"arxiv_id": arxiv_id, "url": arxiv_url})
                    updated.append(result_info)

        if not dry_run:
            conn.commit()

        payload = {
            "dry_run": dry_run,
            "processed": len(candidates),
            "updated": len(updated),
            "s2_enriched": s2_enriched,
            "skipped": len(skipped),
            "updates": updated,
            "skip_reasons": skipped,
        }

        if ctx.obj.get("json"):
            click.echo(json.dumps(payload, ensure_ascii=False))
            return

        action_word = "would enrich" if dry_run else "enriched"
        click.echo(
            f"Paper enrichment: {len(updated)} {action_word} ({s2_enriched} via S2), {len(skipped)} skipped"
        )
        for u in updated:
            fields = u.get("s2_fields", [])
            label = ", ".join(fields) if fields else u.get("url", "url-only")
            click.echo(f"  [{u['paper_id']}] {u['title'][:45]}... -> {label}")
        for s in skipped:
            click.echo(f"  [{s['paper_id']}] skipped: {s['reason']}")
    finally:
        conn.close()


@paper.command("backfill-metadata")
@click.option(
    "--missing",
    "missing_fields",
    default="venue,citation_count",
    help="Comma-separated fields to target",
)
@click.option("--limit", "max_papers", type=int, default=100, help="Max papers per run")
@click.option("--dry-run", is_flag=True, default=False, help="Preview only")
@click.pass_context
def paper_backfill_metadata(
    ctx: click.Context,
    missing_fields: str,
    max_papers: int,
    dry_run: bool,
) -> None:
    """Batch-enrich papers missing key metadata across ALL topics.

    Scans the entire pool for papers missing the specified fields and calls
    Semantic Scholar to fill them. Rate-limited to ~1 req/sec.

    Examples:
        rh paper backfill-metadata                         # default: venue + citation_count, limit 100
        rh paper backfill-metadata --missing venue --limit 50
        rh paper backfill-metadata --dry-run
    """
    import time

    from .core.paper_pool import PaperPool

    fields = [f.strip() for f in missing_fields.split(",") if f.strip()]
    if not fields:
        raise click.ClickException("--missing must list at least one field")

    venue_placeholders = ("", "arxiv", "arxiv.org", "arxiv preprint")

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        rows = conn.execute(
            "SELECT id, title, arxiv_id, doi, s2_id, venue, citation_count FROM papers ORDER BY id DESC"
        ).fetchall()

        candidates: list[tuple[int, str]] = []
        for row in rows:
            has_id = bool(
                (row["arxiv_id"] or "").strip()
                or (row["doi"] or "").strip()
                or (row["s2_id"] or "").strip()
            )
            if not has_id:
                continue
            for f in fields:
                val = row[f] if f in row.keys() else None
                if f == "venue" and (
                    not val or str(val).strip().lower() in venue_placeholders
                ):
                    candidates.append((row["id"], (row["title"] or "")[:50]))
                    break
                elif f != "venue" and (val is None or val == 0):
                    candidates.append((row["id"], (row["title"] or "")[:50]))
                    break
            if len(candidates) >= max_papers:
                break

        click.echo(
            f"Found {len(candidates)} papers missing {', '.join(fields)} (limit {max_papers})"
        )
        if dry_run:
            for pid, title in candidates[:20]:
                click.echo(f"  [{pid}] {title}")
            if len(candidates) > 20:
                click.echo(f"  ... and {len(candidates) - 20} more")
            return

        enriched = 0
        failed = 0
        for i, (pid, title) in enumerate(candidates):
            try:
                result = pool.enrich_metadata(pid)
                if result and "error" not in result:
                    enriched += 1
                    if (i + 1) % 10 == 0:
                        click.echo(
                            f"  [{i + 1}/{len(candidates)}] enriched {enriched} so far..."
                        )
                else:
                    failed += 1
                time.sleep(1.05)
            except Exception as exc:
                failed += 1
                logger.debug("Backfill failed for paper %d: %s", pid, exc)

        click.echo(
            f"Done: {enriched} enriched, {failed} failed out of {len(candidates)}"
        )
    finally:
        conn.close()


@paper.command("link")
@click.argument("paper_id", type=int)
@click.option("--topic", "topic_name", required=True)
@click.option(
    "--relevance", type=click.Choice(["high", "medium", "low"]), default="medium"
)
@click.pass_context
def paper_link(
    ctx: click.Context, paper_id: int, topic_name: str, relevance: str
) -> None:
    """Link a paper to a topic (or update relevance if already linked)."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise click.ClickException(f"paper {paper_id} not found")
        topic_id = _topic_id_or_exit(conn, topic_name)
        conn.execute(
            """
            INSERT INTO paper_topics (paper_id, topic_id, relevance)
            VALUES (?, ?, ?)
            ON CONFLICT(paper_id, topic_id) DO UPDATE SET relevance = excluded.relevance
            """,
            (paper_id, topic_id, relevance),
        )
        conn.commit()
    finally:
        conn.close()
    _echo(
        ctx,
        {
            "paper_id": paper_id,
            "topic": topic_name,
            "topic_id": topic_id,
            "relevance": relevance,
            "linked": True,
        },
        f"Paper {paper_id} linked to topic '{topic_name}' (relevance={relevance})",
    )


@paper.command("status")
@click.argument("paper_id", type=int)
@click.pass_context
def paper_status(ctx: click.Context, paper_id: int) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        payload = _paper_status_payload(conn, paper_obj)
    finally:
        conn.close()

    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    paper = payload["paper"]
    linked_topics = payload["linked_topics"]
    note_count = payload["topic_note_status"]["count"]
    completed_sections = payload["annotation_status"]["completed_sections"]
    missing_sections = payload["annotation_status"]["missing_sections"]
    artifact_types = payload["artifact_status"]["types"]
    click.echo(f"[{paper['id']}] {paper['title']}")
    click.echo(
        f"status={paper['status']} pdf={'yes' if paper['pdf_path'] else 'no'} topics={len(linked_topics)} notes={note_count}"
    )
    click.echo(
        f"annotations: {len(completed_sections)}/{payload['annotation_status']['total_expected']} complete"
    )
    if missing_sections:
        click.echo(f"missing: {', '.join(missing_sections)}")
    if artifact_types:
        click.echo(f"artifacts: {', '.join(artifact_types)}")


@paper.command("queue")
@click.option("--topic", "topic_name", required=True)
@click.option("--limit", type=int, default=None)
@click.option("--only-actionable", is_flag=True, default=False)
@click.pass_context
def paper_queue(
    ctx: click.Context, topic_name: str, limit: int | None, only_actionable: bool
) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        papers = PaperPool(conn).list_papers(topic_id=topic_id)
        queue_items = []
        for paper_obj in papers:
            status_payload = _paper_status_payload(conn, paper_obj)
            queue_items.append(
                _paper_queue_entry(
                    topic_name, status_payload, conn=conn, topic_id=topic_id
                )
            )
    finally:
        conn.close()

    queue_items.sort(
        key=lambda item: (
            item["priority_rank"],
            -len(item["missing_sections"]),
            item["title"].lower(),
            item["paper_id"],
        )
    )
    if only_actionable:
        queue_items = [item for item in queue_items if item["queue_bucket"] != "ready"]
    if limit is not None:
        queue_items = queue_items[:limit]

    summary = {
        "total_papers": len(queue_items),
        "actionable_papers": sum(
            1 for item in queue_items if item["queue_bucket"] != "ready"
        ),
        "by_bucket": {
            bucket: sum(1 for item in queue_items if item["queue_bucket"] == bucket)
            for bucket in [
                "missing_pdf",
                "stale_annotations",
                "missing_sections",
                "missing_card",
                "missing_topic_note",
                "ready",
            ]
        },
    }
    payload = {
        "topic": topic_name,
        "summary": summary,
        "papers": queue_items,
    }
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    click.echo(f"Topic queue: {topic_name}")
    click.echo(
        f"papers={summary['total_papers']} actionable={summary['actionable_papers']}"
    )
    for item in queue_items:
        click.echo(f"[{item['paper_id']}] [{item['queue_bucket']}] {item['title']}")
        click.echo(f"actions: {', '.join(item['next_actions'])}")
        if item["missing_sections"]:
            click.echo(f"missing: {', '.join(item['missing_sections'])}")


@paper.command("annotate")
@click.argument("paper_id", type=int)
@click.option("--pdf", "pdf_path", default=None, help="Override PDF path for this run")
@click.option("--section", "sections", multiple=True, help="Section(s) to extract")
@click.pass_context
def paper_annotate(
    ctx: click.Context, paper_id: int, pdf_path: str | None, sections: tuple[str, ...]
) -> None:
    from .core.paper_pool import PaperPool
    from .integrations.paperindex_adapter import PaperIndexAdapter

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        resolved_pdf = pdf_path or paper_obj.pdf_path
        if not resolved_pdf:
            raise click.ClickException(
                "paper has no pdf_path; provide --pdf or ingest with --pdf-path"
            )
        adapter = PaperIndexAdapter(
            conn, artifacts_root=db.db_path.parent / "artifacts"
        )
        result = adapter.annotate_paper(paper_id, resolved_pdf, list(sections) or None)
    finally:
        conn.close()
    _echo(
        ctx,
        result,
        f"Paper {paper_id} annotated with {result['annotation_count']} sections",
    )


@paper.command("annotations")
@click.argument("paper_id", type=int)
@click.option("--section", "section_name", default=None)
@click.pass_context
def paper_annotations(
    ctx: click.Context, paper_id: int, section_name: str | None
) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        annotations = pool.get_annotations(paper_id)
    finally:
        conn.close()
    if section_name:
        annotations = [item for item in annotations if item.section == section_name]
    payload = [dataclasses.asdict(item) for item in annotations]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    for item in annotations:
        click.echo(f"## {item.section} [{item.source}] ({item.confidence})")
        click.echo(item.content)
        click.echo("")


@paper.group("note")
def paper_note() -> None:
    """Manage topic-specific paper notes."""


@paper_note.command("set")
@click.option("--paper-id", type=int, required=True)
@click.option("--topic", "topic_name", required=True)
@click.option("--type", "note_type", required=True, type=click.Choice(NOTE_TYPES))
@click.option("--content", required=True)
@click.option("--source", default="")
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def paper_note_set(
    ctx: click.Context,
    paper_id: int,
    topic_name: str,
    note_type: str,
    content: str,
    source: str,
    dry_run: bool,
) -> None:
    payload = {
        "paper_id": paper_id,
        "topic": topic_name,
        "note_type": note_type,
        "content": content,
        "source": source,
    }
    if dry_run:
        _echo(
            ctx,
            {"action": "paper.note.set", **payload},
            f"Dry run: note for paper {paper_id} under topic '{topic_name}'",
        )
        return

    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        try:
            note_id = pool.upsert_topic_note(
                TopicPaperNote(
                    paper_id=paper_id,
                    topic_id=topic_id,
                    note_type=note_type,
                    content=content,
                    source=source,
                )
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    _echo(
        ctx,
        {"id": note_id, "topic_id": topic_id, **payload},
        f"Topic note saved: id={note_id}",
    )


@paper_note.command("draft")
@click.option("--paper-id", type=int, required=True)
@click.option("--topic", "topic_name", required=True)
@click.option("--type", "note_type", required=True, type=click.Choice(NOTE_TYPES))
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Save the drafted note into topic_paper_notes",
)
@click.option("--source", default="paperindex:card-draft")
@click.pass_context
def paper_note_draft(
    ctx: click.Context,
    paper_id: int,
    topic_name: str,
    note_type: str,
    save: bool,
    source: str,
) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        topic_row = conn.execute(
            "SELECT relevance FROM paper_topics WHERE paper_id = ? AND topic_id = ?",
            (paper_id, topic_id),
        ).fetchone()
        if topic_row is None:
            raise click.ClickException(
                f"paper {paper_id} is not linked to topic {topic_id}"
            )
        artifact = _paper_artifact_or_exit(conn, paper_id, "paperindex_card")
        metadata = _decode_artifact_metadata(artifact["metadata"])
        card_obj = _load_json_artifact_or_exit(artifact["path"], "paper card")
        if not isinstance(card_obj, dict):
            raise click.ClickException(
                f"paper card artifact at {artifact['path']} must be a JSON object"
            )
        content = _draft_topic_note_from_card(
            paper_obj=paper_obj,
            topic_name=topic_name,
            note_type=note_type,
            card=card_obj,
            topic_relevance=topic_row["relevance"] or "",
        )
        payload = {
            "paper_id": paper_id,
            "topic": topic_name,
            "note_type": note_type,
            "source": source,
            "saved": save,
            "content": content,
            "card_path": artifact["path"],
            "card_metadata": metadata,
        }
        if save:
            note_id = pool.upsert_topic_note(
                TopicPaperNote(
                    paper_id=paper_id,
                    topic_id=topic_id,
                    note_type=note_type,
                    content=content,
                    source=source,
                )
            )
            payload["id"] = note_id
            payload["topic_id"] = topic_id
    finally:
        conn.close()

    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    if save:
        click.echo(f"Topic note drafted and saved: id={payload['id']}")
        click.echo("")
    click.echo(content)


@paper_note.command("list")
@click.option("--paper-id", type=int, required=True)
@click.option("--topic", "topic_name", default=None)
@click.option("--type", "note_type", default=None, type=click.Choice(NOTE_TYPES))
@click.pass_context
def paper_note_list(
    ctx: click.Context, paper_id: int, topic_name: str | None, note_type: str | None
) -> None:
    from .core.paper_pool import PaperPool

    db = get_db(ctx)
    conn = db.connect()
    try:
        pool = PaperPool(conn)
        paper_obj = pool.get(paper_id)
        if paper_obj is None:
            raise click.ClickException(f"paper {paper_id} not found")
        topic_id = _topic_id_or_exit(conn, topic_name) if topic_name else None
        notes = pool.get_topic_notes(paper_id, topic_id=topic_id, note_type=note_type)
    finally:
        conn.close()
    payload = [dataclasses.asdict(item) for item in notes]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    for item in notes:
        click.echo(f"[{item.note_type}] topic={item.topic_id} source={item.source}")
        click.echo(item.content)
        click.echo("")


@paper.command("artifacts")
@click.argument("paper_id", type=int)
@click.pass_context
def paper_artifacts(ctx: click.Context, paper_id: int) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise click.ClickException(f"paper {paper_id} not found")
        artifacts = conn.execute(
            "SELECT artifact_type, path, metadata, created_at FROM paper_artifacts WHERE paper_id = ? ORDER BY created_at DESC, id DESC",
            (paper_id,),
        ).fetchall()
    finally:
        conn.close()
    payload = [dict(item) for item in artifacts]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    for item in artifacts:
        click.echo(f"[{item['artifact_type']}] {item['path']}")


@paper.command("card")
@click.argument("paper_id", type=int)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Export the card JSON to a file",
)
@click.pass_context
def paper_card(ctx: click.Context, paper_id: int, output: str | None) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise click.ClickException(f"paper {paper_id} not found")
        artifact = _paper_artifact_or_exit(conn, paper_id, "paperindex_card")
        metadata = _decode_artifact_metadata(artifact["metadata"])
        card = _load_json_artifact_or_exit(artifact["path"], "paper card")
    finally:
        conn.close()

    output_path: Path | None = None
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    payload = {
        "paper_id": paper_id,
        "artifact_type": artifact["artifact_type"],
        "path": artifact["path"],
        "created_at": artifact["created_at"],
        "metadata": metadata,
        "card": card,
    }
    if output_path is not None:
        payload["exported_to"] = str(output_path)

    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    if output_path is not None:
        click.echo(f"Exported paper card for paper {paper_id} to {output_path}")
        return
    click.echo(json.dumps(card, ensure_ascii=False, indent=2))


@paper.command("acquire")
@click.argument("topic_id", type=int)
@click.option("--download-dir", default=None, help="Directory to save downloaded PDFs")
@click.option(
    "--artifacts-root", default=None, help="Directory for paperindex artifacts"
)
@click.pass_context
def paper_acquire(
    ctx: click.Context,
    topic_id: int,
    download_dir: str | None,
    artifacts_root: str | None,
) -> None:
    """Download PDFs and build paperindex annotations for a topic."""
    from .acquisition.pipeline import acquire_papers

    db = get_db(ctx)
    report = acquire_papers(
        db, topic_id, download_dir=download_dir, artifacts_root=artifacts_root
    )

    if ctx.obj.get("json"):
        click.echo(json.dumps(report.to_dict(), ensure_ascii=False, default=str))
        return

    click.echo(f"Acquisition complete for topic {topic_id}:")
    click.echo(
        f"  Total: {report.total_papers}, Downloaded: {report.downloaded}, "
        f"Annotated: {report.annotated}, Needs manual: {report.needs_manual}, "
        f"Failed: {report.failed}"
    )
    if report.manual_list:
        click.echo(f"\n  {len(report.manual_list)} papers need manual download.")
        click.echo("  See .research-harness/manual_downloads/pending_manual.json")


@paper.command("ingest-manual")
@click.option(
    "--manual-dir", default=None, help="Directory containing manually downloaded PDFs"
)
@click.option(
    "--artifacts-root", default=None, help="Directory for paperindex artifacts"
)
@click.pass_context
def paper_ingest_manual(
    ctx: click.Context, manual_dir: str | None, artifacts_root: str | None
) -> None:
    """Ingest manually downloaded PDFs from the manual_downloads directory."""
    from .acquisition.pipeline import ingest_manual_downloads

    db = get_db(ctx)
    results = ingest_manual_downloads(
        db, manual_dir=manual_dir, artifacts_root=artifacts_root
    )

    if ctx.obj.get("json"):
        click.echo(json.dumps(results, ensure_ascii=False, default=str))
        return

    if not results:
        click.echo("No PDF files found in manual downloads directory.")
        return

    for r in results:
        status = r["status"]
        name = r.get("file", "")
        click.echo(f"  {name}: {status}")
    annotated = sum(1 for r in results if r["status"] == "annotated")
    click.echo(f"\nProcessed {len(results)} files, {annotated} annotated.")


@paper.command("resolve-pdfs")
@click.option("--topic", default=None, help="Topic name or ID to scope resolution")
@click.option("--dry-run", is_flag=True, help="Report matches without writing to DB")
@click.pass_context
def paper_resolve_pdfs(ctx: click.Context, topic: str | None, dry_run: bool) -> None:
    """Discover existing PDFs on disk and link them to papers in the DB."""
    from .acquisition.pdf_resolver import backfill_pdf_paths

    db = get_db(ctx)
    topic_id = None
    if topic:
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT id FROM topics WHERE name = ? OR id = CAST(? AS INTEGER)",
                (topic, topic),
            ).fetchone()
            if row:
                topic_id = row["id"]
            else:
                click.echo(f"Topic '{topic}' not found.", err=True)
                return
        finally:
            conn.close()

    stats = backfill_pdf_paths(db, topic_id=topic_id, dry_run=dry_run)

    if ctx.obj.get("json"):
        click.echo(json.dumps(stats.to_dict(), ensure_ascii=False, default=str))
        return

    mode = " (DRY RUN)" if dry_run else ""
    click.echo(f"PDF Resolution{mode}:")
    click.echo(f"  Missing pdf_path: {stats.total_missing}")
    click.echo(f"  Matched:          {stats.matched}")
    click.echo(f"  Unmatched:        {stats.unmatched}")
    if stats.errors:
        click.echo(f"  Errors:           {stats.errors}")

    if stats.unmatched_papers:
        click.echo(f"\nUnmatched papers ({len(stats.unmatched_papers)}):")
        for p in stats.unmatched_papers[:20]:
            click.echo(
                f"  [{p['paper_id']:>3}] {p['arxiv_id'] or p['doi'] or '?':20s} {p['title']}"
            )
        if len(stats.unmatched_papers) > 20:
            click.echo(f"  ... and {len(stats.unmatched_papers) - 20} more")


@paper.command("move")
@click.argument("paper_ids", nargs=-1, type=int, required=True)
@click.option(
    "--from-topic", "from_topic", required=True, help="Source topic name or ID"
)
@click.option("--to-topic", "to_topic", required=True, help="Target topic name or ID")
@click.option(
    "--relevance",
    type=click.Choice(["high", "medium", "low"]),
    default=None,
    help="Override relevance in target",
)
@click.pass_context
def paper_move(
    ctx: click.Context,
    paper_ids: tuple[int, ...],
    from_topic: str,
    to_topic: str,
    relevance: str | None,
) -> None:
    """Move papers from one topic to another."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        # Resolve topic IDs
        from_row = conn.execute(
            "SELECT id FROM topics WHERE name = ? OR id = CAST(? AS INTEGER)",
            (from_topic, from_topic),
        ).fetchone()
        to_row = conn.execute(
            "SELECT id FROM topics WHERE name = ? OR id = CAST(? AS INTEGER)",
            (to_topic, to_topic),
        ).fetchone()
        if not from_row:
            raise click.ClickException(f"Source topic '{from_topic}' not found")
        if not to_row:
            raise click.ClickException(f"Target topic '{to_topic}' not found")
        from_id = from_row["id"]
        to_id = to_row["id"]

        moved = 0
        for pid in paper_ids:
            # Check paper exists in source topic
            link = conn.execute(
                "SELECT relevance FROM paper_topics WHERE paper_id = ? AND topic_id = ?",
                (pid, from_id),
            ).fetchone()
            if not link:
                click.echo(f"  Paper {pid}: not in source topic, skipping", err=True)
                continue

            rel = relevance or link["relevance"] or "medium"
            # Remove from source
            conn.execute(
                "DELETE FROM paper_topics WHERE paper_id = ? AND topic_id = ?",
                (pid, from_id),
            )
            # Add to target (or update if already there)
            conn.execute(
                "INSERT OR REPLACE INTO paper_topics (paper_id, topic_id, relevance) VALUES (?, ?, ?)",
                (pid, to_id, rel),
            )
            moved += 1
        conn.commit()
    finally:
        conn.close()
    _echo(
        ctx,
        {"moved": moved, "from_topic": from_topic, "to_topic": to_topic},
        f"Moved {moved}/{len(paper_ids)} papers from '{from_topic}' to '{to_topic}'",
    )


@paper.command("bulk-update")
@click.argument("paper_ids", nargs=-1, type=int, required=True)
@click.option(
    "--relevance", type=click.Choice(["high", "medium", "low"]), required=True
)
@click.option(
    "--topic", "topic_name", default=None, help="Topic context for relevance update"
)
@click.pass_context
def paper_bulk_update(
    ctx: click.Context,
    paper_ids: tuple[int, ...],
    relevance: str,
    topic_name: str | None,
) -> None:
    """Bulk update relevance for multiple papers."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = None
        if topic_name:
            row = conn.execute(
                "SELECT id FROM topics WHERE name = ? OR id = CAST(? AS INTEGER)",
                (topic_name, topic_name),
            ).fetchone()
            if not row:
                raise click.ClickException(f"Topic '{topic_name}' not found")
            topic_id = row["id"]

        updated = 0
        for pid in paper_ids:
            if topic_id is not None:
                result = conn.execute(
                    "UPDATE paper_topics SET relevance = ? WHERE paper_id = ? AND topic_id = ?",
                    (relevance, pid, topic_id),
                )
            else:
                result = conn.execute(
                    "UPDATE paper_topics SET relevance = ? WHERE paper_id = ?",
                    (relevance, pid),
                )
            if result.rowcount > 0:
                updated += 1
        conn.commit()
    finally:
        conn.close()
    _echo(
        ctx,
        {"updated": updated, "relevance": relevance},
        f"Updated {updated}/{len(paper_ids)} papers to relevance='{relevance}'",
    )


@topic.command("stats")
@click.argument("topic_name")
@click.pass_context
def topic_stats(ctx: click.Context, topic_name: str) -> None:
    """Show distribution statistics for a topic (venue, year, status, relevance)."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, name FROM topics WHERE name = ? OR id = CAST(? AS INTEGER)",
            (topic_name, topic_name),
        ).fetchone()
        if not row:
            raise click.ClickException(f"Topic '{topic_name}' not found")
        tid = row["id"]
        tname = row["name"]

        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM paper_topics WHERE topic_id = ?",
            (tid,),
        ).fetchone()["cnt"]

        venue_dist = conn.execute(
            """
            SELECT COALESCE(p.venue, '(unknown)') as venue, COUNT(*) as cnt
            FROM papers p JOIN paper_topics pt ON pt.paper_id = p.id
            WHERE pt.topic_id = ?
            GROUP BY venue ORDER BY cnt DESC LIMIT 15
            """,
            (tid,),
        ).fetchall()

        year_dist = conn.execute(
            """
            SELECT COALESCE(p.year, 0) as year, COUNT(*) as cnt
            FROM papers p JOIN paper_topics pt ON pt.paper_id = p.id
            WHERE pt.topic_id = ?
            GROUP BY year ORDER BY year DESC
            """,
            (tid,),
        ).fetchall()

        status_dist = conn.execute(
            """
            SELECT COALESCE(p.status, 'unknown') as status, COUNT(*) as cnt
            FROM papers p JOIN paper_topics pt ON pt.paper_id = p.id
            WHERE pt.topic_id = ?
            GROUP BY status ORDER BY cnt DESC
            """,
            (tid,),
        ).fetchall()

        relevance_dist = conn.execute(
            """
            SELECT COALESCE(pt.relevance, 'unset') as relevance, COUNT(*) as cnt
            FROM paper_topics pt
            WHERE pt.topic_id = ?
            GROUP BY relevance ORDER BY cnt DESC
            """,
            (tid,),
        ).fetchall()

        survey_count = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM topic_paper_notes
            WHERE topic_id = ? AND note_type = 'survey_flag'
            """,
            (tid,),
        ).fetchone()["cnt"]

    finally:
        conn.close()

    result = {
        "topic": tname,
        "total_papers": total,
        "surveys": survey_count,
        "venue": {r["venue"]: r["cnt"] for r in venue_dist},
        "year": {r["year"]: r["cnt"] for r in year_dist},
        "status": {r["status"]: r["cnt"] for r in status_dist},
        "relevance": {r["relevance"]: r["cnt"] for r in relevance_dist},
    }

    if ctx.obj.get("json"):
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
        return

    click.echo(f"Topic: {tname} ({total} papers, {survey_count} surveys)")
    click.echo()

    click.echo("Venue distribution:")
    for r in venue_dist:
        click.echo(f"  {r['venue']:40s} {r['cnt']:>4d}")
    click.echo()

    click.echo("Year distribution:")
    for r in year_dist:
        yr = r["year"] if r["year"] else "unknown"
        click.echo(f"  {yr!s:10s} {r['cnt']:>4d}")
    click.echo()

    click.echo("Status distribution:")
    for r in status_dist:
        click.echo(f"  {r['status']:15s} {r['cnt']:>4d}")
    click.echo()

    click.echo("Relevance distribution:")
    for r in relevance_dist:
        click.echo(f"  {r['relevance']:10s} {r['cnt']:>4d}")


@topic.command("get-contributions")
@click.argument("topic_name")
@click.pass_context
def topic_get_contributions(ctx: click.Context, topic_name: str) -> None:
    """Read the contributions text for a topic."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, contributions FROM topics WHERE name = ?", (topic_name,)
        ).fetchone()
        if row is None:
            raise click.ClickException(f"topic '{topic_name}' not found")
    finally:
        conn.close()
    contributions = row["contributions"] or ""
    _echo(
        ctx,
        {"topic": topic_name, "contributions": contributions},
        contributions if contributions else "(no contributions set)",
    )


@topic.command("set-contributions")
@click.argument("topic_name")
@click.argument("text")
@click.pass_context
def topic_set_contributions(ctx: click.Context, topic_name: str, text: str) -> None:
    """Write the contributions text for a topic."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id FROM topics WHERE name = ?", (topic_name,)
        ).fetchone()
        if row is None:
            raise click.ClickException(f"topic '{topic_name}' not found")
        conn.execute(
            "UPDATE topics SET contributions = ? WHERE id = ?", (text, row["id"])
        )
        conn.commit()
    finally:
        conn.close()
    _echo(
        ctx,
        {"topic": topic_name, "contributions": text, "updated": True},
        f"Contributions updated for topic '{topic_name}'",
    )


@main.group()
def bib() -> None:
    """Manage BibTeX entries."""


@bib.command("set")
@click.option("--paper-id", type=int, required=True)
@click.option("--key", "bibtex_key", required=True)
@click.option("--bibtex", required=True)
@click.option("--source", default="")
@click.option("--verified-by", default="")
@click.pass_context
def bib_set(
    ctx: click.Context,
    paper_id: int,
    bibtex_key: str,
    bibtex: str,
    source: str,
    verified_by: str,
) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise click.ClickException(f"paper {paper_id} not found")
        conn.execute(
            """
            INSERT INTO bib_entries (paper_id, bibtex_key, bibtex, source, verified_by, verified_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (paper_id)
            DO UPDATE SET
                bibtex_key = excluded.bibtex_key,
                bibtex = excluded.bibtex,
                source = excluded.source,
                verified_by = excluded.verified_by,
                verified_at = datetime('now')
            """,
            (paper_id, bibtex_key, bibtex, source, verified_by),
        )
        conn.commit()
        entry = conn.execute(
            "SELECT * FROM bib_entries WHERE paper_id = ?", (paper_id,)
        ).fetchone()
    finally:
        conn.close()
    payload = dict(entry)
    _echo(ctx, payload, f"BibTeX set for paper {paper_id}")


@bib.command("show")
@click.argument("paper_id", type=int)
@click.pass_context
def bib_show(ctx: click.Context, paper_id: int) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        entry = conn.execute(
            "SELECT * FROM bib_entries WHERE paper_id = ?", (paper_id,)
        ).fetchone()
    finally:
        conn.close()
    if entry is None:
        raise click.ClickException(f"bib entry for paper {paper_id} not found")
    payload = dict(entry)
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    click.echo(
        f"[{payload['bibtex_key']}] source={payload['source']} verified_by={payload['verified_by']}"
    )
    click.echo(payload["bibtex"])


@bib.command("export")
@click.option("--topic", "topic_name", required=True)
@click.option("--output", "-o", type=click.Path(), default=None)
@click.pass_context
def bib_export(ctx: click.Context, topic_name: str, output: str | None) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT b.bibtex
            FROM bib_entries b
            JOIN paper_topics pt ON b.paper_id = pt.paper_id
            JOIN topics t ON pt.topic_id = t.id
            WHERE t.name = ?
            ORDER BY b.bibtex_key
            """,
            (topic_name,),
        ).fetchall()
    finally:
        conn.close()

    bib_content = "\n\n".join(row["bibtex"] for row in rows)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(bib_content)
        click.echo(f"Exported {len(rows)} entries to {output}")
        return
    click.echo(bib_content)


@main.group()
def task() -> None:
    """Manage tasks."""


@task.command("list")
@click.option("--topic", "topic_name", default=None)
@click.option("--status", default=None)
@click.pass_context
def task_list(
    ctx: click.Context,
    topic_name: str | None,
    status: str | None,
) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        query = "SELECT t.* FROM tasks t"
        joins: list[str] = []
        conditions: list[str] = []
        params: list[object] = []

        if topic_name:
            joins.append("JOIN topics tp ON t.topic_id = tp.id")
            conditions.append("tp.name = ?")
            params.append(topic_name)
        if status:
            conditions.append("t.status = ?")
            params.append(status)
        if joins:
            query += " " + " ".join(joins)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, t.created_at, t.id"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    if ctx.obj.get("json"):
        click.echo(
            json.dumps([dict(row) for row in rows], ensure_ascii=False, default=str)
        )
        return
    for row in rows:
        click.echo(
            f"[{row['id']}] [{row['status']}] [{row['priority']}] {row['title']}"
        )


@task.command("add")
@click.option("--topic", "topic_name", required=True)
@click.option("--title", required=True)
@click.option(
    "--priority", type=click.Choice(["high", "medium", "low"]), default="medium"
)
@click.option("--description", "-d", default="")
@click.pass_context
def task_add(
    ctx: click.Context,
    topic_name: str,
    title: str,
    priority: str,
    description: str,
) -> None:
    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        conn.execute(
            "INSERT INTO tasks (topic_id, title, description, priority) VALUES (?, ?, ?, ?)",
            (topic_id, title, description, priority),
        )
        conn.commit()
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    _echo(
        ctx,
        {
            "task_id": task_id,
            "title": title,
            "status": "pending",
        },
        f"Task added: id={task_id}",
    )


def _check_review_ready(conn: sqlite3.Connection, topic_id: int) -> bool:
    """Return True when topic has no pending/in_progress tasks and at least one done task."""
    open_tasks = conn.execute(
        "SELECT COUNT(*) as cnt FROM tasks WHERE topic_id = ? AND status IN ('pending', 'in_progress')",
        (topic_id,),
    ).fetchone()["cnt"]
    done_tasks = conn.execute(
        "SELECT COUNT(*) as cnt FROM tasks WHERE topic_id = ? AND status = 'done'",
        (topic_id,),
    ).fetchone()["cnt"]
    return open_tasks == 0 and done_tasks > 0


BUCKET_TASK_TEMPLATES: dict[str, dict[str, str]] = {
    "missing_pdf": {
        "title_template": "Attach PDF for: {title}",
        "description_template": "Paper {paper_id} has no PDF. Locate and attach the PDF file.",
        "priority": "medium",
    },
    "stale_annotations": {
        "title_template": "Refresh stale annotations for: {title}",
        "description_template": "Paper {paper_id} annotations are stale (PDF changed). Re-run annotation.",
        "priority": "high",
    },
    "missing_sections": {
        "title_template": "Annotate: {title}",
        "description_template": "Paper {paper_id} is missing annotation sections: {missing_sections}.",
        "priority": "high",
    },
    "missing_topic_note": {
        "title_template": "Draft topic note for: {title}",
        "description_template": "Paper {paper_id} has annotations but no topic note for this topic. Draft a note from the card.",
        "priority": "medium",
    },
}


def _generate_tasks_for_topic(
    conn: sqlite3.Connection,
    topic_name: str,
    topic_id: int,
    dry_run: bool = False,
) -> dict[str, object]:
    from .core.paper_pool import PaperPool

    papers = PaperPool(conn).list_papers(topic_id=topic_id)
    proposed: list[dict[str, object]] = []
    created_count = 0
    skipped_count = 0

    for paper_obj in papers:
        status_payload = _paper_status_payload(conn, paper_obj)
        entry = _paper_queue_entry(
            topic_name, status_payload, conn=conn, topic_id=topic_id
        )
        bucket = entry["queue_bucket"]
        if bucket == "ready" or bucket not in BUCKET_TASK_TEMPLATES:
            continue

        template = BUCKET_TASK_TEMPLATES[bucket]
        title = template["title_template"].format(
            title=paper_obj.title[:60] if paper_obj.title else f"Paper {paper_obj.id}",
            paper_id=paper_obj.id,
            missing_sections=", ".join(entry.get("missing_sections", [])),
        )
        description = template["description_template"].format(
            paper_id=paper_obj.id,
            missing_sections=", ".join(entry.get("missing_sections", [])),
        )
        priority = template["priority"]

        existing = conn.execute(
            "SELECT id FROM tasks WHERE topic_id = ? AND paper_id = ? AND status IN ('pending', 'in_progress')",
            (topic_id, paper_obj.id),
        ).fetchone()
        if existing:
            skipped_count += 1
            continue

        task_info = {
            "paper_id": paper_obj.id,
            "title": title,
            "description": description,
            "priority": priority,
            "bucket": bucket,
        }
        proposed.append(task_info)

        if not dry_run:
            conn.execute(
                "INSERT INTO tasks (topic_id, paper_id, title, description, priority) VALUES (?, ?, ?, ?, ?)",
                (topic_id, paper_obj.id, title, description, priority),
            )
            created_count += 1

    if not dry_run:
        conn.commit()

    review_ready = _check_review_ready(conn, topic_id)

    if dry_run:
        return {
            "topic": topic_name,
            "dry_run": True,
            "proposed_tasks": proposed,
            "review_ready": review_ready,
        }
    return {
        "topic": topic_name,
        "dry_run": False,
        "created_count": created_count,
        "skipped_count": skipped_count,
        "review_ready": review_ready,
    }


@task.command("generate")
@click.option("--topic", "topic_name", required=True)
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_context
def task_generate(ctx: click.Context, topic_name: str, dry_run: bool) -> None:
    """Auto-generate tasks from the paper queue for a topic."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        result = _generate_tasks_for_topic(conn, topic_name, topic_id, dry_run=dry_run)
    finally:
        conn.close()

    if ctx.obj.get("json"):
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
        return
    if dry_run:
        click.echo(
            f"Dry run: {len(result['proposed_tasks'])} tasks would be created for topic '{topic_name}'"
        )
        for item in result["proposed_tasks"]:
            click.echo(f"  [{item['priority']}] {item['title']}")
    else:
        click.echo(
            f"Generated {result['created_count']} tasks for topic '{topic_name}' (skipped {result['skipped_count']})"
        )


@task.command("update")
@click.argument("task_id", type=int)
@click.option(
    "--status", type=click.Choice(["pending", "in_progress", "done", "blocked"])
)
@click.option("--priority", type=click.Choice(["high", "medium", "low"]))
@click.pass_context
def task_update(
    ctx: click.Context, task_id: int, status: str | None, priority: str | None
) -> None:
    if not status and not priority:
        raise click.ClickException("Nothing to update")
    db = get_db(ctx)
    conn = db.connect()
    try:
        updates: list[str] = []
        params: list[object] = []
        if status:
            updates.append("status = ?")
            params.append(status)
        if priority:
            updates.append("priority = ?")
            params.append(priority)
        updates.append("updated_at = datetime('now')")
        params.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()
    _echo(
        ctx,
        {"task_id": task_id, "status": status, "priority": priority, "updated": True},
        f"Task {task_id} updated",
    )


@main.group()
def review() -> None:
    """Manage gate reviews."""


@review.command("add")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--gate",
    required=True,
    type=click.Choice(["novelty", "method", "writing", "final"]),
)
@click.option(
    "--reviewer", required=True, type=click.Choice(["claude", "codex", "human"])
)
@click.option(
    "--verdict", required=True, type=click.Choice(["pass", "conditional_pass", "fail"])
)
@click.option("--score", type=float, default=None)
@click.option("--findings", "-f", default="")
@click.pass_context
def review_add(
    ctx: click.Context,
    topic_name: str,
    gate: str,
    reviewer: str,
    verdict: str,
    score: float | None,
    findings: str,
) -> None:
    from .core.review_manager import ReviewManager

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        review_id = ReviewManager(conn).add_review(
            topic_id, gate, reviewer, verdict, score, findings
        )
    finally:
        conn.close()
    _echo(
        ctx,
        {
            "id": review_id,
            "topic": topic_name,
            "gate": gate,
            "reviewer": reviewer,
            "verdict": verdict,
            "score": score,
        },
        f"Review recorded: id={review_id}, {gate}/{reviewer} -> {verdict}",
    )


@review.command("list")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.pass_context
def review_list(ctx: click.Context, topic_name: str) -> None:
    from .core.review_manager import ReviewManager

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
        reviews = ReviewManager(conn).list_reviews(topic_id)
    finally:
        conn.close()

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                [dataclasses.asdict(item) for item in reviews],
                ensure_ascii=False,
                default=str,
            )
        )
        return
    for item in reviews:
        score_str = f" ({item.score})" if item.score is not None else ""
        click.echo(
            f"[{item.id}] {item.gate}/{item.reviewer} -> {item.verdict}{score_str}  {item.created_at}"
        )


@main.group()
def primitive() -> None:
    """Research primitives management."""


@primitive.command("list")
@click.pass_context
def primitive_list(ctx: click.Context) -> None:
    """List all registered research primitives."""
    from .primitives import list_primitives

    specs = list_primitives()
    payload = [
        {
            "name": spec.name,
            "category": spec.category.value,
            "description": spec.description,
            "requires_llm": spec.requires_llm,
        }
        for spec in specs
    ]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False))
        return
    for item in payload:
        click.echo(
            f"{item['name']} [{item['category']}] llm={item['requires_llm']} - {item['description']}"
        )


@primitive.command("exec")
@click.argument("name")
@click.option("--args", "json_args", type=str, default="{}")
@click.option("--topic", type=int, default=None)
@click.pass_context
def primitive_exec(
    ctx: click.Context, name: str, json_args: str, topic: int | None
) -> None:
    """Execute a research primitive."""
    from .execution.tracked import TrackedBackend
    from .provenance import ProvenanceRecorder

    try:
        kwargs = json.loads(json_args)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON args: {exc}") from exc
    if not isinstance(kwargs, dict):
        raise click.ClickException("--args must decode to a JSON object")

    raw_backend = _create_backend(ctx)
    backend = TrackedBackend(
        raw_backend, ProvenanceRecorder(get_db(ctx)), default_topic_id=topic
    )
    try:
        result = backend.execute(name, **kwargs)
    except NotImplementedError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = dataclasses.asdict(result)
    _echo(ctx, payload, f"{name}: success={result.success}")


@main.group()
def provenance() -> None:
    """Provenance tracking for research operations."""


@provenance.command("list")
@click.option("--topic", type=int, default=None)
@click.option("--primitive", type=str, default=None)
@click.option("--backend", "backend_name", type=str, default=None)
@click.option("--limit", type=int, default=20)
@click.pass_context
def provenance_list(
    ctx: click.Context,
    topic: int | None,
    primitive: str | None,
    backend_name: str | None,
    limit: int,
) -> None:
    """List provenance records."""
    from .provenance import ProvenanceRecorder

    records = ProvenanceRecorder(get_db(ctx)).list_records(
        topic_id=topic,
        primitive=primitive,
        backend=backend_name,
        limit=limit,
    )
    payload = [dataclasses.asdict(record) for record in records]
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    for record in payload:
        click.echo(
            f"[{record['id']}] {record['primitive']} via {record['backend']} success={record['success']}"
        )


@provenance.command("summary")
@click.option("--topic", type=int, default=None)
@click.option("--backend", "backend_name", type=str, default=None)
@click.pass_context
def provenance_summary(
    ctx: click.Context, topic: int | None, backend_name: str | None
) -> None:
    """Show provenance statistics."""
    from .provenance import ProvenanceRecorder

    summary = ProvenanceRecorder(get_db(ctx)).summarize(
        topic_id=topic, backend=backend_name
    )
    payload = dataclasses.asdict(summary)
    _echo(
        ctx,
        payload,
        f"operations={summary.total_operations} cost={summary.total_cost_usd}",
    )


@provenance.command("show")
@click.argument("record_id", type=int)
@click.pass_context
def provenance_show(ctx: click.Context, record_id: int) -> None:
    """Show a single provenance record."""
    from .provenance import ProvenanceRecorder

    record = ProvenanceRecorder(get_db(ctx)).get(record_id)
    if record is None:
        raise click.ClickException(f"provenance record {record_id} not found")
    payload = dataclasses.asdict(record)
    _echo(ctx, payload, f"record {record_id}: {record.primitive}")


@provenance.command("token-report")
@click.option("--topic", required=False, help="Filter by topic name")
@click.pass_context
def provenance_token_report(ctx: click.Context, topic: str | None) -> None:
    """Long-term token/cost accounting grouped by (backend, model)."""
    from .provenance import ProvenanceRecorder

    db = get_db(ctx)
    topic_id: int | None = None
    if topic:
        conn = db.connect()
        try:
            topic_id = _topic_id_or_exit(conn, topic)
        finally:
            conn.close()

    rows = ProvenanceRecorder(db).token_report_by_agent(topic_id=topic_id)
    totals = {
        "calls": sum(r["calls"] for r in rows),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "total_tokens": sum(r["total_tokens"] for r in rows),
        "cost_usd": sum(r["cost_usd"] for r in rows),
    }
    payload = {"topic_id": topic_id, "agents": rows, "totals": totals}
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return

    if not rows:
        click.echo("No provenance records found.")
        return

    header = f"{'backend':<14} {'model':<28} {'calls':>6} {'prompt_tok':>12} {'completion_tok':>15} {'cost_usd':>11} {'per_call':>10}"
    click.echo(header)
    click.echo("-" * len(header))
    for row in rows:
        click.echo(
            f"{row['backend']:<14} {row['model_used'][:28]:<28} {row['calls']:>6} "
            f"{row['prompt_tokens']:>12} {row['completion_tokens']:>15} "
            f"{row['cost_usd']:>11.4f} {row['cost_per_call']:>10.4f}"
        )
    click.echo("-" * len(header))
    click.echo(
        f"{'TOTAL':<14} {'':<28} {totals['calls']:>6} "
        f"{totals['prompt_tokens']:>12} {totals['completion_tokens']:>15} "
        f"{totals['cost_usd']:>11.4f}"
    )


@provenance.command("export")
@click.option("--topic", required=False, help="Filter by topic name")
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
def provenance_export(
    ctx: click.Context, topic: str | None, fmt: str, output: str | None
) -> None:
    """Export provenance records for analysis."""
    from .provenance import ProvenanceRecorder

    db = get_db(ctx)
    topic_id: int | None = None
    if topic:
        conn = db.connect()
        try:
            topic_id = _topic_id_or_exit(conn, topic)
        finally:
            conn.close()

    records = ProvenanceRecorder(db).list_records(topic_id=topic_id, limit=10000)
    serialized = _serialize_provenance_export(records, fmt)
    if output:
        _write_text_output(output, serialized)
        if not ctx.obj.get("json"):
            click.echo(f"Exported {len(records)} provenance records to {output}")
        return
    click.echo(serialized)


@main.group()
def orchestrator() -> None:
    """Research pipeline orchestrator: stage-gated workflow control."""


@orchestrator.command("init")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--mode",
    type=click.Choice(["explore", "standard", "strict", "demo"]),
    default="standard",
)
@click.pass_context
def orchestrator_init(ctx: click.Context, topic_name: str, mode: str) -> None:
    """Initialize an orchestrator run for a topic."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    run = svc.init_run(topic_id=topic_id, mode=mode)
    payload = {
        "run_id": run.id,
        "topic_id": run.topic_id,
        "mode": run.mode,
        "current_stage": run.current_stage,
        "stage_status": run.stage_status,
    }
    _echo(
        ctx,
        payload,
        f"Orchestrator initialized: {topic_name} -> {run.current_stage}",
    )


@orchestrator.command("status")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.pass_context
def orchestrator_status(ctx: click.Context, topic_name: str) -> None:
    """Show orchestrator status for a topic."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    status = svc.get_status(topic_id)
    _echo(
        ctx, status, f"Status: {status.get('run', {}).get('current_stage', 'unknown')}"
    )


@orchestrator.command("artifacts")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option("--stage", default=None, help="Filter by stage")
@click.option("--type", "artifact_type", default=None, help="Filter by artifact type")
@click.pass_context
def orchestrator_artifacts(
    ctx: click.Context,
    topic_name: str,
    stage: str | None,
    artifact_type: str | None,
) -> None:
    """List artifacts for a topic."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    artifacts = svc.list_artifacts(topic_id, stage=stage, artifact_type=artifact_type)
    payload = [
        {
            "id": a.id,
            "stage": a.stage,
            "type": a.artifact_type,
            "version": a.version,
            "status": a.status,
            "title": a.title,
            "created_at": a.created_at,
        }
        for a in artifacts
    ]
    _echo(ctx, payload, f"{len(artifacts)} artifacts")


@orchestrator.command("advance")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option("--actor", default="user", help="Actor name")
@click.pass_context
def orchestrator_advance(ctx: click.Context, topic_name: str, actor: str) -> None:
    """Advance the topic to the next stage."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    result = svc.advance(topic_id, actor=actor)
    _echo(
        ctx,
        result,
        result.get("error")
        or f"Advanced: {result.get('from_stage')} -> {result.get('to_stage')}",
    )


@orchestrator.command("gate-check")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option("--stage", default=None, help="Stage to check (defaults to current)")
@click.pass_context
def orchestrator_gate_check(
    ctx: click.Context, topic_name: str, stage: str | None
) -> None:
    """Check the gate for a stage."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    decision = svc.check_gate(topic_id, stage=stage)
    payload = {"gate_decision": decision, "stage": stage or "current"}
    _echo(ctx, payload, f"Gate decision: {decision}")


@orchestrator.command("adversarial-run")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--artifact-id", type=int, required=True, help="Target artifact ID to review"
)
@click.option(
    "--proposal",
    "proposal_json",
    required=True,
    help="Proposal snapshot as JSON string",
)
@click.option(
    "--objections", "objections_json", required=True, help="Objections as JSON array"
)
@click.option(
    "--responses",
    "responses_json",
    default=None,
    help="Proposer responses as JSON array",
)
@click.option("--resolver-notes", default="", help="Resolver notes")
@click.option("--actor", default="user", help="Actor name")
@click.pass_context
def orchestrator_adversarial_run(
    ctx: click.Context,
    topic_name: str,
    artifact_id: int,
    proposal_json: str,
    objections_json: str,
    responses_json: str | None,
    resolver_notes: str,
    actor: str,
) -> None:
    """Run an adversarial round against a proposal."""
    import json
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    # Parse JSON inputs
    try:
        proposal = json.loads(proposal_json)
        objections = json.loads(objections_json)
        responses = json.loads(responses_json) if responses_json else None
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON input: {e}", err=True)
        return

    svc = OrchestratorService(db)
    result = svc.run_adversarial_round(
        topic_id=topic_id,
        target_artifact_id=artifact_id,
        proposal_snapshot=proposal,
        objections=objections,
        proposer_responses=responses,
        resolver_notes=resolver_notes,
        actor=actor,
    )
    _echo(
        ctx,
        result,
        result.get("error")
        or f"Adversarial round {result.get('round_number')} recorded",
    )


@orchestrator.command("adversarial-resolve")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--round-artifact-id", type=int, required=True, help="Round artifact ID to resolve"
)
@click.option(
    "--scores",
    "scores_json",
    default="{}",
    help="Scores dict as JSON (e.g. '{\"novelty\": 4.5}')",
)
@click.option("--notes", default="", help="Resolution notes")
@click.option("--actor", default="user", help="Actor name")
@click.pass_context
def orchestrator_adversarial_resolve(
    ctx: click.Context,
    topic_name: str,
    round_artifact_id: int,
    scores_json: str,
    notes: str,
    actor: str,
) -> None:
    """Resolve an adversarial round and determine outcome."""
    import json
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    try:
        scores = json.loads(scores_json) if scores_json else {}
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON scores: {e}", err=True)
        return

    svc = OrchestratorService(db)
    result = svc.resolve_adversarial_round(
        topic_id=topic_id,
        round_artifact_id=round_artifact_id,
        scores=scores,
        notes=notes,
        actor=actor,
    )
    _echo(
        ctx,
        result,
        result.get("error")
        or f"Resolution: {result.get('outcome')} (score: {result.get('mean_score')})",
    )


@orchestrator.command("adversarial-status")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.pass_context
def orchestrator_adversarial_status(ctx: click.Context, topic_name: str) -> None:
    """Check adversarial status for the topic."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    status = svc.check_adversarial_status(topic_id)
    _echo(
        ctx,
        status,
        f"Adversarial status: {status.get('status', status.get('outcome', 'unknown'))}",
    )


@orchestrator.command("review-bundle")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--integrity-artifact-id",
    type=int,
    default=None,
    help="Integrity report artifact ID",
)
@click.option(
    "--scholarly-artifact-id",
    type=int,
    default=None,
    help="Scholarly report artifact ID",
)
@click.pass_context
def orchestrator_review_bundle(
    ctx: click.Context,
    topic_name: str,
    integrity_artifact_id: int | None,
    scholarly_artifact_id: int | None,
) -> None:
    """Create a review bundle from report artifacts."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    try:
        result = svc.create_review_bundle(
            topic_id=topic_id,
            integrity_artifact_id=integrity_artifact_id,
            scholarly_artifact_id=scholarly_artifact_id,
        )
        _echo(
            ctx,
            result,
            result.get("error")
            or f"Review bundle created (cycle {result.get('cycle_number')})",
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@orchestrator.command("review-add-issue")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--review-type",
    required=True,
    type=click.Choice(["integrity", "scholarly"]),
    help="Review type",
)
@click.option(
    "--severity",
    required=True,
    type=click.Choice(["critical", "high", "medium", "low"]),
    help="Issue severity",
)
@click.option("--category", required=True, help="Issue category")
@click.option("--summary", required=True, help="Issue summary")
@click.option("--details", default="", help="Detailed description")
@click.option(
    "--blocking/--no-blocking", default=False, help="Whether issue blocks advancement"
)
@click.option("--recommended-action", default="", help="Recommended fix")
@click.option(
    "--review-artifact-id", type=int, default=None, help="Source review artifact ID"
)
@click.pass_context
def orchestrator_review_add_issue(
    ctx: click.Context,
    topic_name: str,
    review_type: str,
    severity: str,
    category: str,
    summary: str,
    details: str,
    blocking: bool,
    recommended_action: str,
    review_artifact_id: int | None,
) -> None:
    """Add a review finding as an issue."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    result = svc.add_review_issue(
        topic_id=topic_id,
        review_type=review_type,
        severity=severity,
        category=category,
        summary=summary,
        details=details,
        blocking=blocking,
        recommended_action=recommended_action,
        review_artifact_id=review_artifact_id,
    )
    _echo(
        ctx,
        result,
        result.get("error") or f"Issue #{result.get('issue_id')} added ({severity})",
    )


@orchestrator.command("review-issues")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option("--stage", default=None, help="Filter by stage")
@click.option(
    "--status",
    "issue_status",
    default=None,
    type=click.Choice(["open", "in_progress", "resolved", "wontfix"]),
    help="Filter by status",
)
@click.option(
    "--blocking-only", is_flag=True, default=False, help="Show only blocking issues"
)
@click.pass_context
def orchestrator_review_issues(
    ctx: click.Context,
    topic_name: str,
    stage: str | None,
    issue_status: str | None,
    blocking_only: bool,
) -> None:
    """List review issues."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    issues = svc.list_review_issues(
        topic_id=topic_id,
        stage=stage,
        status=issue_status,
        blocking_only=blocking_only,
    )
    _echo(ctx, issues, f"{len(issues)} issues")


@orchestrator.command("review-respond")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option("--issue-id", type=int, required=True, help="Issue ID to respond to")
@click.option(
    "--response-type",
    required=True,
    type=click.Choice(["change", "clarify", "dispute", "acknowledge"]),
    help="Response type",
)
@click.option("--text", required=True, help="Response text")
@click.option("--artifact-id", type=int, default=None, help="Linked artifact ID")
@click.option(
    "--evidence", "evidence_json", default=None, help="Evidence as JSON string"
)
@click.pass_context
def orchestrator_review_respond(
    ctx: click.Context,
    topic_name: str,
    issue_id: int,
    response_type: str,
    text: str,
    artifact_id: int | None,
    evidence_json: str | None,
) -> None:
    """Respond to a review issue."""
    import json as json_mod
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    evidence = None
    if evidence_json:
        try:
            evidence = json_mod.loads(evidence_json)
        except json_mod.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON evidence: {e}", err=True)
            return

    svc = OrchestratorService(db)
    result = svc.respond_to_issue(
        issue_id=issue_id,
        topic_id=topic_id,
        response_type=response_type,
        response_text=text,
        artifact_id=artifact_id,
        evidence=evidence,
    )
    _echo(ctx, result, result.get("error") or f"Response recorded ({response_type})")


@orchestrator.command("review-resolve")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option("--issue-id", type=int, required=True, help="Issue ID to resolve")
@click.option(
    "--status",
    "resolution_status",
    required=True,
    type=click.Choice(["resolved", "wontfix"]),
    help="Resolution status",
)
@click.pass_context
def orchestrator_review_resolve(
    ctx: click.Context,
    topic_name: str,
    issue_id: int,
    resolution_status: str,
) -> None:
    """Resolve a review issue."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    result = svc.resolve_review_issue(issue_id, resolution_status)
    _echo(
        ctx, result, result.get("error") or f"Issue #{issue_id} -> {resolution_status}"
    )


@orchestrator.command("review-status")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.pass_context
def orchestrator_review_status(ctx: click.Context, topic_name: str) -> None:
    """Show review status summary."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    status = svc.get_review_status(topic_id)
    decision = status.get("decision", "unknown")
    blocking = status.get("blocking_open", 0)
    _echo(
        ctx,
        status,
        f"Decision: {decision} | Blocking: {blocking} | Cycle: {status.get('cycle_number', 0)}/{status.get('max_cycles', 2)}",
    )


@orchestrator.command("integrity-check")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.option(
    "--findings", "findings_json", default=None, help="External findings as JSON array"
)
@click.pass_context
def orchestrator_integrity_check(
    ctx: click.Context,
    topic_name: str,
    findings_json: str | None,
) -> None:
    """Run 5-phase integrity verification."""
    import json as json_mod
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    findings = None
    if findings_json:
        try:
            findings = json_mod.loads(findings_json)
        except json_mod.JSONDecodeError as e:
            click.echo(f"Error: Invalid JSON findings: {e}", err=True)
            return

    svc = OrchestratorService(db)
    result = svc.run_integrity_check(topic_id=topic_id, findings=findings)
    passed = "PASSED" if result.get("passed") else "FAILED"
    _echo(
        ctx,
        result,
        f"Integrity: {passed} | Critical: {result.get('critical_count', 0)} | Findings: {result.get('total_findings', 0)}",
    )


@orchestrator.command("finalize")
@click.option("--topic", "topic_name", required=True, help="Topic name")
@click.pass_context
def orchestrator_finalize(ctx: click.Context, topic_name: str) -> None:
    """Produce final bundle and process summary."""
    from .orchestrator import OrchestratorService

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic_name)
    finally:
        conn.close()

    svc = OrchestratorService(db)
    result = svc.finalize(topic_id=topic_id)
    _echo(
        ctx,
        result,
        result.get("error")
        or f"Finalized: {result.get('artifact_count', 0)} artifacts, {result.get('stages_traversed', 0)} stage events",
    )


@main.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:
    from .primitives import list_primitives

    checks: list[dict[str, object]] = []
    checks.append({"check": "python", "version": platform.python_version(), "ok": True})
    checks.append({"check": "sqlite3", "version": sqlite3.sqlite_version, "ok": True})
    try:
        from research_harness import paperindex  # type: ignore

        checks.append(
            {
                "check": "paperindex",
                "version": getattr(paperindex, "__version__", "unknown"),
                "ok": True,
            }
        )
    except ImportError:
        checks.append(
            {
                "check": "paperindex",
                "version": "not installed",
                "ok": True,
                "note": "optional",
            }
        )
    runtime_config = get_runtime_config(ctx)
    checks.append(
        {
            "check": "config",
            "source": runtime_config.source,
            "workspace_root": str(runtime_config.workspace_root)
            if runtime_config.workspace_root
            else None,
            "config_path": str(runtime_config.config_path)
            if runtime_config.config_path
            else None,
            "execution_backend": runtime_config.execution_backend,
            "ok": True,
        }
    )
    db = get_db(ctx)
    db_size = db.db_path.stat().st_size if db.db_path.exists() else 0
    checks.append(
        {
            "check": "database",
            "path": str(db.db_path),
            "size_kb": db_size // 1024,
            "ok": True,
        }
    )
    checks.append(
        {
            "check": "llm_config",
            "configured": bool(
                os.environ.get("OPENAI_API_KEY") or os.environ.get("KIMI_API_KEY")
            ),
            "ok": True,
            "note": "optional: needed for paper annotation",
        }
    )
    checks.append(
        {
            "check": "execution_backend",
            "backend": runtime_config.execution_backend,
            "ok": True,
        }
    )
    checks.append(
        {
            "check": "primitives",
            "registered": len(list_primitives()),
            "ok": True,
        }
    )
    conn = db.connect()
    try:
        provenance_exists = _table_exists(conn, "provenance_records")
        checks.append(
            {
                "check": "provenance",
                "table_exists": provenance_exists,
                "record_count": _count_records(conn, "provenance_records"),
                "ok": provenance_exists,
            }
        )
    finally:
        conn.close()
    if ctx.obj.get("json"):
        click.echo(json.dumps(checks, ensure_ascii=False, default=str))
        return
    for item in checks:
        detail = (
            item.get("version")
            or item.get("path")
            or item.get("backend")
            or item.get("note")
            or ""
        )
        click.echo(f"[OK] {item['check']}: {detail}")


# ---------------------------------------------------------------------------
# Auto-runner commands
# ---------------------------------------------------------------------------


@main.group("auto-runner")
def auto_runner_group() -> None:
    """Autonomous research workflow runner."""


@auto_runner_group.command("start")
@click.option("--topic-id", type=int, required=True, help="Topic ID")
@click.option(
    "--direction", type=str, default="", help="Research direction description"
)
@click.option(
    "--mode",
    type=click.Choice(["explore", "standard", "strict", "demo"]),
    default="standard",
)
@click.option(
    "--session-command",
    type=str,
    default="claude-kimi",
    help="Session command (e.g. claude-kimi)",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Auto-approve human checkpoints (demo mode)",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Show plan without executing"
)
@click.pass_context
def auto_runner_start(
    ctx: click.Context,
    topic_id: int,
    direction: str,
    mode: str,
    session_command: str,
    auto_approve: bool,
    dry_run: bool,
) -> None:
    """Start a new autonomous workflow run."""
    from .auto_runner.runner import run_topic

    result = run_topic(
        topic_id,
        direction=direction,
        mode=mode,
        session_command=session_command.split(),
        auto_approve=auto_approve,
        dry_run=dry_run,
    )
    _echo(ctx, result, result.get("summary", ""))


@auto_runner_group.command("resume")
@click.option("--topic-id", type=int, required=True, help="Topic ID")
@click.option("--auto-approve", is_flag=True, default=False)
@click.pass_context
def auto_runner_resume(ctx: click.Context, topic_id: int, auto_approve: bool) -> None:
    """Resume a paused workflow from checkpoint."""
    from .auto_runner.runner import resume_topic

    result = resume_topic(topic_id, auto_approve=auto_approve)
    _echo(ctx, result, result.get("summary", ""))


@auto_runner_group.command("status")
@click.option("--topic-id", type=int, required=True, help="Topic ID")
@click.pass_context
def auto_runner_status(ctx: click.Context, topic_id: int) -> None:
    """Show current workflow status."""
    from .auto_runner.runner import get_status

    result = get_status(topic_id)
    _echo(
        ctx,
        result,
        f"{result.get('current_stage', '?')} [{result.get('stage_state', '?')}]",
    )


@main.group()
def venues() -> None:
    """Manage venue rankings."""


@venues.command("load")
@click.option(
    "--file",
    "json_file",
    default=None,
    help="Custom JSON file (default: bundled venue_ranks_cs_2024.json)",
)
@click.pass_context
def venues_load(ctx: click.Context, json_file: str | None) -> None:
    """Load venue rankings into the database."""
    if json_file:
        src = Path(json_file)
    else:
        src = Path(__file__).parent / "data" / "venue_ranks_cs_2024.json"
    if not src.exists():
        raise click.ClickException(f"file not found: {src}")
    with open(src, encoding="utf-8") as f:
        entries = json.load(f)

    db = get_db(ctx)
    conn = db.connect()
    try:
        inserted = 0
        for entry in entries:
            try:
                conn.execute(
                    """
                    INSERT INTO venue_ranks (canonical_name, aliases, ccf_rank, cas_zone, discipline, source_snapshot)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(canonical_name) DO UPDATE SET
                        aliases = excluded.aliases,
                        ccf_rank = excluded.ccf_rank,
                        cas_zone = excluded.cas_zone,
                        discipline = excluded.discipline,
                        source_snapshot = excluded.source_snapshot,
                        updated_at = datetime('now')
                    """,
                    (
                        entry["canonical_name"],
                        json.dumps(entry.get("aliases", []), ensure_ascii=False),
                        entry.get("ccf_rank"),
                        entry.get("cas_zone"),
                        entry.get("discipline", "cs"),
                        str(src.name),
                    ),
                )
                inserted += 1
            except Exception as exc:
                click.echo(
                    f"  skip {entry.get('canonical_name', '?')}: {exc}", err=True
                )
        conn.commit()
    finally:
        conn.close()
    _echo(
        ctx,
        {"loaded": inserted, "source": str(src)},
        f"Loaded {inserted} venues from {src.name}",
    )


@main.group()
def calibrate() -> None:
    """Rubric threshold calibration (Youden's J on anchor corpus)."""


@calibrate.command("run")
@click.option("--stage", required=True, help="Stage to calibrate (e.g. analyze)")
@click.option("--tier", default="standard", help="Tier (economy/standard/premium)")
@click.option("--venue-tier", default="B", help="Venue tier (A/B/workshop)")
@click.option("--dry-run", is_flag=True, help="Print recommendation without writing")
@click.pass_context
def calibrate_run(
    ctx: click.Context,
    stage: str,
    tier: str,
    venue_tier: str,
    dry_run: bool,
) -> None:
    """Run rubric calibration for a stage+tier and write the threshold."""
    from .calibration import calibrate_stage_tier, load_anchors

    anchors = load_anchors()
    matching = [a for a in anchors if a.stage == stage and a.tier == tier]
    click.echo(f"Stage: {stage}, Tier: {tier}, Venue: {venue_tier}")
    click.echo(f"Anchor corpus: {len(matching)} entries for this (stage, tier)")

    if dry_run:
        from .calibration.runner import _score_anchor
        from .calibration.roc import youdens_j_threshold
        from .rubrics import get_threshold

        if not matching:
            click.echo("No anchors — dry-run would fall back to default threshold.")
            click.echo(
                f"Default threshold (venue {venue_tier}): {get_threshold(venue_tier)}"
            )
            return
        pos = [_score_anchor(a) for a in matching if a.label == "accept"]
        neg = [_score_anchor(a) for a in matching if a.label == "reject"]
        th, fr, rr = youdens_j_threshold(pos, neg, get_threshold(venue_tier))
        click.echo(
            f"[DRY RUN] threshold={th} false_rollback={fr:.2%} reject_rate={rr:.2%}"
        )
        return

    db = get_db(ctx)
    conn = db.connect()
    try:
        result = calibrate_stage_tier(
            conn, stage, tier, anchors=anchors, venue_tier=venue_tier
        )
    finally:
        conn.close()
    click.echo(
        f"Wrote: threshold={result.threshold} "
        f"anchors={result.anchor_count} "
        f"false_rollback={result.false_rollback_rate:.2%} "
        f"reject_rate={result.reject_rate:.2%}"
        + (" (default — no anchors)" if result.used_default else "")
    )


@calibrate.command("all")
@click.pass_context
def calibrate_all_cmd(ctx: click.Context) -> None:
    """Calibrate every (stage × tier) pair using the bundled anchor corpus."""
    from .calibration import calibrate_all

    db = get_db(ctx)
    conn = db.connect()
    try:
        results = calibrate_all(conn)
    finally:
        conn.close()

    click.echo(f"Calibrated {len(results)} (stage, tier) pairs:")
    for r in results:
        suffix = " (default)" if r.used_default else ""
        click.echo(
            f"  {r.stage}/{r.tier}: threshold={r.threshold} anchors={r.anchor_count}"
            f" fr={r.false_rollback_rate:.2%} rr={r.reject_rate:.2%}{suffix}"
        )


@calibrate.command("list")
@click.pass_context
def calibrate_list(ctx: click.Context) -> None:
    """List current calibration state from rubric_calibrations."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT stage, tier, threshold, anchor_count, false_rollback_rate,"
            " reject_rate, calibrated_at FROM rubric_calibrations"
            " ORDER BY stage, tier"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        click.echo("No calibrations recorded. Run `rh calibrate all` to seed them.")
        return
    for r in rows:
        click.echo(
            f"{r['stage']}/{r['tier']}: threshold={r['threshold']}"
            f" anchors={r['anchor_count']} calibrated_at={r['calibrated_at']}"
        )


@main.group()
def trends() -> None:
    """Domain trends pipeline."""


@trends.command("refresh")
@click.option("--tier", default="standard", help="Tier (economy/standard/premium)")
@click.option("--dry-run", is_flag=True, help="Print results without writing to DB")
@click.pass_context
def trends_refresh(ctx: click.Context, tier: str, dry_run: bool) -> None:
    """Refresh domain trends by analyzing the paper corpus."""
    from .trends import refresh_trends

    db = get_db(ctx)
    conn = db.connect()
    try:
        clusters = refresh_trends(conn, tier=tier, dry_run=dry_run)
        if dry_run:
            click.echo(f"[DRY RUN] Found {len(clusters)} trend clusters:")
        else:
            click.echo(f"Wrote {len(clusters)} trend clusters (tier={tier})")
        for i, c in enumerate(clusters):
            click.echo(
                f"  {i + 1}. {c.name} — score={c.publishability_score:.1f}, "
                f"velocity={c.velocity_yoy:.0f}%"
            )
    finally:
        conn.close()


@main.group()
def experiment() -> None:
    """Autonomous experiment iteration loop (CPU agent experiments)."""


_AGENT_TEMPLATE_PROGRAM = """\
# Experiment: {name}

## Task
{description}

## Primary metric
- **Name:** {metric}
- **Direction:** {direction} (higher is better = max; lower is better = min)

## Fixtures (do NOT modify)
- `eval.jsonl` — evaluation set
- `scorer.py`  — grading logic; reads predictions, prints metrics

## What the LLM edits
- `main.py` — your implementation. Must print one line like:
  `{metric}: <float>`

## Budget
Filled from CLI flags: max_iterations, max_cost_usd, patience.
"""

_AGENT_TEMPLATE_EVAL = (
    '{"input": "2+2", "answer": "4"}\n{"input": "3*5", "answer": "15"}\n'
)

_AGENT_TEMPLATE_SCORER = '''\
"""Fixture scorer: reads eval.jsonl, runs the solver, prints metrics."""

import json
from pathlib import Path


def score(solver):
    correct = 0
    total = 0
    for line in Path("eval.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        try:
            pred = solver(item["input"])
        except Exception:  # noqa: BLE001
            pred = ""
        total += 1
        if str(pred).strip() == str(item["answer"]).strip():
            correct += 1
    acc = correct / total if total else 0.0
    print(f"val_acc: {acc:.4f}")
'''

_AGENT_TEMPLATE_MAIN = '''\
"""Mutable implementation. The LLM rewrites this each iteration."""

from scorer import score


def solve(question: str) -> str:
    # TODO: call your LLM / rule / tool here. Must return a string.
    return ""


if __name__ == "__main__":
    score(solve)
'''


@experiment.command("scaffold")
@click.option("--name", required=True, help="Experiment name.")
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./experiment_scaffold"),
    help="Output directory for the three-file template.",
)
@click.option(
    "--description",
    default="Agent experiment — edit main.py to beat the baseline.",
    help="Task description (written into program.md).",
)
@click.option("--metric", default="val_acc", help="Primary metric name.")
@click.option(
    "--direction",
    type=click.Choice(["max", "min"]),
    default="max",
)
@click.pass_context
def experiment_scaffold(
    ctx: click.Context,
    name: str,
    out_dir: Path,
    description: str,
    metric: str,
    direction: str,
) -> None:
    """Write a karpathy-style three-file experiment template.

    Produces program.md (task spec, read-only), eval.jsonl + scorer.py
    (fixtures) and main.py (mutable). Ready to feed into `rh experiment run`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "program.md").write_text(
        _AGENT_TEMPLATE_PROGRAM.format(
            name=name,
            description=description,
            metric=metric,
            direction=direction,
        ),
        encoding="utf-8",
    )
    (out_dir / "eval.jsonl").write_text(_AGENT_TEMPLATE_EVAL, encoding="utf-8")
    (out_dir / "scorer.py").write_text(_AGENT_TEMPLATE_SCORER, encoding="utf-8")
    (out_dir / "main.py").write_text(_AGENT_TEMPLATE_MAIN, encoding="utf-8")

    click.echo(f"Wrote scaffold to {out_dir}")
    click.echo("  program.md   — task spec (read-only)")
    click.echo("  eval.jsonl   — fixture: evaluation set")
    click.echo("  scorer.py    — fixture: grading logic")
    click.echo("  main.py      — mutable: the LLM rewrites this")
    click.echo("")
    click.echo(
        f"Next: rh experiment run --topic <name> --scaffold {out_dir} "
        f"--metric {metric} --direction {direction}"
    )


def _load_scaffold(scaffold_dir: Path) -> tuple[str, dict[str, str], str]:
    """Return (task_description, fixture_files, mutable_code)."""
    program_md = (scaffold_dir / "program.md").read_text(encoding="utf-8")
    fixtures: dict[str, str] = {}
    for name in ("eval.jsonl", "scorer.py"):
        path = scaffold_dir / name
        if path.exists():
            fixtures[name] = path.read_text(encoding="utf-8")
    # Include any additional fixture files (read-only support: anything not main.py)
    for path in scaffold_dir.iterdir():
        if path.is_file() and path.name not in {"program.md", "main.py"}:
            fixtures.setdefault(path.name, path.read_text(encoding="utf-8"))
    mutable_path = scaffold_dir / "main.py"
    mutable_code = (
        mutable_path.read_text(encoding="utf-8") if mutable_path.exists() else ""
    )
    return program_md, fixtures, mutable_code


@experiment.command("run")
@click.option("--topic", required=True, help="Topic name.")
@click.option(
    "--scaffold",
    "scaffold_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option("--name", default="", help="Experiment display name.")
@click.option("--metric", default="val_acc")
@click.option("--direction", type=click.Choice(["max", "min"]), default="max")
@click.option("--mode", type=click.Choice(["strict", "agent"]), default="agent")
@click.option("--max-iterations", type=int, default=5)
@click.option("--max-cost-usd", type=float, default=0.0)
@click.option("--patience", type=int, default=3)
@click.option("--timeout-sec", type=float, default=300.0)
@click.pass_context
def experiment_run_cmd(
    ctx: click.Context,
    topic: str,
    scaffold_dir: Path,
    name: str,
    metric: str,
    direction: str,
    mode: str,
    max_iterations: int,
    max_cost_usd: float,
    patience: int,
    timeout_sec: float,
) -> None:
    """Run experiment_loop on a scaffold directory."""
    from .primitives.experiment_loop_impl import experiment_loop
    from .primitives.types import ExperimentBudget

    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic)
    finally:
        conn.close()

    task_description, fixtures, _mutable = _load_scaffold(scaffold_dir)

    out = experiment_loop(
        db=db,
        topic_id=topic_id,
        name=name or scaffold_dir.name,
        task_description=task_description,
        fixture_files=fixtures,
        mutable_entry="main.py",
        primary_metric=metric,
        direction=direction,
        mode=mode,
        timeout_sec=timeout_sec,
        budget=ExperimentBudget(
            max_iterations=max_iterations,
            max_cost_usd=max_cost_usd,
            patience=patience,
        ),
    )

    click.echo(
        f"experiment_id={out.experiment_id} "
        f"iterations={out.total_iterations} "
        f"best_iter={out.best_iteration} best={out.best_value} "
        f"stopped={out.stopped_reason} cost=${out.total_cost_usd:.4f}"
    )
    for r in out.runs:
        click.echo(
            f"  #{r.iteration} {r.status:9s} {r.primary_metric_value} "
            f"({r.elapsed_sec:.1f}s, ${r.cost_usd:.3f})"
        )


@experiment.command("list")
@click.option("--topic", required=True)
@click.pass_context
def experiment_list(ctx: click.Context, topic: str) -> None:
    """List autonomous experiments for a topic."""
    db = get_db(ctx)
    conn = db.connect()
    try:
        topic_id = _topic_id_or_exit(conn, topic)
        try:
            rows = conn.execute(
                "SELECT id, name, primary_metric, direction, status, stopped_reason,"
                " best_run_id, created_at FROM experiments WHERE topic_id = ?"
                " ORDER BY created_at DESC",
                (topic_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()

    if not rows:
        click.echo(f"No experiments for topic {topic!r}.")
        return

    for r in rows:
        click.echo(
            f"[{r['id']}] {r['name']:<30s} "
            f"{r['primary_metric']:<12s} {r['direction']:<4s} "
            f"{r['status']:<10s} stopped={r['stopped_reason']}"
        )


if __name__ == "__main__":
    main()
