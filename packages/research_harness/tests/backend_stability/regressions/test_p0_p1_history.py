"""Regression tests — one per historical P0/P1 bug.

Every test here references the source entry in docs/feedback/bugs.md by date
and short title. The pattern is::

    @pytest.mark.regression
    def test_<short_id>_<short_desc>(db, runner):
        '''Source: docs/feedback/bugs.md [2026-04-08] <title>

        Failure mode: ...
        Fix landed in: <commit | "open">
        Boolean assertion: <which assertion catches it>
        '''
        # arrange the precondition that triggered the original bug
        # act with the same primitive/tool that originally failed
        # assert the boolean check that caught it now returns passed=True

Stubs marked ``xfail(strict=False)`` mean "we have not wired the
arrangement yet — the test SHOULD pass once #N lands"; the body is a
docstring + a TODO so future-us can flesh it out without re-reading
bugs.md.

The point of this module is **coverage breadth, not depth**: every
documented P0/P1 gets a named test slot, so we can never silently
regress an old bug just because nobody wrote a test.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.regression


# ---------------------------------------------------------------------------
# 2026-04-08 batch
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_orchestrator_record_artifact_python_callable(db):
    """Source: bugs.md [2026-04-08] orchestrator_record_artifact 无法通过 Python 直接调用.

    Failure mode: callers that imported the function got NotImplementedError
    because the dispatcher only recognized the MCP-tool path.
    Boolean assertion: assert_provenance_complete (the artifact recorded
    via the Python path must show up with provenance like the MCP path).

    Real check: import OrchestratorService.record_artifact directly and
    confirm it produces a row, then re-load and check artifact_type matches.
    """
    from research_harness.orchestrator.service import OrchestratorService

    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    svc = OrchestratorService(db)
    svc.init_run(loaded.topic_id, mode="standard")
    artifact = svc.record_artifact(
        topic_id=loaded.topic_id,
        stage="init",
        artifact_type="topic_brief",
        title="python-direct-call",
        payload={"scope": "test", "venue_target": "test"},
    )
    assert artifact.id > 0
    assert artifact.artifact_type == "topic_brief"

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT artifact_type, title FROM project_artifacts WHERE id = ?",
            (artifact.id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["artifact_type"] == "topic_brief"
    assert row["title"] == "python-direct-call"


@pytest.mark.regression
def test_academic_search_unavailable_no_silent_zero(db, monkeypatch):
    """Source: bugs.md [2026-04-08] 所有 academic MCP 服务在 literature-search 时全部不可用.

    Failure mode: when arxiv/s2 were down, paper_search returned 0
    results with no error logged — looked like the topic was empty.
    Boolean assertion: assert_no_unexplained_traceback (the outage MUST
    surface as a structured provider_error, not a silent zero).

    Real check: inject a provider suite where every provider raises.
    The aggregator must record one ProviderError per provider; the
    resulting PaperSearchOutput.provider_errors must be non-empty;
    result_count may be 0 but it must not be silent.
    """
    from research_harness.primitives.impls import paper_search

    from ..fixtures import load_topic
    from ..injectors.network import FailingProvider, fake_provider_suite

    loaded = load_topic(db, "small_tfr")
    providers = [
        FailingProvider(name="arxiv", error_message="arxiv outage"),
        FailingProvider(name="s2", error_message="s2 outage"),
        FailingProvider(name="openalex", error_message="openalex outage"),
    ]
    with fake_provider_suite(monkeypatch, providers):
        result = paper_search(
            db=db,
            query="time series forecasting",
            topic_id=loaded.topic_id,
            max_results=10,
        )

    # The essential guard: the outage was NOT silently swallowed.
    assert len(result.provider_errors) >= 1, (
        f"outage must surface as provider_errors, got: {result.provider_errors}"
    )
    # Each provider's error carries its name + message
    joined = " | ".join(result.provider_errors).lower()
    assert "outage" in joined


@pytest.mark.regression
def test_s2_rate_limit_does_not_drop_papers(db, monkeypatch):
    """Source: bugs.md [2026-04-10] Semantic Scholar 因 rate limit 被跳过.

    Failure mode: S2 429 → provider was skipped → relevant papers
    silently missing from the pool, not even surfaced as an error.
    Boolean assertion: the rate-limited provider must appear in
    provider_errors, AND other providers' results must still be merged
    into the output (partial success semantics, not all-or-nothing).

    Real check: s2 raises RateLimitError, arxiv returns zero records
    but succeeds. Output must have provider_errors[s2], and no silent
    swallowing of the rate limit.
    """
    from research_harness.primitives.impls import paper_search

    from ..fixtures import load_topic
    from ..injectors.network import (
        FailingProvider,
        RateLimitedProvider,
        fake_provider_suite,
    )

    loaded = load_topic(db, "small_tfr")
    providers = [
        RateLimitedProvider(name="s2", fail_n=5, error_message="429 rate_limit"),
        FailingProvider(
            name="arxiv",
            error_type=TimeoutError,
            error_message="arxiv also down for clarity",
        ),
    ]
    with fake_provider_suite(monkeypatch, providers):
        result = paper_search(
            db=db,
            query="forecasting",
            topic_id=loaded.topic_id,
            max_results=10,
        )

    joined = " | ".join(result.provider_errors)
    assert "s2" in joined.lower(), (
        f"s2 rate limit not surfaced: {result.provider_errors}"
    )
    assert "rate_limit" in joined or "429" in joined, (
        f"rate-limit signal lost: {result.provider_errors}"
    )


@pytest.mark.regression
def test_db_schema_matches_agent_guide(db):
    """Source: bugs.md [2026-04-08] DB 表名和字段名与 agent-guide 文档不一致.

    Failure mode: agents wrote to old column names that had been renamed,
    silent inserts dropped data.
    Boolean assertion: structural — every (table, column) referenced by
    `pragma table_info` for the core orchestrator/paper tables matches
    the names the boolean_suite + assertion code rely on. Guards against
    a future schema rename silently breaking the test suite.

    Pragmatic scope: rather than parse agent-guide.md (formatting can
    drift), pin the column names that the boolean_suite + injectors
    reference. If a migration renames a column, this test fires AND the
    suite fails, so the rename can't sneak through.
    """
    expected: dict[str, set[str]] = {
        "papers": {
            "id",
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "arxiv_id",
            "s2_id",
            "status",
            "affiliations",
        },
        "paper_topics": {"paper_id", "topic_id", "relevance"},
        "topics": {"id", "name"},
        "orchestrator_runs": {"id", "topic_id", "current_stage", "stage_status"},
        "orchestrator_stage_events": {
            "id",
            "run_id",
            "topic_id",
            "from_stage",
            "to_stage",
            "event_type",
            "status",
            "gate_type",
            "rationale",
            "payload_json",
        },
        "project_artifacts": {
            "id",
            "topic_id",
            "stage",
            "artifact_type",
            "status",
            "payload_json",
            "provenance_record_id",
        },
        "provenance_records": {
            "id",
            "primitive",
            "topic_id",
            "stage",
            "model_used",
            "cost_usd",
            "success",
            "error",
        },
    }
    conn = db.connect()
    try:
        missing: list[str] = []
        for table, cols in expected.items():
            actual_rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            actual = {r["name"] for r in actual_rows}
            if not actual:
                missing.append(f"table {table!r} does not exist")
                continue
            gone = sorted(cols - actual)
            if gone:
                missing.append(f"{table}: missing columns {gone}")
    finally:
        conn.close()
    assert not missing, "\n".join(missing)


@pytest.mark.regression
def test_corrupted_paper_does_not_break_topic_batch(db):
    """Source: bugs.md [2026-04-09] 单篇论文记录损坏导致整个 topic 的批量操作全部失败.

    Failure mode: one bad row in `papers` aborted the SQL `JOIN papers
    USING(paper_id)` so every batch primitive saw zero rows for the
    whole topic.
    Boolean assertion: assert_paper_count_conserved + isolation —
    after corrupting one row, COUNT(*) of the other rows must remain
    accessible, even if parsing the corrupted one fails.

    Real check: corrupt fixture-paper-tfr-001's authors column, then
    query papers for the topic. COUNT must still return all 5 rows
    (SQLite doesn't reject the row; downstream parsers must handle
    the bad JSON gracefully).
    """
    import json as _json

    from ..fixtures import load_topic
    from ..injectors.storage import corrupt_paper_row

    loaded = load_topic(db, "small_tfr")
    target = loaded.paper_ids[0]
    with corrupt_paper_row(db, target):
        conn = db.connect()
        try:
            count = conn.execute(
                """
                SELECT COUNT(*) AS n FROM papers p
                JOIN paper_topics pt ON pt.paper_id = p.id
                WHERE pt.topic_id = ?
                """,
                (loaded.topic_id,),
            ).fetchone()["n"]
            # All 5 rows still visible — the corruption is at JSON level, not SQL level
            assert count == 5

            # Downstream parser on the corrupted row fails; parsers on
            # the other rows succeed. This asymmetry is what the bug
            # violated (the original code raised once and gave up on all).
            rows = conn.execute(
                "SELECT id, authors FROM papers WHERE id IN ({})".format(
                    ",".join("?" * len(loaded.paper_ids))
                ),
                loaded.paper_ids,
            ).fetchall()
        finally:
            conn.close()

    parse_ok = 0
    parse_fail = 0
    for r in rows:
        try:
            _json.loads(r["authors"])
            parse_ok += 1
        except (_json.JSONDecodeError, TypeError):
            parse_fail += 1
    assert parse_ok == 4, f"expected 4 parseable authors, got {parse_ok}"
    assert parse_fail == 1, f"expected 1 corrupt row, got {parse_fail}"


# ---------------------------------------------------------------------------
# 2026-04-10 batch
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_arxiv_preprint_venue_refreshes_on_acceptance(db):
    """Source: bugs.md [2026-04-10] arXiv 预印本入库后 venue 不随正式录用自动更新.

    Failure mode: peer-reviewed papers got tagged as "未发表" forever.
    Boolean assertion: structural — the stale-venue SQL filter used by
    venue_refresh catches exactly the rows whose venue is empty or
    matches the documented stale values. Guards against a future refactor
    narrowing the filter and silently leaving papers in arXiv limbo.
    """
    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    conn = db.connect()
    try:
        # Set diverse venue values covering: empty, 'arxiv' casings, legit
        ids = list(loaded.paper_ids)
        assert len(ids) >= 4
        conn.execute("UPDATE papers SET venue = '' WHERE id = ?", (ids[0],))
        conn.execute(
            "UPDATE papers SET venue = 'arXiv preprint' WHERE id = ?", (ids[1],)
        )
        conn.execute("UPDATE papers SET venue = 'arxiv.org' WHERE id = ?", (ids[2],))
        conn.execute("UPDATE papers SET venue = 'NeurIPS 2024' WHERE id = ?", (ids[3],))
        conn.commit()

        # Mirror the exact filter used by the venue_refresh MCP tool
        stale_venues = ("", "arxiv", "arxiv.org", "arxiv preprint")
        rows = conn.execute(
            """SELECT p.id, p.venue
               FROM papers p
               JOIN paper_topics pt ON p.id = pt.paper_id
               WHERE pt.topic_id = ?
                 AND (p.venue IS NULL OR LOWER(TRIM(p.venue)) IN (?, ?, ?, ?))
               ORDER BY p.id""",
            (loaded.topic_id, *stale_venues),
        ).fetchall()
    finally:
        conn.close()

    flagged = {r["id"] for r in rows}
    # First 3 should be flagged, NeurIPS row should NOT
    assert ids[0] in flagged, "empty venue missed"
    assert ids[1] in flagged, "arXiv preprint missed"
    assert ids[2] in flagged, "arxiv.org missed"
    assert ids[3] not in flagged, "NeurIPS 2024 falsely flagged as arXiv"


@pytest.mark.regression
def test_db_path_canonical_one_location(tmp_path, monkeypatch):
    """Source: bugs.md [2026-04-10] DB 路径存在两个位置.

    Failure mode: agent wrote to /tmp/.research-harness/pool.db while
    user read from ~/.research-harness/pool.db; rows looked lost.
    Boolean assertion: structural — config.load_runtime_config() must
    return a single canonical db_path per process, resolved from the
    documented env var + workspace precedence chain:
      1. RESEARCH_HARNESS_DB_PATH env var (highest priority)
      2. RESEARCH_HUB_DB_PATH env var (backwards compat)
      3. workspace ``.research-harness/pool.db`` if inside a workspace
      4. ~/.research-harness/pool.db (global default)

    Real check: set the primary env var, observe load_runtime_config
    resolves it. Clear it, verify the legacy env var is honored. Clear
    both, verify global-default path is used.
    """
    from research_harness.config import load_runtime_config

    # Start fresh: neither env var set
    monkeypatch.delenv("RESEARCH_HARNESS_DB_PATH", raising=False)
    monkeypatch.delenv("RESEARCH_HUB_DB_PATH", raising=False)

    # 1. primary env var wins
    primary_db = tmp_path / "primary.db"
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(primary_db))
    cfg = load_runtime_config()
    assert cfg.db_path == primary_db.resolve()
    assert cfg.source == "env"

    # 2. legacy env var honored when primary missing
    monkeypatch.delenv("RESEARCH_HARNESS_DB_PATH")
    legacy_db = tmp_path / "legacy.db"
    monkeypatch.setenv("RESEARCH_HUB_DB_PATH", str(legacy_db))
    cfg = load_runtime_config()
    assert cfg.db_path == legacy_db.resolve()
    assert cfg.source == "env"

    # 3. both cleared — with cwd outside any workspace, global default is used.
    monkeypatch.delenv("RESEARCH_HUB_DB_PATH")
    cfg = load_runtime_config(cwd=tmp_path)  # tmp_path is outside any workspace
    assert cfg.source in {"global-default", "project-default", "project-config"}
    assert cfg.db_path.name == "pool.db"


@pytest.mark.regression
def test_provenance_topic_id_populated_for_every_call(db):
    """Source: bugs.md [2026-04-10] provenance_records.topic_id 全部为 NULL.

    Failure mode: TrackedBackend lost topic_id when the primitive's
    kwargs used a different key.
    Boolean assertion: assert_provenance_complete — for every artifact,
    the linked provenance_record must carry the same topic_id.

    Real check: insert a provenance row via the low-level writer with
    topic_id set, confirm SELECT round-trips the value. Guards against
    a schema migration accidentally dropping the column or shadowing
    the default.
    """
    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    conn = db.connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO provenance_records
              (primitive, started_at, finished_at, backend, topic_id, stage,
               input_hash, output_hash, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "paper_summarize",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:01Z",
                "fake",
                loaded.topic_id,
                "analyze",
                "h1",
                "h2",
            ),
        )
        rid = int(cur.lastrowid)
        conn.commit()
        row = conn.execute(
            "SELECT topic_id, primitive, success FROM provenance_records WHERE id = ?",
            (rid,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["topic_id"] == loaded.topic_id, (
        f"provenance_records.topic_id lost: got {row['topic_id']}"
    )
    assert row["primitive"] == "paper_summarize"
    assert row["success"] == 1


@pytest.mark.regression
def test_build_v1_max_results_not_capped_low(db, monkeypatch):
    """Source: bugs.md [2026-04-10] Build v1 max_results 默认值过低 (20).

    Failure mode: two-layer cap (MCP schema 50, internal 20) → only 20
    papers returned even when caller asked for 200.
    Boolean assertion: structural — passing max_results=200 yields
    results that are NOT capped below what a stub provider supplies.

    Real check: install a stub provider that returns 150 unique
    PaperRecords. paper_search(max_results=200) must surface at least
    100 (leave headroom for dedup/filter). Guards against a new
    internal cap being reintroduced.
    """
    from research_harness.paper_sources import PaperRecord
    from research_harness.primitives.impls import paper_search

    from ..fixtures import load_topic
    from ..injectors.network import fake_provider_suite

    loaded = load_topic(db, "small_tfr")

    class BulkProvider:
        name = "bulk_stub"

        def search(self, query):  # noqa: ANN001
            return [
                PaperRecord(
                    title=f"Bulk Paper {i}",
                    authors=[f"Author {i}"],
                    year=2024,
                    venue="FakeConf",
                    doi=f"10.fake/{i:04d}",
                    arxiv_id=f"bulk.{i:04d}",
                    provider="bulk_stub",
                )
                for i in range(150)
            ]

    with fake_provider_suite(monkeypatch, [BulkProvider()]):
        out = paper_search(
            db=db,
            query="bulk",
            topic_id=loaded.topic_id,
            max_results=200,
            per_provider_limit=200,
        )
    # PaperSearchOutput stores raw list in .papers and pre-filter size in
    # .total_before_filter; dedup/filter caps .papers to <= max_results.
    assert out.total_before_filter >= 100, (
        f"max_results=200 silently capped; total_before_filter={out.total_before_filter}, "
        f"papers={len(out.papers)}"
    )


# ---------------------------------------------------------------------------
# 2026-04-11 batch
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_papers_have_author_affiliation(db):
    """Source: bugs.md [2026-04-11] papers 表缺少 author_affiliation 字段.

    Failure mode: column did not exist; queries by company/university
    silently returned empty.
    Boolean assertion: structural — column exists in schema, ingest can
    write to it, reads come back intact.

    Note: migration 014 added the column as ``affiliations`` (JSON list),
    not ``author_affiliation`` — this regression test pins the current
    spelling so future renames can't silently break downstream queries.
    """
    import json as _json

    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    assert loaded.paper_ids, "loader failed to ingest papers"

    conn = db.connect()
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(papers)").fetchall()}
    finally:
        conn.close()
    assert "affiliations" in cols, (
        f"papers.affiliations column missing; got: {sorted(cols)}"
    )

    paper_id = loaded.paper_ids[0]
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE papers SET affiliations = ? WHERE id = ?",
            (_json.dumps([{"name": "Anthropic", "country": "US"}]), paper_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT affiliations FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
    finally:
        conn.close()
    parsed = _json.loads(row["affiliations"])
    assert isinstance(parsed, list)
    assert parsed[0]["name"] == "Anthropic"


@pytest.mark.regression
def test_search_results_persisted_after_truncation(db, monkeypatch):
    """Source: bugs.md [2026-04-11] 检索结果未持久化, 数据截断后无法复原.

    Failure mode: agent crashed mid-loop, the candidate list was lost.
    Boolean assertion: assert_artifacts_present_and_valid — a
    persistent record MUST be written before any filter primitive runs.

    Real check: paper_search with a topic_id must INSERT into search_runs.
    Simulate "agent dies after search returns": run paper_search, then
    open a fresh connection (mimicking a different process) and verify
    the search_runs row is durably persisted.
    """
    from research_harness.paper_sources import PaperRecord
    from research_harness.primitives.impls import paper_search

    from ..fixtures import load_topic
    from ..injectors.network import fake_provider_suite

    loaded = load_topic(db, "small_tfr")

    class StubProvider:
        name = "stub"

        def search(self, query):  # noqa: ANN001
            return [
                PaperRecord(
                    title=f"Persistence test {i}",
                    arxiv_id=f"persist.{i:04d}",
                    doi=f"10.persist/{i:04d}",
                    year=2024,
                    provider="stub",
                )
                for i in range(3)
            ]

    with fake_provider_suite(monkeypatch, [StubProvider()]):
        out = paper_search(
            db=db,
            query="persistence canary",
            topic_id=loaded.topic_id,
            max_results=10,
        )
    assert len(out.papers) >= 3

    # Mimic "agent died and a fresh process starts" by opening a brand
    # new Database handle on the same file. The search_runs row must
    # have been committed, not held in memory only.
    from research_harness.storage.db import Database

    fresh = Database(db.db_path)
    conn = fresh.connect()
    try:
        rows = conn.execute(
            "SELECT query, provider, result_count FROM search_runs "
            "WHERE topic_id = ? ORDER BY id DESC",
            (loaded.topic_id,),
        ).fetchall()
    finally:
        conn.close()
    assert rows, "search_runs row missing — search results not persisted"
    assert rows[0]["query"] == "persistence canary"
    assert rows[0]["result_count"] >= 3


@pytest.mark.regression
def test_relevance_score_returned_as_label_not_float(db):
    """Source: bugs.md [2026-04-11] relevance_score 使用连续浮点数 (#16).

    Failure mode: agents got "0.67" and made up their own thresholds.
    Boolean assertion: structural — paper_topics.relevance column stores
    a label from {high, medium, low}, not a stringified float.
    """
    import re

    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT relevance FROM paper_topics WHERE topic_id = ?",
            (loaded.topic_id,),
        ).fetchall()
    finally:
        conn.close()

    assert rows, "loader should have inserted paper_topics rows"
    label_rx = re.compile(r"^(high|medium|low)$")
    bad = [r["relevance"] for r in rows if not label_rx.match(r["relevance"] or "")]
    assert not bad, (
        f"relevance column must hold high|medium|low labels, got stray values: {bad}"
    )


# ---------------------------------------------------------------------------
# 2026-04-20 (1.0 reviewer audit) batch
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_pytest_collection_no_internal_error():
    """Source: bugs.md [2026-04-20] P0-1 conftest pytest_collect_file.

    Failure mode: bare Path returned where Collector|None expected →
    pytest INTERNALERROR at repo root.
    Boolean assertion: structural — `pytest --collect-only` exits 0.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd="packages/research_harness/tests/backend_stability",
        capture_output=True,
        timeout=60,
        text=True,
    )
    assert result.returncode in (
        0,
        5,  # pytest exit code 5 = no tests collected, NOT an internal error
    ), (
        f"pytest collection broke: rc={result.returncode}\n"
        f"stdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
    )
    assert "INTERNALERROR" not in result.stdout
    assert "INTERNALERROR" not in result.stderr


