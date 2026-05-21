"""FastAPI HTTP API for research-harness — REST endpoints for the Next.js frontend.

Wraps the SQLite pool.db as JSON endpoints with pagination, search, and CORS.
Write/action endpoints delegate to MCP tool handlers via execute_tool().
Run standalone: python -m research_harness_mcp.http_api
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from research_harness.api import ResearchAPI
from research_harness.agents.families import get_family
from research_harness.demo import list_entries as demo_list_entries
from research_harness.demo import lookup as demo_lookup
from research_harness_mcp.tools import execute_tool

logger = logging.getLogger(__name__)
# Ensure expansion-worker logs reach the console. Without this, uvicorn
# configures its own access logger at INFO but leaves application modules
# at WARNING with no root handler, so our logger.info() calls get swallowed.
_APP_LOG_HANDLER: logging.Handler | None = None
if not logging.getLogger().handlers:
    _APP_LOG_HANDLER = logging.StreamHandler()
    _APP_LOG_HANDLER.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(_APP_LOG_HANDLER)
    logging.getLogger().setLevel(logging.INFO)
logger.setLevel(logging.INFO)
logging.getLogger("research_harness").setLevel(logging.INFO)
logging.getLogger("research_harness_mcp").setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / ".research-harness" / "pool.db"

DB_PATH = Path(os.environ.get("RESEARCH_HARNESS_DB_PATH") or str(_DEFAULT_DB_PATH))


# ---------------------------------------------------------------------------
# Allowed PDF roots (for /api/papers/{id}/pdf — guards against path traversal
# from arbitrary pdf_path values stored in the DB)
# ---------------------------------------------------------------------------


def _default_pdf_roots() -> list[Path]:
    """Roots under which we trust pdf_path strings. Anything resolving outside
    these is refused with 403, regardless of whether the file exists.

    Note: we do NOT filter out non-existent roots — the trust policy is about
    path prefixes, not about whether the directory exists right now. If a
    trusted dir gets created later, the endpoint should immediately serve from
    it without a restart.
    """
    candidates = [
        Path.home() / ".research-harness",
        Path(__file__).resolve().parents[3] / ".research-harness",
        # Legacy location for users who upgraded from the pre-OSS layout.
        Path.home() / "code" / "research-harness" / ".research-harness",
    ]
    seen: set[Path] = set()
    roots: list[Path] = []
    for c in candidates:
        try:
            r = c.expanduser().resolve()
        except OSError:
            continue
        if r in seen:
            continue
        seen.add(r)
        roots.append(r)
    return roots


_env_roots = os.environ.get("RESEARCH_HARNESS_PDF_ROOTS")
if _env_roots:
    PDF_ROOTS = [Path(p).expanduser().resolve() for p in _env_roots.split(":") if p]
else:
    PDF_ROOTS = _default_pdf_roots()


@contextmanager
def get_db():
    """Yield a sqlite3 connection with Row factory and WAL mode."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_row_to_dict(r) for r in rows]


def _parse_json_field(value: str | None, fallback: Any = None) -> Any:
    """Safely parse a JSON string field. Returns fallback on failure."""
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel):
    data: list[dict[str, Any]]
    pagination: PaginationMeta


class DomainSummary(BaseModel):
    id: int
    name: str
    description: str
    status: str
    topic_count: int
    created_at: str


class DomainDetail(BaseModel):
    id: int
    name: str
    description: str
    status: str
    created_at: str
    topics: list  # list[TopicSummary] — forward-ref resolved below


class CreateDomainRequest(BaseModel):
    name: str
    description: str = ""


class PatchDomainRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class PatchTopicRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    domain_id: int | None = Field(
        default=None, description="Pass null via JSON to unset"
    )
    target_venue: str | None = None
    deadline: str | None = None
    status: str | None = None

    # Pydantic v2: treat explicitly set None as "clear" signal for domain_id.
    model_config = {"extra": "forbid"}


class TopicSummary(BaseModel):
    id: int
    name: str
    description: str
    status: str
    target_venue: str
    deadline: str
    created_at: str
    paper_count: int
    domain_id: int | None
    domain_name: str | None
    current_stage: str | None = None
    stage_status: str | None = None


class TopicDetail(BaseModel):
    id: int
    name: str
    description: str
    status: str
    target_venue: str
    deadline: str
    created_at: str
    paper_count: int
    annotation_count: int
    domain_id: int | None
    domain_name: str | None
    # Orchestrator workflow fields
    current_stage: str | None
    stage_status: str | None
    gate_status: str | None
    contributions: str
    mode: str | None
    stop_before: str | None
    blocking_issue_count: int
    unresolved_issue_count: int
    artifact_counts: dict[str, int]


# Resolve forward reference in DomainDetail
DomainDetail.model_rebuild()


class PaperDetail(BaseModel):
    id: int
    title: str
    authors: list[Any]
    year: int | None
    venue: str
    doi: str
    arxiv_id: str
    s2_id: str
    url: str
    abstract: str
    citation_count: int | None
    deep_read: bool
    status: str
    pdf_path: str
    created_at: str
    annotations: list[dict[str, Any]]
    topics: list[dict[str, Any]]


class DashboardStats(BaseModel):
    total_papers: int
    total_topics: int
    total_domains: int
    total_artifacts: int
    total_provenance_records: int
    papers_with_pdf: int
    recent_papers: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]


class ProvenanceSummary(BaseModel):
    total_records: int
    total_cost_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    by_backend: list[dict[str, Any]]
    by_primitive: list[dict[str, Any]]
    recent_records: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Research Harness API",
    description="REST API for the research-harness pool.db — read endpoints + write/action endpoints via MCP tools",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health_check():
    """Basic liveness probe."""
    exists = DB_PATH.exists()
    return {"status": "ok" if exists else "db_missing", "db_path": str(DB_PATH)}


# ---------------------------------------------------------------------------
# RH Discover
# ---------------------------------------------------------------------------


@app.get("/api/discover/sources")
def get_discover_sources(family: str | None = None):
    """Return the RH Discover seed source registry for the frontend."""
    from research_harness.discover import list_source_definitions

    valid_families = {None, "papers", "blogs", "product", "repos_models", "social"}
    if family not in valid_families:
        raise HTTPException(
            status_code=400, detail=f"unsupported source family: {family}"
        )
    sources = list_source_definitions(family=family)  # type: ignore[arg-type]
    return [source.to_dict() for source in sources]


@app.get("/api/discover/weekly")
def get_discover_weekly(
    sample: bool = True,
    generated_at: str | None = None,
):
    """Return a complete RH Discover Weekly report.

    The current product-ready MVP intentionally exposes the curated sample
    report. Live connector-backed generation comes after manual content
    validation.
    """
    from research_harness.discover import (
        build_sample_weekly_report,
        load_latest_discover_report,
    )

    if not sample:
        try:
            return load_latest_discover_report(cadence="weekly").to_dict()
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="no published RH Discover weekly issue found",
            ) from exc
    return build_sample_weekly_report(generated_at=generated_at).to_dict()


@app.get("/api/discover/issues")
def get_discover_issues(
    cadence: str | None = None,
    include_drafts: bool = False,
):
    """Return the curated RH Discover issue archive."""

    from research_harness.discover import list_discover_issues

    valid_cadences = {None, "daily", "weekly", "special"}
    if cadence not in valid_cadences:
        raise HTTPException(status_code=400, detail=f"unsupported cadence: {cadence}")
    issues = list_discover_issues(cadence=cadence, include_drafts=include_drafts)
    return [issue.to_dict() for issue in issues]


@app.get("/api/discover/issues/{issue_id}")
def get_discover_issue(
    issue_id: str,
    cadence: str | None = "weekly",
    include_drafts: bool = False,
):
    """Return one curated RH Discover issue, or latest by cadence."""

    from research_harness.discover import (
        load_discover_issue,
        load_latest_discover_report,
    )

    try:
        if issue_id == "latest":
            return load_latest_discover_report(
                cadence=cadence,
                include_drafts=include_drafts,
            ).to_dict()
        return load_discover_issue(
            issue_id,
            include_drafts=include_drafts,
        ).to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"RH Discover issue not found: {issue_id}",
        ) from exc


@app.get("/api/discover/opportunities")
def get_discover_opportunities(
    sample: bool = True,
    cadence: str | None = "weekly",
):
    """Return flattened opportunities for the Discovery 1.0 explorer."""

    from research_harness.discover import (
        list_opportunity_cards,
        load_opportunity_report,
    )

    try:
        report = load_opportunity_report(sample=sample, cadence=cadence)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="no RH Discover opportunity report found",
        ) from exc

    return {
        "issue_id": report.issue_id,
        "cadence": report.cadence,
        "generated_at": report.generated_at,
        "opportunities": list_opportunity_cards(report),
    }


@app.get("/api/discover/opportunities/{slug}")
def get_discover_opportunity(
    slug: str,
    sample: bool = True,
    cadence: str | None = "weekly",
):
    """Return one Discovery opportunity by stable slug."""

    from research_harness.discover import (
        find_opportunity,
        load_opportunity_report,
        opportunity_slug,
    )

    try:
        report = load_opportunity_report(sample=sample, cadence=cadence)
        brief = find_opportunity(report, slug)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="no RH Discover opportunity report found",
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"RH Discover opportunity not found: {slug}",
        ) from exc

    return {
        "issue_id": report.issue_id,
        "slug": opportunity_slug(brief),
        "brief": brief.to_dict(),
    }


class DiscoverHandoffRequest(BaseModel):
    user_profile: dict[str, Any] = Field(default_factory=dict)
    selected_goal_preview_ids: list[str] = Field(default_factory=list)


@app.post("/api/discover/opportunities/{slug}/handoff")
def handoff_discover_opportunity(
    slug: str,
    body: DiscoverHandoffRequest,
    sample: bool = True,
    cadence: str | None = "weekly",
):
    """Create an RH Core topic from a selected Discovery opportunity.

    The endpoint deliberately persists only the topic seed and selected goal
    previews. Full RH Core ``goal_pool`` construction remains a downstream
    action after field brief and intake data are available.
    """

    from research_harness.discover import find_opportunity, load_opportunity_report

    try:
        report = load_opportunity_report(sample=sample, cadence=cadence)
        brief = find_opportunity(report, slug)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="no RH Discover opportunity report found",
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"RH Discover opportunity not found: {slug}",
        ) from exc

    payload = brief.to_dict()
    handoff = payload["rh_handoff"]
    selected_ids = set(body.selected_goal_preview_ids)
    selected_goals = [
        goal
        for goal in payload["goal_previews"]
        if not selected_ids or goal["id"] in selected_ids
    ]
    if body.selected_goal_preview_ids and not selected_goals:
        raise HTTPException(
            status_code=400,
            detail="selected goal previews do not belong to this opportunity",
        )

    now = datetime.now(timezone.utc).isoformat()
    topic_name = handoff["topic_name"]
    description = (
        "RH Discovery handoff\n\n"
        f"Source issue: {report.issue_id}\n"
        f"Opportunity: {payload['title']}\n"
        f"Why now: {payload['why_now']}\n"
        f"Initial queries: {json.dumps(handoff['initial_queries'], ensure_ascii=False)}\n"
        f"Selected goal previews: {json.dumps(selected_goals, ensure_ascii=False)}\n"
        f"User profile: {json.dumps(body.user_profile, ensure_ascii=False)}"
    )

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM topics WHERE name = ?",
            (topic_name,),
        ).fetchone()
        if existing:
            topic_id = existing["id"]
            created = False
        else:
            cur = conn.execute(
                """
                INSERT INTO topics (name, description, status, target_venue, deadline, created_at)
                VALUES (?, ?, 'active', ?, ?, ?)
                """,
                (
                    topic_name,
                    description,
                    str(body.user_profile.get("preferred_venue") or ""),
                    str(body.user_profile.get("deadline") or ""),
                    now,
                ),
            )
            conn.commit()
            topic_id = cur.lastrowid
            created = True

    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "created": created,
        "seed_queries": handoff["initial_queries"],
        "goal_seeds": selected_goals,
        "next_url": f"/topics/{topic_id}",
    }


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


@app.get("/api/topics", response_model=list[TopicSummary])
def list_topics(
    domain_id: int | None = Query(None, description="Filter by domain"),
):
    with get_db() as conn:
        conditions: list[str] = []
        params: list[Any] = []

        if domain_id is not None:
            conditions.append("t.domain_id = ?")
            params.append(domain_id)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = conn.execute(
            f"""
            SELECT t.*,
                   d.name AS domain_name,
                   COUNT(pt.paper_id) AS paper_count,
                   o.current_stage AS orch_current_stage,
                   o.stage_status AS orch_stage_status
            FROM topics t
            LEFT JOIN domains d ON d.id = t.domain_id
            LEFT JOIN paper_topics pt ON pt.topic_id = t.id
            LEFT JOIN orchestrator_runs o ON o.topic_id = t.id
            {where_clause}
            GROUP BY t.id
            ORDER BY t.id
            """,
            params,
        ).fetchall()
    return [
        TopicSummary(
            id=r["id"],
            name=r["name"],
            description=r["description"] or "",
            status=r["status"] or "active",
            target_venue=r["target_venue"] or "",
            deadline=r["deadline"] or "",
            created_at=r["created_at"] or "",
            paper_count=r["paper_count"],
            domain_id=r["domain_id"],
            domain_name=r["domain_name"],
            current_stage=r["orch_current_stage"],
            stage_status=r["orch_stage_status"],
        )
        for r in rows
    ]


@app.get("/api/topics/{topic_id}", response_model=TopicDetail)
def get_topic(topic_id: int):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT t.*, d.name AS domain_name
            FROM topics t
            LEFT JOIN domains d ON d.id = t.domain_id
            WHERE t.id = ?
            """,
            (topic_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        paper_count = conn.execute(
            "SELECT COUNT(*) AS c FROM paper_topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()["c"]

        annotation_count = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM paper_annotations pa
            JOIN paper_topics pt ON pt.paper_id = pa.paper_id
            WHERE pt.topic_id = ?
            """,
            (topic_id,),
        ).fetchone()["c"]

        # Orchestrator workflow info
        orch = conn.execute(
            """
            SELECT current_stage, stage_status, gate_status, mode, stop_before,
                   blocking_issue_count, unresolved_issue_count
            FROM orchestrator_runs
            WHERE topic_id = ?
            """,
            (topic_id,),
        ).fetchone()

        # Artifact counts per stage
        stage_rows = conn.execute(
            """
            SELECT pa.stage, COUNT(*) AS cnt
            FROM project_artifacts pa
            WHERE pa.topic_id = ?
            GROUP BY pa.stage
            """,
            (topic_id,),
        ).fetchall()
        artifact_counts = {r["stage"]: r["cnt"] for r in stage_rows}

    return TopicDetail(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        status=row["status"] or "active",
        target_venue=row["target_venue"] or "",
        deadline=row["deadline"] or "",
        created_at=row["created_at"] or "",
        paper_count=paper_count,
        annotation_count=annotation_count,
        domain_id=row["domain_id"],
        domain_name=row["domain_name"],
        current_stage=orch["current_stage"] if orch else None,
        stage_status=orch["stage_status"] if orch else None,
        gate_status=orch["gate_status"] if orch else None,
        contributions=row["contributions"] or "",
        mode=orch["mode"] if orch else None,
        stop_before=orch["stop_before"] if orch else None,
        blocking_issue_count=orch["blocking_issue_count"] if orch else 0,
        unresolved_issue_count=orch["unresolved_issue_count"] if orch else 0,
        artifact_counts=artifact_counts,
    )


@app.get("/api/topics/{topic_id}/papers", response_model=PaginatedResponse)
def list_topic_papers(
    topic_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str = Query("", description="Search in title/authors/venue"),
    sort: str = Query(
        "created_at", description="Sort field: created_at, year, title, citation_count"
    ),
    order: str = Query("desc", description="asc or desc"),
):
    with get_db() as conn:
        # Verify topic exists
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        allowed_sort = {"created_at", "year", "title", "citation_count", "venue"}
        sort_col = sort if sort in allowed_sort else "created_at"
        sort_dir = "ASC" if order.lower() == "asc" else "DESC"

        base_where = "pt.topic_id = ?"
        params: list[Any] = [topic_id]

        if search:
            base_where += " AND (p.title LIKE ? OR p.authors LIKE ? OR p.venue LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])

        count_sql = f"SELECT COUNT(*) AS c FROM papers p JOIN paper_topics pt ON pt.paper_id = p.id WHERE {base_where}"
        total = conn.execute(count_sql, params).fetchone()["c"]

        offset = (page - 1) * per_page
        data_sql = f"""
            SELECT p.*, pt.relevance
            FROM papers p
            JOIN paper_topics pt ON pt.paper_id = p.id
            WHERE {base_where}
            ORDER BY p.{sort_col} {sort_dir}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, [*params, per_page, offset]).fetchall()

    papers = []
    for r in rows:
        d = _row_to_dict(r)
        d["authors"] = _parse_json_field(d.get("authors"), [])
        papers.append(d)

    total_pages = max(1, (total + per_page - 1) // per_page)
    return PaginatedResponse(
        data=papers,
        pagination=PaginationMeta(
            page=page, per_page=per_page, total=total, total_pages=total_pages
        ),
    )


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------


@app.get("/api/domains", response_model=list[DomainSummary])
def list_domains():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT d.*,
                   COUNT(t.id) AS topic_count
            FROM domains d
            LEFT JOIN topics t ON t.domain_id = d.id
            GROUP BY d.id
            ORDER BY d.id
            """
        ).fetchall()
    return [
        DomainSummary(
            id=r["id"],
            name=r["name"],
            description=r["description"] or "",
            status=r["status"] or "active",
            topic_count=r["topic_count"],
            created_at=r["created_at"] or "",
        )
        for r in rows
    ]


# NOTE: literal sub-routes under /api/domains (trends, suggest, etc.) MUST be
# declared before this {domain_id} route. FastAPI matches in registration
# order, and the int-typed param will eat any literal segment otherwise (e.g.
# GET /api/domains/trends -> 422 "trends is not a valid integer"). The trends
# GET endpoint lives further down for code-locality reasons; we register a
# forwarder here that accepts every public query param and delegates to the
# real implementation. Forget one param here and the server silently drops it.


@app.get("/api/domains/trends", include_in_schema=False)
def _domain_trends_proxy(
    tier: str | None = None,
    scope: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
):
    return get_domain_trends(tier=tier, scope=scope, limit=limit)  # type: ignore[name-defined]


