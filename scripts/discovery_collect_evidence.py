#!/usr/bin/env python3
"""Collect RH Discovery evidence via the canonical CLI.

This thin wrapper exists so operators can run a memorable script while keeping
the implementation and validation gates in ``rh discover evidence``.
"""

from __future__ import annotations

import sys

from research_harness.cli import main


if __name__ == "__main__":
    sys.exit(
        main(
            ["discover", "evidence", "collect", *sys.argv[1:]],
            prog_name="discovery_collect_evidence.py",
        )
    )
