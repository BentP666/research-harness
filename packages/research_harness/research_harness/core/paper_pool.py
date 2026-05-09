"""Paper pool management."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Any

from ..storage.models import Paper, PaperAnnotation, TopicPaperNote

logger = logging.getLogger(__name__)


def _parse_authors_for_enrich(raw: str | None) -> list[str]:
    """Check if the DB authors field contains actual author names.

    Recognises the same empty patterns as ``latex_compiler.parse_authors_field``
    without importing it (avoids cross-layer dependency).
    """
    if not raw or raw.strip() in ("[]", '""', "null", '""', ""):
        return []
    text = raw.strip()
    # Unwrap outer JSON string quotes
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
            if isinstance(text, str):
                text = text.strip()
        except (ValueError, TypeError):
            pass
    # Try JSON array
    if isinstance(text, str) and text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(a).strip() for a in parsed if str(a).strip()]
        except (ValueError, TypeError):
            pass
    # Semicolon-separated
    if isinstance(text, str) and ";" in text:
        return [a.strip() for a in text.split(";") if a.strip()]
    if isinstance(text, str) and text.strip():
        return [text.strip()]
    return []


class PaperPool:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def _optional_identifier(self, value: str) -> str | None:
        cleaned = value.strip()
        return cleaned or None

    def ingest(
        self, paper: Paper, topic_id: int | None = None, relevance: str = "medium"
    ) -> int:
        existing = self._find_existing(paper)
        authors_json = json.dumps(paper.authors, ensure_ascii=False)
        affiliations_json = json.dumps(paper.affiliations, ensure_ascii=False)
        if existing:
            paper_id = existing["id"]
            self._conn.execute(
                """
                UPDATE papers
                SET title = CASE WHEN title = '' OR title IS NULL THEN ? ELSE title END,
                    authors = CASE WHEN (authors = '' OR authors = '[]') AND ? != '' THEN ? ELSE authors END,
                    affiliations = CASE WHEN (affiliations = '' OR affiliations = '[]') AND ? != '' THEN ? ELSE affiliations END,
                    year = COALESCE(year, ?),
                    venue = CASE WHEN venue = '' THEN ? ELSE venue END,
                    abstract = CASE WHEN (abstract = '' OR abstract IS NULL) AND ? != '' THEN ? ELSE abstract END,
                    doi = CASE WHEN doi = '' THEN ? ELSE doi END,
                    arxiv_id = CASE WHEN arxiv_id = '' THEN ? ELSE arxiv_id END,
                    s2_id = CASE WHEN s2_id = '' THEN ? ELSE s2_id END,
                    url = CASE WHEN ? != '' THEN ? ELSE url END
                WHERE id = ?
                """,
                (
                    paper.title,
                    authors_json,
                    authors_json,
                    affiliations_json,
                    affiliations_json,
                    paper.year,
                    paper.venue,
                    paper.abstract,
                    paper.abstract,
                    paper.doi,
                    paper.arxiv_id,
                    paper.s2_id,
                    paper.url,
                    paper.url,
                    paper_id,
                ),
            )
        else:
            cur = self._conn.execute(
                """
                INSERT INTO papers (title, authors, affiliations, year, venue, abstract, doi, arxiv_id, s2_id, url, pdf_path, pdf_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.title,
                    authors_json,
                    affiliations_json,
                    paper.year,
                    paper.venue,
                    paper.abstract,
                    self._optional_identifier(paper.doi),
                    self._optional_identifier(paper.arxiv_id),
                    self._optional_identifier(paper.s2_id),
                    self._optional_identifier(paper.url),
                    paper.pdf_path,
                    paper.pdf_hash,
                    paper.status,
                ),
            )
            paper_id = int(cur.lastrowid)

        if topic_id is not None:
            self._conn.execute(
                """
                INSERT INTO paper_topics (paper_id, topic_id, relevance)
                VALUES (?, ?, ?)
                ON CONFLICT(paper_id, topic_id) DO UPDATE SET relevance = excluded.relevance
                """,
                (paper_id, topic_id, relevance),
            )

        self._conn.commit()
        return paper_id

    def get(self, paper_id: int) -> Paper | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_paper(row)

    def list_papers(
        self, topic_id: int | None = None, status: str | None = None
    ) -> list[Paper]:
        query = "SELECT p.* FROM papers p"
        params: list[object] = []
        if topic_id is not None:
            query += " JOIN paper_topics pt ON p.id = pt.paper_id WHERE pt.topic_id = ?"
            params.append(topic_id)
            if status:
                query += " AND p.status = ?"
                params.append(status)
        elif status:
            query += " WHERE p.status = ?"
            params.append(status)
        query += " ORDER BY p.created_at DESC, p.id DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_paper(row) for row in rows]

    def upsert_annotation(self, annotation: PaperAnnotation) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO paper_annotations
            (paper_id, section, content, source, confidence, extractor_version, pdf_hash_at_extraction)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (paper_id, section)
            DO UPDATE SET
                content = excluded.content,
                source = excluded.source,
                confidence = excluded.confidence,
                extractor_version = excluded.extractor_version,
                pdf_hash_at_extraction = excluded.pdf_hash_at_extraction,
                updated_at = datetime('now')
            """,
            (
                annotation.paper_id,
                annotation.section,
                annotation.content,
                annotation.source,
                annotation.confidence,
                annotation.extractor_version,
                annotation.pdf_hash_at_extraction,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def get_annotations(self, paper_id: int) -> list[PaperAnnotation]:
        rows = self._conn.execute(
            "SELECT * FROM paper_annotations WHERE paper_id = ? ORDER BY section",
            (paper_id,),
        ).fetchall()
        return [self._row_to_annotation(row) for row in rows]

    def upsert_topic_note(self, note: TopicPaperNote) -> int:
        linked = self._conn.execute(
            "SELECT 1 FROM paper_topics WHERE paper_id = ? AND topic_id = ?",
            (note.paper_id, note.topic_id),
        ).fetchone()
        if linked is None:
            raise ValueError(
                f"paper {note.paper_id} is not linked to topic {note.topic_id}"
            )

        self._conn.execute(
            """
            INSERT INTO topic_paper_notes (paper_id, topic_id, note_type, content, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (paper_id, topic_id, note_type)
            DO UPDATE SET
                content = excluded.content,
                source = excluded.source,
                created_at = datetime('now')
            """,
            (note.paper_id, note.topic_id, note.note_type, note.content, note.source),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM topic_paper_notes WHERE paper_id = ? AND topic_id = ? AND note_type = ?",
            (note.paper_id, note.topic_id, note.note_type),
        ).fetchone()
        return int(row["id"])

    def get_topic_notes(
        self,
        paper_id: int,
        topic_id: int | None = None,
        note_type: str | None = None,
    ) -> list[TopicPaperNote]:
        query = "SELECT * FROM topic_paper_notes WHERE paper_id = ?"
        params: list[object] = [paper_id]
        if topic_id is not None:
            query += " AND topic_id = ?"
            params.append(topic_id)
        if note_type is not None:
            query += " AND note_type = ?"
            params.append(note_type)
        query += " ORDER BY created_at DESC, id DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_topic_note(row) for row in rows]

    def enrich_metadata(self, paper_id: int) -> dict[str, str]:
        """Enrich paper metadata: OpenAlex first (fast, free), S2 fallback.

        Returns dict of fields updated.
        """
        row = self._conn.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Paper {paper_id} not found")

        # --- Phase 1: OpenAlex (free, no rate limit) --------------------------
        updates = self._enrich_from_openalex(paper_id, row)

        # --- Phase 2: S2 for remaining gaps -----------------------------------
        refreshed = self._conn.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        if refreshed is None:
            return updates

        still_needs = (
            not (refreshed["title"] or "").strip()
            or (refreshed["title"] or "").startswith(("doi:", "s2:", "pdf:"))
            or not (refreshed["abstract"] or "").strip()
            or (refreshed["venue"] or "").strip().lower()
            in ("", "arxiv", "arxiv.org", "arxiv preprint")
            or refreshed["citation_count"] is None
            or refreshed["citation_count"] == 0
            or not (refreshed["s2_id"] or "").strip()
        )
        if not still_needs:
            return updates

        s2_updates = self._enrich_from_s2(paper_id, refreshed)
        updates.update(s2_updates)
        return updates

    def _enrich_from_s2(self, paper_id: int, row: Any) -> dict[str, str]:
        """Enrich via Semantic Scholar API. Rate-limited (~1 req/sec externally)."""
        import urllib.request
        import urllib.error

        arxiv_id = (row["arxiv_id"] or "").strip()
        doi = (row["doi"] or "").strip()
        s2_id = (row["s2_id"] or "").strip()
        title_raw = (row["title"] or "").strip()

        lookup_id = None
        if arxiv_id:
            import re

            clean = re.sub(
                r"v\d+$", "", arxiv_id.removeprefix("arxiv:").removeprefix("arXiv:")
            )
            lookup_id = f"ARXIV:{clean}"
        elif doi:
            lookup_id = f"DOI:{doi.removeprefix('doi:').removeprefix('DOI:')}"
        elif s2_id:
            lookup_id = s2_id.removeprefix("s2:").removeprefix("S2:")
        elif title_raw.startswith(("doi:", "DOI:")):
            lookup_id = f"DOI:{title_raw.removeprefix('doi:').removeprefix('DOI:')}"
        elif title_raw.startswith(("s2:", "S2:")):
            lookup_id = title_raw.removeprefix("s2:").removeprefix("S2:")

        if not lookup_id:
            return {}

        url = f"https://api.semanticscholar.org/graph/v1/paper/{lookup_id}?fields=title,authors.name,authors.affiliations,year,venue,abstract,externalIds,citationCount,openAccessPdf"
        api_key = (
            os.environ.get("S2_API_KEY")
            or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
            or ""
        )
        try:
            headers = {"User-Agent": "research-harness/1.0"}
            if api_key:
                headers["x-api-key"] = api_key
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            return {}

        updates: dict[str, str] = {}
        set_clauses: list[str] = []
        params: list[object] = []

        new_title = (data.get("title") or "").strip()
        old_title = (row["title"] or "").strip()
        if new_title and (
            not old_title or old_title.startswith(("doi:", "s2:", "pdf:"))
        ):
            set_clauses.append("title = ?")
            params.append(new_title)
            updates["title"] = new_title

        new_abstract = (data.get("abstract") or "").strip()
        if new_abstract and not (row["abstract"] or "").strip():
            set_clauses.append("abstract = ?")
            params.append(new_abstract)
            updates["abstract"] = new_abstract[:80] + "..."

        new_authors = [
            a.get("name", "") for a in (data.get("authors") or []) if a.get("name")
        ]
        if new_authors and not _parse_authors_for_enrich(row["authors"] or ""):
            set_clauses.append("authors = ?")
            params.append(json.dumps(new_authors, ensure_ascii=False))
            updates["authors"] = str(len(new_authors))

        new_affiliations: list[str] = []
        _aff_seen: set[str] = set()
        for a in data.get("authors") or []:
            for aff in a.get("affiliations") or [] if isinstance(a, dict) else []:
                name = (aff if isinstance(aff, str) else "").strip()
                if name and name not in _aff_seen:
                    _aff_seen.add(name)
                    new_affiliations.append(name)
        old_affiliations = row["affiliations"] if "affiliations" in row.keys() else "[]"
        if new_affiliations and (old_affiliations or "[]") in ("", "[]"):
            set_clauses.append("affiliations = ?")
            params.append(json.dumps(new_affiliations, ensure_ascii=False))
            updates["affiliations"] = str(len(new_affiliations))

        new_year = data.get("year")
        if new_year and row["year"] is None:
            set_clauses.append("year = ?")
            params.append(new_year)
            updates["year"] = str(new_year)

        new_venue = (data.get("venue") or "").strip()
        old_venue = (row["venue"] or "").strip().lower()
        if new_venue and old_venue in ("", "arxiv", "arxiv.org", "arxiv preprint"):
            set_clauses.append("venue = ?")
            params.append(new_venue)
            updates["venue"] = new_venue

        ext_ids = data.get("externalIds") or {}
        new_doi = ext_ids.get("DOI", "")
        if new_doi and not (row["doi"] or "").strip():
            if not self._conn.execute(
                "SELECT id FROM papers WHERE doi = ? AND id != ?", (new_doi, paper_id)
            ).fetchone():
                set_clauses.append("doi = ?")
                params.append(new_doi)
                updates["doi"] = new_doi

        new_arxiv = ext_ids.get("ArXiv", "")
        if new_arxiv and not (row["arxiv_id"] or "").strip():
            if not self._conn.execute(
                "SELECT id FROM papers WHERE arxiv_id = ? AND id != ?",
                (new_arxiv, paper_id),
            ).fetchone():
                set_clauses.append("arxiv_id = ?")
                params.append(new_arxiv)
                updates["arxiv_id"] = new_arxiv

        new_s2 = data.get("paperId", "")
        if new_s2 and not (row["s2_id"] or "").strip():
            if not self._conn.execute(
                "SELECT id FROM papers WHERE s2_id = ? AND id != ?", (new_s2, paper_id)
            ).fetchone():
                set_clauses.append("s2_id = ?")
                params.append(new_s2)
                updates["s2_id"] = new_s2

        new_citation_count = data.get("citationCount")
        if new_citation_count is not None:
            old_count = (
                row["citation_count"] if "citation_count" in row.keys() else None
            )
            if old_count is None or old_count == 0:
                set_clauses.append("citation_count = ?")
                params.append(int(new_citation_count))
                updates["citation_count"] = str(new_citation_count)

        oa_pdf = data.get("openAccessPdf") or {}
        if isinstance(oa_pdf, dict):
            oa_url = (oa_pdf.get("url") or "").strip()
            old_url = (row["url"] or "").strip() if "url" in row.keys() else ""
            if oa_url and not old_url:
                set_clauses.append("url = ?")
                params.append(oa_url)
                updates["open_access_pdf"] = oa_url

        if set_clauses:
            params.append(paper_id)
            self._conn.execute(
                f"UPDATE papers SET {', '.join(set_clauses)} WHERE id = ?", params
            )
            self._conn.commit()

        return updates

    def _enrich_from_openalex(self, paper_id: int, row: Any) -> dict[str, str]:
        """Fallback enrichment via OpenAlex by DOI (preferred) or title search.

        OpenAlex is free, unmetered, and especially strong for venue normalization
        and citation counts on DOI-bearing papers.
        """
        import urllib.parse
        import urllib.request

        doi = (row["doi"] or "").strip()
        title = (row["title"] or "").strip()
        item: dict[str, Any] | None = None
        api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
        mailto = os.environ.get("OPENALEX_MAILTO", "").strip()

        def _fetch(url: str) -> dict[str, Any] | None:
            params = []
            if api_key:
                params.append(f"api_key={api_key}")
            if mailto:
                params.append(f"mailto={urllib.parse.quote(mailto)}")
            sep = "&" if "?" in url else "?"
            full_url = url + (sep + "&".join(params) if params else "")
            try:
                req = urllib.request.Request(
                    full_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "research-harness/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode())
            except Exception:
                return None

        if doi:
            clean = (
                doi.removeprefix("https://doi.org/")
                .removeprefix("http://doi.org/")
                .removeprefix("doi:")
                .removeprefix("DOI:")
            )
            item = _fetch(f"https://api.openalex.org/works/doi:{clean}")

        if (
            item is None
            and title
            and len(title) > 15
            and not title.startswith(("doi:", "s2:", "pdf:"))
        ):
            search = _fetch(
                f"https://api.openalex.org/works?search={urllib.parse.quote(title)}&per-page=1"
            )
            if isinstance(search, dict):
                results = search.get("results") or []
                if results and isinstance(results[0], dict):
                    candidate = results[0]
                    cand_title = (candidate.get("title") or "").strip().lower()
                    if cand_title and self._title_matches(title.lower(), cand_title):
                        item = candidate

        if not isinstance(item, dict):
            return {}

        set_clauses: list[str] = []
        params: list[Any] = []
        updates: dict[str, str] = {}

        # venue
        old_venue = (row["venue"] or "").strip().lower()
        venue_placeholder = old_venue in ("", "arxiv", "arxiv.org", "arxiv preprint")
        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        new_venue = (source.get("display_name") or "").strip()
        if new_venue and venue_placeholder:
            set_clauses.append("venue = ?")
            params.append(new_venue)
            updates["venue"] = f"{new_venue} (OA)"

        # citation_count
        new_cite = item.get("cited_by_count")
        old_cite = row["citation_count"] if "citation_count" in row.keys() else None
        if isinstance(new_cite, int) and (old_cite is None or old_cite == 0):
            set_clauses.append("citation_count = ?")
            params.append(int(new_cite))
            updates["citation_count"] = f"{new_cite} (OA)"

        # year
        new_year = item.get("publication_year")
        if new_year and row["year"] is None:
            set_clauses.append("year = ?")
            params.append(int(new_year))
            updates["year"] = str(new_year)

        # abstract from inverted_index
        if not (row["abstract"] or "").strip():
            inv = item.get("abstract_inverted_index")
            if isinstance(inv, dict) and inv:
                positions: dict[int, str] = {}
                for word, idxs in inv.items():
                    if isinstance(idxs, list):
                        for i in idxs:
                            if isinstance(i, int):
                                positions[i] = word
                if positions:
                    abstract = " ".join(positions[i] for i in sorted(positions))
                    if abstract:
                        set_clauses.append("abstract = ?")
                        params.append(abstract)
                        updates["abstract"] = abstract[:80] + "..."

        # doi (if missing)
        new_doi = (item.get("doi") or "").strip()
        if new_doi:
            new_doi = new_doi.removeprefix("https://doi.org/").removeprefix(
                "http://doi.org/"
            )
        if new_doi and not (row["doi"] or "").strip():
            dup = self._conn.execute(
                "SELECT id FROM papers WHERE doi = ? AND id != ?", (new_doi, paper_id)
            ).fetchone()
            if not dup:
                set_clauses.append("doi = ?")
                params.append(new_doi)
                updates["doi"] = new_doi

        if set_clauses:
            params.append(paper_id)
            self._conn.execute(
                f"UPDATE papers SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            self._conn.commit()

        return updates

    @staticmethod
    def _title_matches(a: str, b: str) -> bool:
        """Loose title match: normalized identical, or one is prefix of the other."""
        import re

        def norm(s: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", s)[:80]

        na, nb = norm(a), norm(b)
        if not na or not nb:
            return False
        return na == nb or na.startswith(nb[:60]) or nb.startswith(na[:60])

    def _find_existing(self, paper: Paper) -> dict[str, int] | None:
        for field_name, value in (
            ("doi", paper.doi),
            ("arxiv_id", paper.arxiv_id),
            ("s2_id", paper.s2_id),
        ):
            if not value:
                continue
            row = self._conn.execute(
                f"SELECT id FROM papers WHERE {field_name} = ?",
                (value,),
            ).fetchone()
            if row:
                return {"id": row["id"]}
        return None

    @staticmethod
    def _row_to_paper(row: sqlite3.Row) -> Paper:
        keys = row.keys() if hasattr(row, "keys") else []
        return Paper(
            id=row["id"],
            title=row["title"],
            authors=json.loads(row["authors"]) if row["authors"] else [],
            affiliations=json.loads(row["affiliations"])
            if "affiliations" in keys and row["affiliations"]
            else [],
            year=row["year"],
            venue=row["venue"],
            abstract=row["abstract"] if "abstract" in keys else "",
            doi=row["doi"] or "",
            arxiv_id=row["arxiv_id"] or "",
            s2_id=row["s2_id"] or "",
            url=row["url"] or "",
            pdf_path=row["pdf_path"],
            pdf_hash=row["pdf_hash"],
            status=row["status"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_annotation(row: sqlite3.Row) -> PaperAnnotation:
        return PaperAnnotation(
            id=row["id"],
            paper_id=row["paper_id"],
            section=row["section"],
            content=row["content"],
            source=row["source"],
            confidence=row["confidence"],
            extractor_version=row["extractor_version"],
            pdf_hash_at_extraction=row["pdf_hash_at_extraction"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_topic_note(row: sqlite3.Row) -> TopicPaperNote:
        return TopicPaperNote(
            id=row["id"],
            paper_id=row["paper_id"],
            topic_id=row["topic_id"],
            note_type=row["note_type"],
            content=row["content"],
            source=row["source"],
            created_at=row["created_at"],
        )