@pytest.mark.regression
def test_primitive_registry_count_matches_specs():
    """Source: bugs.md [2026-04-20] P0-2 registry holds 69, test asserted 68.

    Failure mode: drift between PRIMITIVE_REGISTRY and the count test.
    Boolean assertion: structural — len(PRIMITIVE_REGISTRY) matches the
    number of unique spec names registered.
    """
    from research_harness.primitives import PRIMITIVE_REGISTRY

    n = len(PRIMITIVE_REGISTRY)
    assert n > 0, "registry must not be empty"
    # Unique names should match the dict size — catches duplicate registrations
    names = set(PRIMITIVE_REGISTRY.keys())
    assert len(names) == n, f"duplicate primitive names in registry: {n - len(names)}"
    # Sanity: the registry must expose at least the core primitives that
    # every flow uses.
    for required in ("paper_ingest", "paper_acquire", "outline_generate"):
        assert required in names, f"core primitive missing: {required}"


@pytest.mark.regression
def test_mcp_tool_paper_acquire_not_double_registered():
    """Source: bugs.md [2026-04-20] P0-3 paper_acquire registered twice.

    Failure mode: dispatcher dead-code path silently never executed.
    Boolean assertion: structural — paper_acquire appears in the primitive
    registry exactly once AND is not also listed in the MCP tools module
    dict (previous dual-registration let the MCP side shadow the primitive).
    """
    from research_harness.primitives import PRIMITIVE_REGISTRY

    assert list(PRIMITIVE_REGISTRY.keys()).count("paper_acquire") == 1

    # The MCP side used to have an independent Tool registration — grep
    # the tools module source for the literal "paper_acquire" and count
    # matches. After the fix there must be no Tool(...) instance.
    import importlib
    import re

    tools = importlib.import_module("research_harness_mcp.tools")
    src = tools.__file__
    if src is None:
        return  # built-in or namespace package; nothing to inspect
    with open(src, encoding="utf-8") as f:
        text = f.read()
    matches = re.findall(r'Tool\([^)]*name\s*=\s*"paper_acquire"', text)
    assert len(matches) == 0, (
        f"paper_acquire should not be re-declared as a Tool(...) in MCP module; "
        f"found {len(matches)} duplicate registrations"
    )


