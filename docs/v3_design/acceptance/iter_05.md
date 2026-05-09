# Iter 05 验收报告

## 自检
- [x] 后端 pytest 全绿（64 passed in 4.61s — 含 6 scoring + 4 endpoint = 10 新测试）
- [x] 前端单元测试 — N/A（本轮无前端变更）
- [x] Playwright E2E — N/A（本轮无前端变更）
- [x] 手动验证 — 纯函数 scoring 输入输出正确

## 测试覆盖

### Scoring 纯函数 (6 tests)
- test_score_headroom_high — delta/baseline 比值高 → headroom > 0.5
- test_score_headroom_low — delta 极小 → headroom < 0.1
- test_score_compute_fit_pass — CPU dataset + CPU budget → 1.0
- test_score_compute_fit_fail — medium GPU dataset + CPU budget → 0.0
- test_score_venue_fit_match — EMNLP target + EMNLP in brief → 1.0
- test_score_venue_fit_mismatch — NeurIPS target, not in brief → 0.3

### Endpoint (4 tests)
- test_post_returns_goals — POST 返回 ≤5 goals with score + breakdown
- test_get_returns_by_priority — GET 按 priority_rank 排序
- test_patch_updates_status — PATCH status='done' 生效
- test_post_409_when_field_brief_missing — 无 field_brief 返回 409

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/059_goal_pool.sql` | 新建 |
| `packages/research_harness/research_harness/primitives/goal_pool_impl.py` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 新增 4 端点 (POST/GET/PATCH/DELETE) |
| `packages/research_harness_mcp/tests/test_goal_pool.py` | 新建 10 个测试 |

## 设计决策
- 评分权重: headroom=0.35, feasibility=0.25, evidence_coverage=0.20, venue_fit=0.10, compute_fit=0.10
- evidence_coverage 下限 0.3（避免因 field_brief 恰好没收录 baseline 就直接判零）
- 硬拒绝: evidence_coverage < 0.3 OR compute_fit < 0.5 的候选直接过滤
- field_brief 缺失时返回 409 Conflict + 明确提示

## 已知问题
- 无