@app.get("/api/domains/{domain_id}", response_model=DomainDetail)
def get_domain(domain_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM domains WHERE id = ?", (domain_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Domain {domain_id} not found")

        topic_rows = conn.execute(
            """
            SELECT t.*,
                   d.name AS domain_name,
                   COUNT(pt.paper_id) AS paper_count
            FROM topics t
            LEFT JOIN domains d ON d.id = t.domain_id
            LEFT JOIN paper_topics pt ON pt.topic_id = t.id
            WHERE t.domain_id = ?
            GROUP BY t.id
            ORDER BY t.id
            """,
            (domain_id,),
        ).fetchall()

    topics = [
        TopicSummary(
            id=r["id"],
            name=r["name"],
            description=r["description"] or "",
            status=r["status"] or "active",
            target_venue=r["target_venue"] or "",
            deadline=r["deadline"] or "",
            created_at=r["created_at"] or "",
            paper_count=r["paper_count"],
            domain_id=r["domain_id"],
            domain_name=r["domain_name"],
        )
        for r in topic_rows
    ]

    return DomainDetail(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        status=row["status"] or "active",
        created_at=row["created_at"] or "",
        topics=topics,
    )


@app.post("/api/domains", response_model=DomainSummary)
def create_domain(body: CreateDomainRequest):
    """Create a new domain."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO domains (name, description, status, created_at)
            VALUES (?, ?, 'active', ?)
            """,
            (body.name, body.description, now),
        )
        conn.commit()
        domain_id = cur.lastrowid
    return DomainSummary(
        id=domain_id,
        name=body.name,
        description=body.description,
        status="active",
        topic_count=0,
        created_at=now,
    )


@app.patch("/api/domains/{domain_id}", response_model=DomainSummary)
def update_domain(domain_id: int, body: PatchDomainRequest):
    """Update a domain's editable fields. Only fields explicitly passed are changed."""
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    allowed = {"name", "description", "status"}
    updates = {k: v for k, v in patch.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [domain_id]

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM domains WHERE id = ?", (domain_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Domain {domain_id} not found")
        conn.execute(f"UPDATE domains SET {set_clause} WHERE id = ?", params)
        conn.commit()

        row = conn.execute(
            """
            SELECT d.*, COUNT(t.id) AS topic_count
            FROM domains d
            LEFT JOIN topics t ON t.domain_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
            """,
            (domain_id,),
        ).fetchone()
    return DomainSummary(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        status=row["status"] or "active",
        topic_count=row["topic_count"] or 0,
        created_at=row["created_at"] or "",
    )


# ---------------------------------------------------------------------------
# Domain suggest + topic candidates (S5)
# ---------------------------------------------------------------------------


class DomainSuggestRequest(BaseModel):
    idea: str


@app.post("/api/domains/suggest")
def domain_suggest(body: DomainSuggestRequest):
    """Suggest a domain from a research idea (stub — returns structured suggestion)."""
    idea = body.idea.strip()
    if not idea:
        raise HTTPException(status_code=400, detail="Idea text is required")
    words = idea.split()
    name_suggestion = " ".join(words[:5]).title() if len(words) >= 3 else idea.title()
    return {
        "suggestion": {
            "name": name_suggestion,
            "description": idea,
            "keywords": words[:10],
        },
        "source": "stub",
    }


class TopicCandidatesRequest(BaseModel):
    tier: str = "standard"
    max_candidates: int = 5


