---
name: rh-paper-deep-reading
description: Run the Research Harness paper deep-reading workflow in Cursor. Use when the user mentions 论文精读, 精读, deep_read, paper card, paper critique, method walkthrough, reproducibility analysis, or topic-specific reading notes.
---

# RH Paper Deep Reading

For paper deep-reading tasks, delegate to the `rh-paper-deep-reader` subagent when available.

If handling directly:

1. Use the `research-harness` MCP server, not ad-hoc files.
2. Resolve `topic_id` first (`topic_show`, `topic_list`, or user-provided ID).
3. Ensure the paper is in RH storage (`paper_ingest` with `topic_id`) before analysis.
4. Prefer `get_deep_reading` for existing notes; otherwise run `deep_read` when RH provider keys are configured.
5. Use `paper_acquire` when PDFs/annotations are missing.
6. If `deep_read` fails because no API key/model is configured, use Cursor's own model over the stored PDF/paperindex output and record the result with `orchestrator_record_artifact(artifact_type="cursor_deep_read_note", ...)`.
7. Record other state-changing outputs with `orchestrator_record_artifact`.
8. Answer in Chinese unless the user asks otherwise.

Report using: 一句话定位 → 问题与动机 → 方法精读 → 实验与证据 → 局限与可复现性 → 对当前 topic 的启发 → 下一步 RH 动作.
