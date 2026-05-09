"""Backend stability test suite.

Three-tier time budget:
- smoke      (10-20min): single-file regressions + schema + 1 fixture topic + mocked LLM
- pre-merge  (30-60min): 2 E2E main chains (autonomous survey + supervised loopback)
                         + core fault injections (mocked LLM, small scope)
- nightly    (2-6h):     full benchmark + kill-9 + DB corruption tiers + concurrency

Run via:
    pytest packages/research_harness/tests/backend_stability -m smoke -q
    pytest packages/research_harness/tests/backend_stability -m pre_merge -q
    pytest packages/research_harness/tests/backend_stability -m nightly -q
"""
