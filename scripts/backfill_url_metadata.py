#!/usr/bin/env python3
"""Backfill metadata for URL-only paper records.

Research Harness can ingest OpenReview/arXiv/DOI sources as URL-only titles
when the provider-specific parser cannot merge metadata immediately. This
script normalizes those records before the usual OpenAlex/S2 enrichment pass.

It is intentionally conservative and safe to re-run:

* only targets URL-like / identifier-like records;
* supports topic scoping;
* defaults to dry-run;
* updates only missing or placeholder fields.

Examples:
    # Preview recent URL-only rows in a topic
    python scripts/backfill_url_metadata.py --topic-id 2 --min-id 1800

    # Apply updates for one topic
    python scripts/backfill_url_metadata.py --topic-id 2 --min-id 1800 --apply

    # Backfill all URL-only rows
    python scripts/backfill_url_metadata.py --all --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "packages", "research_harness")
)

from research_harness.core.paper_pool import PaperPool  # noqa: E402

LOG = logging.getLogger("backfill-url-metadata")

DB_PATH = os.environ.get(
    "RESEARCH_HARNESS_DB_PATH",
    os.path.expanduser("~/.research-harness/pool.db"),
)

URL_RE = re.compile(r"https?://\S+")
OPENREVIEW_RE = re.compile(r"openreview\.net/forum\?id=([A-Za-z0-9_-]+)")
ARXIV_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)(\d{4}\.\d{4,5})(?:v\d+)?",
    re.IGNORECASE,
)
DOI_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Candidate:
    id: int
    title: str
    url: str
    doi: str
    arxiv_id: str
    s2_id: str

    @property
    def source_text(self) -> str:
        return " ".join(v for v in (self.title, self.url, self.doi, self.arxiv_id) if v)


def _value(content: dict[str, Any], key: str) -> Any:
    raw = content.get(key)
    if isinstance(raw, dict) and "value" in raw:
        return raw.get("value")
    return raw


def _is_placeholder_title(title: str) -> bool:
    title = (title or "").strip()
    if not title:
        return True
    lower = title.lower()
    return (
        bool(URL_RE.search(title))
        or lower.startswith(("doi:", "arxiv:", "s2:", "pdf:"))
        or bool(DOI_RE.fullmatch(title))
    )


def _extract_openreview_id(text: str) -> str | None:
    m = OPENREVIEW_RE.search(text or "")
    return m.group(1) if m else None


def _extract_arxiv_id(text: str) -> str | None:
    m = ARXIV_RE.search(text or "")
    return m.group(1) if m else None


def _extract_doi(text: str) -> str | None:
    m = DOI_RE.search(text or "")
    if not m:
        return None
    return m.group(1).rstrip(").,;")


def _fetch_json(url: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "research-harness/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOG.debug("JSON fetch failed for %s: %s", url, exc)
        return None


def _fetch_openreview(forum_id: str) -> dict[str, Any]:
    data = _fetch_json(
        "https://api2.openreview.net/notes?"
        + urllib.parse.urlencode({"forum": forum_id})
    )
    notes = (data or {}).get("notes") or []
    if not notes:
        return {}

    # Prefer the original submission note. api2 returns reviews/decisions too;
    # the submission note usually has id == forum_id and rich fields such as
    # title/authors/abstract. Falling back to a key-count heuristic can pick
    # "Paper Decision" notes, so filter for actual submission-shaped content.
    submission_notes = [
        n
        for n in notes
        if n.get("id") == forum_id
        or {"title", "authors", "abstract"}.issubset((n.get("content") or {}).keys())
    ]
    note_pool = submission_notes or notes
    note = max(note_pool, key=lambda n: len((n.get("content") or {}).keys()))
    content = note.get("content") or {}

    updates: dict[str, Any] = {}
    title = _value(content, "title")
    if isinstance(title, str) and title.strip():
        updates["title"] = title.strip()

    authors = _value(content, "authors")
    if isinstance(authors, list) and authors:
        updates["authors"] = json.dumps([str(a) for a in authors], ensure_ascii=False)

    abstract = _value(content, "abstract")
    if isinstance(abstract, str) and abstract.strip():
        updates["abstract"] = abstract.strip()

    venue = _value(content, "venue")
    if isinstance(venue, str) and venue.strip():
        updates["venue"] = venue.strip()

    bibtex = _value(content, "_bibtex")
    if isinstance(bibtex, str) and bibtex.strip():
        updates["bibtex_auto"] = bibtex.strip()

    pdf = _value(content, "pdf")
    if isinstance(pdf, str) and pdf.strip():
        updates["url"] = (
            "https://openreview.net" + pdf.strip()
            if pdf.startswith("/")
            else pdf.strip()
        )

    return updates


def _fetch_arxiv(arxiv_id: str) -> dict[str, Any]:
    url = (
        "https://export.arxiv.org/api/query?"
        + urllib.parse.urlencode({"id_list": arxiv_id})
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "research-harness/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            root = ET.fromstring(resp.read())
    except (urllib.error.URLError, TimeoutError, ET.ParseError) as exc:
        LOG.debug("arXiv fetch failed for %s: %s", arxiv_id, exc)
        return {}

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return {}

    def text(path: str) -> str:
        node = entry.find(path, ns)
        return " ".join((node.text or "").split()) if node is not None else ""

    title = text("atom:title")
    abstract = text("atom:summary")
    published = text("atom:published")
    authors = [
        " ".join((a.find("atom:name", ns).text or "").split())
        for a in entry.findall("atom:author", ns)
        if a.find("atom:name", ns) is not None
    ]
    updates: dict[str, Any] = {"arxiv_id": arxiv_id, "venue": "arXiv"}
    if title:
        updates["title"] = title
    if abstract:
        updates["abstract"] = abstract
    if published[:4].isdigit():
        updates["year"] = int(published[:4])
    if authors:
        updates["authors"] = json.dumps(authors, ensure_ascii=False)
    updates["url"] = f"https://arxiv.org/abs/{arxiv_id}"
    return updates


def _fetch_crossref(doi: str) -> dict[str, Any]:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    data = _fetch_json(url)
    msg = (data or {}).get("message") or {}
    if not isinstance(msg, dict):
        return {}

    updates: dict[str, Any] = {"doi": doi, "url": f"https://doi.org/{doi}"}

    titles = msg.get("title") or []
    if titles:
        updates["title"] = str(titles[0]).strip()

    abstracts = msg.get("abstract") or ""
    if isinstance(abstracts, str) and abstracts.strip():
        # Crossref abstracts may contain simple JATS tags.
        updates["abstract"] = re.sub(r"<[^>]+>", " ", abstracts).strip()

    containers = msg.get("container-title") or []
    if containers:
        updates["venue"] = str(containers[0]).strip()

    year_parts = (
        ((msg.get("published-print") or {}).get("date-parts") or [])
        or ((msg.get("published-online") or {}).get("date-parts") or [])
        or ((msg.get("created") or {}).get("date-parts") or [])
    )
    if year_parts and year_parts[0] and str(year_parts[0][0]).isdigit():
        updates["year"] = int(year_parts[0][0])

    authors = []
    for author in msg.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = " ".join(
            part
            for part in (author.get("given", ""), author.get("family", ""))
            if part
        ).strip()
        if name:
            authors.append(name)
    if authors:
        updates["authors"] = json.dumps(authors, ensure_ascii=False)

    return {k: v for k, v in updates.items() if v not in ("", None)}


def _apply_updates(
    conn: sqlite3.Connection, candidate: Candidate, updates: dict[str, Any], apply: bool
) -> dict[str, Any]:
    if not updates:
        return {}

    row = conn.execute("SELECT * FROM papers WHERE id = ?", (candidate.id,)).fetchone()
    if row is None:
        return {}

    set_clauses: list[str] = []
    params: list[Any] = []
    applied: dict[str, Any] = {}

    def maybe_set(field: str, value: Any, *, placeholder_only: bool = False) -> None:
        if value is None or value == "":
            return
        old = row[field] if field in row.keys() else None
        if placeholder_only:
            should_set = not old or _is_placeholder_title(str(old))
        else:
            should_set = not old or str(old).strip() in ("", "[]")
        if should_set and field in {"doi", "arxiv_id", "s2_id"}:
            duplicate = conn.execute(
                f"SELECT id FROM papers WHERE {field} = ? AND id != ?",
                (value, candidate.id),
            ).fetchone()
            if duplicate:
                return
        if should_set:
            set_clauses.append(f"{field} = ?")
            params.append(value)
            applied[field] = value

    maybe_set("title", updates.get("title"), placeholder_only=True)
    maybe_set("abstract", updates.get("abstract"))
    maybe_set("authors", updates.get("authors"))
    maybe_set("venue", updates.get("venue"))
    maybe_set("bibtex_auto", updates.get("bibtex_auto"))
    maybe_set("url", updates.get("url"))
    maybe_set("doi", updates.get("doi"))
    maybe_set("arxiv_id", updates.get("arxiv_id"))
    maybe_set("year", updates.get("year"))

    if not set_clauses:
        return {}

    if apply:
        params.append(candidate.id)
        conn.execute(f"UPDATE papers SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()
    return applied


def load_candidates(
    conn: sqlite3.Connection,
    *,
    topic_id: int | None,
    min_id: int | None,
    all_rows: bool,
) -> list[Candidate]:
    query = "SELECT DISTINCT p.* FROM papers p"
    params: list[Any] = []
    clauses: list[str] = []
    if topic_id is not None:
        query += " JOIN paper_topics pt ON p.id = pt.paper_id"
        clauses.append("pt.topic_id = ?")
        params.append(topic_id)
    if min_id is not None:
        clauses.append("p.id >= ?")
        params.append(min_id)
    if not all_rows:
        clauses.append(
            "("
            "p.title LIKE 'http%' OR p.title LIKE 'doi:%' OR p.title LIKE 'arxiv:%' "
            "OR p.url LIKE '%openreview.net/forum?id=%' "
            "OR p.url LIKE '%arxiv.org/abs/%' "
            "OR p.url LIKE '%doi.org/10.%'"
            ")"
        )
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY p.id"

    rows = conn.execute(query, params).fetchall()
    return [
        Candidate(
            id=int(r["id"]),
            title=r["title"] or "",
            url=r["url"] or "",
            doi=r["doi"] or "",
            arxiv_id=r["arxiv_id"] or "",
            s2_id=r["s2_id"] or "",
        )
        for r in rows
    ]


def backfill_candidate(
    conn: sqlite3.Connection,
    pool: PaperPool,
    candidate: Candidate,
    *,
    apply: bool,
    sleep_sec: float,
) -> dict[str, Any]:
    text = candidate.source_text
    updates: dict[str, Any] = {}

    openreview_id = _extract_openreview_id(text)
    if openreview_id:
        updates.update(_fetch_openreview(openreview_id))
        applied = _apply_updates(conn, candidate, updates, apply)
        if apply and applied:
            # OpenReview already provides the fields we usually miss.
            return applied
        return applied

    arxiv_id = candidate.arxiv_id or _extract_arxiv_id(text)
    if arxiv_id:
        updates.update(_fetch_arxiv(arxiv_id))
        applied = _apply_updates(conn, candidate, updates, apply)
        if apply:
            pool.enrich_metadata(candidate.id)
        return applied

    doi = candidate.doi or _extract_doi(text)
    if doi:
        updates.update(_fetch_crossref(doi))
        applied = _apply_updates(conn, candidate, updates, apply)
        if apply:
            pool.enrich_metadata(candidate.id)
        return applied

    time.sleep(sleep_sec)
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB_PATH, help="RH SQLite DB path")
    parser.add_argument("--topic-id", type=int, help="Only update papers linked to topic")
    parser.add_argument("--min-id", type=int, help="Only update papers with id >= min-id")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Inspect all rows in scope, not only URL-like rows",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates. Default is dry-run preview.",
    )
    parser.add_argument("--limit", type=int, help="Max candidates to inspect")
    parser.add_argument("--sleep", type=float, default=0.2, help="Polite delay")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    pool = PaperPool(conn)

    candidates = load_candidates(
        conn, topic_id=args.topic_id, min_id=args.min_id, all_rows=args.all
    )
    if args.limit:
        candidates = candidates[: args.limit]

    LOG.info(
        "Found %d candidates (topic_id=%s, min_id=%s, apply=%s)",
        len(candidates),
        args.topic_id,
        args.min_id,
        args.apply,
    )

    changed = 0
    failed = 0
    for i, candidate in enumerate(candidates, 1):
        try:
            applied = backfill_candidate(
                conn, pool, candidate, apply=args.apply, sleep_sec=args.sleep
            )
        except Exception as exc:  # keep batch backfills resumable
            failed += 1
            LOG.warning("[%d/%d] paper %d failed: %s", i, len(candidates), candidate.id, exc)
            continue
        if applied:
            changed += 1
            preview = {
                key: (str(value)[:120] + "..." if len(str(value)) > 120 else value)
                for key, value in applied.items()
            }
            LOG.info("[%d/%d] paper %d updates=%s", i, len(candidates), candidate.id, preview)
        time.sleep(args.sleep)

    LOG.info(
        "DONE changed=%d/%d failed=%d apply=%s",
        changed,
        len(candidates),
        failed,
        args.apply,
    )
    conn.close()


if __name__ == "__main__":
    main()
