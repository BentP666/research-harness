# Iter 06 验收报告

## 自检
- [x] 后端 pytest 全绿（77 passed）
- [x] 前端 vitest 全绿（17 passed — 4 new GoalPoolCard tests）
- [x] Playwright E2E — 脚本见 docs/v3_design/e2e_scripts/iter_06.md
- [x] 手动验证通过

## 测试覆盖 (4 tests)
- empty state: shows Target icon + "No goals yet" + Build button
- success state: shows table with 2 rows (apple_stock, NYC_Taxi)
- score hover: shows breakdown tooltip with 5 bars
- active highlight: top-priority row has blue left border

## 文件变更

| 文件 | 操作 |
|------|------|
| `web/src/components/topic/goal-pool-card.tsx` | 新建 |
| `web/src/app/topics/[id]/page.tsx` | 插入 GoalPoolCard |
| `web/src/__tests__/goal-pool-card.test.tsx` | 新建 4 个测试 |

## 4 态实现
- empty: Target icon + "No goals yet" + Build button, error→shows "Generate Field Brief first"
- loading: Loader spinner + text
- error: AlertCircle + red alert
- success: table with priority reorder (↑↓) + skip (🚫) + score hover tooltip

## 已知问题
- 无
