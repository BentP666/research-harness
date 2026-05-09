#!/usr/bin/env bash
# Create a new git worktree at ../rh-<feature> on a fresh feat/<feature> branch.
# Run this from the primary repo (research-harness-oss/). See docs/WORKTREES.md.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/wt-new.sh <feature>" >&2
  echo "  example: scripts/wt-new.sh pdf-ai-reader" >&2
  exit 1
fi

feature="$1"
branch="feat/${feature}"
target="../rh-${feature}"

# Sanity: must run from the primary repo
toplevel="$(git rev-parse --show-toplevel)"
if [[ "$(basename "$toplevel")" != "research-harness-oss" ]]; then
  echo "ERROR: run this from the primary checkout (research-harness-oss/), not a worktree." >&2
  echo "  current top-level: $toplevel" >&2
  exit 2
fi

# Sanity: refuse to clobber existing path
if [[ -e "$target" ]]; then
  echo "ERROR: $target already exists." >&2
  exit 3
fi

# Sanity: refuse to reuse an existing branch
if git show-ref --verify --quiet "refs/heads/${branch}"; then
  echo "ERROR: branch ${branch} already exists. Pick another name or remove it first." >&2
  exit 4
fi

base="${BASE:-main}"
echo "Creating worktree ${target} on new branch ${branch} from ${base}..."
git worktree add "$target" -b "$branch" "$base"

echo
echo "Worktree ready. Next steps:"
echo "  cd ${target}"
echo "  cd web && npm install   # one-time per worktree"
echo
echo "Then start a Claude Code session from ${target}."
