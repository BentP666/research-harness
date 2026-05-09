"""DB-backed paper library.

Per-directory SQLite store at ``<root>/_index.db`` replacing the
pre-0.4 on-disk JSON-per-paper layout. One row per paper_id holds the
full ``PaperRecord`` JSON plus a denormalized ``CatalogEntry`` JSON,
so listing and catalog rebuilds are single SELECT statements.

Legacy migration:
    If the store file doesn't exist but the old ``<root>/papers/*.json``
    and/or ``<root>/_catalog.json`` exists, the first ``save``/``list``/
    ``list_catalog`` call backfills the DB from them transparently.
    Callers don't need to opt in.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..types import CatalogEntry, PaperRecord
from ..utils import first_nonempty_line, flatten_nodes

DEFAULT_LIBRARY_DIRNAME = ".paperindex"
CATALOG_FILENAME = "_catalog.json"
INDEX_DB_FILENAME = "_index.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_records (
    paper_id       TEXT PRIMARY KEY,
    doc_name       TEXT NOT NULL DEFAULT '',
    title          TEXT NOT NULL DEFAULT '',
    pdf_hash       TEXT NOT NULL DEFAULT '',
    page_count     INTEGER NOT NULL DEFAULT 0,
    source_path    TEXT NOT NULL DEFAULT '',
    indexed_at     TEXT NOT NULL DEFAULT '',
    record_json    TEXT NOT NULL,
    catalog_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paper_records_hash ON paper_records(pdf_hash);
CREATE INDEX IF NOT EXISTS idx_paper_records_title ON paper_records(title);
"""


class PaperLibrary:
    """DB-backed paper-record store with legacy JSON migration.

    Public API mirrors the pre-0.4 JSON-file store: callers should not
    need to know the persistence backend changed.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.papers_dir = self.root / "papers"  # kept for migration source
        self._db_path = self.root / INDEX_DB_FILENAME
        self._ensure_schema()
        self._migrate_legacy_if_needed()

    # ------------------------------------------------------------------
    # Public API (matches legacy store.py)
    # ------------------------------------------------------------------

    def save(self, record: PaperRecord) -> Path:
        entry = self.build_catalog_entry(record)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO paper_records "
                "(paper_id, doc_name, title, pdf_hash, page_count, "
                " source_path, indexed_at, record_json, catalog_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.paper_id,
                    record.doc_name,
                    record.title,
                    record.pdf_hash,
                    int(record.page_count or 0),
                    record.source_path,
                    record.indexed_at,
                    json.dumps(record.to_dict(), ensure_ascii=False),
                    json.dumps(entry.to_dict(), ensure_ascii=False),
                ),
            )
            conn.commit()
        # Return DB path — callers that just need a "saved somewhere" handle
        # get one, and legacy callers that ignore the value still work.
        return self._db_path

    def get(self, paper_id: str) -> PaperRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM paper_records WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(
                f"paper_id {paper_id!r} not found in {self._db_path}"
            )
        return PaperRecord.from_dict(json.loads(row[0]))

    def list(self) -> list[PaperRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT record_json FROM paper_records ORDER BY LOWER(title), paper_id"
            ).fetchall()
        return [PaperRecord.from_dict(json.loads(r[0])) for r in rows]

    def find_by_hash(self, pdf_hash: str) -> PaperRecord | None:
        if not pdf_hash:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM paper_records WHERE pdf_hash = ? LIMIT 1",
                (pdf_hash,),
            ).fetchone()
        return PaperRecord.from_dict(json.loads(row[0])) if row else None

    def list_catalog(self) -> list[CatalogEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT catalog_json FROM paper_records ORDER BY LOWER(title), paper_id"
            ).fetchall()
        return [CatalogEntry.from_dict(json.loads(r[0])) for r in rows]

    @staticmethod
    def build_catalog_entry(record: PaperRecord) -> CatalogEntry:
        nodes = flatten_nodes(record.structure.tree)
        return CatalogEntry(
            paper_id=record.paper_id,
            title=record.title,
            doc_name=record.doc_name,
            pdf_hash=record.pdf_hash,
            page_count=record.page_count,
            source_path=record.source_path,
            indexed_at=record.indexed_at,
            section_names=sorted(record.sections.keys()),
            node_titles=[node.title for node in nodes],
            node_summaries=[node.summary for node in nodes if node.summary],
            core_idea=first_nonempty_line(record.card.core_idea or ""),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _migrate_legacy_if_needed(self) -> None:
        """Backfill the DB from pre-0.4 JSON files on first access.

        Idempotent: once the DB has any row the legacy JSON files are
        ignored forever (the DB is authoritative).
        """
        with self._connect() as conn:
            has_row = conn.execute("SELECT 1 FROM paper_records LIMIT 1").fetchone()
        if has_row is not None:
            return
        if not self.papers_dir.exists():
            return
        legacy_paths = sorted(self.papers_dir.glob("*.json"))
        if not legacy_paths:
            return
        with self._connect() as conn:
            for path in legacy_paths:
                if path.name == CATALOG_FILENAME:
                    continue
                try:
                    record = PaperRecord.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                except Exception:
                    continue
                entry = self.build_catalog_entry(record)
                conn.execute(
                    "INSERT OR REPLACE INTO paper_records "
                    "(paper_id, doc_name, title, pdf_hash, page_count, "
                    " source_path, indexed_at, record_json, catalog_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.paper_id,
                        record.doc_name,
                        record.title,
                        record.pdf_hash,
                        int(record.page_count or 0),
                        record.source_path,
                        record.indexed_at,
                        json.dumps(record.to_dict(), ensure_ascii=False),
                        json.dumps(entry.to_dict(), ensure_ascii=False),
                    ),
                )
            conn.commit()
