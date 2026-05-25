from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from research_harness.cli import main
from research_harness.storage.db import Database
from research_harness.zotero_sync import (
    ZoteroSyncService,
    build_zotero_item_payload,
    build_zotero_note_html,
    load_topic_sync_records,
)


class FakeZoteroClient:
    def __init__(self) -> None:
        self.collections: dict[tuple[str, str | None], str] = {}
        self.items: dict[str, dict] = {}
        self.notes: dict[str, dict] = {}
        self.attachments: dict[str, dict] = {}
        self.annotations: dict[str, dict] = {}
        self.created_items: list[dict] = []
        self.updated_items: list[tuple[str, dict]] = []
        self.created_notes: list[tuple[str, str, list[str]]] = []
        self.updated_notes: list[tuple[str, str, list[str]]] = []
        self._next = 1

    def _key(self, prefix: str) -> str:
        key = f"{prefix}{self._next:07d}"[-8:]
        self._next += 1
        return key.upper()

    def find_collection(self, name: str, parent_key: str | None = None) -> str | None:
        return self.collections.get((name, parent_key))

    def create_collection(self, name: str, parent_key: str | None = None) -> str:
        key = self._key("C")
        self.collections[(name, parent_key)] = key
        return key

    def find_item_by_tag(self, tag: str) -> str | None:
        for key, payload in self.items.items():
            if tag in {item["tag"] for item in payload.get("tags", [])}:
                return key
        return None

    def create_item(self, payload: dict) -> str:
        key = self._key("I")
        self.items[key] = dict(payload)
        self.created_items.append(dict(payload))
        return key

    def update_item(self, item_key: str, payload: dict) -> None:
        self.items[item_key] = {**self.items.get(item_key, {}), **payload}
        self.updated_items.append((item_key, dict(payload)))

    def create_note(self, parent_item_key: str, note_html: str, tags: list[str]) -> str:
        key = self._key("N")
        self.notes[key] = {"parentItem": parent_item_key, "note": note_html, "tags": tags}
        self.created_notes.append((parent_item_key, note_html, list(tags)))
        return key

    def update_note(
        self, note_key: str, parent_item_key: str, note_html: str, tags: list[str]
    ) -> None:
        self.notes[note_key] = {"parentItem": parent_item_key, "note": note_html, "tags": tags}
        self.updated_notes.append((note_key, note_html, list(tags)))

    def add_child_note(
        self, key: str, parent_item_key: str, note_html: str, tags: list[str] | None = None
    ) -> None:
        self.notes[key] = {
            "parentItem": parent_item_key,
            "note": note_html,
            "tags": list(tags or []),
        }

    def add_attachment(self, key: str, parent_item_key: str, title: str = "PDF") -> None:
        self.attachments[key] = {"parentItem": parent_item_key, "title": title}

    def add_annotation(
        self,
        key: str,
        parent_attachment_key: str,
        *,
        text: str = "",
        comment: str = "",
        color: str = "",
        page_label: str = "",
        annotation_type: str = "highlight",
        tags: list[str] | None = None,
    ) -> None:
        self.annotations[key] = {
            "parentItem": parent_attachment_key,
            "annotationText": text,
            "annotationComment": comment,
            "annotationColor": color,
            "annotationPageLabel": page_label,
            "annotationType": annotation_type,
            "tags": list(tags or []),
        }

    def list_item_children(self, item_key: str) -> list[dict]:
        children = []
        for key, payload in self.notes.items():
            if payload.get("parentItem") != item_key:
                continue
            children.append(
                {
                    "key": key,
                    "data": {
                        "key": key,
                        "itemType": "note",
                        "parentItem": item_key,
                        "note": payload.get("note", ""),
                        "tags": [{"tag": tag} for tag in payload.get("tags", [])],
                    },
                }
            )
        for key, payload in self.attachments.items():
            if payload.get("parentItem") != item_key:
                continue
            children.append(
                {
                    "key": key,
                    "data": {
                        "key": key,
                        "itemType": "attachment",
                        "parentItem": item_key,
                        "title": payload.get("title", ""),
                        "tags": [],
                    },
                }
            )
        for key, payload in self.annotations.items():
            if payload.get("parentItem") != item_key:
                continue
            children.append(
                {
                    "key": key,
                    "data": {
                        "key": key,
                        "itemType": "annotation",
                        "parentItem": item_key,
                        "annotationText": payload.get("annotationText", ""),
                        "annotationComment": payload.get("annotationComment", ""),
                        "annotationColor": payload.get("annotationColor", ""),
                        "annotationPageLabel": payload.get("annotationPageLabel", ""),
                        "annotationType": payload.get("annotationType", ""),
                        "tags": [{"tag": tag} for tag in payload.get("tags", [])],
                    },
                }
            )
        return children


