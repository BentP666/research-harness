# Atlas / Research Harness — 产品审查报告

**日期**: 2026-04-26
**审查者**: PM-grade external review
**方法**: 真实 Playwright 走查 13 个核心页面 + 代码侧深入 + 数据库交叉验证 + 大厂 benchmark
**对照系**: Notion / Linear / Arc / Cursor / GitHub / Vercel / Granola / Perplexity

---

## TL;DR — 跟头部产品的真实差距

Atlas 已经是一个**功能扎实的内部研究工具**，但距离"大厂头部产品"差距主要不在功能，而在**产品设计的克制感、信息密度、状态一致性、与基础交互礼仪**：

| 维度 | 现状 | 头部水位 | 差距 |
|------|------|---------|------|
| 信息架构 | 6 个左侧导航 + 设置 | 3-4 个核心导航 | **过宽** |
| 状态一致性 | 同一 topic 在不同页 stage chip 时有时无、流水线和 stage 不联动 | 状态全局一致 | **P0** |
| 输入效率 | 0 个全局快捷键 / 无命令面板 / 无全局搜索 | Cmd+K 必备 | **P0** |
| 实时反馈 | 全 polling，AI 任务无 streaming | SSE / WebSocket | **P1** |
| 错误/加载状态 | 0 个 loading.tsx / error.tsx / not-found.tsx | App Router 标准全套 | **P1** |
| 可观测性 | 4 个 hydration error 在 /budgets | 0 console error | **P0** |
| 用户教育 | 信号性术语（token / propose / 流水线 0/X）无 hover 解释 | 渐进披露 + tooltip | **P1** |
| 文案 | 中英混排有改进空间，专业感不一致 | 一致中文或一致英文 | **P2** |
| 视觉层级 | 卡片密度高、KPI 三联无对比 | 数据可视化讲故事 | **P2** |
| 前端测试 | 5 个 test 文件 vs 25 个路由 | 关键 user flow 必有 e2e | **P1** |

---

## 一、严重缺陷（P0 — 阻碍发布）

### P0-1. `/budgets` 页面 hydration error 回归
QA Report 2026-04-25 明确写了 `web/src/app/budgets/page.tsx — fixed <p>→<div> hydration`，但**bug 又回来了**：

```tsx
// web/src/app/budgets/page.tsx:194-203
<p className="mt-0.5 text-3xl font-semibold tabular-nums">
  {summaryQ.isPending ? (
    <Skeleton className="h-8 w-24" />   // ❌ Skeleton 渲染 <div>，<p> 不能套 <div>
  ) : (
    formatTokens(totalTokens)
  )}
  <span className="ml-2 text-sm font-normal text-muted-foreground">
    {t("budgets.tokens")}
  </span>
</p>
```

**控制台输出** 4 errors 包括 `Hydration failed because the server rendered HTML didn't match the client`。

**修复**：把外层 `<p>` 改为 `<div>`，或把 Skeleton 替换成内联 `<span>` 风格的 placeholder。

**为什么 P0**：每次新用户打开预算页 React 都警告，给"专业级研究工具"形象致命打击。

### P0-2. `/budgets` 数据自相矛盾
顶部显示"本月 TOKEN 消耗 **2.72M token** （输入 1.10M · 输出 1.62M）"，下方紧接着写"**本月各模型的 token 占比** — 本月暂无使用记录"。**同一页内的事实冲突**。下方 6-stage 柱状图也是空的。

**根因**: 顶部 KPI 来自一个聚合接口，下方明细来自另一个接口，二者数据源未统一。
**修复方向**: 单一聚合接口返回 summary + by_model + by_stage，前端从同一对象 derive。

### P0-3. Topic 详情页流水线全是 `0/X`，与实际 stage 严重背离
访问 `/topics/11` (paper5)：DB 已经是 `propose`、有 179 claims、16 gaps，但流水线节点显示 `Init 0/5  Build 0/10  Analyze 0/8  Propose 0/9`。

用户看完会直接得出结论 "这个系统坏了"。

**根因**：流水线节点的"完成数"是查 stage 内部 sub-step 完成事件（`orchestrator_stage_events.event_type='completed'`），而历史工作未通过 orchestrator 记录。我今天给历史 topic backfill stage 时**没补 stage_events**，所以流水线显示空。