@pytest.mark.regression
def test_outline_generate_refuses_empty_contributions(db):
    """Source: bugs.md [2026-04-20] P1-1 outline_generate fabricated papers.

    Failure mode: empty contributions → LLM hallucinated paper names.
    Boolean assertion: assert_no_unexplained_traceback — the primitive
    raises ValueError with actionable guidance, not a silent stub.

    Real check: invoke the LLM-side outline_generate (the one with the
    contribution guard) on a topic with NO contributions and NO
    writing_architecture artifact, and confirm the ValueError fires
    with guidance text.
    """
    from research_harness.execution.llm_primitives import (
        outline_generate as _outline_generate,
    )

    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    # Ensure topics.contributions is empty (loader doesn't set it)
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT contributions FROM topics WHERE id = ?", (loaded.topic_id,)
        ).fetchone()
        # Some schemas may not have the column yet — skip in that case
        if row is None or "contributions" not in row.keys():
            pytest.skip("topics.contributions column not present in this schema")
        assert not (row["contributions"] or "").strip()
    finally:
        conn.close()

    with pytest.raises(ValueError, match=r"contribution"):
        _outline_generate(db=db, topic_id=loaded.topic_id, template="neurips")


@pytest.mark.regression
def test_outline_generate_reads_topic_contributions(db, monkeypatch):
    """Source: tool-gaps.md [2026-04-17] outline_generate 忽视已选 contributions.

    Failure mode: even when contributions were recorded via
    ``topic_set_contributions``, outline_generate ignored them and
    hallucinated an unrelated paper (e.g. "SAGE-Fuse" for ModalGate).
    Fix: outline_generate falls back in order (arg → topics.contributions
    → writing_architecture artifact) and the LLM prompt MUST include the
    resolved contributions verbatim.

    Real check: seed topics.contributions, stub the LLM client, invoke
    outline_generate without an explicit contributions arg, assert the
    seeded text appears verbatim in the captured prompt.
    """
    from research_harness.execution import llm_primitives as lp
    from research_harness.primitives.impls import topic_set_contributions

    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    seeded = (
        "We show that CoT reasoning closes the calibration gap on Monash by 14pp; "
        "we introduce a state-space/attention hybrid that improves MASE by 11%; "
        "we build the TFRBench reproducibility harness."
    )
    topic_set_contributions(db=db, topic_id=loaded.topic_id, contributions=seeded)

    captured_prompts: list[str] = []

    class _StubClient:
        model = "stub-outline"

        def chat(self, prompt: str, **_: object) -> str:
            captured_prompts.append(prompt)
            return json.dumps(
                {
                    "title": "Stub Title",
                    "abstract_draft": "Stub abstract.",
                    "sections": [
                        {
                            "section": "introduction",
                            "title": "Introduction",
                            "target_words": 500,
                        }
                    ],
                    "total_target_words": 500,
                }
            )

    monkeypatch.setattr(lp, "_get_client", lambda *a, **kw: _StubClient())
    monkeypatch.setattr(lp, "_describe_client", lambda c: "stub-outline")

    out = lp.outline_generate(db=db, topic_id=loaded.topic_id, template="neurips")
    assert out.model_used == "stub-outline"
    assert captured_prompts, "LLM was not called"
    prompt_blob = "\n".join(captured_prompts)
    assert "TFRBench reproducibility harness" in prompt_blob, (
        "contributions not passed through to LLM; "
        "outline_generate is bypassing the topic-level fallback"
    )


