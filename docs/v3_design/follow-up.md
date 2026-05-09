# V3 Follow-up Items

Known limitations from CP2 review. Not blocking v3 release, tracked for future iterations.

## 1. FieldBriefCard / GoalPoolCard stage-gating

**Issue**: Both cards only render when `current_stage === "analyze"`. Topics that have advanced past analyze cannot revisit their field brief or goal pool from the UI.

**Impact**: Low — artifacts are stored in DB and accessible via API. Frontend-only limitation.

**Fix**: Render cards unconditionally (or at stage >= analyze), collapsed by default for non-analyze stages.

**Source**: CP2 PM review (d85e6c8), PLAN偏差 #1

## 2. MethodAtomsLibrary empty state CTA

**Issue**: When no atoms exist, the empty state shows a message but lacks a "Harvest from paper" CTA button that would open a paper selection modal.

**Impact**: Low — users can trigger harvest via WorkflowPipeline or API directly.

**Fix**: Add a button in empty state that opens a modal listing deep-read papers with checkboxes.

**Source**: CP2 PM review, PLAN T7b.4

## 3. iter-09 retrieval-trigger-button.tsx 前端组件 — ✅ 已补完 (2026-04-25)

**Original issue**: iter-09 只完成了后端（迁移 061 + endpoint 包装 + retrieval_log 写入）和 `web/src/lib/api.ts` 里的 typed function，前端 UI 入口缺失。

**Resolution (commit pending v1.0.0 GA)**:
- 新建 `web/src/components/topic/retrieval-trigger-button.tsx`：Search icon ghost button + Dialog modal（5 reason chips + query textarea + success/error 反馈）
- 挂载在 4 个 panel CardHeader：field-brief-card (build) / analysis-panel (analyze) / experiment-leaderboard-card (experiment) / write-panel (write)
- 新建 `web/src/components/topic/retrieval-log-timeline.tsx`：在 topic 详情页 activity 区下方显示 retrieval_log 历史，🔍 icon + reason badge 区分
- `searchPapers` API client 扩展接受 `stage / trigger_reason` 字段
- i18n: en.json + zh.json 各加 `retrieval.*` 命名空间
- vitest 5 测试：4 态 + 提交 payload 校验

**Verification**: live MCP Playwright 在 topic 21 analyze 阶段成功打开 modal，5 reason chip 可切换，query 输入有效。step-12 截图已归档。