**修复**：
1. Backfill: 历史 stage 至少补一条 synthetic `event_type='completed', actor='backfill'` 让节点亮起来；
2. 长期: stage 推进必须配对写 stage_event；
3. 兜底: 流水线节点也读 `paper_count / claims_count / artifact_count` 这些聚合字段做"软完成"判定（粗粒度但永不空）。

### P0-4. `Topic.description` 直接暴露文件系统路径给最终用户
Topic 11 / 12 详情页顶部副标题直接写：
```
auto-bidding -- Safe Deployment Protocol for Auto-Bidding. workspace: <redacted>/paper5 (README placeholder); propose-stage artifacts in .research-hub/adversarial/new-direction-safedeploy-causalbid/novelty_check (3 rounds, 1151 lines)
```

这是我刚 backfill 时塞进去的（为了状态可追溯），但**不该作为面向用户的 description**。

**修复**：
1. `topics.description` 字段保留**面向人**的一句话；
2. 路径线索单独存一个 `topics.workspace_pointer` JSON 字段，前端可以折叠到"⓵ 链接到本地文件系统"二级 detail；
3. 我立刻把 paper5/6 description 改成简洁版（见后）。

### P0-5. 全产品 0 个全局快捷键 / 无命令面板 / 无全局搜索
- `cmdk` 已经在依赖里（`web/src/components/ui/command.tsx`），但**没被任何页面消费**；
- 没有 `/search` 路由；
- 任何 keypress 都没绑定（`grep -E 'metaKey|cmd\+k'` 0 命中）。

任何 2024+ 的"专业生产力工具"都把 Cmd+K 当作底线（Linear, Notion, Vercel, Granola, Cursor, GitHub, Arc, Slack）。**没有它，资深用户的工作流断在切换页面这一步**。

**修复**：
1. 添加 `<CommandPalette>` 全局组件（cmdk 已在）；
2. 命令面板入口至少包含：跳转任意 topic / paper / 报告，触发某个 stage 的 sub-step（e.g. "Run gap_detect on topic 7"）, 切换 locale/theme；
3. 顶部状态栏加 `⌘K` 提示 + 点击触发。

---

## 二、高优先级（P1 — 影响专业感）

### P1-1. App Router 标准 `loading.tsx / error.tsx / not-found.tsx` **完全未实现**
```bash
$ find web/src/app -name 'loading.tsx' -o -name 'not-found.tsx' -o -name 'error.tsx'
(empty)
```

后果：
- 路由切换时屏幕闪空白
- 后端 500 时整个 app 白屏
- 错的 `/topics/9999` 给用户的反馈不可控

**修复**：每个核心路由（dashboard, research, topics/[id], papers/[id], reports）都应该有 `loading.tsx`（骨架屏）+ `error.tsx`（友好错误 + 重试按钮 + 上报）+ `not-found.tsx`（404 引导回首页）。

### P1-2. 状态显示在不同页面**不一致**
| 页面 | Topic stage chip | Topic 进度 dots | 论文计数 |
|------|----|----|----|
| `/`（首页） | ✅ `Propose 阶段 4/6` | ✅ | ✅ |
| `/research` | ❌ 完全没显示 | ❌ | ✅ |
| `/topics/[id]` | ✅ 三处重复（chip + hero + sub label） | ✅（流水线但全 0） | ❌ |

**头部产品**：状态在每个出现 entity 的位置都用同一组件渲染（Linear 的 issue chip 在 list / detail / sidebar 都长一样）。

**修复**：抽 `<TopicStatePill>` + `<TopicProgressDots>` 组件，**所有列表/卡片/header 共用**。

### P1-3. 没有 streaming / SSE / WebSocket — AI 产品的硬伤
全 126 个 API 端点 0 个流式接口（grep 'stream|websocket|server-sent' 命中 0）。`What I'd work on next` 给出的"运行" 按钮按下去后，用户体验是"卡几十秒 → 突然完成"。

**头部产品**：Cursor / Perplexity / Granola 全部 token-by-token 流式输出 LLM 内容。

