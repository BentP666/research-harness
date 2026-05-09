"""Backfill claim_uuid / modality / evidence_spans_json / paper_ids_json / confidence
for existing rows in the claims table.

Migration 050 added the columns but did not populate them. This script fills
historic rows with sensible defaults (modality='text', confidence=0.0,
evidence_spans_json='[]'), computes a deterministic claim_uuid from content,
and derives paper_ids_json from claim_citations.

Usage:
    python -m research_harness.scripts.backfill_claim_modality
    python -m research_harness.scripts.backfill_claim_modality --apply

Default is dry-run (reports what WOULD change without writing).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys

from research_harness.storage.db import Database
from research_harness.config import GLOBAL_DB_PATH

logger = logging.getLogger(__name__)


def _derive_uuid(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"claim_{digest}"


def backfill(db_path: str, *, apply: bool) -> dict[str, int]:
    """Backfill claims table for rows missing migration 050 fields.

    Returns a summary dict with counts of rows touched per field.
    """
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id, text, modality, claim_uuid, paper_ids_json,
                   evidence_spans_json, confidence
            FROM claims
            """
        ).fetchall()
    finally:
        conn.close()

    stats = {
        "total": len(rows),
        "uuid_filled": 0,
        "modality_filled": 0,
        "paper_ids_filled": 0,
        "spans_filled": 0,
        "confidence_filled": 0,
        "rows_touched": 0,
    }

    if not rows:
        return stats

    updates: list[tuple[int, dict]] = []
    for row in rows:
        changes: dict[str, object] = {}
        claim_id = row["id"]

        if not row["claim_uuid"]:
            changes["claim_uuid"] = _derive_uuid(row["text"] or "")
            stats["uuid_filled"] += 1

        if not row["modality"]:
            changes["modality"] = "text"
            stats["modality_filled"] += 1

        if row["paper_ids_json"] is None:
            conn = db.connect()
            try:
                citing = conn.execute(
                    "SELECT paper_id FROM claim_citations WHERE claim_id = ?",
                    (claim_id,),
                ).fetchall()
            finally:
                conn.close()
            pids = [int(r["paper_id"]) for r in citing]
            if pids:
                changes["paper_ids_json"] = json.dumps(pids)
                stats["paper_ids_filled"] += 1

        if row["evidence_spans_json"] is None:
            changes["evidence_spans_json"] = "[]"
            stats["spans_filled"] += 1

        if row["confidence"] is None or row["confidence"] == 0:
            # Migration 050 already defaults confidence=0.0; we only log when
            # the column is NULL (unusual). We don't overwrite 0.0 explicitly
            # since that's the default.
            if row["confidence"] is None:
                changes["confidence"] = 0.0
                stats["confidence_filled"] += 1

        if changes:
            stats["rows_touched"] += 1
            updates.append((claim_id, changes))

    if apply and updates:
        conn = db.connect()
        try:
            for claim_id, changes in updates:
                set_clause = ", ".join(f"{k} = ?" for k in changes)
                values = list(changes.values()) + [claim_id]
                conn.execute(
                    f"UPDATE claims SET {set_clause} WHERE id = ?",
                    values,
                )
            conn.commit()
        finally:
            conn.close()

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--db-path",
        default=str(GLOBAL_DB_PATH),
        help=f"Database path (default: {GLOBAL_DB_PATH})",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    stats = backfill(args.db_path, apply=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Backfill summary for {args.db_path}:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if not args.apply and stats["rows_touched"] > 0:
        print("\nRun again with --apply to write these changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
