"""Smoke tests for the skill manifest, agent config, and install engine.

These run against the actual ``skills/`` directory shipped in this repo, so
they double as a regression check that the manifest stays parseable and that
``paper-writing`` (and its tracks) is always discoverable.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Locate the repo root (works whether tests run from worktree or main)
HERE = Path(__file__).resolve()
REPO_ROOT = next(
    p for p in HERE.parents if (p / "skills").is_dir() and (p / "setup.sh").is_file()
)


def test_build_manifest_finds_all_shipped_skills() -> None:
    from research_harness.skill import build_manifest

    manifest = build_manifest(REPO_ROOT)
    names = manifest.names()
    assert len(names) >= 14, f"expected >= 14 skills, got {names}"
    # paper-writing is the trigger skill that started this whole subsystem
    assert "paper-writing" in names
    pw = manifest.get("paper-writing")
    assert pw is not None
    assert "survey-review" in pw.tracks
    assert "original-research" in pw.tracks


def test_write_then_load_manifest_roundtrip(tmp_path: Path) -> None:
    from research_harness.skill import build_manifest, load_manifest, write_manifest

    fake = tmp_path / "repo"
    (fake / "skills" / "alpha").mkdir(parents=True)
    (fake / "skills" / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: just a test\n---\n# alpha\n"
    )

    manifest = build_manifest(fake)
    assert manifest.names() == ["alpha"]
    write_manifest(manifest, fake)
    loaded = load_manifest(fake)
    assert loaded.names() == ["alpha"]
    assert loaded.skills[0].description == "just a test"


def test_install_symlink_strategy_creates_links(tmp_path: Path) -> None:
    from research_harness.skill import (
        build_manifest,
        install,
        make_explicit_config,
        verify,
    )

    target = tmp_path / "claude-skills"
    config = make_explicit_config(target, strategy="symlink")
    manifest = build_manifest(REPO_ROOT)

    report = install(manifest, config, REPO_ROOT)

    assert all(r.action == "created" for r in report.results)
    pw = target / "paper-writing"
    assert pw.is_symlink()
    assert (pw / "SKILL.md").is_file()
    assert (pw / "tracks" / "survey-review.md").is_file()

    # idempotency
    report2 = install(manifest, config, REPO_ROOT)
    assert all(r.action == "skipped" for r in report2.results)

    # verify reports OK on a clean install
    vreport = verify(manifest, config, REPO_ROOT)
    assert all(r.action == "ok" for r in vreport.results)


def test_install_copy_strategy_writes_files(tmp_path: Path) -> None:
    from research_harness.skill import build_manifest, install, make_explicit_config

    target = tmp_path / "skills-copy"
    config = make_explicit_config(target, strategy="copy")
    manifest = build_manifest(REPO_ROOT)

    install(manifest, config, REPO_ROOT, only=["paper-writing"])
    pw = target / "paper-writing"
    assert pw.is_dir()
    assert not pw.is_symlink()
    assert (pw / "SKILL.md").is_file()
    assert (pw / "tracks" / "survey-review.md").is_file()


def test_agent_config_loader(tmp_path: Path) -> None:
    from research_harness.skill import load_agent_config

    cfg_text = """
[agent]
name = "test-agent"
version = ">=1.0"

[skills]
install_path = "%s"
strategy = "copy"

[skills.include]
only = ["paper-writing", "literature-search"]
""" % str(tmp_path / "out").replace("\\", "/")

    cfg_path = tmp_path / ".rh-agent.toml"
    cfg_path.write_text(cfg_text)
    config = load_agent_config(cfg_path)
    assert config.agent_name == "test-agent"
    assert config.strategy == "copy"
    assert config.include.only == ["paper-writing", "literature-search"]


def test_mcp_runtime_strategy_writes_nothing(tmp_path: Path) -> None:
    from research_harness.skill import build_manifest, install, make_explicit_config

    target = tmp_path / "should-not-be-created"
    config = make_explicit_config(target, strategy="mcp-runtime")
    manifest = build_manifest(REPO_ROOT)
    report = install(manifest, config, REPO_ROOT)

    assert not target.exists()
    assert all(r.action == "runtime-only" for r in report.results)


def test_mcp_skill_tools() -> None:
    sys.path.insert(0, str(REPO_ROOT / "packages" / "research_harness_mcp"))
    from research_harness_mcp.tools_skill import skill_get, skill_list

    out = skill_list({})
    assert out["schema_version"] == "1.0"
    assert any(s["name"] == "paper-writing" for s in out["skills"])

    pw = skill_get({"name": "paper-writing", "track": "survey-review"})
    assert pw["name"] == "paper-writing"
    assert pw.get("track", {}).get("name") == "survey-review"
    assert "Track B" in pw["track"]["content"]


def test_skill_get_unknown_returns_helpful_error() -> None:
    sys.path.insert(0, str(REPO_ROOT / "packages" / "research_harness_mcp"))
    from research_harness_mcp.tools_skill import skill_get

    out = skill_get({"name": "does-not-exist"})
    assert "error" in out
    assert "available" in out
    assert isinstance(out["available"], list)