**修复**：
1. 优先给 LLM 类 primitive（`section_draft`, `claim_extract`, `gap_detect`, `direction_propose`）加 SSE endpoint；
2. 前端用 `EventSource` 渲染流式文本；
3. 兜底：哪怕做不到 token streaming，至少做 **stage progress streaming**（每个 sub-step done 推一次，用户看进度条动）。

### P1-4. "已连接 5 个模型" / "2.7M tok" / "Back online" 三个顶栏 chip — 没有任何解释
鼠标 hover 没 tooltip，点击不知道发生什么。新用户**完全不知道这些数字含义、能不能调整、何时该担心**。

**修复**：
1. 每个 chip 加 hover popover：`已连接 5 个模型` 展开列出 anthropic / openai / kimi / cursor_agent / codex 各自的 model id + 健康状态 + 上次成功时间；
2. `2.7M tok` 加 popover：本月配额 / 本月已用 / 速率窗口 + 跳到 /budgets 链接；
3. `Back online` 三秒后自动消失（toast 行为，不是 chip）。

### P1-5. `/discover`、`/research/trends` 的 score 没有"为什么是 8.9 分"的可点开
头部产品（Pitchbook / Crunchbase / 学术评分类）每个分数都可以点开看 evidence chain。Atlas 现在 score 8.9/10 是个黑盒。

**修复**：score 旁加 `?` icon，点开看构成（paper velocity / citation median / venue quality 各自的输入值 + 时间窗 + N=多少）。

### P1-6. Topic 详情的 sub-step "运行" 按钮没有"上次运行"状态
`4. Propose` 里 4 个 sub-step（方向排序、设计简报、算法候选、竞争分析）都是单一"运行"按钮。

**问题**：
- paper5 已经 propose 了（adversarial novelty check 跑过 3 轮），但这 4 个 sub-step 看起来全是新鲜状态
- 用户不知道哪些跑过、哪些没跑、上次跑出来啥

**修复**：每个 sub-step 行显示：
- 状态 badge：`未运行 / 运行中 / 上次成功 (3h ago) / 失败`
- 最近一次产出的链接 + token cost 实际值（不止 estimate）
- "重新运行" / "查看输出" / "diff 上次" 三个 action

### P1-7. `/research` 页 topic 卡片缺 stage chip 和进度，与首页不一致
首页有 stage chip + dots + 上次活动，研究中心反而只有 papers 数。这页才是用户**待决策时**最常去的页面，信息反而更少。

**修复**：研究中心的 topic 卡片直接复用首页同款组件（解决 P1-2 顺带解决这个）。

### P1-8. 后端 API 风格不统一
- 分页：有的路由用 `page/per_page`，有的用 `limit/offset`，有的纯 `limit`；
- 错误：抛 `HTTPException` 没有统一 envelope（`{error: {code, message, details}}`）；
- 命名：`/api/topics/{id}/force-advance`（kebab）vs `/api/topics/{id}/decisions`（plain）vs `/api/llm/explain`（path-level verb）。

**修复**：
1. 写一份 `docs/API_STYLE.md` 钉死：分页用 cursor-based、错误用统一 envelope、动词用 sub-resource action；
2. 新写的端点照新风格；老的开 deprecation 期；
3. OpenAPI schema 输出后给前端 codegen `openapi-typescript`，类型自动同步。

### P1-9. 前端测试覆盖严重不足
后端 125 个 test 文件 ↔ 前端 5 个 test 文件 / 25 个路由。一个用 vitest 的 Next 项目至少应该：
- 关键 user flow（onboarding 完整流、topic 创建、stage 推进、报告生成下载）有 Playwright 端到端
- 关键组件（TopicStatePill, NextStageHero, WriteStagePanel, BudgetSummary）有 RTL 单测

### P1-10. Hydration 风险还可能存在于其他页（QA report 已经有先例）
- 一定要打开 `next.config` 的 `reactStrictMode: true`（如果未开）
- CI 增加一个 step：headless 跑核心路由，断言 `console.error == 0`
- 现在 4 errors 在 `/budgets` 直接漏出来，说明 CI 没拦住

---

## 三、中等优先级（P2 — 影响"高级感"）

### P2-1. 信息架构过宽，左侧 6 个一级导航
现在：今日概览 / 研究中心 / 学术发现 / 文献资料 / 研究汇报 / 模型配置

