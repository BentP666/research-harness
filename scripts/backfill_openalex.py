#!/usr/bin/env python3
"""Second-pass enrichment: OpenAlex fallback for papers S2 couldn't fill.

Run AFTER backfill_s2_metadata.py completes. Targets papers still missing
venue or citation_count, using OpenAlex DOI lookup + title search.

Usage:
    nohup python scripts/backfill_openalex.py > logs/backfill_openalex.log 2>&1 &
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
log = logging.getLogger("backfill-oa")

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
        SELECT id, title, doi, venue, citation_count
        FROM papers
        WHERE (venue IS NULL OR venue = '' OR LOWER(venue) IN ('arxiv','arxiv.org','arxiv preprint'))
           OR citation_count IS NULL OR citation_count = 0
        ORDER BY id DESC
        """
    ).fetchall()

    candidates = []
    for r in rows:
        v = (r["venue"] or "").strip().lower()
        c = r["citation_count"]
        if v in VENUE_PLACEHOLDERS or c is None or c == 0:
            candidates.append(r["id"])

    log.info("Found %d papers still missing venue/citations for OpenAlex pass", len(candidates))

    enriched = 0
    failed = 0
    for i, pid in enumerate(candidates):
        try:
            row = conn.execute("SELECT * FROM papers WHERE id = ?", (pid,)).fetchone()
            if row is None:
                continue
            result = pool._enrich_from_openalex(pid, row)
            if result:
                enriched += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            log.debug("Paper %d error: %s", pid, exc)

        if (i + 1) % 50 == 0:
            log.info(
                "[%d/%d] enriched=%d failed=%d (%.0f%%)",
                i + 1, len(candidates), enriched, failed,
                enriched * 100 / (i + 1) if i > 0 else 0,
            )
        time.sleep(0.2)  # OpenAlex is generous but be polite

    log.info(
        "DONE: %d enriched, %d failed out of %d total",
        enriched, failed, len(candidates),
    )
    conn.close()


if __name__ == "__main__":
    main()
