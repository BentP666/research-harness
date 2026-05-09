"""Report generation, persistence, and sharing.

Design notes:
- We do NOT compile LaTeX server-side. The PhD's primary consumer is an
  advisor reading in a browser or print-to-PDF — HTML + Markdown is enough.
  This avoids a heavy LaTeX toolchain dependency and ships in one day.
- Reports reuse existing section drafts from artifacts when available, and
  generate-on-demand via section_draft for missing sections.
- Versioning is flat — each regeneration bumps version_minor. Major bumps
  happen on template change.
- Share tokens are opaque URL-safe strings. Advisors open read-only view
  without auth.
"""

from __future__ import annotations

import html
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ..storage.db import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

# Each template defines which sections to include, and a short description.
# The frontend also has i18n copies — keep keys aligned.
REPORT_TEMPLATES: dict[str, dict[str, Any]] = {
    "abstract_only": {
        "name": "Abstract check",
        "sections": ["abstract"],
        "description": "Just the abstract — 5-min advisor review.",
        "estimated_seconds": 120,
        "estimated_cost_usd": 0.05,
    },
    "abstract_intro": {
        "name": "Pitch package",
        "sections": ["abstract", "introduction"],
        "description": "Abstract + Introduction — advisor decides the angle.",
        "estimated_seconds": 240,
        "estimated_cost_usd": 0.10,
    },
    "deep_pitch": {
        "name": "Deep pitch",
        "sections": ["abstract", "introduction", "related_work", "method"],
        "description": "+ Related work + Method outline.",
        "estimated_seconds": 480,
        "estimated_cost_usd": 0.18,
    },
    "full_review": {
        "name": "Full review",
        "sections": [
            "abstract",
            "introduction",
            "related_work",
            "method",
            "experiments",
            "results",
            "discussion",
            "conclusion",
        ],
        "description": "Complete draft with self-assessment and risk list.",
        "estimated_seconds": 1080,
        "estimated_cost_usd": 0.45,
    },
}

SECTION_LABELS = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "related_work": "Related Work",
    "method": "Method",
    "experiments": "Experiments",
    "results": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
}


@dataclass
class ReportSummary:
    id: int
    topic_id: int
    template: str
    title: str
    sections: list[str]
    version_major: int
    version_minor: int
    has_share: bool
    share_token: str | None
    share_expires_at: str | None
    created_at: str
    updated_at: str
    word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Draft sourcing
# ---------------------------------------------------------------------------


def _fetch_existing_section_drafts(
    db: Database, topic_id: int
) -> dict[str, dict[str, Any]]:
    """Pull the latest non-stale section_draft artifacts for a topic."""
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id, artifact_type, title, payload, created_at, is_stale
            FROM artifacts
            WHERE topic_id = ? AND artifact_type = 'section_draft'
              AND COALESCE(is_stale, 0) = 0
            ORDER BY created_at DESC
            """,
            (topic_id,),
        ).fetchall()
    except Exception as exc:
        logger.debug("fetch section_drafts failed: %s", exc)
        return {}
    finally:
        conn.close()

    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        try:
            payload = json.loads(r["payload"]) if r["payload"] else {}
        except (ValueError, TypeError):
            continue
        # Determine section name. Prefer explicit field, fall back to title parse.
        sec = payload.get("section") or payload.get("name") or ""
        if not sec:
            title = (r["title"] or "").lower()
            for candidate in SECTION_LABELS:
                if candidate in title or candidate.replace("_", " ") in title:
                    sec = candidate
                    break
        if sec and sec not in out:
            out[sec] = {
                "content": payload.get("content") or payload.get("text") or "",
                "word_count": payload.get("word_count"),
                "citations": payload.get("citations_used", []),
                "artifact_id": r["id"],
                "created_at": r["created_at"],
            }
    return out


def _draft_section_on_demand(
    db: Database,
    topic_id: int,
    section: str,
    *,
    extra_instructions: str = "",
) -> dict[str, Any]:
    """Call section_draft primitive for sections we don't have yet."""
    try:
        from ..execution.llm_primitives import section_draft
    except Exception as exc:
        return {"content": f"[Section '{section}' unavailable: {exc}]"}
    try:
        out = section_draft(
            db=db,
            topic_id=topic_id,
            section=section,
            extra_instructions=extra_instructions,
        )
        return {
            "content": out.draft.content,
            "word_count": out.draft.word_count,
            "citations": out.draft.citations_used,
        }
    except Exception as exc:  # pragma: no cover
        logger.warning("on-demand section_draft[%s] failed: %s", section, exc)
        return {"content": f"[Could not draft {section}: {exc}]"}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(
    *,
    topic_name: str,
    template: str,
    sections_ordered: list[tuple[str, dict[str, Any]]],
    include_confidence: bool = True,
) -> str:
    """Render a clean, PI-friendly Markdown document."""
    tmpl = REPORT_TEMPLATES.get(template, {})
    lines: list[str] = []
    lines.append(f"# {topic_name}")
    lines.append("")
    lines.append(f"*{tmpl.get('name', template)} · auto-generated draft*")
    lines.append("")
    if include_confidence:
        lines.append(
            "> AI-generated content. Paragraphs tagged `[AI]` are first-pass "
            "output; paragraphs tagged `[reviewed]` have been edited by the author."
        )
        lines.append("")
    for sec_id, sec in sections_ordered:
        lines.append(f"## {SECTION_LABELS.get(sec_id, sec_id.title())}")
        content = (sec.get("content") or "").strip()
        if content:
            lines.append(content)
        else:
            lines.append(f"_[Section '{sec_id}' has no draft yet.]_")
        wc = sec.get("word_count")
        if wc:
            lines.append("")
            lines.append(f"<sub>{wc} words</sub>")
        lines.append("")
    return "\n".join(lines)


