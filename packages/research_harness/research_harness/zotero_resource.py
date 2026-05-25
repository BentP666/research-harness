"""Zotero resource adapter for Research Harness.

This module is the RH-owned boundary around Zotero. It intentionally exposes a
small typed interface to sync code so low-level Zotero write/read plumbing can
later be swapped for a vendored zotero-mcp/pyzotero implementation without
changing RH's topic/paper synchronization semantics.
"""

from __future__ import annotations

import html
import json
import mimetypes
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from random import SystemRandom
from typing import Any, Protocol

import httpx

ZOTERO_API_BASE = "https://api.zotero.org"
ZOTERO_CONNECTOR_BASE = "http://127.0.0.1:23119"
ZOTERO_LOCAL_LIBRARY_ID = "local"

_KEY_ALPHABET = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
_RANDOM = SystemRandom()


class ZoteroResourceError(RuntimeError):
    """Raised when RH cannot read from or write to Zotero."""


@dataclass(frozen=True)
class ZoteroChild:
    key: str
    item_type: str
    parent_item: str = ""
    note_html: str = ""
    annotation_text: str = ""
    annotation_comment: str = ""
    annotation_color: str = ""
    annotation_page_label: str = ""
    annotation_type: str = ""
    annotation_sort_index: str = ""
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class ZoteroResource(Protocol):
    def find_collection(
        self, name: str, parent_key: str | None = None
    ) -> str | None: ...

    def create_collection(self, name: str, parent_key: str | None = None) -> str: ...

    def find_item_by_tag(self, tag: str) -> str | None: ...

    def create_item(self, payload: dict[str, Any]) -> str: ...

    def update_item(self, item_key: str, payload: dict[str, Any]) -> None: ...

    def create_note(
        self, parent_item_key: str, note_html: str, tags: list[str]
    ) -> str: ...

    def update_note(
        self, note_key: str, parent_item_key: str, note_html: str, tags: list[str]
    ) -> None: ...

    def list_item_children(
        self, item_key: str
    ) -> list[dict[str, Any] | ZoteroChild]: ...