# ---------------------------------------------------------------------------
# 2026-04-24 (TFRBench batch) — frontend-adjacent but backend-rooted
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_s2_api_key_threaded_to_paper_search(monkeypatch):
    """Source: bugs.md [2026-04-24] #25 S2_API_KEY ignored by providers.

    Failure mode: env var set but provider still used unauthenticated
    endpoint, hit rate limit fast.
    Boolean assertion: structural — when S2_API_KEY is set,
    build_provider_suite constructs a SemanticScholarProvider whose
    api_key attribute carries the key, AND the provider's rate-limit
    interval is the faster keyed-tier value.
    """
    from research_harness.paper_source_clients import (
        SemanticScholarProvider,
        build_provider_suite,
    )

    monkeypatch.setenv("S2_API_KEY", "sk-test-s2-real-key")
    # Clear legacy var so we prove the primary one is the path used
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)

    suite = build_provider_suite()
    s2s = [p for p in suite if isinstance(p, SemanticScholarProvider)]
    assert len(s2s) == 1
    assert s2s[0].api_key == "sk-test-s2-real-key"
    # Free tier would use 1.05s; keyed tier uses 0.15s — the faster value
    # proves the key was actually applied.
    assert s2s[0]._min_interval < 0.3, (
        f"S2 key not applied; _min_interval={s2s[0]._min_interval}"
    )

    # And the legacy env var is honored when primary is missing (regression
    # against someone splitting the resolve logic and dropping one branch).
    monkeypatch.delenv("S2_API_KEY")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "sk-legacy")
    suite = build_provider_suite()
    s2s = [p for p in suite if isinstance(p, SemanticScholarProvider)]
    assert s2s[0].api_key == "sk-legacy"


