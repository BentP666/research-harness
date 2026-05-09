# Git Worktrees — Multi-Session Workflow

When more than one Claude session works on this repo at the same time, every
session **must** operate in its own git worktree. Sharing the primary checkout
across sessions is unsafe: when one session runs `git checkout`, any other
session's uncommitted edits on the previously-checked-out branch are silently
discarded.

## Convention

```
~/code/research-harness-oss            <- primary, stays on main
~/code/rh-<feature>                    <- one worktree per feature branch
```

Examples:

| Path                                   | Branch                          |
|----------------------------------------|---------------------------------|
| `~/code/research-harness-oss`          | `main`                          |
| `~/code/rh-<feature>`                  | `feat/<feature>`                |

## Creating a worktree

```bash
# From the primary checkout, NOT from another worktree
cd ~/code/research-harness-oss

# Branch off the current main (or whatever base you want)
git worktree add ../rh-<feature> -b feat/<feature>

# Install JS deps once per worktree (they don't share node_modules)
cd ../rh-<feature>/web && npm install
```

Helper:

```bash
scripts/wt-new.sh <feature>          # creates ../rh-<feature> branched from main
```

## Removing a worktree

```bash
# After the branch is merged
git worktree remove ../rh-<feature>
git branch -d feat/<feature>
```

## Rules for Claude sessions

1. **Primary repo (`research-harness-oss/`) stays on `main`.** Don't switch
   branches there — it's the reference checkout. If you need to make a
   feature change, use or create a worktree.
2. **One session per worktree.** Two sessions in the same worktree can still
   collide on uncommitted edits; one session per directory is the rule.
3. **Verify before editing.** Run `pwd && git branch --show-current` at the
   start of any task that will touch source files. The path should match
   `rh-<feature>`, not the primary.
4. **`EnterWorktree` tool.** When Claude Code already runs in the primary
   path but the work belongs to a feature, use `EnterWorktree(path=...)` to
   switch the session into the matching worktree before doing any edits.
5. **Per-worktree `node_modules`.** Each worktree has its own `web/node_modules`.
   The first time you enter a fresh worktree, run `cd web && npm install`.
6. **Shared `.git`.** All worktrees share the same `.git` database, so
   commits, branches, and refs are global. Pull/fetch from any worktree.
7. **Don't share Python venvs.** Activate the project's venv from the
   worktree's path; symlinking across worktrees has caused import-path
   confusion in the past.
