#!/usr/bin/env python3
"""Batch-enrich all papers missing venue/citation_count.

Strategy: OpenAlex first (free, fast), S2 fallback for remaining gaps.

Usage:
    nohup python scripts/backfill_s2_metadata.py > logs/backfill_s2.log 2>&1 &

Safe to re-run — skips already-enriched papers.
"""
import logging
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "research_harness"))

from research_harness.core.paper_pool import PaperPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill")

DB_PATH = os.environ.get(
    "RESEARCH_HARNESS_DB_PATH",
    os.path.expanduser("~/.research-harness/pool.db"),
)
VENUE_PLACEHOLDERS = ("", "arxiv", "arxiv.org", "arxiv preprint")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    pool = PaperPool(conn)

    rows = conn.execute(
        """
        SELECT id, title, venue, citation_count
        FROM papers
        ORDER BY id DESC
        """
    ).fetchall()

    candidates = []
    for r in rows:
        v = (r["venue"] or "").strip().lower()
        c = r["citation_count"]
        title = (r["title"] or "").strip()
        if not title or title.startswith(("doi:", "s2:", "pdf:")):
            candidates.append(r["id"])
        elif v in VENUE_PLACEHOLDERS or c is None or c == 0:
            candidates.append(r["id"])

    log.info("Found %d papers to enrich out of %d total", len(candidates), len(rows))

    enriched = 0
    failed = 0
    s2_calls = 0
    for i, pid in enumerate(candidates):
        try:
            result = pool.enrich_metadata(pid)
            if result and "error" not in result:
                enriched += 1
            else:
                failed += 1
            # If S2 was called (has s2-specific keys), count it for pacing
            if any(k in result for k in ("s2_id", "open_access_pdf", "affiliations")):
                s2_calls += 1
                time.sleep(1.05)
            else:
                time.sleep(0.2)
        except Exception as exc:
            failed += 1
            log.debug("Paper %d error: %s", pid, exc)
            time.sleep(0.2)

        if (i + 1) % 100 == 0:
            log.info(
                "[%d/%d] enriched=%d failed=%d s2_calls=%d (%.0f%%)",
                i + 1, len(candidates), enriched, failed, s2_calls,
                enriched * 100 / (i + 1),
            )

    log.info(
        "DONE: %d enriched, %d failed, %d S2 calls out of %d total",
        enriched, failed, s2_calls, len(candidates),
    )
    conn.close()


if __name__ == "__main__":
    main()
