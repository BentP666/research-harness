# Authoring a Skill

A skill is a folder under [`skills/`](../../skills/) with a single required
file: `SKILL.md`. The format is the same one Claude Code and Codex
already understand, so any compliant agent can consume it.

## Minimum viable skill

```
skills/my-skill/
└── SKILL.md
```

```markdown
---
name: my-skill
description: |
  One-line summary of what this skill does. Trigger on phrases like
  "my-skill", "/my-skill", or "do the thing".
---

# My Skill

Body — any Markdown the agent should follow when this skill is selected.
```

## Front-matter fields

| Key             | Required | Notes                                                    |
|-----------------|----------|----------------------------------------------------------|
| `name`          | yes      | kebab-case; must match the directory name                |
| `description`   | yes      | One-line summary; embed natural-language triggers here   |
| `category`      | no       | Free-form group label, e.g. `writing`, `discovery`       |
| `version`       | no       | Skill version, semver recommended                        |
| `allowed-tools` | no       | List of tool names the agent should restrict to          |

Anything else is preserved under `extras` in the manifest.

## Triggers

Triggers are not a separate field — they live in the `description`. Convention
is to write a sentence like:

> Trigger on phrases like "X", "/X", "中文 X", or equivalent requests.

Agent runtimes match user messages against the description text, so explicit
trigger lists improve recall.

## Multi-track skills

If a skill has variants (like `paper-writing` covering 6 different paper
types), put each track in `tracks/<name>.md`:

```
skills/paper-writing/
├── SKILL.md                ← entrypoint, picks track by user intent
└── tracks/
    ├── original-research.md
    ├── survey-review.md
    └── ...
```

The manifest auto-detects the tracks subdirectory and lists them under the
skill's `tracks` field. The MCP `skill_get` tool accepts a `track` parameter
to fetch a specific variant.

## Supporting files

Anything else in the skill folder — `references/`, examples, JSON
templates — is shipped along with the skill via symlink/copy. Keep it light.

## Conventions in this repo

* All shipped skills are vendor-neutral; don't bake "Claude" or "Codex" into
  the body unless behavior really differs.
* Reference RH primitives by their MCP tool name (e.g.
  `mcp__research-harness__paper_search`), not by CLI command.
* When a skill produces an artifact, mention `orchestrator_record_artifact`
  so it shows up in provenance.

## Local iteration

```bash
# Edit a skill, then:
rh skill index            # regenerate skills/manifest.json
rh skill list             # confirm it shows up
rh skill verify           # confirm install is in sync
```

If you symlinked the skill in (the default), the agent picks up the change
on its next session automatically.
