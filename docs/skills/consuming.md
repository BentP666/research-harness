# Consuming RH Skills From Your Agent

This guide is for **agent authors** — you ship an agent (Claude Code,
Codex, OpenClaw, or something new) and you want users of your agent to pick
up Research Harness skills automatically when they enter an RH-enabled
repo.

## The contract

You declare three things in a single file, `.rh-agent.toml`, that lives at
the root of the repo where your agent runs:

| Field                   | What it tells RH                                                |
|-------------------------|-----------------------------------------------------------------|
| `[agent].name`          | Free-form name (used in logs, never matched on)                 |
| `[skills].install_path` | Where your agent loads skills from                              |
| `[skills].format`       | Which SKILL.md format your agent understands (`claude-skill-md` today) |
| `[skills].strategy`     | `symlink` / `copy` / `mcp-runtime`                              |

That's it. RH doesn't need a code change to support a new agent. If the
agent's `install_path` is correct and its loader understands `SKILL.md`, it
works.

## Minimal example

```toml
# .rh-agent.toml
[agent]
name = "my-agent"

[skills]
install_path = "~/.my-agent/skills"
strategy     = "symlink"
```

Then a user clones an RH repo, runs `./setup.sh` (or `rh skill install`),
and your agent finds the skills.

## Choosing a strategy

| Strategy       | Use when                                                                |
|----------------|-------------------------------------------------------------------------|
| `symlink`      | Local development. Updates to RH flow automatically.                    |
| `copy`         | Your loader doesn't follow symlinks, or in CI/sandbox/Docker layers.    |
| `mcp-runtime`  | Your agent has an MCP client; skip filesystem entirely. Call `skill_list` / `skill_get` at runtime. |

## Filtering skills

Some agents specialize. A writing-only assistant doesn't need
`literature-search`. Use `[skills.include]` or `[skills.exclude]`:

```toml
[skills.include]
only = ["paper-writing", "section-drafting"]

[skills.exclude]
names = ["task-taxonomy"]
```

## Naming transforms

If your agent enforces a naming convention (e.g. snake_case skill folders),
declare it once:

```toml
[skills]
naming = "snake"   # paper-writing -> paper_writing on disk
```

Supported: `as-is` (default), `kebab`, `snake`.

## Discovery order

`rh skill install` (no `--target`, no `--agent`) looks for `.rh-agent.toml`
in this order:

1. `$RH_AGENT_CONFIG` env var (if set, must point to an existing file)
2. `./.rh-agent.toml` in the current directory
3. Walk up to the first `.git` directory, looking for `.rh-agent.toml`
4. `~/.config/research-harness/agent.toml` (user-global default)

If nothing is found, the command exits with a clear error. **It never
guesses by sniffing for `.claude/` or `.codex/` directories** — that
brittleness is exactly what this design avoids.

## When to ship a profile vs use `--target`

* Ship a real `.rh-agent.toml` with your agent if you want users to get
  skills automatically.
* Tell users to use `--target PATH` for one-off installs or quick
  experimentation.
* Keep `agent-profiles/<name>.toml` in your own repo as a template — users
  copy it to `.rh-agent.toml` and customize.

## Examples shipped with RH

See [`skills/agent-profiles/`](../../skills/agent-profiles/):

* `claude-code.toml` — symlink into `~/.claude/skills`
* `codex.toml`       — symlink into `~/.codex/skills`
* `openclaw.toml`    — copy into `${OPENCLAW_HOME}/skills`, with skill filter
* `mcp-runtime.toml` — no filesystem install
