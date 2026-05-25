---
name: rh-codex-verify
description: Verify Codex workflow/config/skill changes in Research Harness. Trigger on phrases like "rh-codex-verify", "/rh-codex-verify", "run codex-check", "验证 Codex 配置", or before handing off Codex-authored changes.
---

# RH Codex Verify

Use this skill after editing Codex configuration, Research Harness skills, workflow docs, or validation scripts.

## Fast Gate

Run:

```bash
scripts/codex-check.sh --quick
```

This validates project-scoped Codex TOML, skill frontmatter, manifest coverage, repo skill discovery symlink, and core RH workflow files.

## Targeted Gates

- Python-facing changes: `scripts/codex-check.sh --python`
- Web/frontend changes: `scripts/codex-check.sh --web`
- MCP wrapper/config changes: `scripts/codex-check.sh --mcp`
- PR-ready local gate: `scripts/codex-check.sh --full`

## Report

Return:

- command(s) run
- pass/fail status
- skipped checks and why
- remaining risks
- exact files changed by the verification work, if any