def render_html(markdown_content: str, *, title: str) -> str:
    """Minimal MD → HTML. Server-side safe subset (no external deps)."""
    # Very small, deliberate MD→HTML (headings, paragraphs, inline code).
    # Heavy rendering happens client-side where we have more libraries.
    body_lines: list[str] = []
    for raw in markdown_content.split("\n"):
        line = raw.rstrip()
        if line.startswith("# "):
            body_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            body_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("> "):
            body_lines.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif not line.strip():
            body_lines.append("")
        else:
            body_lines.append(f"<p>{html.escape(line)}</p>")
    body = "\n".join(body_lines)
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{escaped_title}</title>
  <style>
    body {{ font: 15px/1.75 "Iowan Old Style", Palatino, Georgia, serif;
           max-width: 720px; margin: 48px auto; padding: 0 20px; color: #1f2230; }}
    h1 {{ font-size: 28px; margin: 0 0 4px; letter-spacing: -0.01em; }}
    h2 {{ font-size: 20px; margin: 32px 0 12px; letter-spacing: -0.005em; }}
    p {{ margin: 0 0 14px; text-align: justify; hyphens: auto; }}
    blockquote {{ margin: 12px 0; padding: 10px 16px; border-left: 3px solid #c8c8d6;
                  color: #555; background: #fafaff; font-size: 13px; }}
    sub {{ color: #888; font-size: 11px; }}
    @media print {{
      body {{ margin: 0; max-width: 100%; font-size: 11pt; }}
      h1 {{ page-break-before: avoid; }}
      h2 {{ page-break-after: avoid; }}
    }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_report(
    db: Database,
    topic_id: int,
    *,
    template: str = "abstract_only",
    title: str = "",
    draft_missing: bool = True,
    extra_instructions: str = "",
) -> ReportSummary:
    """Create or regenerate a report for a topic.

    Reuses existing section_draft artifacts when available. If
    ``draft_missing=True`` calls section_draft for any missing section; if
    False the section is filled with a placeholder (cheap preview mode).

    ``extra_instructions`` flows from the advisor-report composer straight into
    section_draft so the author can steer tone, focus, audience, etc. without
    overwriting the standard prompt scaffolding.
    """
    if template not in REPORT_TEMPLATES:
        raise ValueError(f"unknown template: {template}")

    conn = db.connect()
    try:
        topic_row = conn.execute(
            "SELECT id, name FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if topic_row is None:
            raise ValueError(f"topic not found: {topic_id}")
        topic_name = title or topic_row["name"]
    finally:
        conn.close()

    sections = REPORT_TEMPLATES[template]["sections"]
    # When extra instructions are present we deliberately bypass existing
    # section_draft artifacts — otherwise a "focus on XYZ" request would be
    # silently ignored because we'd reuse a previous generic draft.
    existing = (
        {}
        if extra_instructions.strip()
        else _fetch_existing_section_drafts(db, topic_id)
    )

    rendered: list[tuple[str, dict[str, Any]]] = []
    total_words = 0
    for sec in sections:
        sec_content = existing.get(sec)
        if sec_content is None and draft_missing:
            sec_content = _draft_section_on_demand(
                db,
                topic_id,
                sec,
                extra_instructions=extra_instructions,
            )
        if sec_content is None:
            sec_content = {
                "content": f"_[Section '{sec}' not drafted yet.]_",
                "word_count": 0,
            }
        rendered.append((sec, sec_content))
        total_words += int(sec_content.get("word_count") or 0)

    md = render_markdown(
        topic_name=topic_name,
        template=template,
        sections_ordered=rendered,
    )
    html_body = render_html(md, title=topic_name)

    metadata = {
        "word_count": total_words,
        "section_count": len(sections),
        "draft_missing": draft_missing,
        "estimated_cost": REPORT_TEMPLATES[template]["estimated_cost_usd"],
    }

    # Versioning — find last report for this topic+template.
    conn = db.connect()
    try:
        row = conn.execute(
            """
            SELECT MAX(version_minor) AS v
            FROM reports WHERE topic_id = ? AND template = ?
            """,
            (topic_id, template),
        ).fetchone()
        next_minor = int((row["v"] or 0)) + 1
        cur = conn.execute(
            """
            INSERT INTO reports
                (topic_id, template, title, sections_json, content_md,
                 content_html, metadata_json, version_minor, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                topic_id,
                template,
                topic_name,
                json.dumps(sections),
                md,
                html_body,
                json.dumps(metadata),
                next_minor,
            ),
        )
        report_id = int(cur.lastrowid or 0)
        conn.commit()
    finally:
        conn.close()

    return _hydrate_summary(db, report_id)


def list_reports(db: Database, topic_id: int) -> list[ReportSummary]:
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id FROM reports WHERE topic_id = ?
            ORDER BY updated_at DESC
            """,
            (topic_id,),
        ).fetchall()
        ids = [int(r["id"]) for r in rows]
    finally:
        conn.close()
    return [_hydrate_summary(db, rid) for rid in ids]


def get_report(db: Database, report_id: int) -> dict[str, Any] | None:
    """Full report detail, including rendered content."""
    conn = db.connect()
    try:
        row = conn.execute(
            """
            SELECT r.*, t.name AS topic_name
            FROM reports r
            JOIN topics t ON t.id = r.topic_id
            WHERE r.id = ?
            """,
            (report_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
    finally:
        conn.close()
    d["sections"] = json.loads(d.get("sections_json") or "[]")
    d["metadata"] = json.loads(d.get("metadata_json") or "{}")
    return d


def get_report_by_share_token(db: Database, token: str) -> dict[str, Any] | None:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id FROM reports WHERE share_token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        rid = int(row["id"])
    finally:
        conn.close()
    rep = get_report(db, rid)
    if rep is None:
        return None
    # Expiry check
    exp = rep.get("share_expires_at")
    if exp:
        try:
            expires = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires:
                return {"error": "share link expired"}
        except (ValueError, TypeError):
            pass
    return rep


def create_share_token(
    db: Database, report_id: int, *, expires_in_days: int | None = 14
) -> dict[str, Any]:
    token = secrets.token_urlsafe(16)
    expires_at = None
    if expires_in_days:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        ).isoformat()
    conn = db.connect()
    try:
        conn.execute(
            """
            UPDATE reports
            SET share_token = ?, share_expires_at = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (token, expires_at, report_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"token": token, "expires_at": expires_at}


def _hydrate_summary(db: Database, report_id: int) -> ReportSummary:
    full = get_report(db, report_id)
    if full is None:
        raise ValueError(f"report {report_id} not found")
    return ReportSummary(
        id=int(full["id"]),
        topic_id=int(full["topic_id"]),
        template=full["template"],
        title=full.get("title", ""),
        sections=full["sections"],
        version_major=int(full.get("version_major", 0)),
        version_minor=int(full.get("version_minor", 1)),
        has_share=bool(full.get("share_token")),
        share_token=full.get("share_token"),
        share_expires_at=full.get("share_expires_at"),
        created_at=full.get("created_at", ""),
        updated_at=full.get("updated_at", ""),
        word_count=int(full.get("metadata", {}).get("word_count", 0) or 0),
        metadata=full.get("metadata", {}),
    )
