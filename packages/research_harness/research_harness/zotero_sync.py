"""Synchronize Research Harness topic papers into Zotero.

RH remains the provenance system, while Zotero becomes the human reading surface.
The module now supports RH -> Zotero push and Zotero -> RH pull.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .zotero_resource import (
    ZoteroChild,
    ZoteroResource,
    ZoteroWebApiResource,
    clean_zotero_note_html,
    coerce_zotero_child,
    create_zotero_resource_from_env,
)

DEFAULT_ROOT_COLLECTION = "Research Harness"


class ZoteroSyncError(RuntimeError):
    """Raised when Zotero synchronization cannot continue."""


@dataclass(frozen=True)
class ZoteroSyncRecord:
    paper_id: int
    topic_id: int
    topic_name: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""
    abstract: str = ""
    pdf_path: str = ""
    status: str = "meta_only"
    deep_read: bool = False
    relevance: str = "medium"
    ccf_rank: str = ""
    cas_zone: str = ""
    venue_level_label: str = ""
    annotations: list[dict[str, Any]] = field(default_factory=list)
    topic_notes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ZoteroSyncedPaper:
    paper_id: int
    title: str
    action: str
    zotero_item_key: str = ""
    zotero_note_key: str = ""


@dataclass(frozen=True)
class ZoteroSyncResult:
    topic: str
    topic_id: int | None
    dry_run: bool
    planned_count: int
    synced_count: int = 0
    skipped_count: int = 0
    records: list[dict[str, Any]] = field(default_factory=list)
    papers: list[ZoteroSyncedPaper] = field(default_factory=list)
    root_collection_key: str = ""
    topic_collection_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["papers"] = [asdict(item) for item in self.papers]
        return payload


@dataclass(frozen=True)
class ZoteroImportedItem:
    paper_id: int
    title: str
    action: str
    zotero_item_key: str = ""
    zotero_child_key: str = ""
    target_table: str = ""
    target_id: int | None = None


@dataclass(frozen=True)
class ZoteroPullResult:
    topic: str
    topic_id: int | None
    dry_run: bool
    planned_count: int
    imported_count: int = 0
    skipped_count: int = 0
    items: list[ZoteroImportedItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["items"] = [asdict(item) for item in self.items]
        return payload


@dataclass(frozen=True)
class PreparedZoteroChildImport:
    note_type: str
    source_kind: str
    content: str


@dataclass(frozen=True)
class VenueRank:
    ccf_rank: str = ""
    cas_zone: str = ""
    label: str = ""


# Backward-compatible names for callers/tests that imported the old temporary
# raw Web API client from this module. New code should import from
# research_harness.zotero_resource directly.
ZoteroClient = ZoteroResource
ZoteroWebApiClient = ZoteroWebApiResource
create_web_api_client_from_env = create_zotero_resource_from_env


def ensure_zotero_sync_schema(conn: sqlite3.Connection) -> None:
    ensure_topic_note_source_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zotero_item_links (
            paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            zotero_library_id TEXT DEFAULT '',
            zotero_library_type TEXT DEFAULT 'user',
            zotero_collection_key TEXT DEFAULT '',
            zotero_item_key TEXT NOT NULL,
            zotero_note_key TEXT DEFAULT '',
            content_hash TEXT NOT NULL,
            last_synced_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (paper_id, topic_id, zotero_library_id, zotero_library_type)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_zotero_item_links_topic
        ON zotero_item_links(topic_id)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zotero_import_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            zotero_library_id TEXT DEFAULT '',
            zotero_library_type TEXT DEFAULT 'user',
            zotero_item_key TEXT NOT NULL,
            zotero_child_key TEXT NOT NULL,
            zotero_child_type TEXT NOT NULL,
            target_table TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            last_imported_at TEXT DEFAULT (datetime('now')),
            UNIQUE (
                topic_id, paper_id, zotero_library_id, zotero_library_type,
                zotero_child_key, content_hash
            )
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_zotero_import_links_topic
        ON zotero_import_links(topic_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_zotero_import_links_paper
        ON zotero_import_links(paper_id)
        """
    )
    conn.commit()