@app.post("/api/domains/{domain_id}/topic-candidates")
def create_topic_candidates_job(domain_id: int, body: TopicCandidatesRequest):
    """Start an async job to generate topic candidates for a domain."""
    with get_db() as conn:
        domain = conn.execute(
            "SELECT id, name FROM domains WHERE id = ?", (domain_id,)
        ).fetchone()
        if not domain:
            raise HTTPException(status_code=404, detail="Domain not found")

        cur = conn.execute(
            """
            INSERT INTO async_jobs (job_type, domain_id, status, input_params, result)
            VALUES ('topic_candidates', ?, 'completed', ?, ?)
            """,
            (
                domain_id,
                json.dumps({"tier": body.tier, "max_candidates": body.max_candidates}),
                json.dumps(
                    {
                        "candidates": [
                            {
                                "name": f"{domain['name']} — Direction {i + 1}",
                                "description": f"Exploring aspect {i + 1} of {domain['name']}",
                                "rationale": "Generated from domain scope analysis",
                            }
                            for i in range(min(body.max_candidates, 5))
                        ]
                    }
                ),
            ),
        )
        job_id = cur.lastrowid
        conn.commit()

    return {"job_id": job_id, "status": "completed"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    """Poll an async job status."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM async_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
    d = _row_to_dict(row)
    if isinstance(d.get("result"), str):
        d["result"] = _parse_json_field(d["result"])
    if isinstance(d.get("input_params"), str):
        d["input_params"] = _parse_json_field(d["input_params"])
    return d


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------


@app.get("/api/papers", response_model=PaginatedResponse)
def list_papers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str = Query("", description="Search in title/authors/venue"),
    topic_id: int | None = Query(None, description="Filter by topic"),
    domain_id: int | None = Query(None, description="Filter by domain (any topic)"),
    status: str | None = Query(None, description="Filter by paper status"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
):
    with get_db() as conn:
        conditions: list[str] = []
        params: list[Any] = []

        if topic_id is not None:
            conditions.append("pt.topic_id = ?")
            params.append(topic_id)

        if domain_id is not None and topic_id is None:
            # Filter to papers linked to any topic in this domain.
            conditions.append("t.domain_id = ?")
            params.append(domain_id)

        if status:
            conditions.append("p.status = ?")
            params.append(status)

        if search:
            conditions.append("(p.title LIKE ? OR p.authors LIKE ? OR p.venue LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        if topic_id is not None:
            join_clause = "JOIN paper_topics pt ON pt.paper_id = p.id"
        elif domain_id is not None:
            join_clause = (
                "JOIN paper_topics pt ON pt.paper_id = p.id "
                "JOIN topics t ON t.id = pt.topic_id"
            )
        else:
            join_clause = "LEFT JOIN paper_topics pt ON pt.paper_id = p.id"

        # Use DISTINCT to avoid duplicate rows when paper belongs to multiple topics
        count_sql = f"SELECT COUNT(DISTINCT p.id) AS c FROM papers p {join_clause} {where_clause}"
        total = conn.execute(count_sql, params).fetchone()["c"]

        allowed_sort = {"created_at", "year", "title", "citation_count", "venue", "id"}
        sort_col = sort if sort in allowed_sort else "created_at"
        sort_dir = "ASC" if order.lower() == "asc" else "DESC"
        offset = (page - 1) * per_page

        # When scoped to a topic, surface the per-topic relevance so the UI
        # column isn't always "--". The unscoped list has no canonical
        # relevance value (a paper can sit in multiple topics).
        select_extra = ", pt.relevance AS relevance" if topic_id is not None else ""

        data_sql = f"""
            SELECT DISTINCT p.*{select_extra}
            FROM papers p
            {join_clause}
            {where_clause}
            ORDER BY p.{sort_col} {sort_dir}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, [*params, per_page, offset]).fetchall()

    papers = []
    for r in rows:
        d = _row_to_dict(r)
        d["authors"] = _parse_json_field(d.get("authors"), [])
        if topic_id is None and "relevance" not in d:
            d["relevance"] = None
        papers.append(d)

    total_pages = max(1, (total + per_page - 1) // per_page)
    return PaginatedResponse(
        data=papers,
        pagination=PaginationMeta(
            page=page, per_page=per_page, total=total, total_pages=total_pages
        ),
    )


@app.get("/api/papers/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

        ann_rows = conn.execute(
            """
            SELECT id, section, content, source, confidence, created_at, updated_at
            FROM paper_annotations
            WHERE paper_id = ?
            ORDER BY section
            """,
            (paper_id,),
        ).fetchall()

        topic_rows = conn.execute(
            """
            SELECT t.id, t.name, pt.relevance
            FROM topics t
            JOIN paper_topics pt ON pt.topic_id = t.id
            WHERE pt.paper_id = ?
            """,
            (paper_id,),
        ).fetchall()

    annotations = []
    for a in ann_rows:
        d = _row_to_dict(a)
        d["content"] = _parse_json_field(d.get("content"), d.get("content"))
        annotations.append(d)

    return PaperDetail(
        id=row["id"],
        title=row["title"] or "",
        authors=_parse_json_field(row["authors"], []),
        year=row["year"],
        venue=row["venue"] or "",
        doi=row["doi"] or "",
        arxiv_id=row["arxiv_id"] or "",
        s2_id=row["s2_id"] or "",
        url=row["url"] or "",
        abstract=row["abstract"] or "",
        citation_count=row["citation_count"],
        deep_read=bool(row["deep_read"]) if "deep_read" in row.keys() else False,
        status=row["status"] or "meta_only",
        pdf_path=row["pdf_path"] or "",
        created_at=row["created_at"] or "",
        annotations=annotations,
        topics=_rows_to_list(topic_rows),
    )


@app.patch("/api/papers/{paper_id}/deep-read")
def toggle_deep_read(paper_id: int, body: dict[str, Any] | None = None):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT p.id, pt.topic_id
            FROM papers p
            LEFT JOIN paper_topics pt ON pt.paper_id = p.id
            WHERE p.id = ?
            ORDER BY pt.topic_id
            LIMIT 1
            """,
            (paper_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        topic_id = body.get("topic_id") if body else None
        if topic_id is None:
            topic_id = row["topic_id"]
        if topic_id is None:
            raise HTTPException(
                status_code=400,
                detail="topic_id is required for deep-read when paper has no topic",
            )
    api = ResearchAPI(db_path=DB_PATH)
    output = _deep_read_paper_impl(api, paper_id=paper_id, topic_id=int(topic_id))
    return {"success": True, "deep_read": True, "output": output}


@app.get("/api/papers/{paper_id}/pdf")
def get_paper_pdf(paper_id: int):
    """Stream the PDF file for a paper, if locally available and the path
    resolves under one of the configured allowed roots (path-traversal guard).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT pdf_path, title FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

    raw = (row["pdf_path"] or "").strip()
    if not raw:
        raise HTTPException(status_code=404, detail="No PDF on file for this paper")

    try:
        candidate = Path(raw).expanduser().resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid pdf_path: {exc}")

    if not PDF_ROOTS:
        raise HTTPException(
            status_code=500,
            detail="No allowed PDF roots configured (set RESEARCH_HARNESS_PDF_ROOTS)",
        )

    if not any(candidate.is_relative_to(root) for root in PDF_ROOTS):
        raise HTTPException(
            status_code=403,
            detail="PDF path is outside the allowed roots",
        )

    if not candidate.is_file():
        raise HTTPException(
            status_code=404,
            detail="PDF path is recorded but the file is missing on disk",
        )

    return FileResponse(
        candidate,
        media_type="application/pdf",
        filename=candidate.name,
        headers={"Cache-Control": "private, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Topic Orchestrator — Artifacts & Events
# ---------------------------------------------------------------------------


@app.get("/api/topics/{topic_id}/artifacts")
def list_topic_artifacts(
    topic_id: int,
    stage: str | None = Query(None, description="Filter by stage"),
):
    with get_db() as conn:
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        conditions = ["topic_id = ?"]
        params: list[Any] = [topic_id]
        if stage:
            conditions.append("stage = ?")
            params.append(stage)

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"""
            SELECT id, project_id, topic_id, stage, artifact_type, status,
                   version, title, path, payload_json, metadata_json,
                   parent_artifact_id, created_at, updated_at
            FROM project_artifacts
            WHERE {where}
            ORDER BY stage, created_at DESC
            """,
            params,
        ).fetchall()

    # Group by stage
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        d = _row_to_dict(r)
        d["payload"] = _parse_json_field(d.pop("payload_json", None), {})
        d["metadata"] = _parse_json_field(d.pop("metadata_json", None), {})
        grouped.setdefault(d["stage"], []).append(d)

    return {"topic_id": topic_id, "artifacts_by_stage": grouped}


@app.get("/api/topics/{topic_id}/events")
def list_topic_events(topic_id: int):
    with get_db() as conn:
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        rows = conn.execute(
            """
            SELECT e.*
            FROM orchestrator_stage_events e
            WHERE e.topic_id = ?
            ORDER BY e.created_at DESC
            """,
            (topic_id,),
        ).fetchall()

    events = []
    for r in rows:
        d = _row_to_dict(r)
        d["payload"] = _parse_json_field(d.pop("payload_json", None), {})
        events.append(d)

    return {"topic_id": topic_id, "events": events}


class RecordArtifactRequest(BaseModel):
    artifact_type: str
    content: str
    stage: str | None = None


@app.post("/api/topics/{topic_id}/artifacts")
def record_artifact(topic_id: int, body: RecordArtifactRequest):
    """Record an artifact for the topic's current (or specified) stage."""
    return _run_tool(
        "orchestrator_record_artifact",
        {
            "topic_id": topic_id,
            "artifact_type": body.artifact_type,
            "content": body.content,
            **({"stage": body.stage} if body.stage else {}),
        },
    )


class ForceAdvanceRequest(BaseModel):
    target_stage: str | None = None
    actor: str = "web_ui"


@app.post("/api/topics/{topic_id}/force-advance")
def force_advance_topic(topic_id: int, body: ForceAdvanceRequest):
    """Force-advance a topic to the next (or specified) stage, skipping gate checks.

    This is for demo / development use. In production, use /advance which
    respects artifact gates.
    """
    stages = ["init", "build", "analyze", "propose", "experiment", "write"]
    with get_db() as conn:
        run = conn.execute(
            """
            SELECT id, current_stage FROM orchestrator_runs
            WHERE topic_id = ?
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (topic_id,),
        ).fetchone()
        if not run:
            raise HTTPException(
                status_code=404,
                detail=f"No orchestrator run found for topic {topic_id}",
            )
        current = run["current_stage"] or "init"
        if body.target_stage:
            next_stage = body.target_stage
        else:
            idx = stages.index(current) if current in stages else 0
            next_stage = stages[min(idx + 1, len(stages) - 1)]
        conn.execute(
            "UPDATE orchestrator_runs SET current_stage = ?, "
            "stage_status = 'in_progress', updated_at = datetime('now') "
            "WHERE id = ?",
            (next_stage, run["id"]),
        )
        conn.commit()
    return {
        "topic_id": topic_id,
        "previous_stage": current,
        "current_stage": next_stage,
    }


@app.get("/api/topics/{topic_id}/decisions")
def list_topic_decisions(topic_id: int):
    """Return decision_log entries for this topic, newest first."""
    with get_db() as conn:
        try:
            rows = conn.execute(
                """
                SELECT id, project_id, topic_id, stage, checkpoint, choice,
                       reasoning, params_snapshot, created_at, actor, origin
                FROM decision_log
                WHERE topic_id = ?
                ORDER BY created_at DESC
                """,
                (topic_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            # Legacy DBs pre-migration 055 — fall back to the smaller column set.
            try:
                rows = conn.execute(
                    """
                    SELECT id, project_id, topic_id, stage, checkpoint, choice,
                           reasoning, params_snapshot, created_at
                    FROM decision_log
                    WHERE topic_id = ?
                    ORDER BY created_at DESC
                    """,
                    (topic_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

    decisions = []
    for r in rows:
        d = _row_to_dict(r)
        d["params"] = _parse_json_field(d.pop("params_snapshot", None), {})
        d.setdefault("actor", None)
        d.setdefault("origin", None)
        decisions.append(d)

    return {"topic_id": topic_id, "decisions": decisions}


# ---------------------------------------------------------------------------
# Audit drilldown (PR 1 — migration 055)
# ---------------------------------------------------------------------------

_STAGE_KEYS = ("init", "build", "analyze", "propose", "experiment", "write")


@app.get("/api/topics/{topic_id}/primitives")
def list_topic_primitives(topic_id: int, stage: str | None = None):
    """Primitive executions for this topic, optionally scoped to a stage.

    Backs the topic drilldown Trace tab. Returns columns from
    `provenance_records` including the new audit fields (actor/origin/
    retry_ordinal/cache_hit/skipped/skip_reason). Rows are ordered newest
    first.
    """
    if stage is not None and stage not in _STAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown stage {stage!r}")

    with get_db() as conn:
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        clauses = ["topic_id = ?"]
        params: list[Any] = [topic_id]
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        where = " AND ".join(clauses)

        try:
            rows = conn.execute(
                f"""
                SELECT id, primitive, category, started_at, finished_at,
                       backend, model_used, stage, cost_usd, success, error,
                       prompt_tokens, completion_tokens, loop_round,
                       actor, origin, retry_ordinal, cache_hit,
                       parallel_group, skipped, skip_reason,
                       artifact_id, quality_score, created_at
                FROM provenance_records
                WHERE {where}
                ORDER BY started_at DESC
                LIMIT 500
                """,
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            # Legacy DB without the 055 audit columns — retry with base set.
            rows = conn.execute(
                f"""
                SELECT id, primitive, category, started_at, finished_at,
                       backend, model_used, stage, cost_usd, success, error,
                       prompt_tokens, completion_tokens, loop_round,
                       artifact_id, quality_score, created_at
                FROM provenance_records
                WHERE {where}
                ORDER BY started_at DESC
                LIMIT 500
                """,
                params,
            ).fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = _row_to_dict(r)
        d.setdefault("actor", None)
        d.setdefault("origin", None)
        d.setdefault("retry_ordinal", 0)
        d.setdefault("cache_hit", 0)
        d.setdefault("parallel_group", None)
        d.setdefault("skipped", 0)
        d.setdefault("skip_reason", None)
        d["cache_hit"] = bool(d.get("cache_hit") or 0)
        d["skipped"] = bool(d.get("skipped") or 0)
        d["success"] = bool(d.get("success") or 0)
        out.append(d)

    return {"topic_id": topic_id, "stage": stage, "primitives": out}


@app.get("/api/topics/{topic_id}/stage-policy/{stage}")
def get_topic_stage_policy(topic_id: int, stage: str):
    """Serialize STAGE_POLICIES + invariants + loopback state for one stage."""
    if stage not in _STAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown stage {stage!r}")

    try:
        from research_harness.auto_runner.stage_policy import STAGE_POLICIES
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"stage policy unavailable: {exc}")

    policy = STAGE_POLICIES.get(stage)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"No policy for stage {stage}")

    policy_dict = {
        "name": policy.name,
        "tools": list(policy.tools),
        "codex": policy.codex,
        "codex_focus": policy.codex_focus,
        "human_checkpoint": policy.human_checkpoint,
        "retry": policy.retry,
        "max_codex_rounds": policy.max_codex_rounds,
        "description": policy.description,
        "autonomous_allowed": policy.autonomous_allowed,
        "risk_level": policy.risk_level,
        "approval_policy": policy.approval_policy,
        "expansion_paper_budget": policy.expansion_paper_budget,
    }

    # Invariants — deterministic pre-gate checks on current DB state
    invariant_violations: list[dict[str, Any]] = []
    try:
        from research_harness.orchestrator.invariants import InvariantChecker
        from research_harness.storage.db import Database as _Db

        db = _Db(DB_PATH)
        checker = InvariantChecker(db)
        violations = checker.check_all(topic_id, stage)
        for v in violations:
            invariant_violations.append(
                {
                    "check": getattr(v, "check", ""),
                    "severity": getattr(v, "severity", ""),
                    "message": getattr(v, "message", ""),
                    "artifact_id": getattr(v, "artifact_id", None),
                }
            )
    except Exception as exc:
        logger.debug("invariant check failed for %s/%s: %s", topic_id, stage, exc)

    # Loopback state — how many rounds of auto-loopback have fired toward stage
    loopback_state: dict[str, Any] = {
        "rounds_used": 0,
        "rounds_max": 0,
        "last_trigger": None,
    }
    try:
        from research_harness.orchestrator.service import OrchestratorService

        rounds_max = 0
        for (from_stage, _decision), (
            target,
            max_rounds,
            _reason,
            _checkpoint,
        ) in OrchestratorService.AUTO_LOOPBACK_RULES.items():
            if from_stage == stage or target == stage:
                rounds_max = max(rounds_max, int(max_rounds))

        with get_db() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       MAX(created_at) AS last_at,
                       (SELECT trigger FROM rollback_log
                        WHERE topic_id = ? AND to_stage = ?
                        ORDER BY created_at DESC LIMIT 1) AS last_trigger
                FROM rollback_log
                WHERE topic_id = ? AND to_stage = ?
                """,
                (topic_id, stage, topic_id, stage),
            ).fetchone()
            if row is not None:
                loopback_state = {
                    "rounds_used": int(row["n"] or 0),
                    "rounds_max": rounds_max,
                    "last_trigger": row["last_trigger"],
                }
    except Exception as exc:
        logger.debug("loopback state lookup failed: %s", exc)

    return {
        "topic_id": topic_id,
        "stage": stage,
        "policy": policy_dict,
        "invariant_violations": invariant_violations,
        "loopback_state": loopback_state,
    }


@app.get("/api/topics/{topic_id}/stage-summary/{stage}")
def get_topic_stage_summary(topic_id: int, stage: str):
    """Counts + aggregate stats for a single stage.

    Drives the drawer header strip (planned / ran / skipped / cost / tokens).
    """
    if stage not in _STAGE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown stage {stage!r}")

    try:
        from research_harness.auto_runner.stage_policy import STAGE_POLICIES
    except Exception:
        STAGE_POLICIES = {}  # type: ignore[assignment]

    policy = STAGE_POLICIES.get(stage)
    planned = len(policy.tools) if policy is not None else 0

    with get_db() as conn:
        try:
            agg = conn.execute(
                """
                SELECT
                    COUNT(*) AS rows_total,
                    SUM(CASE WHEN COALESCE(skipped, 0) = 0 THEN 1 ELSE 0 END) AS ran,
                    SUM(CASE WHEN COALESCE(skipped, 0) = 1 THEN 1 ELSE 0 END) AS skipped_n,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failed,
                    SUM(COALESCE(prompt_tokens, 0) + COALESCE(completion_tokens, 0)) AS tokens,
                    SUM(COALESCE(cost_usd, 0)) AS cost_usd,
                    MIN(started_at) AS first_at,
                    MAX(finished_at) AS last_at
                FROM provenance_records
                WHERE topic_id = ? AND stage = ?
                """,
                (topic_id, stage),
            ).fetchone()
        except sqlite3.OperationalError:
            agg = None

        rubric_row = None
        try:
            rubric_row = conn.execute(
                """
                SELECT weighted_total, verdict, shadow_verdict, scored_at
                FROM rubric_scores
                WHERE topic_id = ? AND stage = ?
                ORDER BY scored_at DESC
                LIMIT 1
                """,
                (topic_id, stage),
            ).fetchone()
        except sqlite3.OperationalError:
            pass

    # Invariant violation count (reuse checker if available)
    inv_count = 0
    try:
        from research_harness.orchestrator.invariants import InvariantChecker
        from research_harness.storage.db import Database as _Db

        db = _Db(DB_PATH)
        inv_count = len(InvariantChecker(db).check_all(topic_id, stage))
    except Exception:
        pass

    def _i(key: str) -> int:
        if agg is None:
            return 0
        val = agg[key]
        return int(val or 0)

    def _f(key: str) -> float:
        if agg is None:
            return 0.0
        val = agg[key]
        return float(val or 0.0)

    duration_sec = 0.0
    if agg is not None and agg["first_at"] and agg["last_at"]:
        try:
            first = datetime.fromisoformat(str(agg["first_at"]).replace("Z", "+00:00"))
            last = datetime.fromisoformat(str(agg["last_at"]).replace("Z", "+00:00"))
            duration_sec = max(0.0, (last - first).total_seconds())
        except (ValueError, TypeError):
            duration_sec = 0.0

    rubric_dict: dict[str, Any] | None = None
    if rubric_row is not None:
        rubric_dict = {
            "weighted_total": float(rubric_row["weighted_total"] or 0.0),
            "verdict": rubric_row["verdict"],
            "shadow_verdict": rubric_row["shadow_verdict"],
            "scored_at": rubric_row["scored_at"],
        }

    # Soft-completion evidence: counts of artifacts/claims/gaps that exist
    # for this topic+stage even when no orchestrator primitives ran. Used by
    # the frontend to mark legacy/backfilled stages as "has work" instead of
    # showing "0/N" forever.
    evidence_count = 0
    evidence_breakdown: dict[str, int] = {}
    with get_db() as conn:
        try:
            artifact_n = conn.execute(
                "SELECT COUNT(*) AS n FROM project_artifacts "
                "WHERE topic_id = ? AND stage = ?",
                (topic_id, stage),
            ).fetchone()
            evidence_breakdown["artifacts"] = (
                int(artifact_n["n"] or 0) if artifact_n else 0
            )
        except sqlite3.OperationalError:
            evidence_breakdown["artifacts"] = 0

        if stage == "init":
            # Init "done" signal: topic_intake_profile row exists
            try:
                ip_n = conn.execute(
                    "SELECT COUNT(*) AS n FROM topic_intake_profile WHERE topic_id = ?",
                    (topic_id,),
                ).fetchone()
                evidence_breakdown["intake_profile"] = (
                    int(ip_n["n"] or 0) if ip_n else 0
                )
            except sqlite3.OperationalError:
                evidence_breakdown["intake_profile"] = 0

        if stage == "build":
            try:
                paper_n = conn.execute(
                    "SELECT COUNT(*) AS n FROM paper_topics WHERE topic_id = ?",
                    (topic_id,),
                ).fetchone()
                evidence_breakdown["papers"] = int(paper_n["n"] or 0) if paper_n else 0
            except sqlite3.OperationalError:
                evidence_breakdown["papers"] = 0

        if stage in ("analyze", "propose"):
            try:
                claim_n = conn.execute(
                    "SELECT COUNT(*) AS n FROM normalized_claims WHERE topic_id = ?",
                    (topic_id,),
                ).fetchone()
                evidence_breakdown["claims"] = int(claim_n["n"] or 0) if claim_n else 0
            except sqlite3.OperationalError:
                evidence_breakdown["claims"] = 0

        if stage == "analyze":
            try:
                gap_n = conn.execute(
                    "SELECT COUNT(*) AS n FROM gaps WHERE topic_id = ?",
                    (topic_id,),
                ).fetchone()
                evidence_breakdown["gaps"] = int(gap_n["n"] or 0) if gap_n else 0
            except sqlite3.OperationalError:
                evidence_breakdown["gaps"] = 0

    evidence_count = sum(evidence_breakdown.values())

    return {
        "topic_id": topic_id,
        "stage": stage,
        "primitives_planned": planned,
        "primitives_ran": _i("ran"),
        "primitives_skipped": _i("skipped_n"),
        "primitives_failed": _i("failed"),
        "total_tokens": _i("tokens"),
        "total_cost_usd": _f("cost_usd"),
        "duration_sec": duration_sec,
        "invariant_violations_count": inv_count,
        "rubric": rubric_dict,
        "evidence_count": evidence_count,
        "evidence_breakdown": evidence_breakdown,
    }


@app.get("/api/topics/{topic_id}/experiments")
def list_topic_experiments(topic_id: int):
    """Return autonomous-loop experiments for this topic, newest first."""
    with get_db() as conn:
        try:
            rows = conn.execute(
                """
                SELECT id, topic_id, name, task_description, primary_metric,
                       direction, mode, status, stopped_reason, best_run_id,
                       budget_json, created_at, updated_at
                FROM experiments
                WHERE topic_id = ?
                ORDER BY created_at DESC
                """,
                (topic_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        experiments = []
        for r in rows:
            d = _row_to_dict(r)
            d["budget"] = _parse_json_field(d.pop("budget_json", None), {})
            if d.get("best_run_id"):
                try:
                    best = conn.execute(
                        "SELECT iteration, primary_metric_value, cost_usd, tokens_used "
                        "FROM experiment_loop_runs WHERE id = ?",
                        (d["best_run_id"],),
                    ).fetchone()
                    d["best"] = _row_to_dict(best) if best else None
                except sqlite3.OperationalError:
                    d["best"] = None
            else:
                d["best"] = None
            experiments.append(d)

    return {"topic_id": topic_id, "experiments": experiments}


class CreateExperimentRequest(BaseModel):
    """Body for POST /api/topics/{topic_id}/experiments."""

    name: str = ""
    task_description: str
    fixture_files: dict[str, str] = Field(default_factory=dict)
    mutable_entry: str = "main.py"
    primary_metric: str
    direction: str = "max"
    mode: str = "agent"
    timeout_sec: float = 300.0
    env_vars: dict[str, str] = Field(default_factory=dict)
    max_iterations: int = 5
    max_cost_usd: float = 0.0
    max_tokens: int = 0
    patience: int = 3


@app.post("/api/topics/{topic_id}/experiments")
def create_topic_experiment(topic_id: int, req: CreateExperimentRequest):
    """Launch an autonomous experiment_loop for this topic.

    Runs synchronously — returns the ExperimentLoopOutput once the loop
    finishes (patience/budget/max_iterations stopped it). For long-running
    experiments the caller should use shorter budgets and poll
    GET /api/experiments/{id}/runs for progress.
    """
    from research_harness.primitives.experiment_loop_impl import experiment_loop
    from research_harness.primitives.types import ExperimentBudget
    from research_harness.storage.db import Database

    db = Database(db_path=DB_PATH)

    out = experiment_loop(
        db=db,
        topic_id=topic_id,
        name=req.name,
        task_description=req.task_description,
        fixture_files=req.fixture_files,
        mutable_entry=req.mutable_entry,
        primary_metric=req.primary_metric,
        direction=req.direction,
        mode=req.mode,
        timeout_sec=req.timeout_sec,
        env_vars=req.env_vars,
        budget=ExperimentBudget(
            max_iterations=req.max_iterations,
            max_cost_usd=req.max_cost_usd,
            max_tokens=req.max_tokens,
            patience=req.patience,
        ),
    )

    return {
        "experiment_id": out.experiment_id,
        "total_iterations": out.total_iterations,
        "best_iteration": out.best_iteration,
        "best_value": out.best_value,
        "best_run_id": out.best_run_id,
        "stopped_reason": out.stopped_reason,
        "total_cost_usd": out.total_cost_usd,
        "total_tokens": out.total_tokens,
    }


@app.get("/api/experiments/{experiment_id}/runs")
def list_experiment_runs(experiment_id: int):
    """Return per-iteration records for one experiment (leaderboard view)."""
    with get_db() as conn:
        try:
            exp = conn.execute(
                """
                SELECT id, topic_id, name, primary_metric, direction, mode,
                       status, stopped_reason, best_run_id
                FROM experiments WHERE id = ?
                """,
                (experiment_id,),
            ).fetchone()
            rows = conn.execute(
                """
                SELECT id, iteration, code_hash, primary_metric_value,
                       elapsed_sec, cost_usd, tokens_used, status, returncode,
                       stdout_tail, stderr_tail, feedback_to_next, created_at
                FROM experiment_loop_runs
                WHERE experiment_id = ?
                ORDER BY iteration ASC
                """,
                (experiment_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            exp, rows = None, []

    if exp is None:
        return {"experiment": None, "runs": []}

    return {
        "experiment": _row_to_dict(exp),
        "runs": [_row_to_dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Stats / Dashboard
# ---------------------------------------------------------------------------


@app.get("/api/stats", response_model=DashboardStats)
def dashboard_stats():
    with get_db() as conn:
        total_papers = conn.execute("SELECT COUNT(*) AS c FROM papers").fetchone()["c"]
        total_topics = conn.execute("SELECT COUNT(*) AS c FROM topics").fetchone()["c"]
        total_domains = conn.execute("SELECT COUNT(*) AS c FROM domains").fetchone()[
            "c"
        ]
        total_artifacts = conn.execute(
            "SELECT COUNT(*) AS c FROM project_artifacts"
        ).fetchone()["c"]
        total_provenance = conn.execute(
            "SELECT COUNT(*) AS c FROM provenance_records"
        ).fetchone()["c"]
        papers_with_pdf = conn.execute(
            "SELECT COUNT(*) AS c FROM papers WHERE pdf_path IS NOT NULL AND pdf_path != ''"
        ).fetchone()["c"]

        recent_papers = conn.execute(
            """
            SELECT id, title, venue, year, status, created_at
            FROM papers
            ORDER BY created_at DESC
            LIMIT 10
            """
        ).fetchall()

        recent_events = conn.execute(
            """
            SELECT e.id, e.topic_id, e.from_stage, e.to_stage,
                   e.event_type, e.status, e.actor, e.created_at
            FROM orchestrator_stage_events e
            ORDER BY e.created_at DESC
            LIMIT 10
            """
        ).fetchall()

    return DashboardStats(
        total_papers=total_papers,
        total_topics=total_topics,
        total_domains=total_domains,
        total_artifacts=total_artifacts,
        total_provenance_records=total_provenance,
        papers_with_pdf=papers_with_pdf,
        recent_papers=_rows_to_list(recent_papers),
        recent_events=_rows_to_list(recent_events),
    )


@app.get("/api/provenance/summary", response_model=ProvenanceSummary)
def provenance_summary(topic_id: int | None = None):
    """Aggregate provenance metrics, optionally scoped to a single topic."""
    where_sql = ""
    params: tuple = ()
    if topic_id is not None:
        where_sql = " WHERE topic_id = ?"
        params = (topic_id,)

    try:
        with get_db() as conn:
            totals = conn.execute(
                f"""
                SELECT COUNT(*) AS total_records,
                       COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                       COALESCE(SUM(prompt_tokens), 0) AS total_prompt,
                       COALESCE(SUM(completion_tokens), 0) AS total_completion
                FROM provenance_records{where_sql}
                """,
                params,
            ).fetchone()

            by_backend = conn.execute(
                f"""
                SELECT backend,
                       model_used,
                       COUNT(*) AS call_count,
                       COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                       COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) AS completion_tokens
                FROM provenance_records{where_sql}
                GROUP BY backend, model_used
                ORDER BY total_cost DESC
                """,
                params,
            ).fetchall()

            by_primitive = conn.execute(
                f"""
                SELECT primitive,
                       COUNT(*) AS call_count,
                       COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                       COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success_count,
                       SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failure_count
                FROM provenance_records{where_sql}
                GROUP BY primitive
                ORDER BY call_count DESC
                LIMIT 30
                """,
                params,
            ).fetchall()

            recent = conn.execute(
                f"""
                SELECT id, primitive, backend, model_used, cost_usd,
                       prompt_tokens, completion_tokens, success, created_at
                FROM provenance_records{where_sql}
                ORDER BY created_at DESC
                LIMIT 20
                """,
                params,
            ).fetchall()

        return ProvenanceSummary(
            total_records=totals["total_records"],
            total_cost_usd=round(totals["total_cost"], 4),
            total_prompt_tokens=totals["total_prompt"] or 0,
            total_completion_tokens=totals["total_completion"] or 0,
            by_backend=_rows_to_list(by_backend),
            by_primitive=_rows_to_list(by_primitive),
            recent_records=_rows_to_list(recent),
        )
    except (sqlite3.OperationalError, sqlite3.ProgrammingError):
        return ProvenanceSummary(
            total_records=0,
            total_cost_usd=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            by_backend=[],
            by_primitive=[],
            recent_records=[],
        )


@app.get("/api/usage/daily")
def usage_daily(
    days: int = Query(30, ge=1, le=365),
    topic_id: int | None = Query(None),
):
    """Aggregate daily token usage from both token_ledger and provenance_records."""
    where_parts: list[str] = []
    params: list[Any] = []

    if topic_id is not None:
        where_parts.append("topic_id = ?")
        params.append(topic_id)

    where_sql = (" AND " + " AND ".join(where_parts)) if where_parts else ""

    ledger_rows: list = []
    prov_rows: list = []

    with get_db() as conn:
        try:
            ledger_rows = conn.execute(
                f"""
                SELECT substr(ts, 1, 10) AS day,
                       SUM(prompt_tokens) AS prompt_tokens,
                       SUM(completion_tokens) AS completion_tokens,
                       COALESCE(SUM(cost_usd), 0.0) AS cost_usd,
                       COUNT(*) AS calls
                FROM token_ledger
                WHERE ts >= date('now', '-' || ? || ' days'){where_sql}
                GROUP BY day ORDER BY day
                """,
                [days] + params,
            ).fetchall()
        except sqlite3.OperationalError:
            pass

        try:
            prov_rows = conn.execute(
                f"""
                SELECT substr(created_at, 1, 10) AS day,
                       SUM(prompt_tokens) AS prompt_tokens,
                       SUM(completion_tokens) AS completion_tokens,
                       COALESCE(SUM(cost_usd), 0.0) AS cost_usd,
                       COUNT(*) AS calls
                FROM provenance_records
                WHERE created_at >= date('now', '-' || ? || ' days'){where_sql}
                GROUP BY day ORDER BY day
                """,
                [days] + params,
            ).fetchall()
        except sqlite3.OperationalError:
            pass

    merged: dict[str, dict] = {}
    for source, rows in [("ledger", ledger_rows), ("provenance", prov_rows)]:
        for r in rows:
            day = r["day"]
            if day not in merged:
                merged[day] = {
                    "day": day,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            merged[day]["prompt_tokens"] += r["prompt_tokens"] or 0
            merged[day]["completion_tokens"] += r["completion_tokens"] or 0
            merged[day]["cost_usd"] += r["cost_usd"] or 0.0
            merged[day]["calls"] += r["calls"] or 0

    return sorted(merged.values(), key=lambda x: x["day"])


# ---------------------------------------------------------------------------
# Review Issues
# ---------------------------------------------------------------------------


@app.get("/api/topics/{topic_id}/issues")
def list_topic_issues(
    topic_id: int,
    status: str | None = Query(
        None, description="Filter: open, in_progress, resolved, wontfix"
    ),
    blocking_only: bool = Query(False),
):
    with get_db() as conn:
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        conditions = ["topic_id = ?"]
        params: list[Any] = [topic_id]

        if status:
            conditions.append("status = ?")
            params.append(status)

        if blocking_only:
            conditions.append("blocking = 1")

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"""
            SELECT *
            FROM review_issues
            WHERE {where}
            ORDER BY created_at DESC
            """,
            params,
        ).fetchall()

    return {"topic_id": topic_id, "issues": _rows_to_list(rows)}


# ===========================================================================
# WRITE / ACTION ENDPOINTS
# ===========================================================================
#
# These endpoints mutate state — either via raw SQL INSERT or by delegating
# to MCP tool handlers through execute_tool(name, arguments).
# ---------------------------------------------------------------------------


def _run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call execute_tool and translate errors into HTTP 500."""
    try:
        return execute_tool(name, arguments)
    except Exception as exc:
        logger.error(
            "execute_tool(%s) failed: %s\n%s", name, exc, traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_result(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _topic_exists(conn: sqlite3.Connection, topic_id: int) -> bool:
    row = conn.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,)).fetchone()
    return row is not None


def _search_papers_impl(
    api: ResearchAPI, *, query: str, topic_id: int | None = None, max_results: int = 50
) -> dict[str, Any]:
    args: dict[str, Any] = {"query": query, "max_results": max_results}
    if topic_id is not None:
        args["topic_id"] = topic_id
    return _serialize_result(api.paper_search(**args))


def _ingest_paper_impl(
    api: ResearchAPI,
    *,
    source: str,
    topic_id: int | None = None,
    relevance: str = "medium",
) -> dict[str, Any]:
    args: dict[str, Any] = {"source": source, "relevance": relevance}
    if topic_id is not None:
        args["topic_id"] = topic_id
    return _serialize_result(api.paper_ingest(**args))


def _deep_read_paper_impl(
    api: ResearchAPI, *, paper_id: int, topic_id: int, focus: str = ""
) -> dict[str, Any]:
    args: dict[str, Any] = {"paper_id": paper_id, "topic_id": topic_id}
    if focus:
        args["focus"] = focus
    result = execute_tool("deep_read", args)
    with get_db() as conn:
        conn.execute(
            "UPDATE papers SET deep_read = 1 WHERE id = ?",
            (paper_id,),
        )
        conn.commit()
    return _serialize_result(result)


def _get_latest_expansion_job(
    conn: sqlite3.Connection, topic_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, status, retrieval_target, deep_read_target, rounds_target,
               current_round, papers_fetched, papers_deep_read, last_error,
               created_at, updated_at
        FROM expansion_jobs
        WHERE topic_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (topic_id,),
    ).fetchone()


def _topic_paper_stats(conn: sqlite3.Connection, topic_id: int) -> dict[str, int]:
    """Return total and deep-read paper counts for a topic."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN COALESCE(p.deep_read, 0) = 1 THEN 1 ELSE 0 END), 0) AS deep_read
        FROM papers p
        JOIN paper_topics pt ON pt.paper_id = p.id
        WHERE pt.topic_id = ?
        """,
        (topic_id,),
    ).fetchone()
    if row is None:
        return {"total": 0, "deep_read": 0}
    return {"total": int(row["total"] or 0), "deep_read": int(row["deep_read"] or 0)}


def _expansion_job_is_cancelled(job_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT status FROM expansion_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row is not None and row["status"] == "cancelled"


def _update_expansion_job(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    status: str | None = None,
    current_round: int | None = None,
    papers_fetched: int | None = None,
    papers_deep_read: int | None = None,
    last_error: str | None = None,
) -> None:
    updates: dict[str, Any] = {"updated_at": _now_iso()}
    if status is not None:
        updates["status"] = status
    if current_round is not None:
        updates["current_round"] = current_round
    if papers_fetched is not None:
        updates["papers_fetched"] = papers_fetched
    if papers_deep_read is not None:
        updates["papers_deep_read"] = papers_deep_read
    if last_error is not None:
        updates["last_error"] = last_error[:2000]
    set_clause = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(
        f"UPDATE expansion_jobs SET {set_clause} WHERE id = ?",
        [*updates.values(), job_id],
    )
    conn.commit()


def _pick_candidate_source(candidate: dict[str, Any]) -> str:
    for key in ("arxiv_id", "doi", "url", "title"):
        value = str(candidate.get(key) or "").strip()
        if value:
            return value
    return ""


def _paper_already_in_topic(
    conn: sqlite3.Connection, topic_id: int, source: str
) -> bool:
    if source.startswith("10."):
        clause = "p.doi = ?"
    elif "/" not in source and len(source) < 20:
        clause = "p.arxiv_id = ?"
    else:
        clause = "p.title = ? OR p.url = ?"
    params: list[Any] = [topic_id, source]
    if " OR " in clause:
        params.append(source)
    row = conn.execute(
        f"""
        SELECT 1
        FROM papers p
        JOIN paper_topics pt ON pt.paper_id = p.id
        WHERE pt.topic_id = ? AND ({clause})
        LIMIT 1
        """,
        params,
    ).fetchone()
    return row is not None


def _build_expansion_query(
    conn: sqlite3.Connection, topic_id: int, topic_name: str, topic_description: str
) -> str:
    base = " ".join(
        part.strip() for part in (topic_name, topic_description) if part.strip()
    )
    row_limit = 5
    rows = conn.execute(
        """
        SELECT p.title
        FROM papers p
        JOIN paper_topics pt ON pt.paper_id = p.id
        WHERE pt.topic_id = ?
        ORDER BY CASE pt.relevance
                    WHEN 'high' THEN 3
                    WHEN 'medium' THEN 2
                    ELSE 1
                 END DESC,
                 COALESCE(p.year, 0) DESC,
                 p.id DESC
        LIMIT ?
        """,
        (topic_id, row_limit),
    ).fetchall()
    phrases: list[str] = []
    for row in rows:
        title = str(row["title"] or "").strip()
        if not title:
            continue
        words = [word for word in title.split() if len(word) > 3][:6]
        phrase = " ".join(words).strip()
        if phrase:
            phrases.append(phrase)
    return " ".join(part for part in [base, *phrases[:3]] if part).strip() or topic_name


def _deep_read_provider_pool() -> list[str]:
    """Build the agent pool used to fan out expansion deep-reads.

    Respects ``RESEARCH_HARNESS_DEEP_READ_PROVIDERS`` (comma-separated, e.g.
    ``anthropic,cursor_agent``) when set; otherwise falls back to every
    provider that `llm_router.available_providers()` reports as usable.

    Returns ``[""]`` (single empty slot) when nothing is configured — the
    worker then defaults to the tier-routed provider and still benefits from
    parallelism.
    """
    override = os.environ.get("RESEARCH_HARNESS_DEEP_READ_PROVIDERS", "").strip()
    if override:
        pool = [p.strip() for p in override.split(",") if p.strip()]
        if pool:
            return pool
    try:
        from llm_router import available_providers as _available
    except Exception:
        return [""]
    pool = _available()
    return pool or [""]


def _expansion_deep_read_concurrency(pool_size: int) -> int:
    """Max concurrent deep-read workers.

    Defaults to ``max(2, pool_size * 2)`` capped at 8 — enough to saturate
    I/O-bound LLM calls without blowing through per-provider rate limits.
    Override via ``RESEARCH_HARNESS_DEEP_READ_CONCURRENCY``.
    """
    raw = os.environ.get("RESEARCH_HARNESS_DEEP_READ_CONCURRENCY", "").strip()
    if raw:
        try:
            n = int(raw)
            if n >= 1:
                return min(n, 16)
        except ValueError:
            pass
    return min(8, max(2, max(1, pool_size) * 2))


def _expansion_deep_read_paper_timeout() -> float:
    """Wall-clock cap per deep-read paper, in seconds.

    A hung upstream (proxy error, Anthropic SDK socket read block)
    can stall a worker forever. The expansion loop uses this as a hard cap
    via ``Future.result(timeout=...)`` so a stuck provider only costs us
    one paper, not the whole batch. Default 300s (enough for 2 LLM passes on
    a 2000-word abstract). Override via
    ``RESEARCH_HARNESS_DEEP_READ_TIMEOUT`` (seconds, integer).
    """
    raw = os.environ.get("RESEARCH_HARNESS_DEEP_READ_TIMEOUT", "").strip()
    if raw:
        try:
            n = int(raw)
            if n >= 30:
                return float(n)
        except ValueError:
            pass
    return 300.0


def _run_expansion_job(job_id: int, topic_id: int) -> None:
    api = ResearchAPI(db_path=DB_PATH)
    all_rounds_errored = True
    try:
        with get_db() as conn:
            topic = conn.execute(
                "SELECT id, name, description FROM topics WHERE id = ?",
                (topic_id,),
            ).fetchone()
            job = conn.execute(
                "SELECT * FROM expansion_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if topic is None or job is None:
                return
            _update_expansion_job(conn, job_id, status="running", current_round=0)
            retrieval_target = int(job["retrieval_target"])
            deep_read_target = int(job["deep_read_target"])
            rounds_target = int(job["rounds_target"])

        per_round = max(1, round(retrieval_target / rounds_target))
        seen_sources: set[str] = set()
        papers_fetched = 0
        papers_deep_read = 0
        last_error = ""
        topic_name = str(topic["name"] or "").strip()
        topic_description = str(topic["description"] or "").strip()

        for round_index in range(1, rounds_target + 1):
            if _expansion_job_is_cancelled(job_id):
                return
            with get_db() as conn:
                _update_expansion_job(conn, job_id, current_round=round_index)
                query = (
                    _build_expansion_query(
                        conn, topic_id, topic_name, topic_description
                    )
                    if round_index > 1
                    else " ".join(
                        part for part in (topic_name, topic_description) if part
                    ).strip()
                    or topic_name
                )
            round_ingested = 0
            round_error_count = 0
            round_only_errors = False
            try:
                search_out = _search_papers_impl(
                    api, query=query, topic_id=topic_id, max_results=per_round
                )
            except Exception as exc:
                last_error = str(exc)[:2000]
                round_only_errors = True
                with get_db() as conn:
                    _update_expansion_job(conn, job_id, last_error=last_error)
                continue
            provider_errors = search_out.get("provider_errors") or []
            if provider_errors:
                last_error = "; ".join(str(err) for err in provider_errors)[:2000]
                with get_db() as conn:
                    _update_expansion_job(conn, job_id, last_error=last_error)
            if not provider_errors:
                all_rounds_errored = False
            elif not (search_out.get("papers") or []):
                round_only_errors = True
            for candidate in search_out.get("papers") or []:
                if _expansion_job_is_cancelled(job_id):
                    return
                source = _pick_candidate_source(candidate)
                if not source or source in seen_sources:
                    continue
                seen_sources.add(source)
                with get_db() as conn:
                    already_linked = _paper_already_in_topic(conn, topic_id, source)
                if already_linked:
                    continue
                try:
                    ingest_out = _ingest_paper_impl(
                        api, source=source, topic_id=topic_id, relevance="high"
                    )
                except Exception as exc:
                    round_error_count += 1
                    last_error = str(exc)[:2000]
                    with get_db() as conn:
                        _update_expansion_job(conn, job_id, last_error=last_error)
                    continue
                paper_id = int(ingest_out.get("paper_id", 0) or 0)
                if paper_id:
                    with get_db() as conn:
                        linked = conn.execute(
                            "SELECT 1 FROM paper_topics WHERE topic_id = ? AND paper_id = ?",
                            (topic_id, paper_id),
                        ).fetchone()
                        if linked and not already_linked:
                            papers_fetched += 1
                            round_ingested += 1
                            _update_expansion_job(
                                conn, job_id, papers_fetched=papers_fetched
                            )
                all_rounds_errored = False
                if papers_fetched >= retrieval_target:
                    break
            if round_ingested == 0 and round_error_count == len(
                search_out.get("papers") or []
            ):
                round_only_errors = bool(search_out.get("papers"))
                with get_db() as conn:
                    _update_expansion_job(conn, job_id, last_error=last_error)
            if round_only_errors:
                continue
            if papers_fetched >= retrieval_target or round_ingested == 0:
                break

        if _expansion_job_is_cancelled(job_id):
            return

        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT p.id
                FROM papers p
                JOIN paper_topics pt ON pt.paper_id = p.id
                WHERE pt.topic_id = ? AND COALESCE(p.deep_read, 0) = 0
                ORDER BY CASE pt.relevance
                            WHEN 'high' THEN 3
                            WHEN 'medium' THEN 2
                            ELSE 1
                         END DESC,
                         COALESCE(p.year, 0) DESC,
                         p.id DESC
                LIMIT ?
                """,
                (topic_id, deep_read_target),
            ).fetchall()

        provider_pool = _deep_read_provider_pool()
        max_workers = _expansion_deep_read_concurrency(len(provider_pool))
        paper_timeout = _expansion_deep_read_paper_timeout()
        paper_ids = [int(row["id"]) for row in rows]
        progress_lock = threading.Lock()
        logger.info(
            "expansion job %d deep-read phase: %d papers, pool=%s, max_workers=%d, timeout=%.0fs",
            job_id,
            len(paper_ids),
            provider_pool,
            max_workers,
            paper_timeout,
        )

        # Per-provider failure tracking. If a provider hard-fails twice, we
        # quarantine it for the rest of this job and retry the paper with
        # another pool member. Broken-but-registered providers (e.g.
        # openai with no key) thus self-eject without
        # bringing the pool down.
        provider_failures: dict[str, int] = {}
        quarantined: set[str] = set()
        failure_lock = threading.Lock()

        def _try_provider(
            paper_id: int, provider: str
        ) -> tuple[dict[str, Any] | None, str]:
            from research_harness.execution.llm_primitives import (
                set_provider_override,
            )
            import time as _t

            set_provider_override(provider or None)
            t0 = _t.monotonic()
            try:
                result = _deep_read_paper_impl(
                    api, paper_id=paper_id, topic_id=topic_id
                )
            finally:
                set_provider_override(None)
            elapsed = _t.monotonic() - t0
            model_used = (result or {}).get("model_used", "?")
            logger.info(
                "expansion job %d paper %d provider=%s model=%s elapsed=%.1fs",
                job_id,
                paper_id,
                provider or "default",
                model_used,
                elapsed,
            )
            return result, ""

        def _record_failure(provider: str) -> bool:
            """Return True if provider is now quarantined."""
            with failure_lock:
                provider_failures[provider] = provider_failures.get(provider, 0) + 1
                if provider_failures[provider] >= 2 and provider not in quarantined:
                    quarantined.add(provider)
                    return True
                return False

        def _next_provider(tried: set[str]) -> str | None:
            if not provider_pool:
                return None
            with failure_lock:
                for p in provider_pool:
                    if p in tried:
                        continue
                    if p in quarantined:
                        continue
                    return p
            return None

        def _run_one(
            paper_id: int, initial_provider: str
        ) -> tuple[int, dict[str, Any] | None, str]:
            tried: set[str] = set()
            provider = initial_provider
            last_err = ""
            while True:
                if _expansion_job_is_cancelled(job_id):
                    return paper_id, None, ""
                if provider in quarantined:
                    nxt = _next_provider(tried)
                    if nxt is None:
                        return paper_id, None, last_err or "all providers quarantined"
                    provider = nxt
                tried.add(provider)
                try:
                    result, _ = _try_provider(paper_id, provider)
                    if result is not None and result.get("model_used") != "none":
                        return paper_id, result, ""
                    # Treat empty/"none" as a soft failure of this provider —
                    # but only record it if we still have alternatives.
                    _record_failure(provider)
                except Exception as exc:
                    last_err = f"{provider}: {str(exc)[:1500]}"
                    newly_quarantined = _record_failure(provider)
                    if not newly_quarantined and provider_failures.get(provider, 0) < 2:
                        # First failure — retry same provider once (transient).
                        continue
                nxt = _next_provider(tried)
                if nxt is None:
                    return paper_id, None, last_err or f"{provider}: empty output"
                provider = nxt

        # Explicit lifecycle (not a `with` block) because the default context
        # manager calls shutdown(wait=True), which blocks on hung workers and
        # defeats the batch timeout. We shut down with wait=False so the
        # expansion thread can move on while orphaned daemon workers die
        # naturally when the process exits.
        pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=f"expansion-{job_id}-dr"
        )
        try:
            futures = []
            for idx, pid in enumerate(paper_ids):
                provider = (
                    provider_pool[idx % len(provider_pool)] if provider_pool else ""
                )
                futures.append(pool.submit(_run_one, pid, provider))

            import concurrent.futures as _cf

            # Per-paper timeout is enforced on the as_completed() iterator,
            # not on individual fut.result() — by the time as_completed
            # yields a future, fut.result() returns instantly. Compute a
            # batch-wide budget: the slowest paper's wall cap plus slack
            # for queueing. If no progress happens inside that window we
            # treat the remaining futures as hung and bail.
            batch_timeout = paper_timeout + 60.0
            try:
                for fut in as_completed(futures, timeout=batch_timeout):
                    if _expansion_job_is_cancelled(job_id):
                        for pending in futures:
                            pending.cancel()
                        return
                    _pid, result, err = fut.result()
                    if result is not None and result.get("model_used") != "none":
                        with progress_lock:
                            papers_deep_read += 1
                            current = papers_deep_read
                        with get_db() as conn:
                            _update_expansion_job(
                                conn, job_id, papers_deep_read=current
                            )
                        all_rounds_errored = False
                    elif err:
                        last_error = err
                        with get_db() as conn:
                            _update_expansion_job(conn, job_id, last_error=last_error)
                    if papers_deep_read >= deep_read_target:
                        for pending in futures:
                            pending.cancel()
                        break
            except _cf.TimeoutError:
                hung = [f for f in futures if not f.done()]
                last_error = (
                    f"{len(hung)} deep-read worker(s) hung past "
                    f"{batch_timeout:.0f}s; moving on"
                )
                logger.warning(
                    "expansion job %d: %s",
                    job_id,
                    last_error,
                )
                for pending in hung:
                    pending.cancel()
                with get_db() as conn:
                    _update_expansion_job(conn, job_id, last_error=last_error)
        finally:
            # Do not wait for hung workers — they're daemon threads and will
            # die with the process. Cancel any still-pending submissions.
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Older Python without cancel_futures kwarg
                pool.shutdown(wait=False)

        if _expansion_job_is_cancelled(job_id):
            return
        with get_db() as conn:
            status = (
                "failed" if all_rounds_errored and papers_fetched == 0 else "completed"
            )
            _update_expansion_job(
                conn,
                job_id,
                status=status,
                last_error=last_error if status == "failed" else last_error,
            )
    except Exception as exc:
        with get_db() as conn:
            if not _expansion_job_is_cancelled(job_id):
                _update_expansion_job(
                    conn,
                    job_id,
                    status="failed",
                    last_error=str(exc)[:2000],
                )


# ---------------------------------------------------------------------------
# Topic creation
# ---------------------------------------------------------------------------


class CreateTopicRequest(BaseModel):
    name: str
    description: str = ""
    target_venue: str = ""
    deadline: str = ""
    domain_id: int | None = None


@app.post("/api/topics")
def create_topic(body: CreateTopicRequest):
    """Create a new research topic and bootstrap its orchestrator run."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        # Verify domain exists if provided
        if body.domain_id is not None:
            domain = conn.execute(
                "SELECT id FROM domains WHERE id = ?", (body.domain_id,)
            ).fetchone()
            if not domain:
                raise HTTPException(
                    status_code=404, detail=f"Domain {body.domain_id} not found"
                )

        cur = conn.execute(
            """
            INSERT INTO topics (name, description, status, target_venue, deadline,
                                domain_id, created_at)
            VALUES (?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                body.name,
                body.description,
                body.target_venue,
                body.deadline,
                body.domain_id,
                now,
            ),
        )
        conn.commit()
        topic_id = cur.lastrowid

    # Bootstrap orchestrator run
    orch_result = _run_tool("orchestrator_resume", {"topic_id": topic_id})

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT t.*, d.name AS domain_name
            FROM topics t
            LEFT JOIN domains d ON d.id = t.domain_id
            WHERE t.id = ?
            """,
            (topic_id,),
        ).fetchone()

    result = _row_to_dict(row)
    result["orchestrator"] = orch_result
    return result


@app.patch("/api/topics/{topic_id}")
def update_topic(topic_id: int, body: PatchTopicRequest):
    """Partial update. Only fields explicitly present in the body are changed.

    Pass `domain_id: null` to unassign; omit `domain_id` to leave it untouched.
    """
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    allowed = {"name", "description", "domain_id", "target_venue", "deadline", "status"}
    updates = {k: v for k, v in patch.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

        if "domain_id" in updates and updates["domain_id"] is not None:
            dom = conn.execute(
                "SELECT id FROM domains WHERE id = ?", (updates["domain_id"],)
            ).fetchone()
            if not dom:
                raise HTTPException(
                    status_code=404,
                    detail=f"Domain {updates['domain_id']} not found",
                )

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [topic_id]
        conn.execute(f"UPDATE topics SET {set_clause} WHERE id = ?", params)
        conn.commit()

        row = conn.execute(
            """
            SELECT t.*, d.name AS domain_name,
                   (SELECT COUNT(*) FROM paper_topics pt WHERE pt.topic_id = t.id)
                       AS paper_count
            FROM topics t
            LEFT JOIN domains d ON d.id = t.domain_id
            WHERE t.id = ?
            """,
            (topic_id,),
        ).fetchone()
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Intake Profile
# ---------------------------------------------------------------------------


class IntakeProfileBody(BaseModel):
    persona: Literal[
        "p1_no_domain", "p2_domain_no_topic", "p3_topic_weak", "p4_topic_strong"
    ]
    domain_confidence: int = Field(ge=0, le=100)
    topic_confidence: int = Field(ge=0, le=100)
    venue_constraint: Literal["locked", "preferred", "open"]
    target_venue: str | None = None
    compute_budget: Literal["cpu_only", "single_gpu", "multi_gpu", "cluster"]
    time_to_deadline_days: int | None = None
    seed_present: int = 0
    raw_notes: str | None = None


@app.get("/api/topics/{topic_id}/intake-profile")
def get_intake_profile(topic_id: int):
    with get_db() as conn:
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        row = conn.execute(
            "SELECT * FROM topic_intake_profile WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        if not row:
            return None
    return _row_to_dict(row)


@app.put("/api/topics/{topic_id}/intake-profile")
def put_intake_profile(topic_id: int, body: IntakeProfileBody):
    with get_db() as conn:
        topic = conn.execute(
            "SELECT id FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        conn.execute(
            """INSERT INTO topic_intake_profile
               (topic_id, persona, domain_confidence, topic_confidence,
                venue_constraint, target_venue, compute_budget,
                time_to_deadline_days, seed_present, raw_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(topic_id) DO UPDATE SET
                 persona = excluded.persona,
                 domain_confidence = excluded.domain_confidence,
                 topic_confidence = excluded.topic_confidence,
                 venue_constraint = excluded.venue_constraint,
                 target_venue = excluded.target_venue,
                 compute_budget = excluded.compute_budget,
                 time_to_deadline_days = excluded.time_to_deadline_days,
                 seed_present = excluded.seed_present,
                 raw_notes = excluded.raw_notes,
                 updated_at = CURRENT_TIMESTAMP""",
            (
                topic_id,
                body.persona,
                body.domain_confidence,
                body.topic_confidence,
                body.venue_constraint,
                body.target_venue,
                body.compute_budget,
                body.time_to_deadline_days,
                body.seed_present,
                body.raw_notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM topic_intake_profile WHERE topic_id = ?", (topic_id,)
        ).fetchone()

    _run_tool(
        "orchestrator_record_artifact",
        {
            "topic_id": topic_id,
            "artifact_type": "intake_profile",
            "title": "Intake Profile",
            "payload": body.model_dump(),
            "stage": "init",
        },
    )

    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Field Brief
# ---------------------------------------------------------------------------


@app.post("/api/topics/{topic_id}/field-brief")
def build_field_brief_endpoint(topic_id: int):
    """Build (or rebuild) a field brief from the topic's paper pool."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.field_brief_impl import build_field_brief

    db = Database(DB_PATH)
    db.migrate()
    try:
        brief = build_field_brief(topic_id, db)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return brief.model_dump()


@app.get("/api/topics/{topic_id}/field-brief")
def get_field_brief_endpoint(topic_id: int):
    """Return the latest field brief + freshness meta, or null."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.field_brief_impl import get_latest_field_brief

    db = Database(DB_PATH)
    db.migrate()
    return get_latest_field_brief(topic_id, db)


# ---------------------------------------------------------------------------
# Goal Pool
# ---------------------------------------------------------------------------


class PatchGoalRequest(BaseModel):
    status: Literal["active", "done", "skipped"] | None = None
    priority_rank: int | None = None


@app.post("/api/topics/{topic_id}/goal-pool")
def build_goal_pool_endpoint(topic_id: int):
    """Build (or rebuild) the goal pool for a topic. Requires field_brief + intake_profile."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.goal_pool_impl import build_goal_pool

    db = Database(DB_PATH)
    db.migrate()
    try:
        goals = build_goal_pool(topic_id, db)
    except RuntimeError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=500, detail=detail) from exc
    return [g.model_dump() for g in goals]


@app.get("/api/topics/{topic_id}/goals")
def list_goals_endpoint(topic_id: int):
    """List goal pool entries by priority_rank ascending."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        rows = conn.execute(
            "SELECT * FROM goal_pool WHERE topic_id = ? AND status != 'skipped' ORDER BY priority_rank ASC",
            (topic_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        if isinstance(d.get("scoring_breakdown"), str):
            try:
                d["scoring_breakdown"] = json.loads(d["scoring_breakdown"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result


@app.patch("/api/topics/{topic_id}/goals/{goal_id}")
def update_goal_endpoint(topic_id: int, goal_id: int, body: PatchGoalRequest):
    """Update a goal's status or priority_rank."""
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM goal_pool WHERE id = ? AND topic_id = ?",
            (goal_id, topic_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")

        sets = []
        vals = []
        for k, v in patch.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        vals.append(goal_id)
        conn.execute(
            f"UPDATE goal_pool SET {', '.join(sets)} WHERE id = ?",
            vals,
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM goal_pool WHERE id = ?", (goal_id,)
        ).fetchone()
    d = _row_to_dict(updated)
    if isinstance(d.get("scoring_breakdown"), str):
        try:
            d["scoring_breakdown"] = json.loads(d["scoring_breakdown"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


@app.delete("/api/topics/{topic_id}/goals/{goal_id}")
def delete_goal_endpoint(topic_id: int, goal_id: int):
    """Soft-delete a goal (set status='skipped')."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM goal_pool WHERE id = ? AND topic_id = ?",
            (goal_id, topic_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        conn.execute(
            "UPDATE goal_pool SET status = 'skipped', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (goal_id,),
        )
        conn.commit()
    return {"status": "skipped", "goal_id": goal_id}


# ---------------------------------------------------------------------------
# Method Atoms
# ---------------------------------------------------------------------------


class HarvestAtomsRequest(BaseModel):
    paper_ids: list[int]


@app.post("/api/topics/{topic_id}/method-atoms/harvest")
def harvest_atoms_endpoint(topic_id: int, body: HarvestAtomsRequest):
    """Batch-harvest method atoms from a list of papers."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    if not body.paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids list is empty")

    from research_harness.storage.db import Database
    from research_harness.primitives.harvest_atoms_impl import harvest_atoms_batch

    db = Database(DB_PATH)
    db.migrate()
    summary = harvest_atoms_batch(topic_id, body.paper_ids, db)
    return summary


@app.get("/api/topics/{topic_id}/method-atoms")
def list_atoms_endpoint(
    topic_id: int,
    atom_type: str | None = Query(default=None),
):
    """List method atoms for a topic, optionally filtered by atom_type."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        if atom_type:
            rows = conn.execute(
                "SELECT * FROM method_atoms WHERE topic_id = ? AND atom_type = ? ORDER BY id",
                (topic_id, atom_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM method_atoms WHERE topic_id = ? ORDER BY atom_type, id",
                (topic_id,),
            ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        if isinstance(d.get("deps"), str):
            try:
                d["deps"] = json.loads(d["deps"])
            except (json.JSONDecodeError, TypeError):
                d["deps"] = []
        result.append(d)
    return result


@app.delete("/api/method-atoms/{atom_id}")
def delete_atom_endpoint(atom_id: int):
    """Delete a method atom."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM method_atoms WHERE id = ?", (atom_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Atom {atom_id} not found")
        conn.execute("DELETE FROM method_atoms WHERE id = ?", (atom_id,))
        conn.commit()
    return {"deleted": atom_id}


# ---------------------------------------------------------------------------
# Venue Decision + Style Kit
# ---------------------------------------------------------------------------


@app.post("/api/topics/{topic_id}/venue-decision")
def venue_decision_endpoint(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.venue_decision_impl import decide_venue

    db = Database(DB_PATH)
    db.migrate()
    try:
        decision = decide_venue(topic_id, db)
    except RuntimeError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=500, detail=detail) from exc
    return decision.model_dump()


@app.get("/api/topics/{topic_id}/venue-decision")
def get_venue_decision_endpoint(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        row = conn.execute(
            "SELECT * FROM venue_decision WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    for field in ("decision_basis", "fit_risk", "source_venues"):
        if isinstance(d.get(field), str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


@app.post("/api/topics/{topic_id}/venue-style-kit")
def build_style_kit_endpoint(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.venue_decision_impl import build_style_kit

    db = Database(DB_PATH)
    db.migrate()
    try:
        kit = build_style_kit(topic_id, db)
    except RuntimeError as exc:
        detail = str(exc)
        if "not found" in detail.lower() or "need at least" in detail.lower():
            raise HTTPException(status_code=409, detail=detail) from exc
        raise HTTPException(status_code=500, detail=detail) from exc
    return kit.model_dump()


@app.get("/api/topics/{topic_id}/venue-style-kit")
def get_style_kit_endpoint(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        row = conn.execute(
            "SELECT * FROM venue_style_kit WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    for field in (
        "avg_section_lengths",
        "hedging_terms",
        "source_paper_ids",
        "source_venues",
    ):
        if isinstance(d.get(field), str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ---------------------------------------------------------------------------
# Experiment Matrix
# ---------------------------------------------------------------------------


class ProxyPassRequest(BaseModel):
    max_cells: int = Field(default=20, ge=1, le=100)


@app.post("/api/topics/{topic_id}/experiment-matrix/build")
def build_matrix_endpoint(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.experiment_matrix_impl import build_matrix

    db = Database(DB_PATH)
    db.migrate()
    try:
        cells = build_matrix(topic_id, db)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return [c.model_dump() for c in cells]


@app.post("/api/topics/{topic_id}/experiment-matrix/proxy")
def run_proxy_endpoint(topic_id: int, body: ProxyPassRequest):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")

    from research_harness.storage.db import Database
    from research_harness.primitives.experiment_matrix_impl import run_proxy_pass

    db = Database(DB_PATH)
    db.migrate()
    try:
        cells = run_proxy_pass(topic_id, db, max_cells=body.max_cells)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [c.model_dump() for c in cells]


@app.get("/api/topics/{topic_id}/experiment-matrix")
def get_matrix_endpoint(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        rows = conn.execute(
            "SELECT * FROM experiment_matrix_cell WHERE topic_id = ? ORDER BY goal_id, id",
            (topic_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        if isinstance(d.get("atom_combo"), str):
            try:
                d["atom_combo"] = json.loads(d["atom_combo"])
            except (json.JSONDecodeError, TypeError):
                d["atom_combo"] = []
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Retrieval Log
# ---------------------------------------------------------------------------


@app.get("/api/topics/{topic_id}/retrieval-log")
def get_retrieval_log(topic_id: int):
    """Return retrieval log entries for a topic, newest first."""
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        rows = conn.execute(
            """SELECT * FROM retrieval_log
               WHERE topic_id = ?
               ORDER BY created_at DESC""",
            (topic_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        if isinstance(d.get("ingested_paper_ids"), str):
            try:
                d["ingested_paper_ids"] = json.loads(d["ingested_paper_ids"])
            except (json.JSONDecodeError, TypeError):
                d["ingested_paper_ids"] = []
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Orchestrator actions
# ---------------------------------------------------------------------------


class AdvanceRequest(BaseModel):
    actor: str = "web_ui"


class ExpansionRequest(BaseModel):
    retrieval_target: int = Field(default=100)
    deep_read_target: int = Field(default=20)
    rounds: int = Field(default=3)


@app.post("/api/topics/{topic_id}/advance")
def advance_topic(topic_id: int, body: AdvanceRequest):
    """Advance the topic to the next orchestrator stage."""
    return _run_tool(
        "orchestrator_advance", {"topic_id": topic_id, "actor": body.actor}
    )


@app.get("/api/topics/{topic_id}/gate")
def check_gate(topic_id: int):
    """Check the gate for the current orchestrator stage."""
    return _run_tool("orchestrator_gate_check", {"topic_id": topic_id})


@app.post("/api/topics/{topic_id}/expansion")
def create_expansion_job(topic_id: int, body: ExpansionRequest):
    limits = {
        "retrieval_target": (body.retrieval_target, 500),
        "deep_read_target": (body.deep_read_target, 100),
        "rounds": (body.rounds, 10),
    }
    for field_name, (value, cap) in limits.items():
        if value <= 0 or value > cap:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be between 1 and {cap}",
            )

    now = _now_iso()
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        active = conn.execute(
            """
            SELECT id FROM expansion_jobs
            WHERE topic_id = ? AND status IN ('pending', 'running')
            LIMIT 1
            """,
            (topic_id,),
        ).fetchone()
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail="An expansion job is already pending or running for this topic",
            )
        cur = conn.execute(
            """
            INSERT INTO expansion_jobs (
                topic_id, status, retrieval_target, deep_read_target, rounds_target,
                current_round, papers_fetched, papers_deep_read, last_error,
                created_at, updated_at
            ) VALUES (?, 'pending', ?, ?, ?, 0, 0, 0, NULL, ?, ?)
            """,
            (
                topic_id,
                body.retrieval_target,
                body.deep_read_target,
                body.rounds,
                now,
                now,
            ),
        )
        conn.commit()
        job_id = int(cur.lastrowid)

    thread = threading.Thread(
        target=_run_expansion_job,
        args=(job_id, topic_id),
        daemon=True,
        name=f"expansion-job-{job_id}",
    )
    thread.start()
    return {"job_id": job_id, "status": "pending"}


@app.get("/api/topics/{topic_id}/expansion")
def get_expansion_job(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        row = _get_latest_expansion_job(conn, topic_id)
        stats = _topic_paper_stats(conn, topic_id)
    if row is None:
        return None
    payload = _row_to_dict(row)
    payload["topic_paper_count"] = stats["total"]
    payload["topic_deep_read_count"] = stats["deep_read"]
    return payload


@app.post("/api/topics/{topic_id}/expansion/cancel")
def cancel_expansion_job(topic_id: int):
    with get_db() as conn:
        if not _topic_exists(conn, topic_id):
            raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
        row = conn.execute(
            """
            SELECT id FROM expansion_jobs
            WHERE topic_id = ? AND status IN ('pending', 'running')
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (topic_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="No pending or running expansion job found"
            )
        _update_expansion_job(conn, int(row["id"]), status="cancelled")
    return {"job_id": int(row["id"]), "status": "cancelled"}


# ---------------------------------------------------------------------------
# Paper operations
# ---------------------------------------------------------------------------


class PaperSearchRequest(BaseModel):
    query: str
    topic_id: int | None = None
    max_results: int = Field(default=50, ge=1, le=200)
    stage: str | None = None
    trigger_reason: str | None = None


@app.post("/api/papers/search")
def search_papers(body: PaperSearchRequest):
    """Search for papers via configured providers."""
    api = ResearchAPI(db_path=DB_PATH)
    output = _search_papers_impl(
        api, query=body.query, topic_id=body.topic_id, max_results=body.max_results
    )

    results_count = len(output.get("papers") or [])

    # Write retrieval_log if all three context fields are present
    if body.topic_id is not None and body.stage and body.trigger_reason:
        valid_reasons = {
            "missing_evidence",
            "weak_baseline",
            "new_atom_idea",
            "venue_pattern",
            "user_request",
        }
        if body.trigger_reason in valid_reasons:
            try:
                with get_db() as conn:
                    conn.execute(
                        """INSERT INTO retrieval_log
                           (topic_id, stage, trigger_reason, query, results_count)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            body.topic_id,
                            body.stage,
                            body.trigger_reason,
                            body.query,
                            results_count,
                        ),
                    )
                    conn.commit()
            except Exception:
                logger.warning("Failed to write retrieval_log", exc_info=True)

    return {
        "status": "success",
        "summary": f"Found {results_count} papers",
        "output": output,
    }


class PaperIngestRequest(BaseModel):
    source: str  # arxiv ID, DOI, or URL
    topic_id: int | None = None
    relevance: str = "medium"


@app.post("/api/papers/ingest")
def ingest_paper(body: PaperIngestRequest):
    """Ingest a paper by arxiv ID, DOI, or URL."""
    api = ResearchAPI(db_path=DB_PATH)
    output = _ingest_paper_impl(
        api, source=body.source, topic_id=body.topic_id, relevance=body.relevance
    )

    # Mark field_brief stale if paper count grew >15% since last build
    if body.topic_id is not None:
        try:
            with get_db() as conn:
                meta = conn.execute(
                    "SELECT paper_count_at_build FROM field_brief_meta WHERE topic_id = ?",
                    (body.topic_id,),
                ).fetchone()
                if meta:
                    current = conn.execute(
                        "SELECT COUNT(*) FROM paper_topics WHERE topic_id = ?",
                        (body.topic_id,),
                    ).fetchone()[0]
                    if current > meta["paper_count_at_build"] * 1.15:
                        conn.execute(
                            "UPDATE field_brief_meta SET stale = 1 WHERE topic_id = ?",
                            (body.topic_id,),
                        )
                        conn.commit()
        except Exception:
            pass  # non-critical — don't fail ingest over stale tracking

    return {
        "status": "success",
        "summary": f"Ingested paper {output.get('paper_id')}",
        "output": output,
    }


@app.post("/api/papers/{paper_id}/enrich")
def enrich_paper(paper_id: int):
    """Enrich a single paper's metadata via Semantic Scholar."""
    from research_harness.core.paper_pool import PaperPool

    with get_db() as conn:
        pool = PaperPool(conn)
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        result = pool.enrich_metadata(paper_id)
    return {"paper_id": paper_id, "fields_updated": result}


class BatchEnrichRequest(BaseModel):
    topic_id: int | None = None
    missing_fields: list[str] = ["venue", "citation_count"]
    limit: int = 50


@app.post("/api/papers/enrich-batch")
def enrich_batch(body: BatchEnrichRequest, background_tasks: BackgroundTasks):
    """Kick off batch enrichment in the background. Returns immediately."""
    import time as _time

    def _run_batch() -> None:
        from research_harness.core.paper_pool import PaperPool

        venue_placeholders = ("", "arxiv", "arxiv.org", "arxiv preprint")
        with get_db() as conn:
            pool = PaperPool(conn)
            where = ""
            params: list[Any] = []
            if body.topic_id is not None:
                where = (
                    " AND id IN (SELECT paper_id FROM paper_topics WHERE topic_id = ?)"
                )
                params.append(body.topic_id)
            rows = conn.execute(
                f"SELECT id, arxiv_id, doi, s2_id, venue, citation_count FROM papers WHERE 1=1{where} ORDER BY id DESC",
                params,
            ).fetchall()

            count = 0
            for r in rows:
                if count >= body.limit:
                    break
                has_id = bool(
                    (r["arxiv_id"] or "").strip()
                    or (r["doi"] or "").strip()
                    or (r["s2_id"] or "").strip()
                )
                if not has_id:
                    continue
                needs = False
                for f in body.missing_fields:
                    val = r[f] if f in r.keys() else None
                    if f == "venue" and (
                        not val or str(val).strip().lower() in venue_placeholders
                    ):
                        needs = True
                    elif f != "venue" and (val is None or val == 0):
                        needs = True
                if not needs:
                    continue
                try:
                    pool.enrich_metadata(r["id"])
                    count += 1
                    _time.sleep(1.05)
                except Exception:
                    pass

    background_tasks.add_task(_run_batch)
    return {
        "status": "started",
        "limit": body.limit,
        "missing_fields": body.missing_fields,
    }


# ---------------------------------------------------------------------------
# Analysis operations
# ---------------------------------------------------------------------------


class GapDetectRequest(BaseModel):
    focus: str | None = None


@app.post("/api/topics/{topic_id}/gaps")
def detect_gaps(topic_id: int, body: GapDetectRequest):
    """Detect research gaps in a topic's literature."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("gap_detect", args)


class ClaimExtractRequest(BaseModel):
    paper_ids: list[int]
    focus: str | None = None


@app.post("/api/topics/{topic_id}/claims")
def extract_claims(topic_id: int, body: ClaimExtractRequest):
    """Extract research claims from papers within a topic."""
    args: dict[str, Any] = {"topic_id": topic_id, "paper_ids": body.paper_ids}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("claim_extract", args)


class DirectionRankingRequest(BaseModel):
    focus: str | None = None


@app.post("/api/topics/{topic_id}/directions")
def rank_directions(topic_id: int, body: DirectionRankingRequest):
    """Rank candidate research directions by novelty x feasibility x impact."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("direction_ranking", args)


# ---------------------------------------------------------------------------
# Writing operations
# ---------------------------------------------------------------------------


class OutlineGenerateRequest(BaseModel):
    template: str = "neurips"


@app.post("/api/topics/{topic_id}/outline")
def generate_outline(topic_id: int, body: OutlineGenerateRequest):
    """Generate a paper outline from contributions and evidence."""
    return _run_tool(
        "outline_generate",
        {
            "topic_id": topic_id,
            "template": body.template,
        },
    )


class SectionDraftRequest(BaseModel):
    section: str
    outline: str | None = None
    max_words: int = 0


@app.post("/api/topics/{topic_id}/section-draft")
def draft_section(topic_id: int, body: SectionDraftRequest):
    """Draft a paper section using linked evidence."""
    args: dict[str, Any] = {"section": body.section, "topic_id": topic_id}
    if body.outline:
        args["outline"] = body.outline
    if body.max_words > 0:
        args["max_words"] = body.max_words
    return _run_tool("section_draft", args)


class ClaimVerifyRequest(BaseModel):
    pair_budget: int = 200
    persist: bool = True


@app.post("/api/topics/{topic_id}/claim-verify")
def verify_claims_endpoint(topic_id: int, body: ClaimVerifyRequest):
    """v2 Step 5 — bounded pair-wise claim verification."""
    return _run_tool(
        "claim_verify",
        {
            "topic_id": topic_id,
            "pair_budget": body.pair_budget,
            "persist": body.persist,
        },
    )


class AdversarialSectionReviewRequest(BaseModel):
    section: str
    content: str
    target_words: int = 0
    auto_open_issues: bool = True


@app.post("/api/topics/{topic_id}/adversarial-review")
def adversarial_section_review_endpoint(
    topic_id: int, body: AdversarialSectionReviewRequest
):
    """v2 Step 5 — skeptical-reviewer adversarial section review."""
    return _run_tool(
        "adversarial_section_review",
        {
            "topic_id": topic_id,
            "section": body.section,
            "content": body.content,
            "target_words": body.target_words,
            "auto_open_issues": body.auto_open_issues,
        },
    )


# ---------------------------------------------------------------------------
# Stage 1 — Analysis: method taxonomy, baseline identify, evidence matrix
# ---------------------------------------------------------------------------


class MethodTaxonomyRequest(BaseModel):
    focus: str | None = None


@app.post("/api/topics/{topic_id}/method-taxonomy")
def method_taxonomy(topic_id: int, body: MethodTaxonomyRequest):
    """Build a taxonomy of methods from deep-read papers in the topic."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("method_taxonomy", args)


class BaselineIdentifyRequest(BaseModel):
    focus: str | None = None


@app.post("/api/topics/{topic_id}/baselines")
def identify_baselines(topic_id: int, body: BaselineIdentifyRequest):
    """Identify baseline methods and their reported results from the literature."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("baseline_identify", args)


class EvidenceMatrixRequest(BaseModel):
    focus: str | None = None


@app.post("/api/topics/{topic_id}/evidence-matrix")
def evidence_matrix(topic_id: int, body: EvidenceMatrixRequest):
    """Generate a method × metric evidence matrix from the literature."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("evidence_matrix", args)


# ---------------------------------------------------------------------------
# Stage 2 — Propose: algorithm candidates, design loop, competitive learning
# ---------------------------------------------------------------------------


class AlgorithmCandidateRequest(BaseModel):
    focus: str | None = None
    n_candidates: int = 3
    brief: dict[str, Any] | None = None


@app.post("/api/topics/{topic_id}/algorithm-candidates")
def generate_algorithm_candidates(topic_id: int, body: AlgorithmCandidateRequest):
    """Generate algorithm improvement candidates by combinatorial innovation."""
    brief = body.brief or {
        "topic_id": topic_id,
        "focus": body.focus or "",
        "n_candidates": body.n_candidates,
    }
    # Auto-fetch deep_read notes so the LLM has richer context
    deep_read_notes: list[dict[str, Any]] = []
    try:
        from research_harness.execution.compiled_summary import (
            ensure_compiled_summary,
            format_compiled_for_context,
        )
        from research_harness.storage.db import Database

        _db = Database(db_path=DB_PATH)
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.title FROM papers p
                JOIN paper_topics pt ON pt.paper_id = p.id
                WHERE pt.topic_id = ? AND p.deep_read = 1
                ORDER BY p.id DESC LIMIT 10
                """,
                (topic_id,),
            ).fetchall()
        for r in rows:
            compiled = ensure_compiled_summary(_db, int(r["id"]))
            ctx = format_compiled_for_context(compiled)
            if ctx.strip():
                deep_read_notes.append(
                    {
                        "paper_id": r["id"],
                        "title": r["title"],
                        "notes": ctx[:500],
                    }
                )
    except Exception:
        pass
    args: dict[str, Any] = {
        "topic_id": topic_id,
        "brief": brief,
        "deep_read_notes": deep_read_notes or None,
    }
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("algorithm_candidate_generate", args)


class AlgorithmDesignLoopRequest(BaseModel):
    focus: str | None = None
    max_rounds: int = 3


@app.post("/api/topics/{topic_id}/algorithm-design-loop")
def algorithm_design_loop(topic_id: int, body: AlgorithmDesignLoopRequest):
    """Iterative algorithm design: generate → probe → refine → check."""
    args: dict[str, Any] = {"topic_id": topic_id, "max_rounds": body.max_rounds}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("algorithm_design_loop", args)


class CompetitiveLearningRequest(BaseModel):
    venue: str = "EMNLP"
    focus: str | None = None


@app.post("/api/topics/{topic_id}/competitive-learning")
def competitive_learning(topic_id: int, body: CompetitiveLearningRequest):
    """Analyze competitive landscape: venue-level method trends + positioning."""
    args: dict[str, Any] = {"topic_id": topic_id, "venue": body.venue}
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("competitive_learning", args)


class DesignBriefExpandRequest(BaseModel):
    direction: str = ""
    focus: str | None = None


@app.post("/api/topics/{topic_id}/design-brief")
def design_brief_expand(topic_id: int, body: DesignBriefExpandRequest):
    """Expand a high-level design brief into actionable sub-problems."""
    direction = body.direction or body.focus or ""
    if not direction:
        raise HTTPException(
            status_code=422,
            detail="Either 'direction' or 'focus' must be provided.",
        )
    args: dict[str, Any] = {"topic_id": topic_id, "direction": direction}
    return _run_tool("design_brief_expand", args)


# ---------------------------------------------------------------------------
# Stage 3 — Experiment: code generation
# ---------------------------------------------------------------------------


class CodeGenerateRequest(BaseModel):
    spec: str = ""
    focus: str | None = None


@app.post("/api/topics/{topic_id}/code-generate")
def code_generate(topic_id: int, body: CodeGenerateRequest):
    """Generate experiment code from study spec and topic context."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.spec:
        args["spec"] = body.spec
    if body.focus:
        args["focus"] = body.focus
    return _run_tool("code_generate", args)


# ---------------------------------------------------------------------------
# Stage 5 — Writing: review, revise, consistency, writing pattern, architecture
# ---------------------------------------------------------------------------


class SectionReviewRequest(BaseModel):
    section: str
    content: str


@app.post("/api/topics/{topic_id}/section-review")
def review_section(topic_id: int, body: SectionReviewRequest):
    """Review a draft section for quality, citations, and coherence."""
    return _run_tool(
        "section_review",
        {"topic_id": topic_id, "section": body.section, "content": body.content},
    )


class SectionReviseRequest(BaseModel):
    section: str
    content: str
    feedback: str = ""


@app.post("/api/topics/{topic_id}/section-revise")
def revise_section(topic_id: int, body: SectionReviseRequest):
    """Revise a draft section based on review feedback."""
    args: dict[str, Any] = {
        "topic_id": topic_id,
        "section": body.section,
        "content": body.content,
    }
    if body.feedback:
        args["feedback"] = body.feedback
    return _run_tool("section_revise", args)


class ConsistencyCheckRequest(BaseModel):
    sections: list[str] | None = None


@app.post("/api/topics/{topic_id}/consistency-check")
def consistency_check(topic_id: int, body: ConsistencyCheckRequest):
    """Cross-section consistency check for the draft paper."""
    args: dict[str, Any] = {"topic_id": topic_id}
    if body.sections:
        args["sections"] = body.sections
    return _run_tool("consistency_check", args)


class WritingPatternExtractRequest(BaseModel):
    paper_id: int


@app.post("/api/topics/{topic_id}/writing-pattern")
def writing_pattern_extract(topic_id: int, body: WritingPatternExtractRequest):
    """Extract narrative writing patterns from a target venue paper."""
    return _run_tool(
        "writing_pattern_extract",
        {"topic_id": topic_id, "paper_id": body.paper_id},
    )


class WritingArchitectureRequest(BaseModel):
    template: str = "neurips"


@app.post("/api/topics/{topic_id}/writing-architecture")
def writing_architecture(topic_id: int, body: WritingArchitectureRequest):
    """Design the paper's narrative architecture: story arc, section roles, evidence map."""
    return _run_tool(
        "writing_architecture",
        {"topic_id": topic_id, "template": body.template},
    )


@app.post("/api/memory/recall")
def memory_recall(body: dict[str, Any]):
    """v2 Step 8 — workflow memory recall.

    Body: { query: str, exclude_topic_id?: int, top_k?: int,
            max_age_days?: int, require_success?: bool }
    """
    from research_harness.memory import recall_similar_runs

    query = str(body.get("query", "")).strip()
    if not query:
        return {"query": query, "hits": []}
    try:
        from research_harness.storage.db import Database as _DB

        db = _DB(Path(str(DB_PATH)))
        hits = recall_similar_runs(
            db,
            query,
            exclude_topic_id=body.get("exclude_topic_id"),
            top_k=int(body.get("top_k", 5)),
            max_age_days=body.get("max_age_days", 90),
            require_success=bool(body.get("require_success", True)),
        )
    except Exception as exc:
        logger.error("memory_recall failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "query": query,
        "hits": [
            {
                "topic_id": h.topic_id,
                "topic_name": h.topic_name,
                "description": h.description,
                "created_at": h.created_at,
                "score": h.score,
                "lexical_score": h.lexical_score,
                "provenance_success_count": h.provenance_success_count,
                "decision_highlights": h.decision_highlights,
            }
            for h in hits
        ],
    }


class ReportGenerateRequest(BaseModel):
    template: str = "abstract_only"
    title: str = ""
    draft_missing: bool = True
    extra_instructions: str = ""


class ReportBatchGenerateRequest(BaseModel):
    templates: list[str]
    title: str = ""
    draft_missing: bool = True
    extra_instructions: str = ""


def _resolve_db_service():
    from research_harness.storage.db import Database as _DB

    return _DB(Path(str(DB_PATH)))


@app.get("/api/topics/{topic_id}/reports")
def list_topic_reports(topic_id: int):
    """Sprint 1 — list all reports for a topic."""
    from research_harness.reports import list_reports

    try:
        db = _resolve_db_service()
        reports = list_reports(db, topic_id)
    except Exception as exc:
        logger.error("list_reports failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "topic_id": topic_id,
        "reports": [
            {
                "id": r.id,
                "template": r.template,
                "title": r.title,
                "sections": r.sections,
                "version_major": r.version_major,
                "version_minor": r.version_minor,
                "has_share": r.has_share,
                "share_token": r.share_token,
                "share_expires_at": r.share_expires_at,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "word_count": r.word_count,
                "metadata": r.metadata,
            }
            for r in reports
        ],
    }


@app.post("/api/topics/{topic_id}/reports")
def create_topic_report(topic_id: int, body: ReportGenerateRequest):
    """Sprint 1 — generate a new report version."""
    from research_harness.reports import generate_report

    try:
        db = _resolve_db_service()
        report = generate_report(
            db,
            topic_id,
            template=body.template,
            title=body.title,
            draft_missing=body.draft_missing,
            extra_instructions=body.extra_instructions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("generate_report failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "id": report.id,
        "topic_id": report.topic_id,
        "template": report.template,
        "version_minor": report.version_minor,
        "word_count": report.word_count,
        "metadata": report.metadata,
    }


@app.post("/api/topics/{topic_id}/reports:batch")
def create_topic_reports_batch(topic_id: int, body: ReportBatchGenerateRequest):
    """Composer-style batch — generate several templates in one request.

    Each template runs through the standard generate_report flow with the same
    ``extra_instructions``. Returns per-template success/error so the UI can
    render a partial-success table without losing the good ones.
    """
    from research_harness.reports import generate_report

    if not body.templates:
        raise HTTPException(status_code=400, detail="templates must not be empty")

    db = _resolve_db_service()
    results: list[dict[str, Any]] = []
    for template in body.templates:
        try:
            report = generate_report(
                db,
                topic_id,
                template=template,
                title=body.title,
                draft_missing=body.draft_missing,
                extra_instructions=body.extra_instructions,
            )
            results.append(
                {
                    "template": template,
                    "ok": True,
                    "id": report.id,
                    "version_minor": report.version_minor,
                    "word_count": report.word_count,
                }
            )
        except ValueError as exc:
            results.append({"template": template, "ok": False, "error": str(exc)})
        except Exception as exc:
            logger.error(
                "batch generate_report[%s] failed: %s\n%s",
                template,
                exc,
                traceback.format_exc(),
            )
            results.append({"template": template, "ok": False, "error": str(exc)})

    return {"topic_id": topic_id, "results": results}


@app.get("/api/reports/templates")
def list_report_templates_v2():
    """Metadata for the four built-in report templates.

    Registered BEFORE the /{report_id} dynamic route so 'templates' is not
    parsed as an integer path param.
    """
    from research_harness.reports import REPORT_TEMPLATES

    return {"templates": REPORT_TEMPLATES}


@app.get("/api/reports/{report_id}")
def get_report_detail(report_id: int):
    from research_harness.reports import get_report

    try:
        db = _resolve_db_service()
        rep = get_report(db, report_id)
    except Exception as exc:
        logger.error("get_report failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if rep is None:
        raise HTTPException(status_code=404, detail="report not found")
    return rep


@app.get("/api/reports/{report_id}/html", response_class=HTMLResponse)
def get_report_html(report_id: int):
    from research_harness.reports import get_report

    db = _resolve_db_service()
    rep = get_report(db, report_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="report not found")
    return HTMLResponse(content=rep.get("content_html") or "", status_code=200)


@app.get("/api/reports/{report_id}/markdown", response_class=PlainTextResponse)
def get_report_markdown(report_id: int):
    from research_harness.reports import get_report

    db = _resolve_db_service()
    rep = get_report(db, report_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="report not found")
    return PlainTextResponse(rep.get("content_md") or "")


@app.post("/api/reports/{report_id}/share")
def share_report(report_id: int, body: dict[str, Any] | None = None):
    from research_harness.reports import create_share_token

    expires = 14
    if body and "expires_in_days" in body:
        try:
            expires = int(body["expires_in_days"])
        except (TypeError, ValueError):
            expires = 14
    try:
        db = _resolve_db_service()
        out = create_share_token(db, report_id, expires_in_days=expires)
    except Exception as exc:
        logger.error("share_report failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return out


@app.get("/api/shared/reports/{token}")
def get_shared_report(token: str):
    """Public read-only endpoint advisors hit via the share link."""
    from research_harness.reports.service import get_report_by_share_token

    db = _resolve_db_service()
    rep = get_report_by_share_token(db, token)
    if rep is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if isinstance(rep, dict) and rep.get("error"):
        raise HTTPException(status_code=410, detail=rep["error"])
    return {
        "id": rep.get("id"),
        "topic_name": rep.get("topic_name"),
        "title": rep.get("title"),
        "template": rep.get("template"),
        "sections": rep.get("sections"),
        "content_md": rep.get("content_md"),
        "content_html": rep.get("content_html"),
        "version_minor": rep.get("version_minor"),
        "created_at": rep.get("created_at"),
    }


@app.get("/api/topics/{topic_id}/bibtex", response_class=PlainTextResponse)
def export_topic_bibtex(topic_id: int):
    """Export all papers in a topic as a single BibTeX file.

    Reuses the bib_entries table populated by `rh bib` CLI. Falls back to
    a minimal synthesized entry for papers without a registered entry.
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.title, p.authors, p.year, p.venue,
                   p.doi, p.arxiv_id, b.bibtex, b.bibtex_key
            FROM papers p
            JOIN paper_topics pt ON pt.paper_id = p.id
            LEFT JOIN bib_entries b ON b.paper_id = p.id
            WHERE pt.topic_id = ?
            ORDER BY p.year DESC NULLS LAST, p.id
            """,
            (topic_id,),
        ).fetchall()

    entries: list[str] = []
    for r in rows:
        if r["bibtex"]:
            entries.append(r["bibtex"])
            continue
        # Synthesize a minimal @misc entry so Zotero / BibLaTeX imports work.
        key = r["bibtex_key"] or _synthesize_bibkey(
            int(r["id"]), r["title"] or "", r["year"], r["authors"] or ""
        )
        author_str = _parse_author_list(r["authors"] or "")
        parts = [f"@misc{{{key},"]
        if r["title"]:
            parts.append(f"  title={{{r['title']}}},")
        if author_str:
            parts.append(f"  author={{{author_str}}},")
        if r["year"]:
            parts.append(f"  year={{{r['year']}}},")
        if r["venue"]:
            parts.append(f"  howpublished={{{r['venue']}}},")
        if r["arxiv_id"]:
            parts.append(f"  eprint={{{r['arxiv_id']}}},")
            parts.append("  archivePrefix={arXiv},")
        if r["doi"]:
            parts.append(f"  doi={{{r['doi']}}},")
        parts.append("}")
        entries.append("\n".join(parts))
    return PlainTextResponse("\n\n".join(entries) + "\n")


def _synthesize_bibkey(
    paper_id: int, title: str, year: int | str | None, authors: str
) -> str:
    import re as _re

    first_author = ""
    try:
        arr = json.loads(authors)
        if isinstance(arr, list) and arr:
            first = arr[0]
            if isinstance(first, str):
                first_author = first.split()[-1].lower()
            elif isinstance(first, dict):
                first_author = str(first.get("name", "")).split()[-1].lower()
    except (ValueError, TypeError):
        first_author = ""
    first_word = ""
    if title:
        words = _re.findall(r"[A-Za-z]{4,}", title)
        if words:
            first_word = words[0].lower()
    yr = str(year or "")
    parts = [p for p in (first_author, yr, first_word) if p]
    return "-".join(parts) or f"paper-{paper_id}"


def _parse_author_list(authors: str) -> str:
    try:
        arr = json.loads(authors)
    except (ValueError, TypeError):
        return authors
    if not isinstance(arr, list):
        return str(arr)
    names: list[str] = []
    for item in arr:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return " and ".join(names)


@app.get("/api/topics/{topic_id}/contradictions")
def list_contradictions(topic_id: int):
    """List persisted contradictions for a topic (from verify_claims)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, topic_id, claim_a_id, claim_b_id, conflict_reason,
                   status, confidence, created_at
            FROM contradictions WHERE topic_id = ?
            ORDER BY id DESC
            """,
            (topic_id,),
        ).fetchall()
        items = [dict(r) for r in rows]
        # Hydrate claim text for UI convenience
        claim_ids: list[int] = []
        for it in items:
            claim_ids.extend([it["claim_a_id"], it["claim_b_id"]])
        texts: dict[int, dict[str, Any]] = {}
        if claim_ids:
            ph = ",".join("?" * len(claim_ids))
            crows = conn.execute(
                f"SELECT id, claim_text, paper_id, modality, dataset, metric, task "
                f"FROM normalized_claims WHERE id IN ({ph})",
                claim_ids,
            ).fetchall()
            for cr in crows:
                texts[int(cr["id"])] = dict(cr)
        for it in items:
            it["claim_a"] = texts.get(int(it["claim_a_id"]))
            it["claim_b"] = texts.get(int(it["claim_b_id"]))
    return {"topic_id": topic_id, "contradictions": items}


# ---------------------------------------------------------------------------
# Agents — registry, pairings, presets
# ---------------------------------------------------------------------------


class CreateAgentRequest(BaseModel):
    nickname: str
    provider: str
    model: str
    api_key_env: str
    role_prefs: dict[str, bool] = Field(
        default_factory=lambda: {"generator": True, "judge": True}
    )
    monthly_budget_usd: float | None = None


class PatchAgentRequest(BaseModel):
    nickname: str | None = None
    provider: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    role_prefs: dict[str, bool] | None = None
    monthly_budget_usd: float | None = None
    status: str | None = None

    model_config = {"extra": "forbid"}


class CreatePairingRequest(BaseModel):
    name: str
    generator_agent_id: int
    judge_agent_id: int
    challenger_agent_id: int | None = None
    topic_id: int | None = None
    is_global_default: int = 0


class UserPreferencesRequest(BaseModel):
    language: str | None = None
    discipline: str | None = None
    default_venue_tier: str | None = None
    default_quality_tier: str | None = None
    default_autonomy: str | None = None
    monthly_budget_cap_usd: float | None = None
    onboarding_complete: int | None = None
    auto_rollback_live: int | None = None  # 0 = shadow (default), 1 = live

    model_config = {"extra": "forbid"}


@app.get("/api/agents")
def list_agents(status: str | None = Query(None)):
    with get_db() as conn:
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM agent_registry {where} ORDER BY id", params
        ).fetchall()
    result = []
    for r in rows:
        d = _row_to_dict(r)
        d["role_prefs"] = _parse_json_field(d.get("role_prefs"), {})
        result.append(d)
    return result


@app.get("/api/llm/providers")
def list_llm_providers():
    """Return LLM providers available via env/CLI plus resolved tier routes.

    The agent_registry table holds user-registered personas; this endpoint
    exposes the system-level availability (env vars, CLI tools) so the UI
    never falsely claims "demo mode" when real credentials exist.
    """
    try:
        from llm_router.config import (
            detect_available_providers,
            get_tier_route,
            load_config,
        )
    except Exception as exc:
        logger.warning("llm_router import failed: %s", exc)
        return {"providers": [], "tier_routes": {}, "config_loaded": False}

    available = detect_available_providers()
    try:
        cfg = load_config()
    except Exception:
        cfg = {}

    # Collect litellm provider metadata for display and tier suggestions.
    _litellm_meta: dict[str, Any] = {}
    try:
        from llm_router.litellm_backend import (
            LITELLM_PROVIDERS,
            resolve_provider_api_key,
        )

        _litellm_meta = {name: meta for name, meta in LITELLM_PROVIDERS.items()}
    except ImportError:
        pass

    providers = []
    for p in available:
        entry: dict[str, Any] = {
            "provider": p,
            "family": get_family(p),
            "source": "litellm" if p in _litellm_meta else "env",
        }
        meta = _litellm_meta.get(p)
        if meta is not None:
            entry["display_name"] = meta.display_name
            entry["has_key"] = bool(resolve_provider_api_key(meta))
            entry["tier_suggestions"] = dict(meta.tier_suggestions)
        providers.append(entry)

    tier_routes: dict[str, dict[str, str]] = {}
    _default_models: dict[str, dict[str, str]] = {
        "anthropic": {
            "light": "claude-haiku-4-5-20251001",
            "medium": "claude-sonnet-4-6",
            "heavy": "claude-opus-4-6",
        },
        "openai": {"light": "gpt-4o-mini", "medium": "gpt-4o", "heavy": "o3"},
        "kimi": {
            "light": "kimi-for-coding",
            "medium": "kimi-for-coding",
            "heavy": "kimi-for-coding",
        },
    }
    for name, meta in _litellm_meta.items():
        if name not in _default_models and meta.tier_suggestions:
            _default_models[name] = dict(meta.tier_suggestions)
    for tier in ("light", "medium", "heavy"):
        env_key = f"LLM_ROUTE_{tier.upper()}"
        env_val = os.environ.get(env_key, "").strip()
        source = None
        provider = ""
        model = ""
        if env_val and ":" in env_val:
            provider, model = env_val.split(":", 1)
            source = "env"
        else:
            route = get_tier_route(tier, cfg)
            if route:
                provider, model = route
                source = "config"
        if not provider:
            for p in available:
                if p in _default_models and tier in _default_models[p]:
                    provider = p
                    model = _default_models[p][tier]
                    source = "default"
                    break
        if provider and model:
            tier_routes[tier] = {
                "provider": provider.strip(),
                "model": model.strip(),
                "source": source or "",
            }

    return {
        "providers": providers,
        "tier_routes": tier_routes,
        "config_loaded": bool(cfg),
    }


@app.get("/api/llm/tier-suggestions")
def get_tier_suggestions():
    """Return auto-suggested tier mapping from currently available providers."""
    try:
        from llm_router.config import detect_available_providers
        from llm_router.litellm_backend import suggest_tier_mapping

        available = detect_available_providers()
        suggested = suggest_tier_mapping(available)
        return {
            "available": available,
            "suggestions": {
                tier: {"provider": prov, "model": model}
                for tier, (prov, model) in suggested.items()
            },
        }
    except ImportError:
        return {"available": [], "suggestions": {}}


class _ProviderTestRequest(BaseModel):
    provider: str
    model: str
    base_url: str = ""

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if v and not v.startswith("https://"):
            raise ValueError("base_url must use https:// scheme")
        return v


@app.post("/api/llm/providers/test")
def test_provider(body: _ProviderTestRequest):
    """Send a minimal completion to validate a provider config."""
    try:
        from llm_router import get_provider

        fn = get_provider(body.provider)
        result = fn(
            "Say 'ok' and nothing else.",
            body.model,
            base_url=body.base_url,
            temperature=0.0,
        )
        return {"ok": True, "response_preview": result[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/agents", status_code=201)
def create_agent(body: CreateAgentRequest):
    provider_family = get_family(body.provider)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO agent_registry
                    (nickname, provider, provider_family, model, api_key_env, role_prefs, monthly_budget_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.nickname,
                    body.provider,
                    provider_family,
                    body.model,
                    body.api_key_env,
                    json.dumps(body.role_prefs),
                    body.monthly_budget_usd,
                    now,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        row = conn.execute(
            "SELECT * FROM agent_registry WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    d = _row_to_dict(row)
    d["role_prefs"] = _parse_json_field(d.get("role_prefs"), {})
    return d


# -- Agent pairings (must be before {agent_id} to avoid route collision) --


@app.get("/api/agents/pairings")
def list_pairings(topic_id: int | None = Query(None)):
    with get_db() as conn:
        conditions: list[str] = []
        params: list[Any] = []
        if topic_id is not None:
            conditions.append("(ap.topic_id = ? OR ap.topic_id IS NULL)")
            params.append(topic_id)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"""
            SELECT ap.*,
                   g.nickname AS generator_name, g.provider AS generator_provider, g.model AS generator_model,
                   j.nickname AS judge_name, j.provider AS judge_provider, j.model AS judge_model,
                   c.nickname AS challenger_name, c.provider AS challenger_provider, c.model AS challenger_model
            FROM agent_pairings ap
            JOIN agent_registry g ON g.id = ap.generator_agent_id
            JOIN agent_registry j ON j.id = ap.judge_agent_id
            LEFT JOIN agent_registry c ON c.id = ap.challenger_agent_id
            {where}
            ORDER BY ap.id
            """,
            params,
        ).fetchall()
    return _rows_to_list(rows)


@app.post("/api/agents/pairings", status_code=201)
def create_pairing(body: CreatePairingRequest):
    with get_db() as conn:
        gen = conn.execute(
            "SELECT provider_family FROM agent_registry WHERE id = ?",
            (body.generator_agent_id,),
        ).fetchone()
        if not gen:
            raise HTTPException(status_code=404, detail="Generator agent not found")
        judge = conn.execute(
            "SELECT provider_family FROM agent_registry WHERE id = ?",
            (body.judge_agent_id,),
        ).fetchone()
        if not judge:
            raise HTTPException(status_code=404, detail="Judge agent not found")

        if gen["provider_family"] == judge["provider_family"]:
            raise HTTPException(
                status_code=422,
                detail=f"Generator and Judge must belong to different provider families. "
                f"Both are '{gen['provider_family']}'. "
                f"This ensures adversarial diversity in rubric scoring.",
            )

        if body.generator_agent_id == body.judge_agent_id:
            raise HTTPException(
                status_code=422,
                detail="Generator and Judge must be different agents.",
            )

        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = conn.execute(
                """
                INSERT INTO agent_pairings
                    (name, generator_agent_id, judge_agent_id, challenger_agent_id,
                     topic_id, is_global_default, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.name,
                    body.generator_agent_id,
                    body.judge_agent_id,
                    body.challenger_agent_id,
                    body.topic_id,
                    body.is_global_default,
                    now,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        row = conn.execute(
            "SELECT * FROM agent_pairings WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _row_to_dict(row)


# -- Agent presets (must be before {agent_id} to avoid route collision) --

AGENT_PRESETS = [
    {
        "id": "heavy",
        "name": "Opus 4.7 + Gemini 2.5 Pro",
        "description": "Maximum quality — heavy tier",
        "agents": [
            {
                "nickname": "opus-gen",
                "provider": "anthropic",
                "model": "claude-opus-4-7",
                "api_key_env": "ANTHROPIC_API_KEY",
                "role_prefs": {"generator": True},
            },
            {
                "nickname": "gemini-judge",
                "provider": "google",
                "model": "gemini-2.5-pro",
                "api_key_env": "GOOGLE_API_KEY",
                "role_prefs": {"judge": True},
            },
        ],
    },
    {
        "id": "balanced",
        "name": "GPT-5 + Claude Sonnet 4.6",
        "description": "Balanced cost and quality",
        "agents": [
            {
                "nickname": "gpt5-gen",
                "provider": "openai",
                "model": "gpt-5",
                "api_key_env": "OPENAI_API_KEY",
                "role_prefs": {"generator": True},
            },
            {
                "nickname": "sonnet-judge",
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "api_key_env": "ANTHROPIC_API_KEY",
                "role_prefs": {"judge": True},
            },
        ],
    },
    {
        "id": "cost-optimised",
        "name": "Claude Sonnet + Kimi K2",
        "description": "Cost-optimised — good for exploration",
        "agents": [
            {
                "nickname": "sonnet-gen",
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
                "api_key_env": "ANTHROPIC_API_KEY",
                "role_prefs": {"generator": True},
            },
            {
                "nickname": "kimi-judge",
                "provider": "kimi",
                "model": "kimi-k2",
                "api_key_env": "KIMI_API_KEY",
                "role_prefs": {"judge": True},
            },
        ],
    },
]


@app.get("/api/agents/presets")
def list_presets():
    return AGENT_PRESETS


# ---------------------------------------------------------------------------
# Token ledger (must be before {agent_id} to avoid route collision)
# ---------------------------------------------------------------------------


@app.get("/api/agents/ledger")
def get_ledger(
    topic_id: int | None = Query(None),
    agent_id: int | None = Query(None),
    since: str | None = Query(None, description="ISO date, e.g. 2026-04-01"),
    group_by: str | None = Query(
        None, description="Grouping: agent, topic, stage, month"
    ),
):
    try:
        with get_db() as conn:
            conditions: list[str] = []
            params: list[Any] = []
            if topic_id is not None:
                conditions.append("tl.topic_id = ?")
                params.append(topic_id)
            if agent_id is not None:
                conditions.append("tl.agent_id = ?")
                params.append(agent_id)
            if since:
                conditions.append("tl.ts >= ?")
                params.append(since)

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

            if group_by == "agent":
                rows = conn.execute(
                    f"""
                    SELECT tl.agent_id, ar.nickname, ar.model,
                           SUM(tl.prompt_tokens) AS total_prompt,
                           SUM(tl.completion_tokens) AS total_completion,
                           SUM(tl.cost_usd) AS total_cost,
                           COUNT(*) AS call_count
                    FROM token_ledger tl
                    LEFT JOIN agent_registry ar ON ar.id = tl.agent_id
                    {where}
                    GROUP BY tl.agent_id
                    ORDER BY total_cost DESC
                    """,
                    params,
                ).fetchall()
            elif group_by == "stage":
                rows = conn.execute(
                    f"""
                    SELECT tl.stage,
                           SUM(tl.prompt_tokens) AS total_prompt,
                           SUM(tl.completion_tokens) AS total_completion,
                           SUM(tl.cost_usd) AS total_cost,
                           COUNT(*) AS call_count
                    FROM token_ledger tl
                    {where}
                    GROUP BY tl.stage
                    ORDER BY total_cost DESC
                    """,
                    params,
                ).fetchall()
            elif group_by == "month":
                rows = conn.execute(
                    f"""
                    SELECT substr(tl.ts, 1, 7) AS month,
                           SUM(tl.cost_usd) AS total_cost,
                           COUNT(*) AS call_count
                    FROM token_ledger tl
                    {where}
                    GROUP BY month
                    ORDER BY month DESC
                    """,
                    params,
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""
                    SELECT tl.*, ar.nickname AS agent_name, ar.model AS agent_model
                    FROM token_ledger tl
                    LEFT JOIN agent_registry ar ON ar.id = tl.agent_id
                    {where}
                    ORDER BY tl.ts DESC
                    LIMIT 200
                    """,
                    params,
                ).fetchall()

            return _rows_to_list(rows)
    except sqlite3.OperationalError:
        return []


# -- Agent by ID (after specific sub-routes) --


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM agent_registry WHERE id = ?", (agent_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    d = _row_to_dict(row)
    d["role_prefs"] = _parse_json_field(d.get("role_prefs"), {})
    return d


@app.patch("/api/agents/{agent_id}")
def update_agent(agent_id: int, body: PatchAgentRequest):
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM agent_registry WHERE id = ?", (agent_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        if "provider" in patch:
            patch["provider_family"] = get_family(patch["provider"])
        if "role_prefs" in patch:
            patch["role_prefs"] = json.dumps(patch["role_prefs"])

        allowed = {
            "nickname",
            "provider",
            "provider_family",
            "model",
            "api_key_env",
            "role_prefs",
            "monthly_budget_usd",
            "status",
        }
        updates = {k: v for k, v in patch.items() if k in allowed}
        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [agent_id]
        conn.execute(f"UPDATE agent_registry SET {set_clause} WHERE id = ?", params)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_registry WHERE id = ?", (agent_id,)
        ).fetchone()

    d = _row_to_dict(row)
    d["role_prefs"] = _parse_json_field(d.get("role_prefs"), {})
    return d


@app.delete("/api/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: int):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM agent_registry WHERE id = ?", (agent_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        conn.execute("DELETE FROM agent_registry WHERE id = ?", (agent_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------


@app.get("/api/user/preferences")
def get_user_preferences():
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM user_preferences ORDER BY id LIMIT 1"
        ).fetchone()
    if not row:
        return {
            "language": "en",
            "discipline": "cs",
            "default_venue_tier": "B",
            "default_quality_tier": "standard",
            "default_autonomy": "L2",
            "monthly_budget_cap_usd": 100,
            "onboarding_complete": 0,
            "auto_rollback_live": 0,
        }
    return _row_to_dict(row)


@app.patch("/api/user/preferences")
def update_user_preferences(body: UserPreferencesRequest):
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM user_preferences ORDER BY id LIMIT 1"
        ).fetchone()
        if existing:
            allowed = {
                "language",
                "discipline",
                "default_venue_tier",
                "default_quality_tier",
                "default_autonomy",
                "monthly_budget_cap_usd",
                "onboarding_complete",
                "auto_rollback_live",
            }
            updates = {k: v for k, v in patch.items() if k in allowed and v is not None}
            updates["updated_at"] = now
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [existing["id"]]
            conn.execute(
                f"UPDATE user_preferences SET {set_clause} WHERE id = ?", params
            )
        else:
            cols = {
                "language": patch.get("language", "en"),
                "discipline": patch.get("discipline", "cs"),
                "default_venue_tier": patch.get("default_venue_tier", "B"),
                "default_quality_tier": patch.get("default_quality_tier", "standard"),
                "default_autonomy": patch.get("default_autonomy", "L2"),
                "monthly_budget_cap_usd": patch.get("monthly_budget_cap_usd", 100),
                "onboarding_complete": patch.get("onboarding_complete", 0),
                "auto_rollback_live": patch.get("auto_rollback_live", 0),
                "created_at": now,
                "updated_at": now,
            }
            placeholders = ", ".join("?" for _ in cols)
            col_names = ", ".join(cols.keys())
            conn.execute(
                f"INSERT INTO user_preferences ({col_names}) VALUES ({placeholders})",
                list(cols.values()),
            )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM user_preferences ORDER BY id LIMIT 1"
        ).fetchone()
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Demo replay
# ---------------------------------------------------------------------------


@app.get("/api/demo/replay")
def demo_replay_list():
    return {"entries": demo_list_entries()}


class DemoReplayRequest(BaseModel):
    stage: str
    primitive: str
    prompt: str


@app.post("/api/demo/replay")
def demo_replay(body: DemoReplayRequest):
    result = demo_lookup(body.stage, body.primitive, body.prompt)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No canned response for {body.stage}:{body.primitive}",
        )
    return {"canned": True, "cost_usd": 0, **result}


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


class CreateBudgetRequest(BaseModel):
    scope: str  # 'global' | 'topic'
    scope_id: int | None = None
    monthly_cap_usd: float
    hard_stop: int = 1


class PatchBudgetRequest(BaseModel):
    monthly_cap_usd: float | None = None
    hard_stop: int | None = None

    model_config = {"extra": "forbid"}


@app.get("/api/budgets")
def list_budgets():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM budgets ORDER BY scope, scope_id").fetchall()
    return _rows_to_list(rows)


@app.post("/api/budgets", status_code=201)
def create_budget(body: CreateBudgetRequest):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO budgets (scope, scope_id, monthly_cap_usd, hard_stop, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (body.scope, body.scope_id, body.monthly_cap_usd, body.hard_stop, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM budgets WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _row_to_dict(row)


@app.patch("/api/budgets/{budget_id}")
def update_budget(budget_id: int, body: PatchBudgetRequest):
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM budgets WHERE id = ?", (budget_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        allowed = {"monthly_cap_usd", "hard_stop"}
        updates = {k: v for k, v in patch.items() if k in allowed and v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [budget_id]
        conn.execute(f"UPDATE budgets SET {set_clause} WHERE id = ?", params)
        conn.commit()
        row = conn.execute(
            "SELECT * FROM budgets WHERE id = ?", (budget_id,)
        ).fetchone()
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# Venues
# ---------------------------------------------------------------------------


@app.get("/api/venues")
def list_venues(
    ccf_rank: str | None = None,
    cas_zone: int | None = None,
    discipline: str | None = None,
):
    with get_db() as conn:
        query = "SELECT * FROM venue_ranks WHERE 1=1"
        params: list[object] = []
        if ccf_rank:
            query += " AND ccf_rank = ?"
            params.append(ccf_rank)
        if cas_zone is not None:
            query += " AND cas_zone = ?"
            params.append(cas_zone)
        if discipline:
            query += " AND discipline = ?"
            params.append(discipline)
        query += " ORDER BY ccf_rank, cas_zone, canonical_name"
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Topic autonomy + tier
# ---------------------------------------------------------------------------


class PatchAutonomyRequest(BaseModel):
    level: str = Field(pattern=r"^L[0-3]$")


class PatchTierRequest(BaseModel):
    tier: str = Field(pattern=r"^(economy|standard|premium)$")


@app.get("/api/topics/{topic_id}/autonomy")
def get_topic_autonomy(topic_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, autonomy_level FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")
        auto_row = conn.execute(
            "SELECT * FROM topic_autonomy WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    return {
        "topic_id": topic_id,
        "level": row["autonomy_level"] or "L2",
        "overrides": _row_to_dict(auto_row) if auto_row else None,
    }


@app.patch("/api/topics/{topic_id}/autonomy")
def patch_topic_autonomy(topic_id: int, body: PatchAutonomyRequest):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")
        conn.execute(
            "UPDATE topics SET autonomy_level = ? WHERE id = ?",
            (body.level, topic_id),
        )
        conn.execute(
            """
            INSERT INTO topic_autonomy (topic_id, level)
            VALUES (?, ?)
            ON CONFLICT(topic_id) DO UPDATE SET
                level = excluded.level,
                updated_at = datetime('now')
            """,
            (topic_id, body.level),
        )
        conn.commit()
    return {"topic_id": topic_id, "level": body.level}


@app.get("/api/topics/{topic_id}/tier")
def get_topic_tier(topic_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, quality_tier, target_venue_tier FROM topics WHERE id = ?",
            (topic_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")
    from research_harness.tiers import get_tier

    cfg = get_tier(row["quality_tier"])
    return {
        "topic_id": topic_id,
        "quality_tier": row["quality_tier"] or "standard",
        "target_venue_tier": row["target_venue_tier"] or "B",
        "config": {
            "judge_mode": cfg.judge_mode,
            "retries": cfg.retries_after_rubric_miss,
            "rubric_dimensions": cfg.rubric_dimensions,
            "cost_estimate": cfg.cost_estimate_usd,
        },
    }


@app.patch("/api/topics/{topic_id}/tier")
def patch_topic_tier(topic_id: int, body: PatchTierRequest):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")
        conn.execute(
            "UPDATE topics SET quality_tier = ? WHERE id = ?",
            (body.tier, topic_id),
        )
        conn.commit()
    return {"topic_id": topic_id, "quality_tier": body.tier}


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class RollbackRequest(BaseModel):
    to_stage: str
    reason: str


@app.post("/api/topics/{topic_id}/rollback")
def rollback_topic(topic_id: int, body: RollbackRequest):
    from research_harness.storage.db import Database

    db = Database(DB_PATH)
    db.migrate()
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")

        from research_harness.orchestrator.snapshots import rollback_to_stage

        result = rollback_to_stage(
            conn, topic_id, body.to_stage, body.reason, trigger="user"
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Rollback failed")
            )
    finally:
        conn.close()
    return result


@app.get("/api/topics/{topic_id}/rollback/log")
def get_rollback_log(topic_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")
        rows = conn.execute(
            "SELECT * FROM rollback_log WHERE topic_id = ? ORDER BY created_at DESC",
            (topic_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Domain trends (S6)
# ---------------------------------------------------------------------------


_DEFAULT_TRENDS_SCOPE = "discipline:cs"


def _validate_scope(scope: str | None) -> str:
    """Accepted forms: `discipline:<name>`, `domain:<int>`, `topic:<int>`.
    Falls back to the default if None. Raises 400 on malformed input."""
    if not scope:
        return _DEFAULT_TRENDS_SCOPE
    if ":" not in scope:
        raise HTTPException(
            status_code=400,
            detail=f"scope must be `kind:value`, got {scope!r}",
        )
    kind, _, value = scope.partition(":")
    if kind not in {"discipline", "domain", "topic"}:
        raise HTTPException(
            status_code=400,
            detail=f"scope kind must be discipline|domain|topic, got {kind!r}",
        )
    if kind in {"domain", "topic"}:
        try:
            int(value)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"scope `{kind}:` expects an integer, got {value!r}",
            )
    return scope


@app.get("/api/domains/trends")
def get_domain_trends(
    tier: str | None = None,
    scope: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
):
    resolved_scope = _validate_scope(scope)
    with get_db() as conn:
        conditions = ["scope = ?"]
        params: list[Any] = [resolved_scope]
        if tier:
            conditions.append("tier = ?")
            params.append(tier)
        where_sql = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM domain_trends WHERE {where_sql}"
            " ORDER BY publishability_score DESC LIMIT ?",
            (*params, limit),
        ).fetchall()

    if not rows:
        # Editorial seed fallback — only makes sense for the discipline view.
        if resolved_scope == _DEFAULT_TRENDS_SCOPE:
            seed_path = (
                Path(__file__).resolve().parents[2]
                / "research_harness"
                / "research_harness"
                / "data"
                / "domain_trends_seed.json"
            )
            if seed_path.exists():
                seed = json.loads(seed_path.read_text())
                return [
                    {
                        **c,
                        # Tag seed fallback clusters so the UI can label them
                        # honestly ("editorial baseline", not computed).
                        "source": "seed",
                        "paper_count": len(c.get("seed_papers", [])),
                    }
                    for c in seed[:limit]
                ]
        return []

    results = []
    for r in rows:
        d = _row_to_dict(r)
        for field in ("top_venues", "seed_papers"):
            if isinstance(d.get(field), str):
                d[field] = _parse_json_field(d[field], [])
        # Clusters written to the DB by the pipeline are "computed" — derived
        # from real papers in the scope. (Semantic clustering is stubbed in
        # v0.3.x so we still only produce one "Landscape Overview" per scope;
        # the label is honest about what we have.)
        d.setdefault("source", "computed")
        if "paper_count" not in d:
            d["paper_count"] = len(d.get("seed_papers") or [])
        results.append(d)
    return results


class TrendsRefreshRequest(BaseModel):
    tier: str = "standard"
    scope: str | None = None
    dry_run: bool = False

    model_config = {"extra": "forbid"}


@app.post("/api/domains/trends/refresh")
def refresh_domain_trends(body: TrendsRefreshRequest | None = None):
    """Run the trends pipeline for a single scope and persist clusters.
    Refreshing one scope does NOT touch others — delete and insert are both
    keyed on (tier, scope)."""
    from research_harness.trends import refresh_trends

    payload = body or TrendsRefreshRequest()
    resolved_scope = _validate_scope(payload.scope)
    with get_db() as conn:
        try:
            clusters = refresh_trends(
                conn,
                tier=payload.tier,
                scope=resolved_scope,
                dry_run=payload.dry_run,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return {
        "tier": payload.tier,
        "scope": resolved_scope,
        "dry_run": payload.dry_run,
        "cluster_count": len(clusters),
        "clusters": [
            {
                "name": c.name,
                "publishability_score": c.publishability_score,
                "velocity_yoy": c.velocity_yoy,
                "paper_count": c.paper_count,
            }
            for c in clusters
        ],
    }


@app.get("/api/trends/yearly")
def get_trends_yearly(
    scope: str | None = None,
    years: int = Query(default=5, ge=1, le=30),
):
    """Yearly aggregates for the given scope — paper count, median citations,
    distinct venue count. Used by sparklines and cluster detail line charts.
    Server-side aggregated so clients only see ≤ years rows."""
    from research_harness.trends import yearly_counts

    resolved_scope = _validate_scope(scope)
    with get_db() as conn:
        try:
            rows = yearly_counts(conn, scope=resolved_scope, years=years)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return {"scope": resolved_scope, "years": years, "rows": rows}


# ---------------------------------------------------------------------------
# Rubric calibration
# ---------------------------------------------------------------------------


@app.get("/api/calibrations")
def list_calibrations():
    """Return all rubric calibration rows (stage × tier × threshold + stats)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT stage, tier, threshold, false_rollback_rate, reject_rate,"
            " anchor_count, calibrated_at FROM rubric_calibrations"
            " ORDER BY stage, tier"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


class CalibrationRunRequest(BaseModel):
    stage: str | None = None  # None = calibrate all stages
    tier: str | None = None  # None = calibrate all tiers (only with stage=None)
    venue_tier: str = "B"

    model_config = {"extra": "forbid"}


@app.post("/api/calibrations/run")
def run_calibration(body: CalibrationRunRequest | None = None):
    """Recalibrate thresholds from the bundled anchor corpus. Pass no body
    (or stage=null) to calibrate every (stage × tier) combination."""
    from research_harness.calibration import calibrate_all, calibrate_stage_tier

    payload = body or CalibrationRunRequest()
    with get_db() as conn:
        if payload.stage is None:
            results = calibrate_all(conn)
        else:
            tier = payload.tier or "standard"
            results = [
                calibrate_stage_tier(
                    conn,
                    payload.stage,
                    tier,
                    venue_tier=payload.venue_tier,
                )
            ]
    return {
        "count": len(results),
        "results": [
            {
                "stage": r.stage,
                "tier": r.tier,
                "threshold": r.threshold,
                "anchor_count": r.anchor_count,
                "false_rollback_rate": r.false_rollback_rate,
                "reject_rate": r.reject_rate,
                "used_default": r.used_default,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# Rubric scores
# ---------------------------------------------------------------------------


@app.get("/api/topics/{topic_id}/rubric-scores")
def get_rubric_scores(topic_id: int, stage: str | None = None):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found")
        if stage:
            rows = conn.execute(
                "SELECT * FROM rubric_scores WHERE topic_id = ? AND stage = ? ORDER BY scored_at DESC",
                (topic_id, stage),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM rubric_scores WHERE topic_id = ? ORDER BY scored_at DESC",
                (topic_id,),
            ).fetchall()
    results = []
    for r in rows:
        d = _row_to_dict(r)
        if isinstance(d.get("dimension_scores"), str):
            import json as _json

            d["dimension_scores"] = _json.loads(d["dimension_scores"])
        if isinstance(d.get("critique"), str):
            import json as _json

            d["critique"] = _json.loads(d["critique"])
        if isinstance(d.get("evidence_refs"), str):
            import json as _json

            d["evidence_refs"] = _json.loads(d["evidence_refs"])
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# LLM explain — generic endpoint for the in-app PDF reader
# ---------------------------------------------------------------------------


_EXPLAIN_PRESETS: dict[str, str] = {
    "explain": (
        "Explain the following passage in clear, concise English. "
        "Define jargon, expand abbreviations, and clarify any implicit "
        "assumptions. If the passage references a method or result, briefly "
        "describe what it is and why it matters."
    ),
    "summarize": (
        "Summarize the following passage in 2-3 sentences. Capture the main "
        "claim, the evidence, and any caveat the authors explicitly call out."
    ),
    "translate_zh": (
        "Translate the following passage into fluent Simplified Chinese. "
        "Preserve technical terms and cite the English original term in "
        "parentheses on first use."
    ),
    "critique": (
        "Critically evaluate the following passage. Identify any unsupported "
        "claims, ambiguities, or potential weaknesses in reasoning. Be "
        "specific and brief."
    ),
}


class ExplainRequest(BaseModel):
    text: str = Field(..., description="Selected text from the PDF")
    preset: str | None = Field(
        None,
        description="Optional preset id: explain | summarize | translate_zh | critique",
    )
    custom_prompt: str | None = Field(
        None,
        description="User-supplied prompt — overrides preset if both provided",
    )
    paper_title: str | None = Field(None, description="Paper title for context")
    paper_id: int | None = Field(None, description="Paper id for provenance")
    tier: Literal["light", "medium", "heavy"] = Field(
        "medium", description="LLM routing tier"
    )


@app.post("/api/llm/explain")
def llm_explain(body: ExplainRequest):
    """Run a single-shot LLM call against selected PDF text."""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 8000:
        raise HTTPException(
            status_code=400,
            detail=f"selection too long ({len(text)} chars > 8000)",
        )

    instruction = (body.custom_prompt or "").strip()
    if not instruction and body.preset:
        instruction = _EXPLAIN_PRESETS.get(body.preset, "").strip()
    if not instruction:
        instruction = _EXPLAIN_PRESETS["explain"]

    prompt_parts = [instruction, ""]
    if body.paper_title:
        prompt_parts.append(f"Paper: {body.paper_title}")
    prompt_parts.extend(["Passage:", '"""', text, '"""'])
    prompt = "\n".join(prompt_parts)

    try:
        from llm_router import LLMClient
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail=f"llm_router import failed: {exc}"
        ) from exc

    try:
        client = LLMClient()
        response, usage = client.chat_with_usage(prompt, tier=body.tier)
    except Exception as exc:
        logger.exception("llm.explain failed")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    usage_payload: dict[str, Any] | None = None
    if usage is not None:
        usage_payload = {
            "provider": getattr(usage, "provider", None),
            "model": getattr(usage, "model", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
        }

    return {
        "response": response,
        "preset_used": body.preset if not body.custom_prompt else None,
        "tier": body.tier,
        "usage": usage_payload,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    # Ensure our own module-level loggers (e.g. research_harness_mcp.http_api,
    # expansion worker) actually emit at INFO level. Without this uvicorn only
    # configures its own loggers and ours stay silent.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("research_harness_mcp").setLevel(logging.INFO)
    logging.getLogger("research_harness").setLevel(logging.INFO)

    # Restrict reload watcher to the Python package so web/node_modules and other
    # large trees don't trigger spurious reloads when running alongside the
    # Next.js dashboard.
    _package_dir = str(Path(__file__).resolve().parent)

    uvicorn.run(
        "research_harness_mcp.http_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[_package_dir],
    )