class ZoteroWebApiResource:
    """Minimal Zotero Web API v3 resource adapter.

    This is the default RH adapter until the zotero-mcp-derived pyzotero writer
    is vendored or introduced as an optional dependency. It deliberately mirrors
    zotero-mcp's hybrid-write assumptions: writes require a Web API key.
    """

    def __init__(
        self,
        *,
        library_id: str,
        library_type: str = "user",
        api_key: str,
        base_url: str = ZOTERO_API_BASE,
        timeout: float = 30.0,
    ) -> None:
        if library_type not in {"user", "group"}:
            raise ValueError("library_type must be 'user' or 'group'")
        if not library_id:
            raise ValueError("library_id is required for Zotero resource sync")
        if not api_key:
            raise ValueError("api_key is required for Zotero resource sync")
        self.library_id = library_id
        self.library_type = library_type
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Zotero-API-Key": api_key,
                "Zotero-API-Version": "3",
                "Content-Type": "application/json",
            },
        )

    @property
    def _prefix(self) -> str:
        kind = "users" if self.library_type == "user" else "groups"
        return f"/{kind}/{self.library_id}"

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
        if response.status_code >= 400:
            raise ZoteroResourceError(
                f"Zotero API {method} {path} failed: "
                f"HTTP {response.status_code} {response.text[:500]}"
            )
        return response

    def _paginate(
        self, path: str, params: dict[str, Any] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        start = 0
        results: list[dict[str, Any]] = []
        while True:
            page_params = dict(params or {})
            page_params.update({"limit": limit, "start": start})
            response = self._request("GET", path, params=page_params)
            page = response.json()
            if not isinstance(page, list):
                return results
            results.extend(page)
            if len(page) < limit:
                return results
            start += limit

    def _create_object(self, path: str, payload: dict[str, Any]) -> str:
        response = self._request("POST", path, json=[payload])
        body = response.json()
        success = body.get("success") or body.get("successful") or {}
        key = success.get("0")
        if not key:
            failed = body.get("failed") or {}
            raise ZoteroResourceError(f"Zotero object creation failed: {failed}")
        return str(key)

    def find_collection(self, name: str, parent_key: str | None = None) -> str | None:
        for item in self._paginate(f"{self._prefix}/collections"):
            data = item.get("data", item)
            if data.get("name") != name:
                continue
            parent = data.get("parentCollection")
            normalized_parent = None if parent in (False, "", None) else str(parent)
            if normalized_parent == parent_key:
                return str(data.get("key") or item.get("key"))
        return None

    def create_collection(self, name: str, parent_key: str | None = None) -> str:
        payload: dict[str, Any] = {"name": name, "parentCollection": False}
        if parent_key:
            payload["parentCollection"] = parent_key
        return self._create_object(f"{self._prefix}/collections", payload)

    def find_item_by_tag(self, tag: str) -> str | None:
        for item in self._paginate(f"{self._prefix}/items", {"tag": tag}, limit=25):
            data = item.get("data", item)
            if data.get("itemType") in {"note", "attachment", "annotation"}:
                continue
            return str(data.get("key") or item.get("key"))
        return None

    def create_item(self, payload: dict[str, Any]) -> str:
        return self._create_object(f"{self._prefix}/items", payload)

    def update_item(self, item_key: str, payload: dict[str, Any]) -> None:
        self._request("PATCH", f"{self._prefix}/items/{item_key}", json=payload)

    def create_note(self, parent_item_key: str, note_html: str, tags: list[str]) -> str:
        return self._create_object(
            f"{self._prefix}/items", _note_payload(parent_item_key, note_html, tags)
        )

    def update_note(
        self, note_key: str, parent_item_key: str, note_html: str, tags: list[str]
    ) -> None:
        self._request(
            "PATCH",
            f"{self._prefix}/items/{note_key}",
            json=_note_payload(parent_item_key, note_html, tags),
        )

    def list_item_children(self, item_key: str) -> list[dict[str, Any] | ZoteroChild]:
        return self._paginate(f"{self._prefix}/items/{item_key}/children")


class ZoteroConnectorResource:
    """Local Zotero Connector adapter for create-first desktop workflows.

    Zotero's connector server can create items and then update the active save
    session target/note, but it cannot create collections directly and its
    local ``/api`` surface is read-only in Zotero 9. RH therefore uses the
    connector for item/note/PDF creation and the local SQLite DB for safe
    read-after-write key lookup. Collection rows can be created only when the
    Zotero DB is not locked (normally while Zotero is closed).
    """

    def __init__(
        self,
        *,
        connector_url: str = ZOTERO_CONNECTOR_BASE,
        db_path: str | Path | None = None,
        timeout: float = 30.0,
        poll_timeout: float = 10.0,
    ) -> None:
        self.connector_url = connector_url.rstrip("/")
        self.db_path = Path(db_path or Path.home() / "Zotero" / "zotero.sqlite")
        self.poll_timeout = poll_timeout
        self._client = httpx.Client(timeout=timeout)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, f"{self.connector_url}{path}", **kwargs)
        if response.status_code >= 400:
            raise ZoteroResourceError(
                f"Zotero Connector {method} {path} failed: "
                f"HTTP {response.status_code} {response.text[:500]}"
            )
        return response

    def _read_conn(self) -> sqlite3.Connection:
        uri = f"file:{self.db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _write_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=2.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def find_collection(self, name: str, parent_key: str | None = None) -> str | None:
        with self._read_conn() as conn:
            parent_id = self._collection_id_for_key(conn, parent_key)
            if parent_key and parent_id is None:
                return None
            row = conn.execute(
                """
                SELECT key FROM collections
                WHERE collectionName = ?
                  AND COALESCE(parentCollectionID, 0) = COALESCE(?, 0)
                ORDER BY collectionID DESC
                LIMIT 1
                """,
                (name, parent_id),
            ).fetchone()
        return str(row["key"]) if row else None

    def create_collection(self, name: str, parent_key: str | None = None) -> str:
        """Create a collection row directly when Zotero is not holding the DB.

        This is intentionally narrow and only used for the local connector
        adapter. If the database is locked, the caller should close/restart
        Zotero or pre-create the collection through Zotero's UI.
        """
        key = _new_zotero_key()
        try:
            with self._write_conn() as conn:
                parent_id = self._collection_id_for_key(conn, parent_key)
                conn.execute(
                    """
                    INSERT INTO collections (
                        collectionName, parentCollectionID, libraryID, key,
                        version, synced
                    ) VALUES (?, ?, 1, ?, 0, 0)
                    """,
                    (name, parent_id, key),
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            raise ZoteroResourceError(
                "Cannot create a Zotero collection through the local Connector "
                "while zotero.sqlite is locked. Close Zotero or pre-create the "
                f"collection '{name}', then retry."
            ) from exc
        return key

    def find_item_by_tag(self, tag: str) -> str | None:
        # Avoid adopting old/manual connector smoke-test items from unrelated
        # collections. RH's own zotero_item_links table provides idempotency for
        # connector-created items after the first sync.
        return None

    def create_item(self, payload: dict[str, Any]) -> str:
        item_key, _ = self.create_item_with_note(payload, "", [], attachment_path="")
        return item_key

    def create_item_with_note(
        self,
        payload: dict[str, Any],
        note_html: str,
        note_tags: list[str],
        *,
        attachment_path: str = "",
    ) -> tuple[str, str]:
        collection_keys = payload.get("collections") or []
        collection_key = str(collection_keys[0]) if collection_keys else ""
        collection_id = self._collection_id_for_key_required(collection_key)
        target = f"C{collection_id}"
        session_id = f"rh-{uuid.uuid4().hex[:16]}"
        connector_item_id = f"rh-item-{uuid.uuid4().hex[:16]}"
        item_payload = _connector_item_payload(payload, connector_item_id)

        self._request(
            "POST",
            "/connector/saveItems",
            json={
                "sessionID": session_id,
                "uri": item_payload.get("url") or "https://research-harness.local/",
                "items": [item_payload],
            },
        )
        self._request(
            "POST",
            "/connector/updateSession",
            json={
                "sessionID": session_id,
                "target": target,
                "tags": _dedupe(
                    [*_tags_from_zotero(payload.get("tags") or []), *note_tags]
                ),
                "note": note_html,
            },
        )

        if attachment_path:
            self._save_attachment(
                session_id=session_id,
                connector_item_id=connector_item_id,
                attachment_path=attachment_path,
                title=str(payload.get("title") or Path(attachment_path).name),
            )

        paper_tag = _first_tag_with_prefix(payload, "rh-paper-id:")
        item = self._poll_item_by_tag_in_collection(paper_tag, collection_id)
        note_key = self._latest_child_note_key(item["itemID"])
        return str(item["key"]), note_key

    def update_item(self, item_key: str, payload: dict[str, Any]) -> None:
        try:
            with self._write_conn() as conn:
                item = conn.execute(
                    "SELECT itemID FROM items WHERE key = ? AND libraryID = 1",
                    (item_key,),
                ).fetchone()
                if item is None:
                    raise ZoteroResourceError(f"Zotero item not found: {item_key}")
                item_id = int(item["itemID"])
                for collection_key in payload.get("collections") or []:
                    collection_id = self._collection_id_for_key(
                        conn, str(collection_key)
                    )
                    if collection_id is not None:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO collectionItems (collectionID, itemID)
                            VALUES (?, ?)
                            """,
                            (collection_id, item_id),
                        )
                _add_item_tags(
                    conn, item_id, _tags_from_zotero(payload.get("tags") or [])
                )
                conn.execute(
                    """
                    UPDATE items
                    SET dateModified = CURRENT_TIMESTAMP,
                        clientDateModified = CURRENT_TIMESTAMP,
                        synced = 0
                    WHERE itemID = ?
                    """,
                    (item_id,),
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            raise ZoteroResourceError(
                "Cannot update a Zotero item through the local Connector adapter "
                "while zotero.sqlite is locked. Close Zotero, then retry."
            ) from exc

    def create_note(self, parent_item_key: str, note_html: str, tags: list[str]) -> str:
        raise ZoteroResourceError(
            "Zotero Connector cannot create RH child notes independently; "
            "create the parent item and initial note together."
        )

    def update_note(
        self, note_key: str, parent_item_key: str, note_html: str, tags: list[str]
    ) -> None:
        try:
            with self._write_conn() as conn:
                note = conn.execute(
                    "SELECT itemID FROM items WHERE key = ? AND libraryID = 1",
                    (note_key,),
                ).fetchone()
                parent = conn.execute(
                    "SELECT itemID FROM items WHERE key = ? AND libraryID = 1",
                    (parent_item_key,),
                ).fetchone()
                if note is None:
                    raise ZoteroResourceError(f"Zotero note not found: {note_key}")
                if parent is None:
                    raise ZoteroResourceError(
                        f"Zotero parent item not found: {parent_item_key}"
                    )
                note_id = int(note["itemID"])
                conn.execute(
                    """
                    UPDATE itemNotes
                    SET parentItemID = ?, note = ?
                    WHERE itemID = ?
                    """,
                    (int(parent["itemID"]), _zotero_note_db_html(note_html), note_id),
                )
                _add_item_tags(conn, note_id, tags)
                conn.execute(
                    """
                    UPDATE items
                    SET dateModified = CURRENT_TIMESTAMP,
                        clientDateModified = CURRENT_TIMESTAMP,
                        synced = 0
                    WHERE itemID = ?
                    """,
                    (note_id,),
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            raise ZoteroResourceError(
                "Cannot update a Zotero note through the local Connector adapter "
                "while zotero.sqlite is locked. Close Zotero, then retry."
            ) from exc

    def list_item_children(self, item_key: str) -> list[dict[str, Any] | ZoteroChild]:
        with self._read_conn() as conn:
            parent = conn.execute(
                "SELECT itemID FROM items WHERE key = ? AND libraryID = 1",
                (item_key,),
            ).fetchone()
            if parent is None:
                return []
            notes = conn.execute(
                """
                SELECT i.key, n.note
                FROM itemNotes n
                JOIN items i ON i.itemID = n.itemID
                WHERE n.parentItemID = ?
                ORDER BY i.itemID
                """,
                (int(parent["itemID"]),),
            ).fetchall()
        return [
            ZoteroChild(
                key=str(row["key"]),
                item_type="note",
                parent_item=item_key,
                note_html=str(row["note"] or ""),
            )
            for row in notes
        ]

    def _collection_id_for_key_required(self, collection_key: str) -> int:
        with self._read_conn() as conn:
            collection_id = self._collection_id_for_key(conn, collection_key)
        if collection_id is None:
            raise ZoteroResourceError(
                f"Zotero collection key not found in local DB: {collection_key}"
            )
        return collection_id

    @staticmethod
    def _collection_id_for_key(
        conn: sqlite3.Connection, collection_key: str | None
    ) -> int | None:
        if not collection_key:
            return None
        row = conn.execute(
            "SELECT collectionID FROM collections WHERE key = ? AND libraryID = 1",
            (collection_key,),
        ).fetchone()
        return int(row["collectionID"]) if row else None

    def _poll_item_by_tag_in_collection(
        self, paper_tag: str, collection_id: int
    ) -> sqlite3.Row:
        if not paper_tag:
            raise ZoteroResourceError(
                "Connector-created items need an rh-paper-id tag for lookup"
            )
        deadline = time.monotonic() + self.poll_timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with self._read_conn() as conn:
                    row = conn.execute(
                        """
                        SELECT i.itemID, i.key
                        FROM items i
                        JOIN itemTags it ON it.itemID = i.itemID
                        JOIN tags t ON t.tagID = it.tagID
                        JOIN collectionItems ci ON ci.itemID = i.itemID
                        JOIN itemTypes typ ON typ.itemTypeID = i.itemTypeID
                        WHERE t.name = ?
                          AND ci.collectionID = ?
                          AND typ.typeName NOT IN ('note', 'attachment', 'annotation')
                        ORDER BY i.itemID DESC
                        LIMIT 1
                        """,
                        (paper_tag, collection_id),
                    ).fetchone()
                if row is not None:
                    return row
            except Exception as exc:  # pragma: no cover - transient DB state
                last_error = exc
            time.sleep(0.25)
        raise ZoteroResourceError(
            f"Timed out locating connector-created Zotero item with tag {paper_tag}"
        ) from last_error

    def _latest_child_note_key(self, parent_item_id: int) -> str:
        with self._read_conn() as conn:
            row = conn.execute(
                """
                SELECT i.key
                FROM itemNotes n
                JOIN items i ON i.itemID = n.itemID
                WHERE n.parentItemID = ?
                ORDER BY i.itemID DESC
                LIMIT 1
                """,
                (parent_item_id,),
            ).fetchone()
        return str(row["key"]) if row else ""

    def _save_attachment(
        self,
        *,
        session_id: str,
        connector_item_id: str,
        attachment_path: str,
        title: str,
    ) -> None:
        path = Path(attachment_path).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        if not path.exists() or not path.is_file():
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/pdf"
        metadata = {
            "sessionID": session_id,
            "parentItemID": connector_item_id,
            "title": path.name if title == str(path) else title,
            "url": path.as_uri(),
        }
        self._request(
            "POST",
            "/connector/saveAttachment",
            headers={
                "X-Metadata": json.dumps(metadata, ensure_ascii=False),
                "Content-Type": content_type,
                "Content-Length": str(len(content)),
            },
            content=content,
        )


def create_zotero_resource_from_env(
    *,
    library_id: str | None = None,
    library_type: str = "user",
    api_key: str | None = None,
    base_url: str | None = None,
) -> ZoteroWebApiResource:
    return ZoteroWebApiResource(
        library_id=library_id or os.getenv("ZOTERO_LIBRARY_ID", ""),
        library_type=library_type or os.getenv("ZOTERO_LIBRARY_TYPE", "user"),
        api_key=api_key or os.getenv("ZOTERO_API_KEY", ""),
        base_url=base_url or os.getenv("ZOTERO_API_BASE", ZOTERO_API_BASE),
    )


def create_zotero_resource(
    *,
    adapter: str | None = None,
    library_id: str | None = None,
    library_type: str = "user",
    api_key: str | None = None,
    base_url: str | None = None,
    connector_url: str | None = None,
    db_path: str | Path | None = None,
) -> ZoteroResource:
    adapter_name = (adapter or os.getenv("ZOTERO_ADAPTER") or "web").strip().lower()
    if adapter_name in {"connector", "local", "desktop"}:
        return ZoteroConnectorResource(
            connector_url=connector_url
            or os.getenv("ZOTERO_CONNECTOR_URL", ZOTERO_CONNECTOR_BASE),
            db_path=db_path or os.getenv("ZOTERO_DB_PATH") or None,
        )
    if adapter_name in {"web", "api", "web-api"}:
        return create_zotero_resource_from_env(
            library_id=library_id,
            library_type=library_type,
            api_key=api_key,
            base_url=base_url,
        )
    raise ValueError("adapter must be one of: web, connector")


def coerce_zotero_child(raw: dict[str, Any] | ZoteroChild) -> ZoteroChild:
    if isinstance(raw, ZoteroChild):
        return raw
    data = raw.get("data", raw)
    return ZoteroChild(
        key=str(data.get("key") or raw.get("key") or ""),
        item_type=str(data.get("itemType") or ""),
        parent_item=str(data.get("parentItem") or ""),
        note_html=str(data.get("note") or ""),
        annotation_text=str(data.get("annotationText") or ""),
        annotation_comment=str(data.get("annotationComment") or ""),
        annotation_color=str(data.get("annotationColor") or ""),
        annotation_page_label=str(data.get("annotationPageLabel") or ""),
        annotation_type=str(data.get("annotationType") or ""),
        annotation_sort_index=str(data.get("annotationSortIndex") or ""),
        tags=_tags_from_zotero(data.get("tags") or []),
        raw=raw,
    )


def clean_zotero_note_html(note_html: str) -> str:
    text = str(note_html or "")
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</\s*(p|div|h[1-6]|li)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _note_payload(
    parent_item_key: str, note_html: str, tags: list[str]
) -> dict[str, Any]:
    return {
        "itemType": "note",
        "parentItem": parent_item_key,
        "note": note_html,
        "tags": [{"tag": tag} for tag in tags],
    }


def _tags_from_zotero(tags: list[Any]) -> list[str]:
    values: list[str] = []
    for tag in tags:
        if isinstance(tag, dict):
            value = str(tag.get("tag") or "").strip()
        else:
            value = str(tag).strip()
        if value:
            values.append(value)
    return values


def _new_zotero_key() -> str:
    return "".join(_RANDOM.choice(_KEY_ALPHABET) for _ in range(8))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _connector_item_payload(
    payload: dict[str, Any], connector_item_id: str
) -> dict[str, Any]:
    item = {
        key: value
        for key, value in payload.items()
        if key not in {"collections"} and value not in (None, "")
    }
    item["id"] = connector_item_id
    item["tags"] = _tags_from_zotero(payload.get("tags") or [])
    return item


def _first_tag_with_prefix(payload: dict[str, Any], prefix: str) -> str:
    for tag in _tags_from_zotero(payload.get("tags") or []):
        if tag.startswith(prefix):
            return tag
    return ""


def _add_item_tags(conn: sqlite3.Connection, item_id: int, tags: list[str]) -> None:
    for tag in _dedupe(tags):
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (tag,)).fetchone()
        if row is None:
            continue
        tag_id = int(row["tagID"])
        conn.execute(
            """
            INSERT OR IGNORE INTO itemTags (itemID, tagID, type)
            VALUES (?, ?, 1)
            """,
            (item_id, tag_id),
        )


def _zotero_note_db_html(note_html: str) -> str:
    text = str(note_html or "")
    if 'class="zotero-note' in text or "class='zotero-note" in text:
        return text
    return f'<div class="zotero-note znv1">{text}</div>'