**对照 Linear**：3 个一级（Inbox / My Issues / Projects），其他全部 Cmd+K
**对照 Notion**：1 个 Workspace tree

**建议合并**：
- 「今日概览」+「研究中心」→ 「研究」（首页 = Today，子页 = 全部 topic）
- 「学术发现」→ 留在研究下作为 tab（Discover 是研究的支线，不是平级动作）
- 「文献资料」+「研究汇报」→ 「资料库」（Papers + Reports tab）
- 「模型配置」→ 移到右上角 Settings 里

最终 3 个一级：**研究 / 资料库 / 设置**。视觉刷新立刻"高级"。

### P2-2. 视觉密度
- KPI 三联（论文 3882 / 领域 5 / 课题 17）只有数字，没有趋势 sparkline、没有对比（"较上月 +X 篇"）
- "进行中" 卡片网格 3 列，但其实首屏只能看 6 个，第 7 个 topic 已经下沉到第三屏 — 排序逻辑（按 last activity? stage? deadline?）也不透明

**改**：
- KPI 加 30 天 sparkline + delta；
- "进行中" 改为更紧凑的列表 + 关键指标（停滞天数 / 下一动作 / 预计 cost），或者 5x2 网格；
- 增加 sort 控件（默认 by deadline → stage → last activity）。

### P2-3. 文案 ZH/EN 混排
- "📄 流水线 / 检索与精读批次"（中文）
- "What I'd work on next"（英文）
- "Quality scorecard / Step-by-step / Smart checkpoints / Full auto"（英文）

要么全中（专业研究者更舒服），要么全英（国际化产品形象）。**混着看像 hackathon demo**。

**修复**：i18n 文件已有 `locales/{en,zh}.json`，把 hardcoded 英文（包括 "Quality scorecard" 这类）抽进去；非 i18n 的术语（Cmd+K 这类）保留英文一致即可。

### P2-4. 「Generate advisor report」按钮在 stage 没到的 topic 也亮着
`/research` 列表中未分类的 v3-demo + agent-research-infra 都显示 "Generate advisor report →"。Advisor report 一般是 propose 之后的可交付物，**stage 还在 init 就给生成入口反而误导**。

**修复**：按钮改成 stage-gated（`propose+` 才亮，其它 stage 灰 + tooltip "需要先完成方向提案"）。

### P2-5. Topic 11/12 副标题路径过长（→ 已改）
现在 paper5 副标题：

> auto-bidding -- Safe Deployment Protocol for Auto-Bidding. workspace: <redacted>/paper5 (README placeholder); propose-stage artifacts in .research-hub/adversarial/new-direction-safedeploy-causalbid/novelty_check (3 rounds, 1151 lines)

应当改成：

> Safe Deployment Protocol for Auto-Bidding · 出价策略安全上线框架

技术性路径放到「⓵ 关联本地工作区」二级折叠区。

### P2-6. 预算页 Stage 维度图全是 0 — 应给空状态
即使有数据，6 个 stage 全 0 时也应展示**说明性占位**："本月还没有 token 消耗按 stage 落账。下次 primitive 运行时会自动写入。"，而不是一根光秃秃的 X 轴。

### P2-7. 流水线节点术语 `0/5` `0/10` 完全没解释
鼠标 hover 节点应该弹"Init: 5 个 sub-step（topic_framing / persona / venue 选取 / autonomy 设定 / 预算配置），已完成 0 个"。

### P2-8. 设置页只有 4 张卡片，且都是导航卡
模型与 API 密钥 / 评分规则 / 趋势管线 / 模型提供商配置——这些都"看起来像设置"但实际入口分散到 `/agents` `/settings/scoring` `/research/trends` `/settings/providers`。

**修复**：要么把这些直接 inline 在 `/settings` 一页（Tab 切换），要么至少在卡片上展示当前关键值（比如评分规则当前是 Standard，"切换 → " 按钮）。

### P2-9. "正在升温" 卡片不可 follow / watch
头部产品（GitHub Trending / Pinterest / Are.na）都允许"关注一个主题"。Atlas 看到 RAG at Scale +180% 想 watch 但**没办法跟踪**。