def ensure_topic_note_source_schema(conn: sqlite3.Connection) -> None:
    """Allow multiple Zotero-origin notes while preserving typed-note upserts.

    Historical RH schemas enforced one ``topic_paper_notes`` row per
    ``(paper_id, topic_id, note_type)``. That is useful for RH-authored note
    types such as ``relevance`` but too restrictive for Zotero, where a human can
    create many notes/highlights for the same paper. The source-aware unique
    index keeps legacy ``INSERT OR REPLACE`` behavior for empty-source notes and
    lets imported Zotero rows remain individually traceable.
    """
    conn.execute("UPDATE topic_paper_notes SET source = '' WHERE source IS NULL")
    conn.execute(
        """
        DELETE FROM topic_paper_notes
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM topic_paper_notes
            GROUP BY paper_id, topic_id, note_type, source
        )
        """
    )
    conn.execute("DROP INDEX IF EXISTS idx_topic_paper_notes_unique")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_topic_paper_notes_unique_source
        ON topic_paper_notes(paper_id, topic_id, note_type, source)
        """
    )


def load_topic_sync_records(
    conn: sqlite3.Connection, *, topic_name: str, limit: int | None = None
) -> list[ZoteroSyncRecord]:
    limit_sql = " LIMIT ?" if limit is not None else ""
    params: list[Any] = [topic_name]
    if limit is not None:
        params.append(limit)
    rows = conn.execute(
        f"""
        SELECT p.*, t.id AS topic_id, t.name AS topic_name, pt.relevance
        FROM papers p
        JOIN paper_topics pt ON pt.paper_id = p.id
        JOIN topics t ON t.id = pt.topic_id
        WHERE t.name = ?
        ORDER BY COALESCE(p.deep_read, 0) DESC, p.year DESC, p.id
        {limit_sql}
        """,
        params,
    ).fetchall()
    return [_record_from_row(conn, row) for row in rows]


def filter_sync_records_by_paper_ids(
    records: list[ZoteroSyncRecord], paper_ids: list[int] | None
) -> list[ZoteroSyncRecord]:
    """Preserve caller order when selecting a subset of topic records."""
    if not paper_ids:
        return records
    wanted_ids = [int(paper_id) for paper_id in paper_ids if int(paper_id) > 0]
    if not wanted_ids:
        return []
    record_by_id = {record.paper_id: record for record in records}
    return [
        record_by_id[paper_id] for paper_id in wanted_ids if paper_id in record_by_id
    ]


def build_zotero_item_payload(
    record: ZoteroSyncRecord, *, collection_key: str
) -> dict[str, Any]:
    tags = _tags_for(record)
    extra_lines = [
        f"RH paper_id: {record.paper_id}",
        f"RH topic_id: {record.topic_id}",
        f"RH topic: {record.topic_name}",
    ]
    if record.arxiv_id:
        extra_lines.append(f"arXiv: {record.arxiv_id.removeprefix('arxiv:')}")

    payload: dict[str, Any] = {
        "itemType": "journalArticle",
        "title": record.title or f"RH Paper {record.paper_id}",
        "creators": [_creator_payload(author) for author in record.authors],
        "date": str(record.year or ""),
        "publicationTitle": record.venue,
        "DOI": record.doi,
        "url": record.url or _arxiv_url(record.arxiv_id),
        "abstractNote": record.abstract,
        "extra": "\n".join(extra_lines),
        "tags": [{"tag": tag} for tag in tags],
        "collections": [collection_key],
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def build_zotero_note_html(record: ZoteroSyncRecord) -> str:
    deep_reading = _deep_reading_dict(record)
    venue_level = _record_venue_level_label(record)
    parts = [
        "<h1>RH 精读卡片</h1>",
        "<p>"
        + "<br/>".join(
            _escape_lines(
                [
                    f"RH paper_id: {record.paper_id}",
                    f"主题: {record.topic_name}",
                    f"相关性: {record.relevance}",
                    f"状态: {record.status}",
                    f"精读: {'是' if record.deep_read else '否'}",
                    f"论文级别: {venue_level}" if venue_level else "",
                    f"Venue: {record.venue}" if record.venue else "",
                ]
            )
        )
        + "</p>",
    ]

    reading_reason = _first_topic_note(record) or record.abstract
    if reading_reason:
        parts.extend(
            [
                "<h2>为什么值得读</h2>",
                _brief_zh_paragraph(
                    reading_reason,
                    max_chars=260,
                    fallback=(
                        f"这篇论文已被 RH 标记为 {record.relevance} 相关并完成精读。"
                        "建议重点核对问题设定、方法流程、评估设计、证据强度与局限。"
                    ),
                ),
            ]
        )
    if deep_reading.get("algorithm_walkthrough"):
        parts.extend(
            [
                "<h2>核心方法</h2>",
                _brief_zh_paragraph(
                    deep_reading["algorithm_walkthrough"],
                    max_chars=520,
                    fallback=(
                        "RH 已完成方法层精读；建议重点查看论文的任务设定、"
                        "系统/算法流程、关键假设、baseline 与评估指标。"
                    ),
                ),
            ]
        )
    risk_text = deep_reading.get("limitation_analysis") or deep_reading.get(
        "critical_assessment"
    )
    if risk_text:
        parts.extend(
            [
                "<h2>局限/风险</h2>",
                _brief_zh_paragraph(
                    risk_text,
                    max_chars=420,
                    fallback=(
                        "RH 已记录该论文的局限与风险；阅读时应重点检查假设是否过强、"
                        "实验是否充分、结论是否可外推，以及是否存在评测或引用偏差。"
                    ),
                ),
            ]
        )
    if deep_reading.get("reproducibility_assessment"):
        parts.extend(
            [
                "<h2>复现/证据</h2>",
                _brief_zh_paragraph(
                    deep_reading["reproducibility_assessment"],
                    max_chars=320,
                    fallback=(
                        "RH 已记录复现/证据判断；阅读时应核对代码、数据、"
                        "实验细节、消融、统计显著性与人工/模型评审协议。"
                    ),
                ),
            ]
        )
    implications = deep_reading.get("research_implications")
    if implications:
        parts.extend(
            [
                "<h2>RH 启示</h2>",
                _brief_zh_list(
                    implications,
                    max_items=2,
                    max_chars=220,
                    fallback=(
                        "这篇论文可作为 RH 设计科研流程、证据治理、"
                        "可复现性检查或人机协作边界时的参考样例。"
                    ),
                ),
            ]
        )
    if record.topic_notes:
        parts.append("<h2>Topic Notes</h2>")
        for note in record.topic_notes[:2]:
            note_type = html.escape(str(note.get("note_type") or "note"))
            source = html.escape(str(note.get("source") or ""))
            parts.append(f"<h3>{note_type}</h3>")
            if source:
                parts.append(f"<p><em>source: {source}</em></p>")
            parts.append(
                _brief_zh_paragraph(
                    note.get("content"),
                    max_chars=260,
                    fallback="RH 已记录该 topic note；可在 RH 数据库中查看完整内容。",
                )
            )

    return "\n".join(parts)


def build_content_hash(item_payload: dict[str, Any], note_html: str) -> str:
    blob = json.dumps(
        {"item": item_payload, "note": note_html},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ZoteroSyncService:
    def __init__(
        self,
        *,
        db_path: str | Path,
        client: ZoteroClient | None = None,
        library_id: str = "",
        library_type: str = "user",
    ) -> None:
        self.db_path = Path(db_path)
        self.client = client
        self.library_id = library_id
        self.library_type = library_type

    def sync_topic(
        self,
        topic_name: str,
        *,
        root_collection: str = DEFAULT_ROOT_COLLECTION,
        topic_collection_name: str | None = None,
        target_collection_key: str | None = None,
        include_notes: bool = True,
        dry_run: bool = False,
        limit: int | None = None,
        force: bool = False,
        paper_ids: list[int] | None = None,
    ) -> ZoteroSyncResult:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            ensure_zotero_sync_schema(conn)
            records = load_topic_sync_records(
                conn,
                topic_name=topic_name,
                limit=None if paper_ids else limit,
            )
            records = filter_sync_records_by_paper_ids(records, paper_ids)
            if limit is not None:
                records = records[:limit]
            topic_id = records[0].topic_id if records else None
            if dry_run:
                return ZoteroSyncResult(
                    topic=topic_name,
                    topic_id=topic_id,
                    dry_run=True,
                    planned_count=len(records),
                    records=[_record_preview(record) for record in records],
                )
            if self.client is None:
                raise ZoteroSyncError("A Zotero client is required unless dry_run=True")

            root_key = ""
            topic_key = str(target_collection_key or "").strip()
            if not topic_key:
                root_key = self._ensure_collection(root_collection, None)
                zotero_topic_collection = topic_collection_name or topic_name
                topic_key = self._ensure_collection(zotero_topic_collection, root_key)
            synced: list[ZoteroSyncedPaper] = []
            skipped = 0
            for record in records:
                item_payload = build_zotero_item_payload(
                    record, collection_key=topic_key
                )
                note_html = build_zotero_note_html(record) if include_notes else ""
                content_hash = build_content_hash(item_payload, note_html)
                existing = self._existing_link(conn, record)
                if existing and not force and existing["content_hash"] == content_hash:
                    if (
                        existing["zotero_library_id"] != self.library_id
                        or existing["zotero_library_type"] != self.library_type
                    ):
                        self._upsert_link(
                            conn,
                            record,
                            str(existing["zotero_collection_key"] or topic_key),
                            str(existing["zotero_item_key"] or ""),
                            str(existing["zotero_note_key"] or ""),
                            content_hash,
                        )
                    skipped += 1
                    synced.append(
                        ZoteroSyncedPaper(
                            paper_id=record.paper_id,
                            title=record.title,
                            action="skipped",
                            zotero_item_key=existing["zotero_item_key"],
                            zotero_note_key=existing["zotero_note_key"] or "",
                        )
                    )
                    continue

                action = "created"
                item_key = existing["zotero_item_key"] if existing else ""
                if not item_key:
                    item_key = (
                        self.client.find_item_by_tag(f"rh-paper-id:{record.paper_id}")
                        or ""
                    )
                if item_key:
                    self.client.update_item(item_key, item_payload)
                    action = "updated"
                else:
                    item_key, note_key = self._create_item_and_initial_note(
                        item_payload=item_payload,
                        note_html=note_html,
                        include_notes=include_notes,
                        record=record,
                    )
                    self._upsert_link(
                        conn, record, topic_key, item_key, note_key, content_hash
                    )
                    synced.append(
                        ZoteroSyncedPaper(
                            paper_id=record.paper_id,
                            title=record.title,
                            action=action,
                            zotero_item_key=item_key,
                            zotero_note_key=note_key,
                        )
                    )
                    continue

                note_key = existing["zotero_note_key"] if existing else ""
                if include_notes:
                    note_tags = _rh_note_tags(record.paper_id)
                    if note_key:
                        self.client.update_note(
                            note_key, item_key, note_html, note_tags
                        )
                    else:
                        note_key = self.client.create_note(
                            item_key, note_html, note_tags
                        )

                self._upsert_link(
                    conn, record, topic_key, item_key, note_key, content_hash
                )
                synced.append(
                    ZoteroSyncedPaper(
                        paper_id=record.paper_id,
                        title=record.title,
                        action=action,
                        zotero_item_key=item_key,
                        zotero_note_key=note_key,
                    )
                )
            conn.commit()
            return ZoteroSyncResult(
                topic=topic_name,
                topic_id=topic_id,
                dry_run=False,
                planned_count=len(records),
                synced_count=len([p for p in synced if p.action != "skipped"]),
                skipped_count=skipped,
                records=[_record_preview(record) for record in records],
                papers=synced,
                root_collection_key=root_key,
                topic_collection_key=topic_key,
            )
        finally:
            conn.close()

    def pull_topic(
        self,
        topic_name: str,
        *,
        dry_run: bool = False,
        limit: int | None = None,
        include_rh_generated: bool = False,
    ) -> ZoteroPullResult:
        """Import Zotero user-authored notes and annotations for RH-linked papers.

        Pull is append-only by default: each distinct Zotero child/content hash
        becomes one RH topic note and one import-link row. RH-generated deep-read
        notes are skipped unless ``include_rh_generated`` is set.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            ensure_zotero_sync_schema(conn)
            links = _load_topic_zotero_links(
                conn,
                topic_name=topic_name,
                library_id=self.library_id,
                library_type=self.library_type,
                limit=limit,
            )
            topic_id = int(links[0]["topic_id"]) if links else None
            if self.client is None:
                raise ZoteroSyncError("A Zotero client is required for pull_topic")

            imported: list[ZoteroImportedItem] = []
            skipped = 0
            planned = 0
            for link in links:
                paper_id = int(link["paper_id"])
                item_key = str(link["zotero_item_key"])
                title = str(link["title"] or "")
                rh_note_key = str(link["zotero_note_key"] or "")
                for child in self._list_reading_children(item_key):
                    if not child.key:
                        continue
                    if not include_rh_generated and _is_rh_generated_child(
                        child.key, child.tags, rh_note_key
                    ):
                        skipped += 1
                        continue
                    prepared = _prepare_zotero_child_import(child)
                    if prepared is None:
                        skipped += 1
                        continue
                    content_hash = _hash_zotero_child_content(
                        child.key, prepared.content
                    )
                    existing = _find_import_link(
                        conn,
                        topic_id=int(link["topic_id"]),
                        paper_id=paper_id,
                        library_id=self.library_id,
                        library_type=self.library_type,
                        child_key=child.key,
                        content_hash=content_hash,
                    )
                    if existing is not None:
                        skipped += 1
                        imported.append(
                            ZoteroImportedItem(
                                paper_id=paper_id,
                                title=title,
                                action="skipped",
                                zotero_item_key=item_key,
                                zotero_child_key=child.key,
                                target_table=existing["target_table"],
                                target_id=int(existing["target_id"]),
                            )
                        )
                        continue

                    planned += 1
                    if dry_run:
                        imported.append(
                            ZoteroImportedItem(
                                paper_id=paper_id,
                                title=title,
                                action="would_import",
                                zotero_item_key=item_key,
                                zotero_child_key=child.key,
                                target_table="topic_paper_notes",
                            )
                        )
                        continue

                    target_id = _insert_zotero_note(
                        conn,
                        topic_id=int(link["topic_id"]),
                        paper_id=paper_id,
                        child_key=child.key,
                        note_type=prepared.note_type,
                        source_kind=prepared.source_kind,
                        content=prepared.content,
                        content_hash=content_hash,
                    )
                    _insert_import_link(
                        conn,
                        topic_id=int(link["topic_id"]),
                        paper_id=paper_id,
                        library_id=self.library_id,
                        library_type=self.library_type,
                        item_key=item_key,
                        child_key=child.key,
                        child_type=child.item_type,
                        target_id=target_id,
                        content_hash=content_hash,
                    )
                    imported.append(
                        ZoteroImportedItem(
                            paper_id=paper_id,
                            title=title,
                            action="imported",
                            zotero_item_key=item_key,
                            zotero_child_key=child.key,
                            target_table="topic_paper_notes",
                            target_id=target_id,
                        )
                    )
            if not dry_run:
                conn.commit()
            return ZoteroPullResult(
                topic=topic_name,
                topic_id=topic_id,
                dry_run=dry_run,
                planned_count=planned,
                imported_count=0
                if dry_run
                else len([item for item in imported if item.action == "imported"]),
                skipped_count=skipped,
                items=imported,
            )
        finally:
            conn.close()

    def _list_reading_children(self, item_key: str) -> list[ZoteroChild]:
        """Return Zotero notes plus PDF annotations nested under attachments."""
        assert self.client is not None
        reading_children = []
        for raw_child in self.client.list_item_children(item_key):
            child = coerce_zotero_child(raw_child)
            if child.item_type in {"note", "annotation"}:
                reading_children.append(child)
                continue
            if child.item_type != "attachment" or not child.key:
                continue
            for raw_grandchild in self.client.list_item_children(child.key):
                grandchild = coerce_zotero_child(raw_grandchild)
                if grandchild.item_type == "annotation":
                    reading_children.append(grandchild)
        return reading_children

    def _ensure_collection(self, name: str, parent_key: str | None) -> str:
        assert self.client is not None
        existing = self.client.find_collection(name, parent_key)
        if existing:
            return existing
        return self.client.create_collection(name, parent_key)

    def _create_item_and_initial_note(
        self,
        *,
        item_payload: dict[str, Any],
        note_html: str,
        include_notes: bool,
        record: ZoteroSyncRecord,
    ) -> tuple[str, str]:
        assert self.client is not None
        if include_notes:
            note_tags = _rh_note_tags(record.paper_id)
            create_item_with_note = getattr(self.client, "create_item_with_note", None)
            if callable(create_item_with_note):
                item_key, note_key = create_item_with_note(
                    item_payload,
                    note_html,
                    note_tags,
                    attachment_path=record.pdf_path,
                )
                return str(item_key), str(note_key or "")
            item_key = self.client.create_item(item_payload)
            note_key = self.client.create_note(item_key, note_html, note_tags)
            return item_key, note_key

        item_key = self.client.create_item(item_payload)
        return item_key, ""

    def _existing_link(
        self, conn: sqlite3.Connection, record: ZoteroSyncRecord
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT * FROM zotero_item_links
            WHERE paper_id = ? AND topic_id = ?
              AND zotero_library_id = ? AND zotero_library_type = ?
            """,
            (record.paper_id, record.topic_id, self.library_id, self.library_type),
        ).fetchone()
        if row is not None:
            return row
        if self.library_type == "user" and self.library_id not in {"", "local"}:
            return conn.execute(
                """
                SELECT * FROM zotero_item_links
                WHERE paper_id = ? AND topic_id = ?
                  AND zotero_library_id = 'local' AND zotero_library_type = 'user'
                """,
                (record.paper_id, record.topic_id),
            ).fetchone()
        return None

    def _upsert_link(
        self,
        conn: sqlite3.Connection,
        record: ZoteroSyncRecord,
        collection_key: str,
        item_key: str,
        note_key: str,
        content_hash: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO zotero_item_links (
                paper_id, topic_id, zotero_library_id, zotero_library_type,
                zotero_collection_key, zotero_item_key, zotero_note_key,
                content_hash, last_synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (paper_id, topic_id, zotero_library_id, zotero_library_type)
            DO UPDATE SET
                zotero_collection_key = excluded.zotero_collection_key,
                zotero_item_key = excluded.zotero_item_key,
                zotero_note_key = excluded.zotero_note_key,
                content_hash = excluded.content_hash,
                last_synced_at = datetime('now')
            """,
            (
                record.paper_id,
                record.topic_id,
                self.library_id,
                self.library_type,
                collection_key,
                item_key,
                note_key,
                content_hash,
            ),
        )


