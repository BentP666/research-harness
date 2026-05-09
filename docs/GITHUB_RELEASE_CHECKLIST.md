# GitHub Release Checklist

Use this before publishing a public GitHub update or opening the release PR.

## Product surface

- [ ] Workbench opens at `/` and clearly explains the user outcome.
- [ ] Primary navigation contains only core surfaces: Workbench, Workflow,
      Library, Reports.
- [ ] Labs / Advanced surfaces remain reachable but are not the first-run path.
- [ ] `/demo` works without an LLM key and explains the product story.
- [ ] Empty state includes a copyable agent handoff prompt.

## Docs

- [ ] `README.md` is concise and outcome-first.
- [ ] `README.zh-CN.md` is synchronized with the English README.
- [ ] `docs/DEMO.md` describes no-key and live demos.
- [ ] `docs/frontend-workbench.md` records frontend positioning and copy rules.
- [ ] `docs/quickstart.md` points to the current FastAPI + Next.js workbench.

## Verification

Run from `web/`:

```bash
npm run lint
npm run test
npm run build
```

Run from repo root when Python changes are included:

```bash
/Users/biajin/miniconda3/envs/research-harness/bin/python -m pytest packages/research_harness_mcp/tests/test_agents.py -q
```

## Git hygiene

- [ ] Review `git diff --stat`.
- [ ] Confirm whether `.cursor/` and `docs/cursor-agent.md` should be committed.
- [ ] Confirm release tag strategy (`v0.4.0`, `v1.0.0-preview`, or no tag yet).
- [ ] Do not push, publish, or tag without explicit approval.