**修复**：每个 cluster 卡片加 `🔔 关注` 按钮，关注后系统每周生成一份 digest。

### P2-10. 没有「最近查看」/「最近搜索」/「Pinned」
重度用户每天都看同一两个 topic + 同一批 papers。没有 pin / recent，全靠重新点导航。

---

## 四、内容/文案优化（P2-P3）

| 现在 | 建议 |
|------|------|
| `Powered by Research Harness` | 删掉或改为脚注（自夸）|
| `晚上好` （22 点）| 加用户名 `晚上好，Neal` |
| `你有 17 个课题正在进行` | 改 `你有 5 个 topic 这周需要决策` —— 行动导向 |
| `Back online`  | 静默成功 toast（3s 自动消失，无需占位）|
| `已连接 5 个模型` | 直接 `Anthropic · OpenAI · Kimi · Cursor · Codex` 或图标横排 |
| `Code generation, sandbox execution, metric evaluation` (Experiment 副标题) | 中文："生成代码 → 沙箱跑实验 → 自动评指标" |

---

## 五、对照大厂的"非功能性"差距清单

不是每条都要立即做，但这是"专业感"的真实来源：

| 维度 | 头部水位 | Atlas 现状 |
|------|---------|-----------|
| **Cmd+K 命令面板** | Linear / Notion / Vercel / Granola 全有 | ❌ |
| **全局搜索 + 最近** | 跨 entity 搜（papers/topics/reports/sections） | ❌ |
| **键盘快捷键** | `j/k` 列表 / `e` 编辑 / `?` 帮助 | ❌ |
| **撤销与历史** | Linear 删除可撤销；Atlas 删 topic 数据是真删 | ❌ |
| **批量操作** | 多选 + bulk action（move to domain / advance stage） | ❌ |
| **协作迹象** | Avatar / 谁正在看这个 topic / 评论 | ❌（即使单人版也至少留位） |
| **离线可用** | Notion / Linear / Granola 离线缓存 | ❌（看到一个 offline cache PR 但深度未知）|
| **键盘选择文本 → AI** | Cursor 的 Cmd+L | PDF 阅读器有，但其他页没有 |
| **API 公开 + Webhook** | Linear / Notion 都有 | 只有内部 HTTP API，无 webhook |
| **审计日志 / 操作历史** | 任何 enterprise 工具必有 | 只有 stage_event 不够 |
| **状态页 / SLO** | status.linear.app 等 | ❌ |
| **键盘可访问性 (a11y)** | WCAG AA | 未审 |

---

## 六、立即可做的修复清单（按 ROI 排序）

| # | 项 | 估时 | 影响 |
|---|----|------|------|
| 1 | 修 P0-1：`/budgets` Skeleton 包在 `<p>` 里 | 5 min | console 静音；专业感 +30% |
| 2 | 修 P0-4：paper5/6 description 改简洁版 | 10 min | topic 详情 hero 不再吓人 |
| 3 | 修 P0-2：budgets summary + by_model 单接口 | 1 h | 数据自洽 |
| 4 | 给 5 个核心路由加 `loading.tsx` | 2 h | 路由切换不再闪空白 |
| 5 | 顶栏 chip 加 popover（"5 个模型" / "2.7M tok"） | 1 h | 用户教育 |
| 6 | 实现 `<CommandPalette>` v0（仅跳转用） | 4 h | 重度用户的口碑分裂线 |
| 7 | 流水线节点用 `paper_count / claims / artifacts` 做软完成判定 | 1 h | P0-3 的兜底，不再"全 0" |
| 8 | 抽 `<TopicStatePill>` + `<TopicProgressDots>` 共享组件 | 2 h | 跨页一致性 |
| 9 | sub-step 行加"上次运行"状态 + 输出链接 | 4 h | Topic 详情可用度 +50% |
| 10 | i18n 把英文硬编码（"Quality scorecard" 等）抽出来 | 2 h | 文案专业 |

**第 1-7 项一天搞定，肉眼可见效果。**

---

## 七、走向"头部产品"的中长期战略建议

