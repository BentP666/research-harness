-- Migration 065: add topics.updated_at so topic_set_contributions's
-- "SET updated_at = datetime('now')" stops failing with
-- "no such column: updated_at".
--
-- Background: 001_initial_schema gave topics only ``created_at``. Later
-- code (037_domains_and_project_merge added contributions, and the
-- topic_set_contributions primitive) started writing ``updated_at`` on
-- every UPDATE, which silently blew up at runtime on any DB that was
-- migrated from before this date.

ALTER TABLE topics ADD COLUMN updated_at TEXT DEFAULT '';

-- Back-fill rows so the column is queryable:
UPDATE topics SET updated_at = COALESCE(created_at, datetime('now'))
WHERE COALESCE(updated_at, '') = '';