def _load_topic_zotero_links(
    conn: sqlite3.Connection,
    *,
    topic_name: str,
    library_id: str,
    library_type: str,
    limit: int | None,
) -> list[sqlite3.Row]:
    limit_sql = " LIMIT ?" if limit is not None else ""
    params: list[Any] = [topic_name, library_id, library_type]
    if limit is not None:
        params.append(limit)
    return conn.execute(
        f"""
        SELECT zil.*, p.title, t.name AS topic_name
        FROM zotero_item_links zil
        JOIN papers p ON p.id = zil.paper_id
        JOIN topics t ON t.id = zil.topic_id
        WHERE t.name = ?
          AND zil.zotero_library_id = ?
          AND zil.zotero_library_type = ?
        ORDER BY p.id
        {limit_sql}
        """,
        params,
    ).fetchall()


def _is_rh_generated_child(
    child_key: str, child_tags: list[str], rh_note_key: str
) -> bool:
    tag_set = set(child_tags)
    return (
        bool(rh_note_key and child_key == rh_note_key)
        or "rh-generated" in tag_set
        or "rh-deep-read-note" in tag_set
    )


def _rh_note_tags(paper_id: int) -> list[str]:
    return [
        "rh",
        "rh-generated",
        "rh-deep-read-note",
        f"rh-paper-id:{paper_id}",
    ]


