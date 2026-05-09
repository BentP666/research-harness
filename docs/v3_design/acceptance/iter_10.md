# Iter 10 验收报告

## 自检
- [x] 后端 pytest 全绿（84 passed）
- [x] 前端 vitest 全绿（17 passed）
- [x] E2E 9步路径全部跑通（API 级验证）
- [x] EMNLP 409 红线明确标注为预期行为
- [x] cost-log 记录在 journey-script.md
- [x] RELEASE_NOTES.md 完成
- [x] 验收指南_v3.md 完成 (100 项)
- [x] follow-up.md 记录 2 个已知遗漏
- [x] PROGRESS.md 更新

## E2E Journey 结果

| Step | Action | Result |
|------|--------|--------|
| 1-2 | Intake profile | 200 OK |
| 3 | Stage advance | init → build → analyze |
| 4 | Field brief | 200 OK (sat=0.62, 30 ds, 10 bl) |
| 5 | Goal pool | 200 OK (5 goals) |
| 6 | Stage advance | analyze → propose → experiment |
| 7 | Atoms harvest ×5 | 200 OK (30 atoms) |
| 8 | Matrix build | 200 OK (150 cells) |
| 9a | Venue decision | 200 OK (EMNLP) |
| 9b | Style kit | **409** (Q4 red line — 0 EMNLP/family papers) |
| 10 | Retrieval trigger | 200 OK (5 papers, log written) |

## 已知问题
- ~~MCP Playwright browser session expired — screenshots deferred to review session~~ → 已由 review session 在 2026-04-25 用 MCP Playwright 实操补全（11 张归档到 docs/assets/v3-demo/journey-screenshots/）
- Anthropic provider usage not reflected in local provenance table (calls confirmed successful by data)
- iter-09 前端组件 retrieval-trigger-button.tsx 未实现（PLAN T9.4-T9.5 跳过），已记录 follow-up.md #3。step-12 retrieval modal 截图无法采集（组件不存在）

## Review Session 补全的截图清单（11 张，docs/assets/v3-demo/journey-screenshots/）

桌面 1440×900（8 张）：
- step-01-onboarding-persona-p3.png — 4 persona 卡片，p3 选中蓝色 ring
- step-02-onboarding-constraints-emnlp.png — venue 锁定 EMNLP / 单卡 / 90 天
- step-04-fieldbrief-success.png — saturation 0.62 黄色 zone + 6 tile + goal pool 5 行表格 (一张图同时验证 iter-04 + iter-06 success 态)
- step-05-fieldbrief-tile-detail.png — FieldBrief 顶部完整
- step-06-fieldbrief-dataset-list.png — 30 数据集列表展开 + GPU req tag
- step-08-09-atoms-matrix.png — 30 atoms 6 类分组 + 5×30=150 cells matrix 网格
- step-10-venue-decision-emnlp.png — VenueDecisionBanner: EMNLP decided
- step-11-stylekit-409-redline.png — Q4 红线 live 实证: family ['emnlp','acl','naacl','eacl','coling','findings'] 全 0 篇 → 409

移动 375×667（3 张）：
- mobile-01-onboarding.png — persona 卡片单列堆叠
- mobile-02-fieldbrief-success.png — 6 tile 3×2 grid + goal pool 表格滚动
- mobile-03-venue-409-redline.png — 409 错误完整显示，不破版
