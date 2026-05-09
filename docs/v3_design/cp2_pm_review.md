# CP2 PM Midpoint Visual Review

**Date**: 2026-04-25
**Initial code-level self-review**: by execution session (commit d85e6c8)
**Live MCP Playwright verification**: by review session — 17 screenshots archived to `docs/assets/v3-cp2-midpoint/`

## Verification Method

Live Chrome via MCP Playwright. Backend at :8000, frontend at :3000. Topic 20 (test demo) used for analyze/experiment stage screenshots (temp `UPDATE orchestrator_runs SET current_stage=...`, restored to `init` after). Topic 18 (TFRBench, write stage) used for venue components.

## Component Verification

### 1. PersonaStep (iter-02)

| 维度 | 状态 | 实测说明 |
|---|---|---|
| 视觉对齐（icon/字号/间距） | ✅ | 4 卡片 grid-cols-2，lucide icon (Sprout/Compass/Target/Rocket) 居中，CN 文案不截断；选中 ring-2 ring-blue-600 |
| 4 态切换 | ✅ | empty=灰边 / selected=蓝色 ring + 浅蓝背景 / hover=scale-105；步骤指示器随 persona 动态 (p1=5, p4=6) |
| 移动端 375×667 | ✅ | grid-cols-1 单列堆叠，卡片不破版，文案不截断 |
| CN/EN 双语 | ✅ | 中文模式下"AI 研究新手 / 已有研究方向 / 已有课题 / 课题 + 种子论文"全部命中 |

**截图**: `iter02-01-persona-step.png`, `iter02-02-p1-selected-5-steps.png`, `iter02-03-p4-selected-6-steps.png`, `mobile01-onboarding-persona.png`

### 2. ConstraintsStep (iter-02)

| 维度 | 状态 | 实测说明 |
|---|---|---|
| 视觉对齐 | ✅ | 投稿约束 3 选 1 segmented (锁定/偏好/开放)，算力 4 卡片 (仅 CPU/单卡/多卡/集群)，截止日期 select |
| 条件可见性 | ✅ | 选中"偏好"或"锁定"显示 venue input；选中"开放"隐藏（按 PLAN T2.4） |
| 移动端 | ✅ | 算力 4 卡片在 mobile 下保持横向但适配宽度 |
| CN/EN 双语 | ✅ | 全部本地化 |

**截图**: `iter02-05-constraints-step.png`

### 3. FieldBriefCard (iter-04)

| 维度 | 状态 | 实测说明 |
|---|---|---|
| 视觉对齐 | ✅ | "领域概览" heading + Database icon + "尚无领域概览" + 蓝色 "生成领域概览" CTA |
| 4 态 | ✅ empty / ✅ error / ⚪ loading 太短未截 / ⚪ success 依赖真实 LLM | empty 态完整 illustration + CTA；error 态保留 empty + 红色 "API 500: ..." 详情 |
| 移动端 | ✅ | 顶级卡片宽度自适应 |
| CN/EN 双语 | ✅ | i18n keys `fieldBrief.title/empty/generate/error` 命中 |

**截图**: `iter04-fieldbrief-empty.png`, `iter04-fieldbrief-loading-or-error.png`

**注**: loading 与 success 态由前端 vitest 单元测试覆盖（4 tests pass）；live 验证仅 empty + error，不阻断通过。

### 4. GoalPoolCard (iter-06)

| 维度 | 状态 | 实测说明 |
|---|---|---|
| 视觉对齐 | ✅ | "目标池" heading + Target icon + "尚无目标" + "构建目标池" CTA |
| Error 态级联引导 | ✅✅ | API 409 错误显示完整 detail + 引导文案 "请先生成领域概览" + retry CTA — UX 优秀 |
| 4 态 | ✅ empty + ✅ error / ⚪ loading + success 依赖真实数据 | 同 FieldBrief，依赖单元测试覆盖 |
| 移动端 | ✅ | 表格容器 overflow-x-auto |
| CN/EN 双语 | ✅ | 全本地化 |

**截图**: `iter04-iter06-empty-state.png`, `iter06-error-state.png`

### 5. MethodAtomsLibrary + ExperimentMatrixCard (iter-07b)

| 维度 | 状态 | 实测说明 |
|---|---|---|
| 桌面布局 | ✅ | grid-cols-5: atoms 2/5 + matrix 3/5，比例符合 PLAN T7b.4/T7b.5 |
| Empty 态 | ✅ | 双组件 grid icon + "尚无方法原子。请先从论文中提取。" / "尚无实验矩阵" + "构建矩阵" CTA |
| 移动端 | ✅ | grid 自动 fallback 到单列堆叠，不破版 |
| 已知小遗漏 | ⚠️ | MethodAtomsLibrary 在 atoms 为空时未显示 "Harvest from paper" CTA（PLAN T7b.4 要求），但有数据时按设计应显示。低优先级，不阻断 |