def _prepare_zotero_child_import(
    child: Any,
) -> PreparedZoteroChildImport | None:
    if child.item_type == "note":
        content = clean_zotero_note_html(child.note_html)
        if not content:
            return None
        return PreparedZoteroChildImport(
            note_type="zotero_note",
            source_kind="note",
            content=content,
        )
    if child.item_type == "annotation":
        content = _format_zotero_annotation_content(child)
        if not content:
            return None
        return PreparedZoteroChildImport(
            note_type="zotero_annotation",
            source_kind="annotation",
            content=content,
        )
    return None


def _format_zotero_annotation_content(child: Any) -> str:
    annotation_type = _clean_zotero_text(child.annotation_type) or "annotation"
    text = _clean_zotero_text(child.annotation_text)
    comment = _clean_zotero_text(child.annotation_comment)
    page_label = _clean_zotero_text(child.annotation_page_label)
    color = _clean_zotero_text(child.annotation_color)
    sort_index = _clean_zotero_text(child.annotation_sort_index)

    metadata = []
    if page_label:
        metadata.append(f"page {page_label}")
    if color:
        metadata.append(f"color {color}")
    if child.parent_item:
        metadata.append(f"attachment {child.parent_item}")
    if sort_index:
        metadata.append(f"sort {sort_index}")
    if child.tags:
        metadata.append("tags " + ", ".join(child.tags))

    parts = [f"Zotero {annotation_type}"]
    if metadata:
        parts[0] += " (" + "; ".join(metadata) + ")"
    if text:
        parts.extend(["", "Highlighted text:", text])
    if comment:
        parts.extend(["", "Comment:", comment])
    if len(parts) == 1 and not metadata:
        return ""
    return "\n".join(parts).strip()


