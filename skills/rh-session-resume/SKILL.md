---
name: rh-session-resume
description: Resume an existing Research Harness topic/session in Codex without restarting work. Trigger on phrases like "rh-session-resume", "/rh-session-resume", "接手已有 topic", "继续上次 Research Harness", "resume RH topic", or equivalent requests to recover current state before acting.
---

# RH Session Resume

Use this skill before continuing an existing Research Harness topic, artifact, or research thread.

## Workflow

1. Read `docs/agent-guide.md` if the session has not already loaded it.
2. Identify the topic from the user prompt, current files, or recent memory.
3. Prefer MCP state recovery:
   - `orchestrator_resume(topic_id=...)` when a topic is known
   - otherwise `topic_list`, `topic_show`, `orchestrator_status`, `decision_log_list`, and recent artifacts
4. Check local project/memory records before web search. Do not start fresh external search until local state is understood.
5. Build a compact resume packet:
   - topic id/slug
   - current stage and gate status
   - latest durable artifacts
   - important paper ids and queues
   - open blockers/risks
   - next 3 concrete actions
6. If the user asks to continue execution, proceed from the resume packet rather than restarting the workflow.

## Rules

- Never treat a missing chat summary as proof there is no prior work; inspect RH state first.
- Do not scatter paper lists or findings in files outside the RH database/artifact system.
- If MCP is unavailable, report the missing tool and fall back to read-only CLI/status commands.
- If context is already large, produce a checkpoint before opening more large files.