class FakeConnectorZoteroClient(FakeZoteroClient):
    """Connector-style fake: item and RH child note must be created together."""

    def __init__(self) -> None:
        super().__init__()
        self.create_item_with_note_calls: list[tuple[dict, str, list[str], str]] = []

    def create_item_with_note(
        self,
        payload: dict,
        note_html: str,
        note_tags: list[str],
        *,
        attachment_path: str = "",
    ) -> tuple[str, str]:
        self.create_item_with_note_calls.append(
            (dict(payload), note_html, list(note_tags), attachment_path)
        )
        item_key = self.create_item(payload)
        note_key = super().create_note(item_key, note_html, note_tags)
        return item_key, note_key

    def create_note(self, parent_item_key: str, note_html: str, tags: list[str]) -> str:
        raise AssertionError(
            "connector clients create the initial RH note with the parent item"
        )


def _seed_db(path: Path) -> Database:
    db = Database(path)
    db.migrate()
    conn = db.connect()
    try:
        conn.execute("INSERT INTO topics (name, description) VALUES ('demo-topic', 'Demo topic')")
        conn.execute(
            """
            INSERT INTO papers
                (
                    title, authors, year, venue, doi, arxiv_id, url, abstract,
                    pdf_path, status, deep_read
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Agentic Paper Reading",
                json.dumps(["Ada Lovelace", "Alan Turing"]),
                2026,
                "ICLR",
                "10.1234/demo",
                "2601.00001",
                "https://arxiv.org/abs/2601.00001",
                "A paper about agentic paper reading.",
                "/tmp/demo.pdf",
                "pdf_ready",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO paper_topics (paper_id, topic_id, relevance) "
            "VALUES (1, 1, 'high')"
        )
        conn.execute(
            """
            INSERT INTO paper_annotations (paper_id, section, content, source, confidence)
            VALUES (1, 'deep_reading', ?, 'deep_read', 0.95)
            """,
            (
                json.dumps(
                    {
                        "algorithm_walkthrough": "Step-by-step reading workflow.",
                        "limitation_analysis": "Needs human verification.",
                        "reproducibility_assessment": "Artifacts are partially available.",
                        "critical_assessment": "Useful but not enough alone.",
                        "industrial_feasibility": {"viability": "medium"},
                        "research_implications": ["Bridge RH and Zotero."],
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO topic_paper_notes (paper_id, topic_id, note_type, content, source)
            VALUES (1, 1, 'relevance', 'High relevance to the Zotero sync workflow.', 'codex')
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_build_zotero_payload_and_note_html_include_rh_metadata(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    conn = db.connect()
    try:
        record = load_topic_sync_records(conn, topic_name="demo-topic")[0]
    finally:
        conn.close()

    payload = build_zotero_item_payload(record, collection_key="COLLKEY1")
    assert payload["itemType"] == "journalArticle"
    assert payload["title"] == "Agentic Paper Reading"
    assert payload["DOI"] == "10.1234/demo"
    assert payload["collections"] == ["COLLKEY1"]
    assert {tag["tag"] for tag in payload["tags"]} >= {
        "rh",
        "rh-topic:demo-topic",
        "rh-paper-id:1",
        "rh-deep-read",
        "rh-relevance:high",
        "ccf:A*",
        "paper-level:CCF-A*",
    }

    note_html = build_zotero_note_html(record)
    assert "RH 精读卡片" in note_html
    assert "核心方法" in note_html
    assert "局限/风险" in note_html
    assert "RH 已完成方法层精读" in note_html
    assert "这篇论文已被 RH 标记为" in note_html
    assert "RH paper_id: 1" in note_html
    assert len(note_html) < 5000


def test_zotero_payload_adds_cas_partition_tags_when_known(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    conn = db.connect()
    try:
        conn.execute("UPDATE papers SET venue = 'TPAMI' WHERE id = 1")
        conn.commit()
        record = load_topic_sync_records(conn, topic_name="demo-topic")[0]
    finally:
        conn.close()

    payload = build_zotero_item_payload(record, collection_key="COLLKEY1")
    tags = {tag["tag"] for tag in payload["tags"]}
    assert "ccf:A" in tags
    assert "中科院:Q1" in tags
    assert "paper-level:CAS-Q1" in tags


def test_zotero_sync_creates_collections_item_note_and_mapping(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)

    result = service.sync_topic("demo-topic", include_notes=True)

    assert result.synced_count == 1
    assert fake.find_collection("Research Harness") is not None
    topic_collection = fake.find_collection("demo-topic", fake.find_collection("Research Harness"))
    assert topic_collection is not None
    assert len(fake.created_items) == 1
    assert len(fake.created_notes) == 1
    assert "RH 精读卡片" in fake.created_notes[0][1]
    assert "核心方法" in fake.created_notes[0][1]

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM zotero_item_links "
            "WHERE paper_id = 1 AND topic_id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["zotero_item_key"] in fake.items
    assert row["zotero_note_key"] in fake.notes


def test_zotero_sync_can_use_display_collection_name(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)

    result = service.sync_topic(
        "demo-topic", include_notes=True, topic_collection_name="自动科研"
    )

    root = fake.find_collection("Research Harness")
    topic_collection = fake.find_collection("自动科研", root)
    assert result.topic_collection_key == topic_collection
    assert topic_collection is not None


def test_zotero_sync_can_push_selected_papers_into_existing_collection(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    fake.collections[("当前目录", None)] = "CURRDIR1"
    service = ZoteroSyncService(db_path=db.path, client=fake)

    result = service.sync_topic(
        "demo-topic",
        include_notes=False,
        target_collection_key="CURRDIR1",
        paper_ids=[1],
    )

    assert result.synced_count == 1
    assert result.root_collection_key == ""
    assert result.topic_collection_key == "CURRDIR1"
    assert fake.find_collection("Research Harness") is None
    assert fake.created_items[0]["collections"] == ["CURRDIR1"]


def test_zotero_sync_uses_connector_create_item_with_note_when_available(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeConnectorZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)

    result = service.sync_topic("demo-topic", include_notes=True)

    assert result.synced_count == 1
    assert len(fake.create_item_with_note_calls) == 1
    payload, note_html, note_tags, attachment_path = fake.create_item_with_note_calls[0]
    assert payload["title"] == "Agentic Paper Reading"
    assert "RH 精读卡片" in note_html
    assert "核心方法" in note_html
    assert "rh-generated" in note_tags
    assert attachment_path == "/tmp/demo.pdf"

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT zotero_item_key, zotero_note_key FROM zotero_item_links "
            "WHERE paper_id = 1 AND topic_id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["zotero_item_key"] in fake.items
    assert row["zotero_note_key"] in fake.notes


def test_zotero_sync_is_idempotent_when_content_hash_matches(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)

    first = service.sync_topic("demo-topic", include_notes=True)
    second = service.sync_topic("demo-topic", include_notes=True)

    assert first.synced_count == 1
    assert second.skipped_count == 1
    assert len(fake.created_items) == 1
    assert len(fake.created_notes) == 1
    assert fake.updated_items == []
    assert fake.updated_notes == []


def test_zotero_sync_migrates_matching_legacy_local_link_to_web_api_id(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    local_service = ZoteroSyncService(
        db_path=db.path,
        client=fake,
        library_id="local",
        library_type="user",
    )
    first = local_service.sync_topic("demo-topic", include_notes=True)
    web_service = ZoteroSyncService(
        db_path=db.path,
        client=fake,
        library_id="16929158",
        library_type="user",
    )

    second = web_service.sync_topic(
        "demo-topic",
        target_collection_key=first.topic_collection_key,
        paper_ids=[1],
    )

    assert second.skipped_count == 1
    assert len(fake.created_items) == 1
    assert fake.updated_items == []
    conn = db.connect()
    try:
        web_row = conn.execute(
            """
            SELECT zotero_collection_key, zotero_item_key, zotero_note_key
            FROM zotero_item_links
            WHERE paper_id = 1 AND topic_id = 1
              AND zotero_library_id = '16929158'
              AND zotero_library_type = 'user'
            """
        ).fetchone()
    finally:
        conn.close()
    assert web_row is not None
    assert web_row["zotero_item_key"] == first.papers[0].zotero_item_key
    assert web_row["zotero_note_key"] == first.papers[0].zotero_note_key
    assert web_row["zotero_collection_key"] == first.topic_collection_key


def test_zotero_sync_reuses_legacy_local_user_link_for_web_api_user_id(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    fake.items["LOCALITM"] = {"title": "Existing Zotero item"}
    fake.notes["LOCALNTE"] = {
        "parentItem": "LOCALITM",
        "note": "<p>Old RH note</p>",
        "tags": ["rh-generated", "rh-paper-id:1"],
    }
    service = ZoteroSyncService(
        db_path=db.path,
        client=fake,
        library_id="16929158",
        library_type="user",
    )
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO zotero_item_links (
                paper_id, topic_id, zotero_library_id, zotero_library_type,
                zotero_collection_key, zotero_item_key, zotero_note_key,
                content_hash, last_synced_at
            )
            VALUES (1, 1, 'local', 'user', 'CURRDIR1', 'LOCALITM', 'LOCALNTE', 'old', '')
            """
        )
        conn.commit()
    finally:
        conn.close()

    result = service.sync_topic(
        "demo-topic",
        target_collection_key="CURRDIR1",
        paper_ids=[1],
    )

    assert result.synced_count == 1
    assert fake.created_items == []
    assert fake.updated_items[0][0] == "LOCALITM"
    assert fake.updated_notes[0][0] == "LOCALNTE"

    conn = db.connect()
    try:
        web_row = conn.execute(
            """
            SELECT zotero_item_key, zotero_note_key FROM zotero_item_links
            WHERE paper_id = 1 AND topic_id = 1
              AND zotero_library_id = '16929158'
              AND zotero_library_type = 'user'
            """
        ).fetchone()
    finally:
        conn.close()
    assert web_row is not None
    assert web_row["zotero_item_key"] == "LOCALITM"
    assert web_row["zotero_note_key"] == "LOCALNTE"


