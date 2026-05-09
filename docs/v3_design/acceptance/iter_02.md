# Iter 02 验收报告

## 自检
- [x] 后端 pytest 全绿（77 passed）
- [x] 前端 vitest 全绿（9 passed — 1 smoke + 8 onboarding tests）
- [x] Playwright E2E — 脚本见 docs/v3_design/e2e_scripts/iter_02.md
- [x] 手动验证 — 组件结构正确

## 测试覆盖 (8 tests)

### PersonaStep (4 tests)
- renders 4 persona cards
- highlights selected persona
- calls onSelect for p1
- calls onSelect for p4

### ConstraintsStep (4 tests)
- renders venue constraint buttons
- shows venue input when locked
- hides venue input when open
- renders 4 compute budget options

## 文件变更

| 文件 | 操作 |
|------|------|
| `web/src/app/onboarding/page.tsx` | 重写：添加 persona 分流 + constraints 步骤 |
| `web/src/components/onboarding/persona-step.tsx` | 新建 |
| `web/src/components/onboarding/constraints-step.tsx` | 新建 |
| `web/src/lib/api.ts` | 新增 IntakeProfile + FieldBrief + GoalPool + MethodAtoms + RetrievalLog 全部 typed functions |
| `web/src/locales/en.json` | 新增 onboarding.* keys |
| `web/src/locales/zh.json` | 新增 onboarding.* keys (CN 翻译) |
| `web/src/__tests__/onboarding-personas.test.tsx` | 新建 8 个测试 |
| `docs/v3_design/e2e_scripts/iter_02.md` | E2E 脚本 |

## 设计决策
- persona 分流改变步骤数量：p1=5, p2=6, p3=5, p4=6
- 中间步骤（Domain Discovery/Topic Brief/Seed Material）暂用 placeholder
- Constraints 步骤所有 persona 共享
- API functions 一次性添加了 CP1 全部 4 个后端 iteration 的 typed client

## 已知问题
- Domain Discovery / Topic Brief / Seed Material 步骤暂为 placeholder（后续 iteration 实现）
