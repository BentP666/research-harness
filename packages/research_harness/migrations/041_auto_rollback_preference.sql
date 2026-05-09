-- Migration 041: user-togglable auto-rollback mode
-- Stores shadow/live state so the judge engine can be flipped from the UI
-- without editing env vars or redeploying.
--
-- NULL / 0 (default) = shadow mode (safe; spec §7.3 requires shadow window
-- before enabling auto-rollback on a topic).
-- 1 = live mode (rubric verdict drives auto-rollback).

ALTER TABLE user_preferences
  ADD COLUMN auto_rollback_live INTEGER NOT NULL DEFAULT 0;