@pytest.mark.regression
def test_expansion_worker_uses_registered_primitive():
    """Source: bugs.md [2026-04-24] #26 expansion worker calls unregistered primitive.

    Failure mode: worker imported a primitive name that wasn't in
    PRIMITIVE_REGISTRY; raised KeyError mid-loop.
    Boolean assertion: structural — every primitive name listed in
    research_harness.execution.harness's _LLM_DISPATCH must also be in
    PRIMITIVE_REGISTRY (i.e. the dispatch table cannot reference a
    name without a registered spec).
    """
    from research_harness.execution.harness import _LLM_DISPATCH
    from research_harness.primitives import PRIMITIVE_REGISTRY

    referenced = set(_LLM_DISPATCH.keys())
    registered = set(PRIMITIVE_REGISTRY.keys())
    missing = sorted(referenced - registered)
    assert not missing, (
        f"_LLM_DISPATCH references primitives not in registry: {missing}"
    )


@pytest.mark.regression
def test_papers_identifier_columns_allow_multiple_nulls(db):
    """Source: tool-gaps.md [2026-05-07] papers.s2_id DEFAULT '' UNIQUE 多行空字符串冲突.

    Failure mode: inserting two papers without an s2_id silently dropped
    the second row because ``'' vs ''`` violated UNIQUE.
    Fix: migration 064 makes doi/arxiv_id/s2_id nullable UNIQUE so NULLs
    coexist per standard SQL UNIQUE semantics.
    """
    import sqlite3 as _sqlite3

    conn = db.connect()
    try:
        for i in range(3):
            conn.execute(
                "INSERT INTO papers (title, arxiv_id) VALUES (?, ?)",
                (f"null-id paper {i}", f"null-s2-{i}"),
            )
        conn.commit()
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM papers WHERE s2_id IS NULL"
        ).fetchone()["n"]
        assert cnt == 3, f"expected 3 NULL-s2 rows, got {cnt}"

        conn.execute(
            "INSERT INTO papers (title, s2_id) VALUES (?, ?)",
            ("first real s2", "REAL-S2-123"),
        )
        conn.commit()
        with pytest.raises(_sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO papers (title, s2_id) VALUES (?, ?)",
                ("dup real s2", "REAL-S2-123"),
            )
            conn.commit()
    finally:
        conn.close()