1. **押注 streaming**——AI 产品没流式 = 输了一半。下一个版本核心：所有 LLM-driven primitive 都走 SSE，前端 `useEventSource` hook 标准化。
2. **把命令面板做成"下一代研究 IDE"**——不止跳转，而是"指令式做研究"：`> propose new direction for paper7 with novelty constraint`，回车直接跑，结果折叠在面板里。这是 Atlas 真正的差异化（研究语义的命令面板，没人做过）。
3. **内嵌 PDF reader 的 AI 选区**已经做了——继续把这个 pattern 推广到 reports / drafts，让"选中文字 → AI 解释/改写/找证据"成为全 app 一级交互。
4. **公开 API + Webhook**——研究本质是协作，留 Webhook 钩子让用户能把 stage 完成事件 push 到 Slack / Notion。
5. **可信度可视化**——每条结论给"证据来源 → claim ID → paper ID + 句子坐标"。这是与"普通 AI 总结"拉开差距的关键，技术栈已具备（normalized_claims 表 93+ 条 / topic），UI 暂未充分利用。
6. **从单人到多人就位**——即使初期单人版，也把 actor / created_by / version 留位；未来加协作不需要重写数据模型。

---

## 八、附：本次审查走查的页面截图清单

文件位于仓库根：

| 文件 | 页面 |
|------|------|
| `audit-01-home.png` | `/` 首页 dashboard |
| `audit-02-research.png` | `/research` 研究中心 |
| `audit-03-discover.png` | `/discover` 学术发现 |
| `audit-04-library.png` | `/library` 文献资料 |
| `audit-05-topic-detail.png` `05c` `05d` | `/topics/11` paper5 详情（顶/中/下） |
| `audit-06-reports.png` | `/reports` 导师汇报 |
| `audit-07-paper-detail.png` | `/papers/3` 论文详情 |
| `audit-08-settings.png` | `/settings` 设置 |
| `audit-09-budgets.png` | `/budgets` 预算（**4 hydration errors**） |
| `audit-10-welcome.png` | `/welcome` 欢迎页 |
| `audit-11-onboarding.png` | `/onboarding` 引导 |
| `audit-12-trends.png` | `/research/trends` 趋势 |
| `audit-13-agents.png` | `/agents` 模型注册 |

---

## 九、美观 / 大气 / 易用性专题

### 9.1 设计系统现状（基础不差）
- **字体**：Geist (UI sans) + Fraunces (heading serif) — 是 2024+ 流行的"现代研究感"组合（Vercel × 学术 vibe）。基础选得不错。
- **色彩**：oklch 色彩空间，蓝色 primary（`oklch(0.488 0.243 264.376)`）；亮色卡片 `oklch(1 0 0)`，暗色卡片 `oklch(0.17 ...)`。色彩系统现代。
- **圆角**：base `0.5rem` + 6 档梯度（sm→4xl）。结构合理。
- **图标**：72 处 lucide-react，统一无杂牌。
- **动效**：装了 `framer-motion@12.38` 但**走查时基本没看到任何 micro-interaction**——这是巨大的浪费。

**结论**：底子是头部水平的，问题在**应用力度**与**克制**——不是工具不行，是没人推动它达到该有的"成品感"。

### 9.2 美观差距（与 Linear / Granola / Arc 对比）

#### a) **缺少节奏感（rhythm）**
看截图 `audit-01-home.png`：hero card → 三联 KPI → 6 卡片网格，三段都是相似的"白底卡片 + 圆角 + 等距留白"。整页**没有视觉重音**，眼睛找不到落点。

**头部产品做法**：用一个超大字号 + 一段轻量 muted text + 然后是密度更高的列表。落差让 hero 区"呼吸感"出来。

**改**：
- 首页 hero `晚上好` 上面那行 `Powered by Research Harness · 4月26日星期日` 删掉或下沉到次级元数据，让 hero 文案立得起来；
- KPI 三联用更大字号（48-56px）且去掉 icon → 让数字本身成为视觉主体；
- 进行中卡片改为列表行（更高密度、列对齐，类似 Linear issue list）。

#### b) **卡片化过度（card-stuffing）**
现在几乎每个 section 都被装进一个 white card with rounded corners。造成两个问题：
1. 视觉上一片白底 + 圆角白卡，对比度不够；
2. "万物皆 card" 让信息层次扁平——重要的和不重要的看起来一样重。

