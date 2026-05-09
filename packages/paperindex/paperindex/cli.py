"""paperindex CLI — thin wrapper around research_harness.paperindex.cli.

Kept so `pip install paperindex` + `paperindex <cmd>` continue to work.
All real logic lives in research_harness.paperindex.cli.
"""

from research_harness.paperindex.cli import main  # noqa: F401

if __name__ == "__main__":
    main()