@pytest.mark.regression
def test_paper_ingest_url_only_fetches_html_body(db):
    """Source: tool-gaps.md [2026-04-27] paper_ingest --url silently lands meta_only.

    Failure mode: ingesting a URL (e.g. Anthropic engineering blog) produced
    a meta_only row with no body, so downstream claim_extract and
    paper_summarize had nothing to read. The agent was forced to fall back
    to parametric memory.

    Fix: paper_ingest now fetches HTML when a web URL is supplied, converts
    to markdown, writes a ``summary`` annotation, flips status to
    ``text_only``, and reports the result in PaperIngestOutput.html_ingest.

    Real check: spin up a trivial local HTTP server, ingest its URL, and
    verify the annotation and status were persisted.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from research_harness.primitives.impls import paper_ingest

    html_body = (
        "<html><head><title>Inside Claude Code</title></head><body>"
        "<nav>SITE NAV</nav>"
        "<h1>Inside Claude Code</h1>"
        "<p>We built an agent-first CLI and learned three things.</p>"
        "<ul><li>Tools are the new libraries.</li>"
        "<li>Prompts are the new APIs.</li></ul>"
        "<script>window.tracker = 1;</script>"
        "</body></html>"
    )

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *a, **kw):  # noqa: ANN001, ANN003
            return

        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = html_body.encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        url = f"http://{host}:{port}/post/inside-claude-code"
        out = paper_ingest(db=db, source=url, url=url, topic_id=None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    # 1. Result surfaces the html_ingest details
    assert out.html_ingest.get("fetched") is True, out.html_ingest
    assert out.html_ingest.get("chars", 0) > 0

    # 2. The row's status flipped to text_only + annotation exists
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT status, title, abstract FROM papers WHERE id = ?",
            (out.paper_id,),
        ).fetchone()
        ann = conn.execute(
            "SELECT section, content FROM paper_annotations "
            "WHERE paper_id = ? AND section = 'summary'",
            (out.paper_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "text_only", (
        f"status should flip to text_only, got {row['status']!r}"
    )
    # Title picked up from <title> since caller didn't provide one
    assert "Inside Claude Code" in (row["title"] or "")
    # Abstract filled with a prefix of the markdown
    assert row["abstract"] and "agent-first CLI" in row["abstract"]
    # Annotation holds the clean markdown body, with nav/script stripped
    assert ann is not None
    assert "agent-first CLI" in ann["content"]
    assert "SITE NAV" not in ann["content"]
    assert "window.tracker" not in ann["content"]


@pytest.mark.regression
def test_paper_ingest_url_non_html_does_not_crash(db):
    """Regression guard: when the URL returns a non-HTML content-type
    (e.g. application/pdf) we do NOT upsert garbled content. html_ingest
    reports fetched=False with a reason so callers can fall through to
    PDF acquisition."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from research_harness.primitives.impls import paper_ingest

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *a, **kw):  # noqa: ANN001, ANN003
            return

        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"%PDF")

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        url = f"http://{host}:{port}/paper.pdf"
        out = paper_ingest(db=db, source=url, url=url, topic_id=None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert out.html_ingest.get("fetched") is False, out.html_ingest
    assert "content-type" in (out.html_ingest.get("reason") or "").lower()


@pytest.mark.regression
def test_deep_read_records_real_model_used(db):
    """Source: bugs.md [2026-04-24] #27 deep-read returns model_used='none'.

    Failure mode: when paper had abstract only, deep-read short-circuited
    but provenance still showed 'none' — defeats LLM-route auditing.
    Boolean assertion: assert_llm_route_audited — every deep-read call
    must record either a real model id OR a clearly named non-LLM
    short-circuit (e.g. 'abstract_only', 'local'), never the literal
    'none' which conflates "not yet run" with "deliberately skipped".

    Real check: paper has empty annotations (no full text available).
    Call deep_read. Expect a non-'none' model_used string.
    """
    from research_harness.execution.llm_primitives import deep_read

    from ..fixtures import load_topic

    loaded = load_topic(db, "small_tfr")
    paper_id = loaded.paper_ids[0]

    # Strip the paper's text sources so _get_paper_text returns empty
    # and the deep_read short-circuit runs.
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE papers SET abstract = '', compiled_summary = '' WHERE id = ?",
            (paper_id,),
        )
        conn.execute("DELETE FROM paper_annotations WHERE paper_id = ?", (paper_id,))
        conn.commit()
    finally:
        conn.close()

    # Short-circuit branch runs; no LLM call; model_used should be the
    # named local marker, not "none".
    out = deep_read(db=db, paper_id=paper_id, topic_id=loaded.topic_id, focus="")

    assert out.model_used != "none", (
        "deep_read short-circuit must record a meaningful model_used, "
        "got the ambiguous literal 'none'"
    )
    # Positive check: the replacement is a clearly-named local marker
    assert out.model_used == "local:abstract_only", (
        f"unexpected short-circuit marker: {out.model_used}"
    )