**改**：
- 一级容器（page background）和二级（card）色差再加大一点；
- 不是所有内容都需要 card：**列表行 + 分隔线**（Linear / Notion 主流）反而更高级；
- 重要信息用更深的 surface elevation（subtle shadow），次要信息直接平铺。

#### c) **品牌"AI 研究感"没立住**
Hero 里 `Powered by Research Harness ⊕ 晚上好` 是**通用 SaaS 模板感**，不像"研究伙伴"。

**头部产品锚点**：
- Granola：随便点一处，都能看到"对话→笔记"的产品本质；
- Linear：每个像素都在说"speed";
- Cursor：UI 99% 时间不打扰你，命令面板和对话栏才是品牌。

**Atlas 应该立的"研究伙伴"形象**——但现在没有任何视觉/交互锚点说"我帮你做研究"。

**改**：
- 首页 hero 副标题用一句**真正的研究语言**："今天值得做的下一步：给 paper5 跑一次 gap_detect，预计 ~40s · ~$0.04"——直接把"下一步行动"摆到首屏，**这才是研究伙伴**；
- 把当前的 "What I'd work on next"（在 topic 详情底部）提升到全局首屏；
- 全局命令面板（Cmd+K）的占位文案用研究动词："propose a direction · find papers about · explain this section"。

#### d) **动画几乎为零**
framer-motion 装了但**几乎不用**。"高级感"很大程度上来自 micro-interaction：
- 数字变化时的 count-up 动画（KPI 三联）
- 列表 reorder 时 layout animation
- stage 推进时的进度条 sweep
- 报告生成时打字机式 typing
- hover 时 card 微微 lift（`translateY(-2px) shadow-lg`）

**改**：
- 首屏数字加 `<motion.span>` count-up；
- 卡片 hover 微 lift；
- stage chip 颜色切换给 spring 动画；
- 列表换页用 fade 而不是 hard cut。

每个 200-400ms 的小动画——大厂的"精致感"全靠这些。

#### e) **数据可视化粗糙**
预算页柱状图、趋势页折线——能看出是 recharts/echarts 默认样式。
- Y 轴数字 `0 / 15000 / 30000 / 45000 / 60000` 没有人性化（应是 `0 / 15K / 30K / 45K / 60K`）；
- bar 颜色全部一致（应该 highlight 当前选中阶段，其他降低透明度）；
- 没有 tooltip 与数据点 hover；
- 无空状态插画。

**改**：把所有图表过一遍 design polish——或者干脆抽一个 `<ChartFrame>` wrapper 统一处理 axis formatter / tooltip / empty / loading。

### 9.3 大气感差距

> "大气" = 留白 + 字号 + 节奏 + 不慌不忙

#### a) **留白偏紧**
Sidebar 60px、卡片 padding 20px、卡片 gap 16px——都偏小一档。

**改**：把 sidebar 拓宽到 240px，卡片 padding 24-32px，卡片 gap 24px。**信息少 20%，体验高 50%。**

#### b) **每屏塞太多**
首页一屏：左导航 + 顶栏 chip + hero + KPI 三联 + 6 张卡片网格——共 17 个独立元素。Linear 首屏一般 ≤ 8。

**改**：删掉 KPI 三联（移到 sidebar 底部脚注），让 hero + 进行中列表占满首屏。

#### c) **顶栏 chip 噪音过多**
`已连接 5 个模型 / 2.7M tok / 中文 / ⚙️` 四个 chip 全部静态展示——给人"仪表盘看护工"压力，不是"专业工具"。

**改**：
- `已连接 5 个模型` → 改成一个 ⚙️ 图标，点击展开 detail；
- `2.7M tok` → 同上，并入 ⚙️；
- 顶栏只留：左侧搜索框（Cmd+K trigger）+ 右侧 settings + theme + locale。**减半**。

#### d) **左侧导航 6 项 + 底部 2 个 toggle**
sidebar 太满。**改**：6 项合并为 3 项（前文 P2-1 IA 简化），底部只留主题切换。

### 9.4 易用性差距

#### a) **零认知线索（zero affordance）**
- 流水线节点 `0/5` 看上去**不像可点的**；
- "何时该 force-advance vs 检查就绪度"，UI 没引导；
- "Quality scorecard / dual_gate judge / 1 retries / 7 rubric dims" — 一长串黑话，新用户看不懂、老用户也未必关心。

