---
name: rh-artifact-record
description: Record durable Research Harness outputs as orchestrator artifacts with provenance. Trigger on phrases like "rh-artifact-record", "/rh-artifact-record", "记录 artifact", "产出入库", "save RH artifact", or when a research output should not remain only in chat/files.
---

# RH Artifact Record

Use this skill whenever a research output, decision, evidence map, review, or draft should be durable.

## Workflow

1. Identify `topic_id`, stage, artifact type, title, and the output payload.
2. Normalize payloads before recording:
   - concise summary
   - inputs used (paper ids, artifact ids, URLs, commands, or files)
   - claims/decisions and confidence where relevant
   - limitations and follow-up tasks
3. Use MCP `orchestrator_record_artifact` as the primary write path.
4. If the output also lives in a file, record the path, purpose, and any stable identifier in the artifact payload.
5. Return an artifact receipt with id, title, stage/type, and how it should be used next.

## Payload Checklist

- No secrets, tokens, raw credentials, or private keys.
- No long copyrighted excerpts; summarize instead.
- Paper-backed claims include paper ids or source URLs.
- Replaced/superseded artifacts are named explicitly.
- Human-confirmation items are separated from direct implementation items.

## Fallback

If MCP artifact recording is unavailable, do not silently pretend it was recorded. Produce a pending artifact packet and tell the user what needs to be recorded once MCP is available.