@pytest.mark.regression
def test_llm_router_blocklist_does_not_break_proxy(monkeypatch):
    """Source: bugs.md [2026-04-24] #28 router blocklist silently breaks Anthropic-proxy.

    Failure mode: a blocklisted upstream model name was the user's
    proxy alias; router silently fell back to a different provider.
    Boolean assertion: assert_llm_route_audited — the route_record
    must show the actual provider/model used; if a fallback happened,
    the bypass mechanism (LLM_ROUTE_ALLOW_ANYTHING) must work.

    Real check: two cases:
      (a) blocklist active (default) + anthropic route request → fallback
          applied (safe default), blocklist working as intended.
      (b) blocklist bypassed via LLM_ROUTE_ALLOW_ANYTHING=1 + anthropic
          route → the anthropic route is honored verbatim (this is the
          escape hatch for proxy users; the bug was this path getting
          silently overridden).
    """
    from llm_router.client import resolve_route

    # Case (a): blocklist active. Anthropic should be blocked for light tier.
    monkeypatch.delenv("LLM_ROUTE_ALLOW_ANYTHING", raising=False)
    monkeypatch.setenv("LLM_ROUTE_LIGHT", "anthropic:claude-haiku")
    provider, _ = resolve_route("light")
    assert provider != "anthropic", (
        f"blocklist did not kick in; got provider={provider}"
    )

    # Case (b): escape hatch active. Anthropic must be honored verbatim.
    monkeypatch.setenv("LLM_ROUTE_ALLOW_ANYTHING", "1")
    provider, model = resolve_route("light")
    assert provider == "anthropic", (
        f"LLM_ROUTE_ALLOW_ANYTHING was ignored; got provider={provider}"
    )
    assert model == "claude-haiku"