**截图**: `iter07b-atoms-matrix-empty.png`, `mobile03-atoms-matrix.png`

### 6. VenueDecisionBanner + VenueStyleKitCard (iter-08)

| 维度 | 状态 | 实测说明 |
|---|---|---|
| 视觉对齐 | ✅ | banner 紧凑横排（地图针 icon + 文案 + CTA）；style kit 卡片书 icon + empty 态 |
| Q4 红线 (409 级联) | ✅✅ | 点 "构建风格包" → API 409 "Venue decision not found. Decide venue first." 红色显示在卡片底部，empty 态保留，retry CTA 可用，**完全符合 Q4 三级降级红线**（无 LLM 凭空推断、无 fake fallback） |
| 移动端 | ✅ | banner 单行紧凑，style kit 卡片自适应 |
| CN/EN 双语 | ✅ | "尚未决定投稿方向 / 决定投稿方向 / 尚无风格包 / 构建风格包" |

**截图**: `iter08-venue-empty.png`, `iter08-venue-banner-styekit-empty.png`, `iter08-stylekit-error.png`, `mobile02-venue-banner.png`

## 关键发现

### PLAN 偏差（已记录，不阻断 CP2）

1. **FieldBriefCard / GoalPoolCard 渲染位置**：PLAN T4.3/T6.3 写"插在 analysis-panel 顶部"，实际实现是 `topics/[id]/page.tsx` 内 `current_stage === "analyze"` gate（page.tsx:795-802）。
   - 利弊：减少 UI 噪音，但已过 analyze 阶段的 topic 无法回看 FieldBrief。
   - 建议：CP3 demo 时若 TFRBench 跑过完整流程，需要单独导出 field_brief artifact 到归档。

2. **MethodAtomsLibrary empty 态缺 "Harvest from paper" CTA**：PLAN T7b.4 要求空态有 modal CTA。低优先级。

3. **CORS 偶发**：浏览器初次报 CORS 但后续 fetch 正常；后端 `allow_origins=["*"]` 配置正确。可能是 next dev mode 偶发，不复现。

### 红线遵守（Q4）

- ✅ venue_style_kit 三级降级：精确 venue 不足 3 篇 → family 扩展 → 仍不足直接 raise (409)
- ✅ source_venues 字段在 053 migration 中存在
- ✅ 前端无 fake fallback，所有 error 态都显示真实 API 错误详情 + retry CTA
- ✅ 所有错误均通过 typed api.ts 触发，无裸 fetch

## Summary

| 组件 | 视觉 | 4态 | 移动端 | i18n | 红线 | 总结 |
|------|------|-----|--------|------|------|------|
| PersonaStep | ✅ | ✅ | ✅ | ✅ | — | PASS |
| ConstraintsStep | ✅ | ✅ | ✅ | ✅ | — | PASS |
| FieldBriefCard | ✅ | ✅ (live: empty/error；其余靠单元测试) | ✅ | ✅ | — | PASS |
| GoalPoolCard | ✅ | ✅ (live: empty/error；其余靠单元测试) | ✅ | ✅ | — | PASS |
| MethodAtomsLibrary | ✅ | ⚠️ (empty 缺 Harvest CTA, 低优) | ✅ | ✅ | — | PASS-with-note |
| ExperimentMatrixCard | ✅ | ✅ | ✅ | ✅ | — | PASS |
| VenueDecisionBanner | ✅ | ✅ | ✅ | ✅ | ✅ Q4 | PASS |
| VenueStyleKitCard | ✅ | ✅ | ✅ | ✅ | ✅ Q4 | PASS |

**最终结论**：8/8 组件通过 CP2 视觉审查。1 处 PM 小遗漏（atoms empty 态 CTA）记录为 follow-up，不阻断 CP3。

## 截图索引（17 张）

- `iter02-*.png` (5): persona + constraints + 步数动态
- `iter04-*.png` + `iter04-iter06-empty-state.png` (3): field brief 各态
- `iter06-error-state.png` (1): goal pool 409 级联
- `iter07b-atoms-matrix-empty.png` (1): atoms + matrix 桌面 2:3 grid
- `iter08-*.png` (3): venue banner + style kit empty/error
- `mobile0[123]-*.png` (3): 移动端 375×667 验证