def _clean_zotero_text(value: Any) -> str:
    return clean_zotero_note_html(str(value or ""))


def _hash_zotero_child_content(child_key: str, content: str) -> str:
    blob = json.dumps(
        {"child_key": child_key, "content": content},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _find_import_link(
    conn: sqlite3.Connection,
    *,
    topic_id: int,
    paper_id: int,
    library_id: str,
    library_type: str,
    child_key: str,
    content_hash: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM zotero_import_links
        WHERE topic_id = ? AND paper_id = ?
          AND zotero_library_id = ? AND zotero_library_type = ?
          AND zotero_child_key = ? AND content_hash = ?
        """,
        (topic_id, paper_id, library_id, library_type, child_key, content_hash),
    ).fetchone()


def _insert_zotero_note(
    conn: sqlite3.Connection,
    *,
    topic_id: int,
    paper_id: int,
    child_key: str,
    note_type: str,
    source_kind: str,
    content: str,
    content_hash: str,
) -> int:
    source = _zotero_import_source(source_kind, child_key, content_hash)
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO topic_paper_notes
            (paper_id, topic_id, note_type, content, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (paper_id, topic_id, note_type, content, source),
    )
    if cursor.rowcount:
        return int(cursor.lastrowid)
    row = conn.execute(
        """
        SELECT id FROM topic_paper_notes
        WHERE paper_id = ? AND topic_id = ? AND note_type = ? AND source = ?
        """,
        (paper_id, topic_id, note_type, source),
    ).fetchone()
    if row is None:
        raise ZoteroSyncError(f"failed to import Zotero {source_kind} {child_key}")
    return int(row["id"])


def _zotero_import_source(source_kind: str, child_key: str, content_hash: str) -> str:
    return f"zotero:{source_kind}:{child_key}:{content_hash[:12]}"


def _insert_import_link(
    conn: sqlite3.Connection,
    *,
    topic_id: int,
    paper_id: int,
    library_id: str,
    library_type: str,
    item_key: str,
    child_key: str,
    child_type: str,
    target_id: int,
    content_hash: str,
) -> None:
    conn.execute(
        """
        INSERT INTO zotero_import_links (
            topic_id, paper_id, zotero_library_id, zotero_library_type,
            zotero_item_key, zotero_child_key, zotero_child_type,
            target_table, target_id, content_hash, last_imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'topic_paper_notes', ?, ?, datetime('now'))
        """,
        (
            topic_id,
            paper_id,
            library_id,
            library_type,
            item_key,
            child_key,
            child_type,
            target_id,
            content_hash,
        ),
    )


def _lookup_venue_rank(conn: sqlite3.Connection, venue: str) -> VenueRank:
    venue = str(venue or "").strip()
    if not venue:
        return VenueRank()

    db_rank = _lookup_venue_rank_table(conn, venue)
    if db_rank.label:
        return db_rank

    try:
        from .primitives.venue_tiers import get_venue_tier
    except Exception:  # pragma: no cover - defensive fallback
        return VenueRank()

    tier = get_venue_tier(venue)
    ccf = str(getattr(getattr(tier, "ccf", ""), "value", "") or "")
    cas = str(getattr(getattr(tier, "cas", ""), "value", "") or "")
    label = str(getattr(tier, "label", "") or "")
    return VenueRank(ccf_rank=ccf, cas_zone=cas, label=label)


def _lookup_venue_rank_table(conn: sqlite3.Connection, venue: str) -> VenueRank:
    try:
        rows = conn.execute(
            "SELECT canonical_name, aliases, ccf_rank, cas_zone FROM venue_ranks"
        ).fetchall()
    except sqlite3.OperationalError:
        return VenueRank()

    normalized = _normalize_venue_for_rank(venue)
    for row in rows:
        names = [str(row["canonical_name"] or "")]
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except json.JSONDecodeError:
            aliases = []
        if isinstance(aliases, list):
            names.extend(str(item) for item in aliases)
        normalized_names = {_normalize_venue_for_rank(name) for name in names if name}
        if normalized not in normalized_names:
            continue
        ccf = str(row["ccf_rank"] or "").upper().strip()
        cas = _cas_zone_label(row["cas_zone"])
        label_parts = []
        if ccf:
            label_parts.append(f"CCF-{ccf}")
        if cas:
            label_parts.append(f"CAS-{cas}")
        return VenueRank(
            ccf_rank=ccf,
            cas_zone=cas,
            label="/".join(label_parts),
        )
    return VenueRank()


def _normalize_venue_for_rank(venue: str) -> str:
    try:
        from .primitives.venue_tiers import normalize_venue_name

        return normalize_venue_name(venue)
    except Exception:  # pragma: no cover - defensive fallback
        return re.sub(r"\s+", " ", str(venue or "").strip().lower())


def _record_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> ZoteroSyncRecord:
    paper_id = int(row["id"])
    topic_id = int(row["topic_id"])
    venue_rank = _lookup_venue_rank(conn, row["venue"] or "")
    annotations = [
        dict(item)
        for item in conn.execute(
            """
            SELECT section, content, source, confidence, updated_at
            FROM paper_annotations
            WHERE paper_id = ?
            ORDER BY section
            """,
            (paper_id,),
        ).fetchall()
    ]
    topic_notes = [
        dict(item)
        for item in conn.execute(
            """
            SELECT note_type, content, source, created_at
            FROM topic_paper_notes
            WHERE paper_id = ? AND topic_id = ?
            ORDER BY created_at, id
            """,
            (paper_id, topic_id),
        ).fetchall()
    ]
    keys = set(row.keys())
    return ZoteroSyncRecord(
        paper_id=paper_id,
        topic_id=topic_id,
        topic_name=row["topic_name"],
        title=row["title"] or "",
        authors=_parse_json_list(row["authors"] or "[]"),
        year=row["year"],
        venue=row["venue"] or "",
        doi=row["doi"] or "",
        arxiv_id=row["arxiv_id"] or "",
        url=row["url"] or "",
        abstract=row["abstract"] if "abstract" in keys and row["abstract"] else "",
        pdf_path=row["pdf_path"] or "",
        status=row["status"] or "meta_only",
        deep_read=bool(row["deep_read"]) if "deep_read" in keys else False,
        relevance=row["relevance"] or "medium",
        ccf_rank=venue_rank.ccf_rank,
        cas_zone=venue_rank.cas_zone,
        venue_level_label=venue_rank.label,
        annotations=annotations,
        topic_notes=topic_notes,
    )


def _parse_json_list(value: str) -> list[str]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(data, list):
        return [str(item) for item in data if str(item).strip()]
    return []


def _creator_payload(author: str) -> dict[str, str]:
    author = author.strip()
    if not author:
        return {"creatorType": "author", "name": ""}
    if "," in author:
        last, first = [part.strip() for part in author.split(",", 1)]
        return {"creatorType": "author", "firstName": first, "lastName": last}
    parts = author.split()
    if len(parts) >= 2:
        return {
            "creatorType": "author",
            "firstName": " ".join(parts[:-1]),
            "lastName": parts[-1],
        }
    return {"creatorType": "author", "name": author}


def _tags_for(record: ZoteroSyncRecord) -> list[str]:
    tags = [
        "rh",
        f"rh-topic:{record.topic_name}",
        f"rh-paper-id:{record.paper_id}",
        f"rh-relevance:{record.relevance}",
        f"rh-status:{record.status}",
    ]
    if record.deep_read:
        tags.append("rh-deep-read")
    tags.extend(_paper_level_tags(record))
    return tags


def _paper_level_tags(record: ZoteroSyncRecord) -> list[str]:
    tags: list[str] = []
    ccf = str(record.ccf_rank or "").upper().strip()
    if ccf:
        tags.extend([f"ccf:{ccf}", f"paper-level:CCF-{ccf}"])
    cas = _cas_zone_label(record.cas_zone)
    if cas:
        tags.extend([f"中科院:{cas}", f"paper-level:CAS-{cas}"])
    if not ccf and not cas and record.arxiv_id:
        tags.extend(["publication:arxiv", "paper-level:preprint"])
    return tags


def _cas_zone_label(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text.startswith("Q") and text[1:].isdigit():
        return text
    if text.isdigit():
        return f"{text}区"
    if text.endswith("区"):
        return text
    return text


def _note_payload(
    parent_item_key: str, note_html: str, tags: list[str]
) -> dict[str, Any]:
    return {
        "itemType": "note",
        "parentItem": parent_item_key,
        "note": note_html,
        "tags": [{"tag": tag} for tag in tags],
    }


def _arxiv_url(arxiv_id: str) -> str:
    if not arxiv_id:
        return ""
    clean = arxiv_id.removeprefix("arxiv:").removeprefix("arXiv:")
    return f"https://arxiv.org/abs/{clean}"


def _escape_lines(lines: list[str]) -> list[str]:
    return [html.escape(line) for line in lines if line]


def _paragraph(text: str) -> str:
    return "".join(f"<p>{html.escape(part)}</p>" for part in _split_paragraphs(text))


def _split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", str(text)) if part.strip()]


def _find_annotation(record: ZoteroSyncRecord, section: str) -> dict[str, Any] | None:
    for annotation in record.annotations:
        if annotation.get("section") == section:
            return annotation
    return None


def _deep_reading_dict(record: ZoteroSyncRecord) -> dict[str, Any]:
    deep_reading = _find_annotation(record, "deep_reading")
    if not deep_reading:
        return {}
    raw = deep_reading.get("content")
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return {"algorithm_walkthrough": str(raw or "")}
    return data if isinstance(data, dict) else {"algorithm_walkthrough": str(raw or "")}


def _first_topic_note(record: ZoteroSyncRecord) -> str:
    for note in record.topic_notes:
        content = str(note.get("content") or "").strip()
        if content:
            return content
    return ""


def _record_venue_level_label(record: ZoteroSyncRecord) -> str:
    label = str(record.venue_level_label or "").strip()
    if label:
        return label
    parts = []
    if record.ccf_rank:
        parts.append(f"CCF-{str(record.ccf_rank).upper()}")
    cas = _cas_zone_label(record.cas_zone)
    if cas:
        parts.append(f"CAS-{cas}")
    if parts:
        return "/".join(parts)
    if record.arxiv_id:
        return "预印本/未分级"
    return ""


def _brief_paragraph(value: Any, *, max_chars: int) -> str:
    text = _truncate_for_zotero_note(_stringify(value), max_chars=max_chars)
    if not text:
        return ""
    escaped = html.escape(text).replace("\n", "<br/>")
    return f"<p>{escaped}</p>"


def _brief_zh_paragraph(value: Any, *, max_chars: int, fallback: str) -> str:
    text = _stringify(value)
    if _looks_mostly_english(text):
        text = fallback
    return _brief_paragraph(text, max_chars=max_chars)


def _brief_list(value: Any, *, max_items: int, max_chars: int) -> str:
    if isinstance(value, list):
        items = [
            _truncate_for_zotero_note(str(item), max_chars=max_chars)
            for item in value[:max_items]
            if str(item).strip()
        ]
    else:
        items = [_truncate_for_zotero_note(_stringify(value), max_chars=max_chars)]
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _brief_zh_list(value: Any, *, max_items: int, max_chars: int, fallback: str) -> str:
    if isinstance(value, list):
        zh_items = [str(item) for item in value if not _looks_mostly_english(str(item))]
        if zh_items:
            return _brief_list(zh_items, max_items=max_items, max_chars=max_chars)
    elif value and not _looks_mostly_english(_stringify(value)):
        return _brief_list(value, max_items=max_items, max_chars=max_chars)
    return _brief_list([fallback], max_items=1, max_chars=max_chars)


def _looks_mostly_english(text: str) -> bool:
    value = str(text or "")
    cjk = len(re.findall(r"[\u4e00-\u9fff]", value))
    latin = len(re.findall(r"[A-Za-z]", value))
    if cjk == 0 and latin >= 10:
        return True
    return latin >= 30 and cjk < 8


def _truncate_for_zotero_note(text: str, *, max_chars: int) -> str:
    normalized = re.sub(r"[ \t]+", " ", str(text or ""))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _deep_reading_html(raw: Any) -> list[str]:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return ["<h2>Deep Reading</h2>", _content_html(raw)]
    if not isinstance(data, dict):
        return ["<h2>Deep Reading</h2>", _content_html(raw)]

    labels = [
        ("Algorithm Walkthrough", data.get("algorithm_walkthrough")),
        ("Limitation Analysis", data.get("limitation_analysis")),
        ("Reproducibility Assessment", data.get("reproducibility_assessment")),
        ("Critical Assessment", data.get("critical_assessment")),
    ]
    parts = ["<h2>Deep Reading</h2>"]
    for label, value in labels:
        if value:
            parts.append(f"<h3>{html.escape(label)}</h3>")
            parts.append(_content_html(value))
    feasibility = data.get("industrial_feasibility")
    if isinstance(feasibility, dict) and any(feasibility.values()):
        parts.append("<h3>Industrial Feasibility</h3>")
        for key, value in feasibility.items():
            if value:
                key_html = html.escape(str(key))
                value_html = html.escape(_stringify(value))
                parts.append(f"<p><strong>{key_html}:</strong> {value_html}</p>")
    implications = data.get("research_implications")
    if isinstance(implications, list) and implications:
        parts.append("<h3>Research Implications</h3>")
        items = "".join(f"<li>{html.escape(str(item))}</li>" for item in implications)
        parts.append(f"<ul>{items}</ul>")
    return parts


def _content_html(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return (
            f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre>"
        )
    return _paragraph(str(value or ""))


def _stringify(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _record_preview(record: ZoteroSyncRecord) -> dict[str, Any]:
    return {
        "paper_id": record.paper_id,
        "topic_id": record.topic_id,
        "title": record.title,
        "year": record.year,
        "doi": record.doi,
        "arxiv_id": record.arxiv_id,
        "relevance": record.relevance,
        "deep_read": record.deep_read,
        "ccf_rank": record.ccf_rank,
        "cas_zone": record.cas_zone,
        "venue_level": record.venue_level_label,
        "annotation_count": len(record.annotations),
        "topic_note_count": len(record.topic_notes),
    }
