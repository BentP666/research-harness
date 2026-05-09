# Skill Subsystem — Future Improvements

Captured during the 2026-04-27 industry survey. Today's design (`.rh-agent.toml`
self-declaration + `rh skill install` + MCP `skill_list`/`skill_get`) covers
all functional needs and is more vendor-neutral than most projects we
benchmarked. The items below are improvements that would broaden compatibility
or lower the install bar, ranked by ROI.

## Industry comparison (Apr 2026)

Standards / projects we surveyed:

* [Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) —
  open standard, adopted by OpenAI Codex, Cursor, Gemini CLI, Copilot, JetBrains,
  Antigravity (Dec 2025).
* [`anthropics/skills`](https://github.com/anthropics/skills) — official
  marketplace.json + SKILL.md template repo.
* [`agentskills.io`](https://agentskills.io/home) — community registry.
* [MCP Skills Over MCP charter](https://modelcontextprotocol.io/community/skills-over-mcp/charter)
  + [SEP-2076](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2076)
  + [`experimental-ext-skills`](https://github.com/modelcontextprotocol/experimental-ext-skills)
  — proposed first-class MCP primitive for skills.
* [skills.json registry proposal](https://github.com/modelcontextprotocol/registry/discussions/895).
* [`everything-claude-code`](https://github.com/affaan-m/everything-claude-code) —
  multi-agent ECC harness with `install-plan.js`/`install-apply.js`.
* [`TheQtCompanyRnD/agent-skills`](https://github.com/TheQtCompanyRnD/agent-skills) —
  per-platform manifest example (`.claude-plugin/`, `gemini-extension.json`).

What we already do well:

* Agent self-declaration via `.rh-agent.toml` — RH stays vendor-neutral,
  new agents need zero RH change.
* Three install strategies (symlink / copy / mcp-runtime).
* Single `skills/` source of truth (no per-platform parallel manifests).
* MCP runtime fallback (`skill_list` / `skill_get`).

---

## TODO

### 1. Ship `.claude-plugin/marketplace.json` for native `/plugin install` UX

**Why.** Claude Code users can install our skills with the built-in plugin
command without first installing the RH CLI. This is purely additive — keeps
`rh skill install` for everyone else, adds a zero-friction path for the
biggest single audience.

**Sketch.**

```json
// .claude-plugin/marketplace.json
{
  "name": "research-harness",
  "plugins": [
    {
      "name": "rh-skills",
      "description": "Research Harness skill catalog",
      "skills": ["skills/paper-writing", "skills/literature-search", ...]
    }
  ]
}
```

User runs in Claude Code:

```
/plugin install rh-skills@research-harness
```

Effort: ~30 min.

---

### 2. Write `.skill-meta.json` per installed skill

**Why.** `npx skills` and other PMs write a per-skill metadata file at install
time so the tool can detect updates, source, and version skew. Today our
`verify` can only compare contents; with a meta file we can answer "what's
new" and "is my install stale?".

**Sketch.**

```json
// <install-target>/<skill>/.skill-meta.json
{
  "source": "/Users/.../research-harness-oss/skills/paper-writing",
  "source_repo": "research-harness-oss",
  "source_branch": "main",
  "source_commit": "044d1f5",
  "installed_at": "2026-04-27T15:23:00Z",
  "strategy": "symlink",
  "manifest_version": "1.0",
  "skill_version": "1.2.0"
}
```

Add a `rh skill outdated` subcommand that compares meta to current manifest.

Effort: ~30 min.

---

### 3. `.agents/skills/` fallback when no `.rh-agent.toml`

**Why.** `.agents/skills/` has emerged as the de facto cross-client
interoperability path that Cursor, Codex, OpenCode and others scan
automatically. If a user runs `rh skill install` with no flags and no
`.rh-agent.toml`, instead of erroring out we should propose installing into
`./.agents/skills/` (project-local) and explain the fallback.

**Sketch.** Update `find_agent_config()` to add a fourth fallback that
synthesizes a default config pointing at `./.agents/skills/`, behind a prompt
or `--default-agents` flag.

Effort: ~30 min.

---

### 4. Migrate `skill_list`/`skill_get` to MCP Resources primitive (SEP-2076)

**Why.** The MCP Skills Over MCP working group's draft direction is to expose
skills as MCP `resources/list` results with `skill://` URIs, not custom tools.
Aligning means any MCP client can discover RH skills without us shipping
client-specific code. We keep the current Tool aliases for backward
compatibility.

**Sketch.**

```
resources/list -> [{"uri": "skill://paper-writing", "name": "...", ...}]
resources/read?uri=skill://paper-writing&track=survey-review -> SKILL.md text
```

Effort: 1–2 hours. Requires touching the MCP server's resource handlers.

---

### 5. `npx`-style installer for users who don't have RH installed yet

**Why.** Today users must `git clone` + `setup.sh` + `pip install` before they
can pull skills. The community standard (`npx skills add`) lets users install
a skill in one shell line. This is the biggest UX gap — but also the biggest
investment because it requires publishing an npm package.

**Sketch.** Publish a thin npm package `@research-harness/skills-cli` whose
`main` shells out to a Python entrypoint, OR write a pure-Node mirror of
`rh skill install` for the common case (download + symlink).

Usage:

```bash
npx @research-harness/skills-cli install --agent claude-code
```

Effort: 1 day to publish; ongoing cost to keep it in sync with the Python CLI.

---

## What we explicitly are NOT doing

* **Per-platform parallel manifests** (Qt-style `.claude-plugin/` +
  `gemini-extension.json` + `.codex-plugin/plugin.json` all in one repo). The
  whole point of `.rh-agent.toml` is that adding a platform shouldn't require
  changes inside RH. Ship the skill once, let agents declare for themselves.

* **A central registry server.** `agentskills.io` and the MCP registry already
  fill this niche; building our own is duplicative. If someone wants RH skills
  in a registry, we publish to one of those.