**改**：
- 关键术语加 `?` 图标 + 简短气泡解释；
- 复杂面板默认折叠，"显示高级"才展开。

#### b) **没有撤销 / 历史**
我今天误创建 topic 22（duplicate），只能 SQL DELETE。一个产品的"安全感"很大程度上来自**所有破坏性操作可撤销**。

**改**：
- 删除 topic、移动 paper、推进 stage 都用 toast + Undo 按钮（5s 内可撤销）；
- 后端实际是 soft-delete + audit log，不是真删。

#### c) **没有键盘**
全篇只能鼠标点击。
- `j/k` 上下选 topic
- `↩` 进 detail
- `e` 编辑
- `?` 显示快捷键 help
- `Cmd+K` 命令面板
- `Cmd+/` 切换 sidebar

**头部产品全部具备。**

#### d) **错误状态太敷衍**
- `还没有实验 — 点击「新建」启动一次自主迭代` 是好的；
- 但 `No review issues recorded` / `暂无事件记录` / `本月暂无使用记录` 这几个空状态都是干文字，**没有插画 / icon / 引导下一步**。

**改**：每个空状态都给：图标 + 一句话原因 + 一个 CTA + 一个学习链接。

#### e) **Loading 全裸**
路由切换 / 数据加载几乎全部"白屏闪烁"。`loading.tsx` 完全没用上 (P1-1 已说)。

#### f) **可访问性 (a11y) 未审**
- 颜色对比度未测；
- focus ring（globals.css 里有 `--ring` token）的实际可见性未走查；
- 键盘 tab 顺序未审；
- 屏幕阅读器 aria-label 未审。

**改**：跑一次 axe-core 自动审计 + 手工 tab-walk 一遍核心流程。

### 9.5 视觉/易用性"立刻可做"清单

| # | 项 | 估时 | 视觉冲击 |
|---|---|------|---------|
| 1 | KPI 三联数字加 count-up + 删 icon + 字号到 56px | 1h | ⭐⭐⭐ |
| 2 | 卡片 hover 加 lift（`hover:-translate-y-0.5 hover:shadow-lg`）| 0.5h | ⭐⭐⭐ |
| 3 | sidebar 拓到 240px + padding 加大 | 0.5h | ⭐⭐ |
| 4 | 顶栏 chip 合并到一个 ⚙️ 入口 | 1h | ⭐⭐⭐ |
| 5 | Hero 副标题改为"研究伙伴语言"（下一动作 + 时间 + cost） | 1h | ⭐⭐⭐⭐ |
| 6 | 所有 chart Y 轴改 `15K / 30K` 格式 | 0.5h | ⭐⭐ |
| 7 | 5 个核心路由 `loading.tsx` + `error.tsx` | 2h | ⭐⭐⭐ |
| 8 | toast + Undo 模式（删除/推进 stage） | 3h | ⭐⭐⭐ |
| 9 | Cmd+K 命令面板 v0 | 4h | ⭐⭐⭐⭐ |
| 10 | axe-core 自动审计 + 修一轮 a11y | 2h | ⭐⭐ |

**全部约 15 小时，可以两天内推完。**

### 9.6 大气感的"公式"

如果只能记一句话：
> **更少的入口 × 更大的留白 × 每个数字都能解释自己 × 每个动作都可撤销 × 每次延迟都有反馈。**

---

## 结语

Atlas 现在的位置：**功能 70 分 / 视觉基底 70 分 / 视觉应用 45 分 / 易用性 40 分 / 工程 65 分 / 状态一致性 40 分**——是一个"研究者用着不错"的内部工具，不是一个"演示给投资人/同行会羡慕"的头部产品。

距离不在做**更多功能**，而在把已有功能**用产品力收敛**：少做 30% 的入口、把 5 个核心 flow 打磨到 0 缺陷、让每个数字都能解释自己。

**下一步建议**：从上面"立即可做"列表前 3 项动手，2 天后再做一次走查，验证 "console 0 error / `/budgets` 数据自洽 / topic 详情副标题简洁" 三个交付目标。