def test_zotero_sync_dry_run_cli_outputs_plan(tmp_path, monkeypatch):
    db_path = tmp_path / "rh.db"
    _seed_db(db_path)
    monkeypatch.setenv("RESEARCH_HUB_DB_PATH", str(db_path))

    result = CliRunner().invoke(
        main,
        ["--json", "zotero", "sync", "--topic", "demo-topic", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["planned_count"] == 1
    assert payload["records"][0]["paper_id"] == 1
    assert payload["records"][0]["title"] == "Agentic Paper Reading"


def test_zotero_sync_cli_connector_adapter_and_topic_collection(tmp_path, monkeypatch):
    db_path = tmp_path / "rh.db"
    _seed_db(db_path)
    fake = FakeConnectorZoteroClient()
    monkeypatch.setenv("RESEARCH_HUB_DB_PATH", str(db_path))
    monkeypatch.setattr(
        "research_harness.zotero_resource.create_zotero_resource",
        lambda **_: fake,
    )

    result = CliRunner().invoke(
        main,
        [
            "--json",
            "zotero",
            "sync",
            "--topic",
            "demo-topic",
            "--adapter",
            "connector",
            "--library-id",
            "local",
            "--topic-collection",
            "自动科研",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["synced_count"] == 1
    root = fake.find_collection("Research Harness")
    assert fake.find_collection("自动科研", root) == payload["topic_collection_key"]
    assert len(fake.create_item_with_note_calls) == 1


def test_zotero_pull_imports_user_notes_and_skips_rh_generated_notes(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    item_key = push.papers[0].zotero_item_key

    fake.add_child_note(
        "USERNOTE1",
        item_key,
        "<h1>Human reading note</h1><p>This is my Zotero insight.</p>",
        tags=["human"],
    )

    result = service.pull_topic("demo-topic")

    assert result.imported_count == 1
    assert result.skipped_count == 1  # the RH-generated deep-read note is skipped
    assert result.items[0].zotero_child_key == "USERNOTE1"

    conn = db.connect()
    try:
        notes = conn.execute(
            "SELECT * FROM topic_paper_notes "
            "WHERE source LIKE 'zotero:note:USERNOTE1:%'"
        ).fetchall()
        imports = conn.execute(
            "SELECT * FROM zotero_import_links "
            "WHERE zotero_child_key = 'USERNOTE1'"
        ).fetchall()
    finally:
        conn.close()

    assert len(notes) == 1
    assert notes[0]["note_type"] == "zotero_note"
    assert "Human reading note" in notes[0]["content"]
    assert "This is my Zotero insight" in notes[0]["content"]
    assert len(imports) == 1
    assert imports[0]["target_table"] == "topic_paper_notes"


def test_zotero_pull_is_idempotent_by_child_content_hash(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    item_key = push.papers[0].zotero_item_key
    fake.add_child_note("USERNOTE1", item_key, "<p>Stable Zotero note.</p>")

    first = service.pull_topic("demo-topic")
    second = service.pull_topic("demo-topic")

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_count >= 1

    conn = db.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM topic_paper_notes "
            "WHERE source LIKE 'zotero:note:USERNOTE1:%'"
        ).fetchone()["count"]
    finally:
        conn.close()
    assert count == 1


def test_zotero_pull_dry_run_reports_importable_notes_without_mutation(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    item_key = push.papers[0].zotero_item_key
    fake.add_child_note("USERNOTE1", item_key, "<p>Preview only.</p>")

    result = service.pull_topic("demo-topic", dry_run=True)

    assert result.dry_run is True
    assert result.planned_count == 1
    assert result.imported_count == 0
    assert result.items[0].action == "would_import"

    conn = db.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM topic_paper_notes "
            "WHERE source LIKE 'zotero:note:USERNOTE1:%'"
        ).fetchone()["count"]
    finally:
        conn.close()
    assert count == 0


def test_zotero_pull_dry_run_cli_uses_resource_adapter(tmp_path, monkeypatch):
    db_path = tmp_path / "rh.db"
    db = _seed_db(db_path)
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    fake.add_child_note("USERNOTE1", push.papers[0].zotero_item_key, "<p>CLI preview.</p>")
    monkeypatch.setenv("RESEARCH_HUB_DB_PATH", str(db_path))
    monkeypatch.setattr(
        "research_harness.zotero_resource.create_zotero_resource_from_env",
        lambda **_: fake,
    )

    result = CliRunner().invoke(
        main,
        ["--json", "zotero", "pull", "--topic", "demo-topic", "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["planned_count"] == 1
    assert payload["items"][0]["zotero_child_key"] == "USERNOTE1"


def test_zotero_sync_direction_pull_cli_uses_resource_adapter(tmp_path, monkeypatch):
    db_path = tmp_path / "rh.db"
    db = _seed_db(db_path)
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    fake.add_child_note(
        "USERNOTE1",
        push.papers[0].zotero_item_key,
        "<p>Unified sync pull preview.</p>",
    )
    monkeypatch.setenv("RESEARCH_HUB_DB_PATH", str(db_path))
    monkeypatch.setattr(
        "research_harness.zotero_resource.create_zotero_resource_from_env",
        lambda **_: fake,
    )

    result = CliRunner().invoke(
        main,
        [
            "--json",
            "zotero",
            "sync",
            "--topic",
            "demo-topic",
            "--direction",
            "pull",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["planned_count"] == 1
    assert payload["items"][0]["zotero_child_key"] == "USERNOTE1"


def test_zotero_sync_direction_both_cli_returns_push_and_pull_payloads(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "rh.db"
    db = _seed_db(db_path)
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    fake.add_child_note(
        "USERNOTE1",
        push.papers[0].zotero_item_key,
        "<p>Unified both preview.</p>",
    )
    monkeypatch.setenv("RESEARCH_HUB_DB_PATH", str(db_path))
    monkeypatch.setattr(
        "research_harness.zotero_resource.create_zotero_resource_from_env",
        lambda **_: fake,
    )

    result = CliRunner().invoke(
        main,
        [
            "--json",
            "zotero",
            "sync",
            "--topic",
            "demo-topic",
            "--direction",
            "both",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["direction"] == "both"
    assert payload["dry_run"] is True
    assert payload["push"]["planned_count"] == 1
    assert payload["pull"]["planned_count"] == 1
    assert payload["pull"]["items"][0]["zotero_child_key"] == "USERNOTE1"


def test_zotero_pull_imports_multiple_user_notes_for_same_paper(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    item_key = push.papers[0].zotero_item_key
    fake.add_child_note("USERNOTE1", item_key, "<p>First Zotero note.</p>")
    fake.add_child_note("USERNOTE2", item_key, "<p>Second Zotero note.</p>")

    result = service.pull_topic("demo-topic")

    assert result.imported_count == 2
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT note_type, content, source FROM topic_paper_notes "
            "WHERE source LIKE 'zotero:note:%' ORDER BY source"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert {row["note_type"] for row in rows} == {"zotero_note"}
    assert [row["content"] for row in rows] == [
        "First Zotero note.",
        "Second Zotero note.",
    ]


def test_zotero_pull_appends_changed_user_note_version(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    item_key = push.papers[0].zotero_item_key
    fake.add_child_note("USERNOTE1", item_key, "<p>Original Zotero note.</p>")

    first = service.pull_topic("demo-topic")
    fake.add_child_note("USERNOTE1", item_key, "<p>Revised Zotero note.</p>")
    second = service.pull_topic("demo-topic")

    assert first.imported_count == 1
    assert second.imported_count == 1
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT content, source FROM topic_paper_notes "
            "WHERE source LIKE 'zotero:note:USERNOTE1:%' ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert [row["content"] for row in rows] == [
        "Original Zotero note.",
        "Revised Zotero note.",
    ]
    assert len({row["source"] for row in rows}) == 2


def test_zotero_pull_imports_attachment_annotations(tmp_path):
    db = _seed_db(tmp_path / "rh.db")
    fake = FakeZoteroClient()
    service = ZoteroSyncService(db_path=db.path, client=fake)
    push = service.sync_topic("demo-topic", include_notes=True)
    item_key = push.papers[0].zotero_item_key
    fake.add_attachment("PDFATT01", item_key, title="Paper PDF")
    fake.add_annotation(
        "ANNOT001",
        "PDFATT01",
        text="This highlighted claim matters.",
        comment="Check against the baseline section.",
        color="#ffd400",
        page_label="7",
        annotation_type="highlight",
        tags=["important"],
    )

    result = service.pull_topic("demo-topic")

    assert result.imported_count == 1
    imported = [item for item in result.items if item.action == "imported"]
    assert imported[0].zotero_child_key == "ANNOT001"
    assert imported[0].target_table == "topic_paper_notes"

    conn = db.connect()
    try:
        notes = conn.execute(
            "SELECT * FROM topic_paper_notes "
            "WHERE source LIKE 'zotero:annotation:ANNOT001:%'"
        ).fetchall()
        imports = conn.execute(
            "SELECT * FROM zotero_import_links "
            "WHERE zotero_child_key = 'ANNOT001'"
        ).fetchall()
    finally:
        conn.close()

    assert len(notes) == 1
    assert notes[0]["note_type"] == "zotero_annotation"
    assert "highlight" in notes[0]["content"]
    assert "page 7" in notes[0]["content"]
    assert "This highlighted claim matters" in notes[0]["content"]
    assert "Check against the baseline section" in notes[0]["content"]
    assert "#ffd400" in notes[0]["content"]
    assert "important" in notes[0]["content"]
    assert len(imports) == 1
    assert imports[0]["zotero_child_type"] == "annotation"
