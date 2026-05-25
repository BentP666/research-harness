# Zotero Resource Sync Capability

## CAPABILITY

Research Harness treats Zotero as a first-class local research resource, not as an ad hoc external plugin. A researcher can let RH discover, ingest, rank, and deep-read papers, then see those papers and RH outputs inside Zotero for human reading; the same researcher can later annotate, highlight, and write notes in Zotero, and RH can pull those human reading signals back into its provenance-aware paper/topic records.

## CONSTRAINTS

- **RH remains the source of research provenance.** RH owns `topic_id`, `paper_id`, orchestrator artifacts, claim extraction, gap analysis, and deep-read outputs.
- **Zotero remains the human reading surface.** Zotero owns manual reading workflows: collections, PDF reading, highlights, annotations, and personal notes.
- **Zotero is a RH resource.** Integration belongs under RH CLI/API/MCP surfaces and must not require the user to manually coordinate a separate agent-side Zotero workflow.
- **Do not duplicate low-level Zotero API logic long-term.** Zotero write/read plumbing should reuse or vendor the mature writer/reader patterns from `54yyyu/zotero-mcp` / `pyzotero` where possible.
- **No unsafe overwrite.** RH-generated Zotero notes and user-authored Zotero notes must be distinguishable. Pulling from Zotero must append/import as traceable RH notes or annotations unless a future explicit overwrite policy is approved.
- **Idempotency is mandatory.** Re-running sync must not create duplicate Zotero items, duplicate RH notes, or duplicate RH artifacts.
- **Local-only Zotero is not enough for writes.** Zotero local access is useful for reads/full text, but child-note and item writes require Zotero Web API credentials or a hybrid local-read/web-write mode.
- **Credentials stay outside repo.** Zotero API key/library ID must come from env/keychain/user config, never committed project config.
- **PDF attachment sync is optional in phase 1.** Papers and notes are more important than binary PDF upload; attachment handling can follow after metadata and notes are stable.

## IMPLEMENTATION CONTRACT

### Actors

- **Researcher**: reads in Zotero, highlights, writes notes, and uses RH for literature work.
- **RH CLI/API/MCP**: exposes sync commands/tools and records provenance.
- **Zotero Resource Adapter**: RH-internal adapter responsible for read/write operations against Zotero.
- **Zotero Desktop/Web API**: external library and PDF reading system.

### Surfaces

Required RH-owned surfaces:

- `rh zotero push --topic <topic>`: RH → Zotero.
- `rh zotero pull --topic <topic>`: Zotero → RH.
- `rh zotero sync --topic <topic> --direction push|pull|both`: combined orchestration for one-command RH↔Zotero sync.
- MCP tool `zotero_sync(topic, direction=push|pull|both, ...)`: agent/tool-callable sync surface backed by the same RH Python service.
- HTTP API `POST /api/topics/{topic_id}/zotero-sync`: frontend/API sync surface backed by the same RH Python service.

### Direction A: RH → Zotero

Inputs:

- RH `topics`, `papers`, `paper_topics`, `paper_annotations`, `topic_paper_notes`, `bib_entries`.

Outputs:

- Zotero collection tree:
  - `Research Harness / <topic-name>` by default.
- Zotero parent items for RH papers.
- Zotero child notes containing RH deep-read results, paper annotations, topic notes, and RH identifiers.
- Zotero tags such as:
  - `rh`
  - `rh-topic:<topic-name>`
  - `rh-paper-id:<paper_id>`
  - `rh-relevance:<high|medium|low>`
  - `rh-deep-read`
  - `rh-generated`

State/mapping:

- `zotero_item_links` maps `(paper_id, topic_id, library_id, library_type)` to Zotero item/note keys and content hash.
- The RH-generated child note must be identifiable by either the mapped `zotero_note_key` or tag `rh-generated` / `rh-deep-read-note`.

### Direction B: Zotero → RH

Inputs:

- Zotero items that already map to RH papers via `zotero_item_links` or `rh-paper-id:<paper_id>` tag.
- Zotero child notes, tags, and annotations associated with those mapped parent items.

Outputs:

- Imported human notes into RH as `topic_paper_notes.note_type='zotero_note'`, with source values such as `zotero:note:<note_key>:<content_hash_prefix>`.
- Imported Zotero annotation summaries into RH as `topic_paper_notes.note_type='zotero_annotation'`, because pull is currently topic-scoped through `zotero_item_links`.
- Optional orchestrator artifacts for milestone imports, e.g. `zotero_reading_import`.

State/mapping:

- A new import mapping table should track Zotero-origin records, e.g. `zotero_import_links`:
  - `topic_id`
  - `paper_id`
  - `zotero_item_key`
  - `zotero_child_key`
  - `zotero_child_type` (`note`, `annotation`, etc.)
  - `target_table`
  - `target_id`
  - `content_hash`
  - `last_imported_at`
- Pull must skip RH-generated notes by default to avoid re-importing RH's own deep-read note as human feedback.

### States and transitions

- `unlinked`: RH paper has no Zotero item.
- `pushed`: RH paper has a Zotero item and optional RH-generated note.
- `zotero_modified`: Zotero item/children changed since last import.
- `pulled`: Zotero notes/annotations imported into RH.
- `conflict`: same target content changed in both systems and requires explicit resolution.

### Data ownership

- RH-generated notes are owned by RH and may be updated by RH push when content hash changes.
- Zotero user notes and annotations are owned by Zotero/user and imported into RH append-only by default; exact duplicate child/content hashes are skipped.
- RH should not delete Zotero user notes or highlights.
- Zotero should not directly mutate RH primitives; pull converts Zotero content into RH records with explicit source/provenance.

### Adapter boundary

`research_harness.zotero_resource` should expose a stable RH-facing interface, independent of whether implementation is vendored from `zotero-mcp`, imports `zotero-mcp-server`, or uses `pyzotero` directly:

```python
class ZoteroResource:
    def ensure_collection(self, name: str, parent_key: str | None = None) -> str: ...
    def upsert_item(self, payload: ZoteroItemPayload, external_id: str) -> str: ...
    def upsert_child_note(self, parent_key: str, note_html: str, tags: list[str], existing_key: str | None = None) -> str: ...
    def list_item_children(self, item_key: str) -> list[ZoteroChild]: ...
    def find_items_by_rh_tag(self, paper_id: int | None = None, topic_name: str | None = None) -> list[ZoteroItem]: ...
```

The current minimal `ZoteroWebApiResource` in `zotero_resource.py` should be treated as the first adapter, not the final low-level Zotero implementation; richer zotero-mcp/pyzotero behavior can be added behind the same interface.

## NON-GOALS

- RH will not become a full Zotero replacement.
- RH will not own the user's entire Zotero library, only RH-linked items/collections.
- Phase 1 will not attempt bidirectional conflict-free editing of the same note body.
- Phase 1 will not require PDF binary upload, WebDAV management, or Zotero storage quota handling.
- Phase 1 will not run RH research primitives through Zotero MCP; RH primitives remain RH-native.

## OPEN QUESTIONS

- Should pulled Zotero highlights be stored as `paper_annotations` or `topic_paper_notes` by default?
- Should a pull create an orchestrator artifact every time, or only on explicit `--record-artifact`?
- Should Zotero user notes be imported only when tagged `rh-import`, or should all non-RH-generated child notes be imported?
- Should RH create/maintain Better BibTeX citation keys or only preserve those already present in Zotero?
- How should duplicate Zotero items be reconciled when multiple items carry the same `rh-paper-id` tag?

## HANDOFF

Implementation status:

1. **Resource adapter refactor**: implemented as `research_harness.zotero_resource`; the default adapter is still a minimal Web API resource and should later absorb more mature zotero-mcp/pyzotero writer behavior.
2. **Push hardening**: implemented for RH → Zotero items/collections/child notes with `zotero_item_links` idempotency.
3. **Pull implementation**: implemented for Zotero child notes and PDF annotations → `topic_paper_notes` with `zotero_import_links`, dry-run reporting, RH-generated note skipping, and content-hash idempotency. Pull traverses parent item → attachment → annotation because Zotero exposes PDF annotations as child items of attachments.
4. **External note multiplicity**: implemented a source-aware `topic_paper_notes` uniqueness migration so multiple Zotero notes/highlights and changed note versions can coexist while RH-authored typed-note upserts still update one row per note type.
5. **Unified sync command**: implemented `rh zotero sync --direction push|pull|both`, with `push` remaining as a compatibility alias and `pull` remaining as a direct command.
6. **MCP/API surfaces**: implemented MCP tool `zotero_sync` and HTTP endpoint `POST /api/topics/{topic_id}/zotero-sync`, both reusing the RH-owned sync service instead of delegating to an external Zotero MCP.

Next implementation phases:

1. Add richer zotero-mcp-derived metadata/PDF writer behavior behind `zotero_resource`.
2. Add optional orchestrator artifact recording for Zotero pull batches.
3. Add frontend affordances for previewing push/pull plans and showing last Zotero sync status per topic.
