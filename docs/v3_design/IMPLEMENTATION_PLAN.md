# Research Harness v3 — Researcher Journey Implementation Plan

> **目的**：把 RH 的 6 阶段流水线（Init/Build/Analyze/Propose/Experiment/Write）升级为支持 4 类用户起点 + 显式目标池/方法原子/SOTA 对标 + 自适应 venue + 跨阶段检索触发的端到端研究路径。
>
> **执行约束**：本文档面向"开发能力较弱"的执行模型。每个 Iteration 必须严格按顺序、单 commit 落地，禁止跨步骤、禁止 fake fallback。
>
> **基线**：截止 2026-04-25 commit `4d88652`。6 阶段已对齐，104 个 HTTP endpoint，前端 WorkflowPipeline 已存在。

---

## 0. 全局约束（每个 iteration 都必须遵守）

### 0.1 commit 规范
- 每个 iteration **一个 commit**。
- commit message：`feat(rh-v3): iter-NN <短标题>`，示例：`feat(rh-v3): iter-01 intake_profile schema + endpoints`
- commit 前必须本地跑通该 iteration 的"验收清单"全部项。
- **完成后停下等 review**，不要自动开始下一个 iteration。

### 0.2 后端规范
- DB 迁移文件位置：**`packages/research_harness/migrations/0NN_<name>.sql`**（注意不是 `research_harness/data/migrations/`）
- 编号沿用现有最大编号 +1（**当前最大 056，本批从 057 起**）。
- 后端测试文件位置：**`packages/research_harness_mcp/tests/test_<feature>.py`**（注意不是 `research_harness_mcp/research_harness_mcp/tests/`）
- `record_artifact` 真实签名（见 `orchestrator/service.py:351`）：
  ```python
  service.record_artifact(
      topic_id=tid, stage='init', artifact_type='intake_profile',
      title='Intake Profile', payload=profile_dict,  # payload 是 dict，不是 content=str
  )
  ```
  且必须通过 `OrchestratorService` 实例调用（不是直接 import 函数）。
- 所有 SQL `CREATE TABLE` 必须 `IF NOT EXISTS` + 包含 `CHECK` 约束 + 外键 + `created_at/updated_at` 时间戳。
- 所有新 endpoint 在 `packages/research_harness_mcp/research_harness_mcp/http_api.py`，按现有模块顺序插入。
- 所有 LLM 输出**必须**用 `pydantic` BaseModel 校验后再返回前端。**禁止**直接把原始 LLM 文本返回。
- LLM 调用必须经过 `llm_router`，按 tier 路由。**禁止**直接 import 单一 provider。
- 所有 primitive 写在 `packages/research_harness/research_harness/primitives/<name>_impl.py`，必须调 `record_artifact()` 持久化。
- 端点失败时 `raise HTTPException`，**禁止** `return {"status":"error", "data": fake}`。
- 现有 `domain_suggest` 那种字符串 split 假实现是反例，绝对不允许新增同类。

### 0.3 前端规范
- 所有新 endpoint 必须在 `web/src/lib/api.ts` 里有 typed function；前端组件**禁止**用裸 `fetch`。
- 所有新组件在 `web/src/components/topic/<kebab-name>.tsx`，使用 `tanstack/react-query`。
- 所有组件必须有 4 态：`empty / loading / error / success`，每态都要可见反馈，**禁止**白屏。
- 配色复用 `STAGE_BG_COLORS / STAGE_TEXT_COLORS`，icon 用 `lucide-react`。
- i18n：所有用户可见文案走 `useT()`，CN + EN 双语 key 同步加到 `web/src/lib/i18n/`。
- 移动端：所有新组件 `md:` 断点下不破版（用 chrome devtools 模拟 iPhone 13 验证）。

### 0.4 测试规范
- 后端：`pytest packages/research_harness_mcp/research_harness_mcp/tests/test_<feature>.py -q` 必须全绿。
- 后端覆盖率：每个新 endpoint **至少** 1 正常路径 + 1 异常路径 + 1 边界（如空数据）。
- 前端单元：`pnpm --filter web test web/src/__tests__/<feature>.test.tsx`，覆盖 4 态渲染。
- 前端 E2E：`pnpm --filter web playwright test tests/e2e/<feature>.spec.ts --reporter=list`。
- E2E 必须截图：每个关键步骤截一张，归档 `docs/assets/v3-iter-NN/<step>.png`。
- 手动验收：每个 iteration 完成后填写 `docs/v3_design/acceptance/iter_NN.md`（模板见附录 E）。

### 0.5 启动开发环境（每次开始 iteration 前）
```bash
# 后端
cd research-harness-oss
python -m research_harness_mcp.http_api  # 监听 8000
# 前端
cd web && pnpm dev  # 监听 3000
```
若端口被占用：`lsof -ti:8000 | xargs kill -9` 然后重启。

### 0.6 弱模型自检清单（每个 iteration 提交前必跑）
- [ ] 该 iteration 的所有任务都打了 ✅
- [ ] 后端测试 `pytest -q` 全绿
- [ ] 前端单元测试全绿
- [ ] Playwright E2E 通过 + 截图归档
- [ ] 手动启动 dev 环境，按验收清单点一遍
- [ ] commit message 符合规范
- [ ] **未开始下一个 iteration**

---

## 1. Iteration 总览

| # | 标题 | 后端工作 | 前端工作 | 依赖 |
|---|---|---|---|---|
| 01 | intake_profile 数据层 | 迁移 049 + 2 端点 | — | 无 |
| 02 | intake_profile 向导分流 | — | onboarding 加 persona step + 分支 | 01 |
| 03 | field_brief 后端 primitive | 迁移 050 + 2 端点 + LLM primitive | — | 01 |
| 04 | field_brief 前端展示 | — | analysis-panel 顶部插 FieldBriefCard | 03 |
| 05 | prioritized_goals 后端评分 | 迁移 051 + 4 端点 + 评分函数 | — | 03 |
| 06 | prioritized_goals 前端 | — | analysis-panel 加 GoalPoolCard | 05 |
| 07a | method_atoms 数据 + 采集 | 迁移 052 + 3 端点 + LLM primitive | — | 03 |
| 07b | experiment_matrix 单段 proxy | 迁移 052b + 2 端点 | experiment 区加 MethodAtomsLibrary + Matrix | 07a |
| 08 | venue_decision + style_kit | 迁移 053 + 2 端点 + 2 primitive | write-panel 顶部加 banner + kit | 03 |
| 09 | retrieval_log 跨阶段 | 迁移 054 + endpoint 包装 | 每个 stage 右上加 🔍 trigger | 无 |
| 10 | TFRBench 端到端联调 + Demo | — | Playwright 录全程 | 全部 |

依赖图：01 → 02; 01 → 03 → {04, 05, 07a, 08}; 05 → 06; 07a → 07b; 09 独立; 10 收口。

---

## 2. Iteration 01 — intake_profile 数据层

### 2.1 后端任务

**T1.1** 创建迁移文件 `packages/research_harness/migrations/057_intake_profile.sql`：
```sql
CREATE TABLE IF NOT EXISTS topic_intake_profile (
  topic_id INTEGER PRIMARY KEY,
  persona TEXT NOT NULL CHECK(persona IN ('p1_no_domain','p2_domain_no_topic','p3_topic_weak','p4_topic_strong')),
  domain_confidence INTEGER NOT NULL CHECK(domain_confidence BETWEEN 0 AND 100),
  topic_confidence INTEGER NOT NULL CHECK(topic_confidence BETWEEN 0 AND 100),
  venue_constraint TEXT NOT NULL CHECK(venue_constraint IN ('locked','preferred','open')),
  target_venue TEXT,
  compute_budget TEXT NOT NULL CHECK(compute_budget IN ('cpu_only','single_gpu','multi_gpu','cluster')),
  time_to_deadline_days INTEGER,
  seed_present INTEGER NOT NULL DEFAULT 0,
  raw_notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_intake_persona ON topic_intake_profile(persona);
```

**T1.2** 在 `http_api.py` 找到 `@app.patch("/api/topics/{topic_id}")`（约 line 2478）之后，新增：

- pydantic model `IntakeProfileBody`（所有字段，含 enum 校验）
- `GET /api/topics/{topic_id}/intake-profile` → `IntakeProfileBody | None`，404 if topic 不存在
- `PUT /api/topics/{topic_id}/intake-profile` → 写入或更新；同时通过 `OrchestratorService` 实例调用：
  ```python
  service.record_artifact(
      topic_id=topic_id, stage='init', artifact_type='intake_profile',
      title='Intake Profile', payload=body.model_dump(),
  )
  ```

**T1.3** `OrchestratorService.record_artifact` 真实签名见 `orchestrator/service.py:351`：参数名是 `payload`（类型 `dict`），不是 `content` 字符串。后续所有 iteration 同此规则。

### 2.2 测试任务

**T1.4** 新建 `packages/research_harness_mcp/tests/test_intake_profile.py`：
- `test_put_intake_profile_creates_record` — PUT 后 GET 能拿回
- `test_put_invalid_persona_400` — persona 不在枚举返回 400
- `test_put_invalid_compute_budget_400`
- `test_get_404_when_topic_missing`
- `test_put_writes_artifact` — 写入后 `project_artifacts` 表能查到 stage='init' artifact_type='intake_profile'
- `test_put_updates_existing` — 第二次 PUT 更新而不是插入

运行：
```bash
pytest packages/research_harness_mcp/tests/test_intake_profile.py -q
```

### 2.3 验收清单

- [ ] 迁移自动跑通（重启服务后 sqlite 表存在：`sqlite3 .research-harness/pool.db ".schema topic_intake_profile"`）
- [ ] 6 个 pytest 全绿
- [ ] curl 实测：
  ```bash
  curl -X PUT http://localhost:8000/api/topics/1/intake-profile \
    -H "Content-Type: application/json" \
    -d '{"persona":"p3_topic_weak","domain_confidence":80,"topic_confidence":60,"venue_constraint":"preferred","target_venue":"EMNLP","compute_budget":"single_gpu","time_to_deadline_days":120,"seed_present":0}'
  curl http://localhost:8000/api/topics/1/intake-profile  # 应返回上面的内容
  ```
- [ ] sqlite 查询：`SELECT * FROM project_artifacts WHERE topic_id=1 AND artifact_type='intake_profile';` 应有记录
- [ ] commit：`feat(rh-v3): iter-01 intake_profile schema + endpoints`

---

## 3. Iteration 02 — intake_profile 向导分流

### 3.1 前端任务（产品经理视角）

**T2.1** 在 `web/src/app/onboarding/page.tsx`：

- 把现有 `STEPS` 常量改为函数 `getSteps(persona: Persona | null): string[]`：
  - persona 为 null → `['Persona']`（只显示第一步）
  - p1 → `['Persona','Domain Discovery','Constraints','Agents','Done']`
  - p2 → `['Persona','Domain Selection','Topic Hint','Constraints','Agents','Done']`
  - p3 → `['Persona','Topic Brief','Constraints','Agents','Done']`
  - p4 → `['Persona','Topic Brief','Seed Material','Constraints','Agents','Done']`
- `WizardData` 增加字段：`persona, domainConfidence, topicConfidence, venueConstraint, targetVenue, computeBudget, deadlineDays, seedPresent, rawNotes`

**T2.2** 新建组件 `web/src/components/onboarding/persona-card.tsx`：
- props: `{ persona, icon, title, scenario, selected, onClick }`
- 卡片尺寸：240×160px 桌面；移动端 full-width
- selected 时 ring-2 ring-blue-600 + shadow-lg
- hover: scale-105 transition

**T2.3** Persona Step 渲染 4 张卡片（grid-cols-2 桌面 / cols-1 移动）：
| persona | icon | title | scenario |
|---|---|---|---|
| p1_no_domain | 🌱 (Sprout from lucide) | "I'm new to AI research" | "Show me the AI landscape and help me pick a domain" |
| p2_domain_no_topic | 🧭 (Compass) | "I know my domain" | "Help me find a topic worth pursuing" |
| p3_topic_weak | 🎯 (Target) | "I have a topic" | "Map the field for me — datasets, SOTA, venues" |
| p4_topic_strong | 🚀 (Rocket) | "I have topic + seeds" | "Fast track with my prior work" |

**T2.4** Constraints Step（所有 persona 都有）：
- 三段表单：
  - Venue constraint：3 选 1 segmented control（Locked / Preferred / Open）+ 当 Locked|Preferred 时显示 venue 文本输入
  - Compute budget：4 选 1 卡片（CPU only / Single GPU / Multi-GPU / Cluster）
  - Deadline：日期选择器（默认 90 天后），换算成 `time_to_deadline_days`

**T2.5** 完成时（finishMut）：
- 创建/找到 topic（沿用现有逻辑），拿到 topicId
- 调 `setIntakeProfile(topicId, { ...mapped fields })`
- 跳转 `/topics/{topicId}`

**T2.6** 在 `web/src/lib/api.ts` 增加：
```ts
export interface IntakeProfile { /* 字段 */ }
export async function setIntakeProfile(topicId: number, body: IntakeProfile): Promise<IntakeProfile>;
export async function fetchIntakeProfile(topicId: number): Promise<IntakeProfile | null>;
```

### 3.2 测试任务

**T2.7** 单元测试 `web/src/__tests__/onboarding-personas.test.tsx`：
- 渲染 4 张 persona 卡片
- 点击 p1 → 步骤数 = 5
- 点击 p4 → 步骤数 = 6 且包含 "Seed Material"
- venueConstraint=Locked → target_venue 输入框 required

**T2.8** E2E `web/tests/e2e/onboarding-personas.spec.ts`：
- 4 个测试 case，每种 persona 走完整向导，断言最终 `GET /api/topics/{id}/intake-profile` 返回正确 persona
- 每步 `await page.screenshot({ path: 'docs/assets/v3-iter-02/p{N}-step-{i}.png' })`

运行：
```bash
cd web
pnpm test src/__tests__/onboarding-personas.test.tsx
pnpm playwright test tests/e2e/onboarding-personas.spec.ts --reporter=list
```

### 3.3 验收清单

- [ ] 4 张 persona 卡片视觉对齐 mockup（图标 + 标题 + 场景文案居中，不截断）
- [ ] 选择 p1 → 步骤数 5，选择 p4 → 步骤数 6
- [ ] 移动端（375×667）卡片不破版，单列排列
- [ ] 完成向导后 DB 里 4 条不同 persona 记录字段正确
- [ ] CN/EN 双语切换无遗漏
- [ ] 截图归档 `docs/assets/v3-iter-02/`（至少 4×3=12 张）
- [ ] commit：`feat(rh-v3): iter-02 onboarding persona branching`

---

## 4. Iteration 03 — field_brief 后端 primitive

### 4.1 后端任务

**T3.1** 迁移 `050_field_brief_meta.sql`：
```sql
CREATE TABLE IF NOT EXISTS field_brief_meta (
  topic_id INTEGER PRIMARY KEY,
  artifact_id INTEGER NOT NULL,
  paper_count_at_build INTEGER NOT NULL,
  built_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  stale INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
  FOREIGN KEY (artifact_id) REFERENCES project_artifacts(id) ON DELETE CASCADE
);
```

**T3.2** 创建 `packages/research_harness/research_harness/primitives/field_brief_impl.py`：

pydantic schema：
```python
class Dataset(BaseModel):
    name: str
    size: str | None
    license: str | None
    gpu_req: Literal['cpu','low','medium','high']
class Baseline(BaseModel):
    name: str
    paper_id: int | None
    metric_name: str
    metric_value: float
class Challenge(BaseModel):
    problem: str
    maturity: Literal['saturated','hot','niche']
class VenueOption(BaseModel):
    name: str
    deadline: str | None  # ISO date
    acceptance_rate: float | None
class FieldBrief(BaseModel):
    datasets: list[Dataset]
    baselines: list[Baseline]
    narrative_patterns: list[str]
    open_challenges: list[Challenge]
    compute_bands: list[str]
    venue_options: list[VenueOption]
    saturation_score: float = Field(ge=0, le=1)
```

主函数 `def build_field_brief(topic_id: int) -> FieldBrief`：
- 读取该 topic 所有 paper card（`SELECT ... FROM papers JOIN topic_papers ...`）
- 拼 prompt（系统提示 + 论文卡片摘要列表 + 严格 JSON schema 输出要求）
- 调 `llm_router.complete(prompt, tier='medium', expect_json=True)`
- pydantic 校验
- 写 artifact + 更新 `field_brief_meta`
- raise 而不是 fallback fake

**T3.3** 在 `http_api.py` 添加：
- `POST /api/topics/{topic_id}/field-brief` → 触发 build，返回 FieldBrief JSON
- `GET /api/topics/{topic_id}/field-brief` → 返回最新 field_brief artifact 内容 + meta（包含 stale 标志）

**T3.4** Freshness 标记：在现有 `paper_ingest` 端点完成后追加：
```python
# 检查并标记 stale
meta = conn.execute("SELECT paper_count_at_build FROM field_brief_meta WHERE topic_id=?", (tid,)).fetchone()
if meta:
    current = conn.execute("SELECT COUNT(*) FROM topic_papers WHERE topic_id=?", (tid,)).fetchone()[0]
    if current > meta["paper_count_at_build"] * 1.15:
        conn.execute("UPDATE field_brief_meta SET stale=1 WHERE topic_id=?", (tid,))
```
另：定时任务跳过（用读取时计算 `built_at` 是否 >21 天），若读取时 `(now - built_at).days > 21` 也置 stale=1。

### 4.2 测试任务

**T3.5** 新建 `packages/research_harness_mcp/research_harness_mcp/tests/test_field_brief.py`：
- mock `llm_router.complete` 返回固定 JSON
- `test_build_returns_valid_schema`
- `test_build_writes_artifact`
- `test_build_writes_meta`
- `test_get_returns_latest`
- `test_invalid_llm_output_raises_500`（mock 返回不合法 JSON）
- `test_stale_flag_after_paper_ingest`（mock 加 paper 触发 stale）
- `test_stale_flag_after_21_days`（手工把 built_at 改为 22 天前）

### 4.3 验收清单

- [ ] 7 个 pytest 全绿
- [ ] 用 TFRBench topic 实测：`curl -X POST http://localhost:8000/api/topics/{tfr_id}/field-brief` 返回 6 个 list + saturation_score
- [ ] sqlite 查 `SELECT * FROM field_brief_meta;` 有记录
- [ ] 手动加一篇 paper 后再 GET，stale=1
- [ ] LLM 失败时返回 500（**不是** 200 + fake data）
- [ ] commit：`feat(rh-v3): iter-03 field_brief primitive + freshness`

---

## 5. Iteration 04 — field_brief 前端展示

### 5.1 前端任务

**T4.1** 新建 `web/src/components/topic/field-brief-card.tsx`：

布局（产品经理设计）：
```
┌───────────────────────────────────────────────────────┐
│  Field Brief         [stale pill]    [Refresh button] │
│  ─────────────────────────────────────────────────────│
│  Saturation: ▓▓▓▓░░░░░░  0.42  (Yellow zone)          │
│  ─────────────────────────────────────────────────────│
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐           │
│  │ 📊 │ │ 🎯 │ │ ✍️ │ │ ❓ │ │ 💻 │ │ 📅 │           │
│  │ 5  │ │ 8  │ │ 4  │ │ 12 │ │ 3  │ │ 6  │           │
│  │ DS │ │ BL │ │ NP │ │ CH │ │ CB │ │ VO │           │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘           │
│  (点击 tile 展开 list)                                 │
└───────────────────────────────────────────────────────┘
```

- saturation 进度条颜色：`<0.33` blue / `0.33-0.66` yellow / `>0.66` red，文案对应 `Blue ocean / Yellow zone / Red ocean`
- 6 个 tile 横向 grid，hover 高亮，点击切换展开下方 list 区
- list 区每个 entry 显示完整字段（dataset 显示 name/size/license/gpu_req 等）
- stale pill：橙色 `Outdated · {n} new papers since last build`
- empty 态：illustration + 大字 `No field brief yet` + button `Generate Field Brief`
- loading 态：skeleton 6 个 tile + 骨架进度条
- error 态：红色 alert + 重试按钮

**T4.2** `web/src/lib/api.ts` 增加：
```ts
export interface FieldBrief { /* 字段 */ }
export interface FieldBriefResponse { brief: FieldBrief; meta: { stale: boolean; built_at: string; paper_count_at_build: number } }
export async function fetchFieldBrief(topicId: number): Promise<FieldBriefResponse | null>;
export async function rebuildFieldBrief(topicId: number): Promise<FieldBrief>;
```

**T4.3** 在 `web/src/components/topic/analysis-panel.tsx` 顶部插入 `<FieldBriefCard topicId={topicId} />`（在所有现有 card 之上）。

**T4.4** 在 `web/src/components/topic/workflow-pipeline.tsx` 的 `build` 阶段把现有 `expansion_hint` 步骤之后增加一个 step：
```ts
{ id: 'field_brief', label: '生成 Field Brief', description: '从论文池蒸馏 6 维结构化快照', run: () => rebuildFieldBrief(topicId) }
```

### 5.2 测试任务

**T4.5** 单元 `web/src/__tests__/field-brief-card.test.tsx`：4 态各一个 case + saturation 颜色断言。

**T4.6** E2E `web/tests/e2e/field-brief.spec.ts`：
- 进入 TFRBench topic 详情
- 点击 Generate
- 等待 success
- 断言 6 个 tile 显示
- 点击 datasets tile，下方 list 出现
- 截图 4 张归档

### 5.3 验收清单

- [ ] 4 态截图齐全
- [ ] saturation 颜色正确切换
- [ ] tile 点击展开/折叠流畅
- [ ] WorkflowPipeline build 阶段新增的 field_brief 步骤可点击且成功
- [ ] 移动端不破版
- [ ] CN/EN 双语 key 已加
- [ ] commit：`feat(rh-v3): iter-04 field_brief card UI`

---

## 6. Iteration 05 — prioritized_goals 后端评分

### 6.1 后端任务

**T5.1** 迁移 `051_goal_pool.sql`：
```sql
CREATE TABLE IF NOT EXISTS goal_pool (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  dataset TEXT NOT NULL,
  baseline TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  baseline_metric REAL NOT NULL,
  target_metric_delta REAL NOT NULL,  -- 期望提升的 delta
  target_venue TEXT,
  time_window_days INTEGER,
  score REAL NOT NULL,
  scoring_breakdown TEXT NOT NULL,  -- JSON: {headroom, feasibility, evidence_coverage, venue_fit, compute_fit}
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','done','skipped')),
  priority_rank INTEGER NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_goal_topic_rank ON goal_pool(topic_id, priority_rank);
```

**T5.2** 创建 `packages/research_harness/research_harness/primitives/goal_pool_impl.py`：

```python
def _score_goal(goal_raw: dict, field_brief: dict, intake: dict) -> tuple[float, dict]:
    """纯函数评分，禁止 LLM 算分。"""
    # headroom: target_metric_delta / baseline_metric 归一到 0-1
    # feasibility: 1 - challenge maturity 'saturated' weight
    # evidence_coverage: matching baselines in field_brief / total baselines
    # venue_fit: target_venue in field_brief.venue_options ? 1 : 0.3
    # compute_fit: gpu_req <= intake.compute_budget ? 1 : 0
    # ...
    breakdown = {...}
    score = (0.35*breakdown['headroom'] + 0.25*breakdown['feasibility']
             + 0.20*breakdown['evidence_coverage'] + 0.10*breakdown['venue_fit']
             + 0.10*breakdown['compute_fit'])
    return score, breakdown

def build_goal_pool(topic_id: int, max_goals: int = 5) -> list[Goal]:
    field_brief = _load_latest_field_brief(topic_id)  # raise if missing
    intake = _load_intake_profile(topic_id)            # raise if missing
    raw_candidates = _llm_propose_candidates(field_brief, intake, n=10)  # tier=light
    scored = [(_score_goal(c, field_brief, intake), c) for c in raw_candidates]
    # 硬拒绝
    scored = [(s, c) for (s, b), c in scored if b['evidence_coverage'] >= 0.6 and b['compute_fit'] >= 0.5]
    scored.sort(key=lambda x: -x[0][0])
    top = scored[:max_goals]
    # 写 DB + record_artifact
    ...
```

**T5.3** 在 `http_api.py` 添加：
- `POST /api/topics/{topic_id}/goal-pool` → 重建并返回 list
- `GET /api/topics/{topic_id}/goals` → 返回当前 list（按 priority_rank asc）
- `PATCH /api/topics/{topic_id}/goals/{goal_id}` → body 支持 `status / priority_rank` 修改
- `DELETE /api/topics/{topic_id}/goals/{goal_id}` → 软删除（status='skipped'）

### 6.2 测试任务

**T5.4** `tests/test_goal_pool_scoring.py`（纯函数）：
- `test_score_headroom_high_baseline_low_target` 等 6 个 case，每个 case 断言 score 与 breakdown 关键值

**T5.5** `tests/test_goal_pool_endpoints.py`：
- mock LLM 返回 8 候选
- POST → 返回 ≤5 条
- GET → 顺序按 priority_rank
- PATCH → 改 status 后再 GET 字段更新
- 当 field_brief 不存在时 POST 返回 409 with msg

### 6.3 验收清单

- [ ] scoring 6 case 全绿
- [ ] endpoint 4 个 case 全绿
- [ ] curl 实测 TFRBench topic 拿到 goal list 且 scoring_breakdown 字段非空
- [ ] commit：`feat(rh-v3): iter-05 goal_pool scoring + endpoints`

---

## 7. Iteration 06 — prioritized_goals 前端

### 7.1 前端任务

**T6.1** 新建 `web/src/components/topic/goal-pool-card.tsx`：

布局：
```
┌───────────────────────────────────────────────────────┐
│  Goal Pool                          [Build/Rebuild]   │
│  ─────────────────────────────────────────────────────│
│  ┌─┬────────┬──────────┬──────┬───────┬──────┬────┐  │
│  │#│Dataset │Baseline  │Δ目标 │Venue  │Score │Op  │  │
│  ├─┼────────┼──────────┼──────┼───────┼──────┼────┤  │
│  │1│apple   │TimeLLM   │-5MAPE│EMNLP  │0.84  │⬆⬇🚫│  │
│  │2│NYC_Taxi│Chronos   │-8MAPE│NeurIPS│0.76  │... │  │
│  └─┴────────┴──────────┴──────┴───────┴──────┴────┘  │
│  hover score → 弹出 5 分量分解条形图                  │
└───────────────────────────────────────────────────────┘
```

- 表格用 shadcn/ui Table
- score 列 hover 用 Recharts BarChart 渲染 5 分量（headroom/feasibility/evidence_coverage/venue_fit/compute_fit）
- 操作列三个 icon button：⬆ priority_rank-1 / ⬇ +1 / 🚫 status='skipped'
- 头部 [Build/Rebuild] 按钮：若有数据=Rebuild，无数据=Build
- 当前正在 active 实验的 goal 行用 `bg-blue-50 dark:bg-blue-950 border-l-4 border-blue-600` 高亮（active 判定：status='active' 且 priority_rank=1）
- empty 态：CTA "Build Goal Pool"
- error 态：若 field_brief 不存在则提示 "Generate Field Brief first" + 跳转链接

**T6.2** `api.ts` 增加 `fetchGoals / buildGoalPool / updateGoal / deleteGoal`。

**T6.3** 在 `analysis-panel.tsx` 中 `<FieldBriefCard />` 之后插入 `<GoalPoolCard topicId={topicId} />`。

**T6.4** WorkflowPipeline analyze 阶段在现有 3 step 之后增加：
```ts
{ id: 'goal_pool', label: '构建目标池', description: 'SOTA 对标目标 + 评分', run: () => buildGoalPool(topicId) }
```

### 7.2 测试任务

**T6.5** 单元 4 态 + 操作回调断言。
**T6.6** E2E：build → 表格 5 行 → 点击 ⬆ → 顺序变化 → 点击 🚫 → 行消失 → 截图 5 张。

### 7.3 验收清单

- [ ] hover score 弹出条形图正确
- [ ] active goal 高亮可见
- [ ] field_brief 缺失时提示链接可跳转
- [ ] commit：`feat(rh-v3): iter-06 goal_pool UI + interactions`

---

## 8. Iteration 07a — method_atoms 数据 + 采集

### 8.1 后端任务

**T7a.1** 迁移 `052_method_atoms.sql`：
```sql
CREATE TABLE IF NOT EXISTS method_atoms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  source_paper_id INTEGER NOT NULL,
  atom_type TEXT NOT NULL CHECK(atom_type IN ('loss','data_trick','augmentation','training_schedule','inference_heuristic','micro_block')),
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  deps TEXT NOT NULL DEFAULT '[]',  -- JSON list of atom names this depends on
  reported_gain TEXT,                -- free text, e.g. "+2.3 BLEU"
  reuse_risk TEXT NOT NULL CHECK(reuse_risk IN ('low','medium','high')),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
  FOREIGN KEY (source_paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atom_topic_type ON method_atoms(topic_id, atom_type);
```

**T7a.2** Primitive `harvest_atoms_impl.py`：
- 函数 `harvest_atoms_from_paper(topic_id, paper_id) -> list[Atom]`
- 输入：paper card + section "Method"
- LLM tier=light，prompt 指定输出严格 schema list
- pydantic 校验，写 DB

**T7a.3** Endpoints：
- `POST /api/topics/{topic_id}/method-atoms/harvest` body: `{paper_ids: [int]}` → 批量采集
- `GET /api/topics/{topic_id}/method-atoms?atom_type=...` → 列表
- `DELETE /api/method-atoms/{atom_id}`

### 8.2 测试

**T7a.4** mock 1 篇 paper 返回 6 类原子，断言 DB 写入。

### 8.3 验收

- [ ] TFRBench 选 5 篇 paper 一键 harvest，DB 至少 10 条原子
- [ ] commit：`feat(rh-v3): iter-07a method_atoms harvest`

---

## 9. Iteration 07b — experiment_matrix 单段 proxy

### 9.1 后端任务

**T7b.1** 迁移 `052b_experiment_matrix.sql`：
```sql
CREATE TABLE IF NOT EXISTS experiment_matrix_cell (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  atom_combo TEXT NOT NULL,  -- JSON list of atom_ids
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','proxy_running','proxy_done','pruned','promoted')),
  proxy_metric_name TEXT,
  proxy_metric_value REAL,
  baseline_metric REAL,
  delta_to_sota REAL,
  proxy_run_id TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (goal_id) REFERENCES goal_pool(id) ON DELETE CASCADE
);
```

**T7b.2** Primitive `experiment_matrix_impl.py`：
- `build_matrix(topic_id) -> list[Cell]`：active goals × all atoms（**只 single-atom**，combo=[atom_id]），生成 pending cells
- `run_proxy_pass(topic_id, max_cells=20) -> list[Cell]`：每个 pending cell 调 `code_generate` + sandbox 跑微型 epoch，填 metric
- 剪枝规则：delta_to_sota <= 0 → status='pruned'；> 0 → status='promoted'

**T7b.3** Endpoints：
- `POST /api/topics/{topic_id}/experiment-matrix/build`
- `POST /api/topics/{topic_id}/experiment-matrix/proxy` body: `{max_cells: 20}`
- `GET /api/topics/{topic_id}/experiment-matrix`

### 9.2 前端

**T7b.4** 新建 `web/src/components/topic/method-atoms-library.tsx`（左 2/5 宽）：
- 6 个 atom_type 折叠分组
- 每个 atom 一行：name + reuse_risk pill + delete icon
- "Harvest from paper" 按钮 → 弹出 modal 选 paper

**T7b.5** 新建 `web/src/components/topic/experiment-matrix-card.tsx`（右 3/5 宽）：
- 网格：行=atoms 列=goals
- cell 颜色：promoted=green / pruned=red / pending=gray / running=blue pulse
- cell 内显示 delta_to_sota 数字
- 顶部按钮 "Build Matrix" / "Run Proxy Pass (max 20)"

**T7b.6** 在 `topics/[id]/page.tsx` 现有 ExperimentLeaderboardCard 上方插入两列布局容器，容纳 atoms library + matrix。

### 9.3 测试

**T7b.7** 后端：mock atom + sandbox，断言 cell 状态流转。
**T7b.8** E2E：选 3 atoms × 2 goals → matrix 6 cells → run proxy → 部分变绿部分变红 → 截图。

### 9.4 验收

- [ ] 矩阵渲染正确，颜色对应状态
- [ ] proxy pass 完成后 cell 数字可见
- [ ] commit：`feat(rh-v3): iter-07b experiment_matrix proxy pass + UI`

---

## 10. Iteration 08 — venue_decision + style_kit

### 10.1 后端

**T8.1** 迁移 `053_venue_decision.sql`：
```sql
CREATE TABLE IF NOT EXISTS venue_decision (
  topic_id INTEGER PRIMARY KEY,
  decided_venue TEXT NOT NULL,
  decision_basis TEXT NOT NULL,  -- JSON
  fit_risk TEXT,                  -- JSON list of risks
  decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS venue_style_kit (
  topic_id INTEGER PRIMARY KEY,
  venue TEXT NOT NULL,
  avg_section_lengths TEXT NOT NULL,  -- JSON {introduction: 800, ...}
  citation_density REAL NOT NULL,
  hedging_terms TEXT NOT NULL,        -- JSON top-20 list
  source_paper_ids TEXT NOT NULL,     -- JSON list of paper_ids used
  built_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
```

**T8.2** Primitives：
- `venue_decision_impl.py`：读 intake.venue_constraint + field_brief.venue_options + 当前最佳 cell delta_to_sota
  - constraint=locked → decided_venue=intake.target_venue，emit fit_risk if 当前最佳 delta < acceptance_bar 阈值
  - constraint=preferred → 同 locked 但允许 fit_risk 触发"建议换 venue X"
  - constraint=open → 在 venue_options 中 argmax(delta_fit × deadline_fit)
- `venue_style_kit_impl.py`：读 paper_pool 中该 venue 命中 3-5 篇，每篇调 paperindex 抽 section 长度 / 引用数 / 用词 → 聚合

**T8.3** Endpoints：
- `POST /api/topics/{topic_id}/venue-decision`
- `GET /api/topics/{topic_id}/venue-decision`
- `POST /api/topics/{topic_id}/venue-style-kit`
- `GET /api/topics/{topic_id}/venue-style-kit`

### 10.2 前端

**T8.4** 在 `web/src/components/topic/write-panel.tsx` 顶部插入：
- `VenueDecisionBanner`：显示 decided_venue + 截止日倒计时（红/黄/绿三色）+ fit_risk 数量徽章
- 点击展开显示 decision_basis JSON 树形视图

**T8.5** banner 下方插入 `VenueStyleKitCard`：
- 4 个 metric tile：avg intro length / citation density / hedging top-3 / source paper 数
- "Apply style to drafts" 按钮 → 设置一个 topic-level flag，后续 `draft_section` 调用时把 style_kit 注入 prompt

**T8.6** `draft_section` 后端 primitive 增加可选参数 `style_kit_topic_id`，若提供则把 style_kit JSON 拼入 system prompt。

### 10.3 测试 + 验收

**T8.7** 单元 + E2E + 验收清单：
- [ ] locked 模式不允许换 venue
- [ ] preferred 模式 fit_risk 显示建议
- [ ] open 模式自动选 venue
- [ ] style_kit 应用后 draft 长度 / 引用密度向 venue 风格靠拢（手动验证 1 篇）
- [ ] commit：`feat(rh-v3): iter-08 venue_decision + style_kit`

---

## 11. Iteration 09 — retrieval_log 跨阶段触发

### 11.1 后端

**T9.1** 迁移 `054_retrieval_log.sql`：
```sql
CREATE TABLE IF NOT EXISTS retrieval_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  stage TEXT NOT NULL,
  trigger_reason TEXT NOT NULL CHECK(trigger_reason IN ('missing_evidence','weak_baseline','new_atom_idea','venue_pattern','user_request')),
  query TEXT NOT NULL,
  results_count INTEGER NOT NULL DEFAULT 0,
  ingested_paper_ids TEXT NOT NULL DEFAULT '[]',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_retrieval_topic_stage ON retrieval_log(topic_id, stage);
```

**T9.2** 包装现有 `POST /api/papers/search`：增加可选 body 字段 `{topic_id, stage, trigger_reason}`；若三者齐全则在搜索完成后写一条 retrieval_log。

**T9.3** 增加 `GET /api/topics/{topic_id}/retrieval-log`。

### 11.2 前端

**T9.4** 新建 `web/src/components/topic/retrieval-trigger-button.tsx`：
- 圆形小按钮 🔍，固定挂在每个 panel 右上角
- 点击弹 modal：select reason + textarea query + 触发 search
- search 结果展示后用户勾选 ingest，ingest 完成回写 retrieval_log

**T9.5** 在以下组件右上角各挂一个：
- `analysis-panel.tsx`（stage='analyze'）
- `experiment-leaderboard-card.tsx`（stage='experiment'）
- `write-panel.tsx`（stage='write'）
- `field-brief-card.tsx`（stage='build'）

**T9.6** 在 `expansion-panel.tsx` 时间线里穿插 retrieval_log 事件（区别于现有 expansion 事件，用 🔍 icon 区分）。

### 11.3 验收

- [ ] 4 个 panel 都能触发 retrieval
- [ ] DB 5 种 reason 都能写入
- [ ] expansion timeline 显示混合事件
- [ ] commit：`feat(rh-v3): iter-09 retrieval_trigger cross-stage`

---

## 12. Iteration 10 — TFRBench 端到端联调 + Demo

### 12.1 任务

**T10.1** 用一个全新 topic（不复用 TFRBench 已有）走完整流程：
1. 从首页进 onboarding，选 p3 persona
2. Constraints：venue_constraint=preferred / target=EMNLP / compute=single_gpu / deadline=120
3. 进入 topic 详情，触发 papers/search ingest 30 篇 time series 论文
4. 触发 field_brief
5. 触发 goal_pool
6. 选 5 篇 paper 触发 method_atoms harvest
7. build experiment_matrix → run proxy
8. 触发 venue_decision + style_kit
9. write outline + draft introduction（应用 style_kit）
10. 任意阶段触发一次 retrieval

**T10.2** 全程 Playwright 录制 mp4：`docs/assets/v3-demo/full-journey.mp4`

**T10.3** 写 `docs/v3_design/RELEASE_NOTES.md`：列出所有新 artifact / 端点 / 组件 / 测试。

**T10.4** 写 `docs/验收指南_v3.md`：人工验收 checklist 100 项。

### 12.2 验收

- [ ] mp4 完整无中断
- [ ] 9 个新 artifact 全部在 DB
- [ ] 新 endpoint 全部可 curl
- [ ] 9 类 UI 组件都可点击且有反馈
- [ ] commit：`feat(rh-v3): iter-10 e2e demo + release notes`

---

## 13. 附录

### 附录 A — API 命名规范
- 资源复数：`/api/topics/{id}/method-atoms`（不是 method-atom）
- 动作 RPC 风格：`/api/topics/{id}/field-brief`（POST=build/rebuild，GET=read latest）
- 子资源 PATCH 走单数：`/api/topics/{id}/goals/{goal_id}`

### 附录 B — 测试基础设施
- 后端 fixture 在 `packages/research_harness_mcp/research_harness_mcp/tests/conftest.py`
- 前端测试用 vitest + React Testing Library
- E2E 用 Playwright，配置在 `web/playwright.config.ts`
- E2E 默认 baseURL=`http://localhost:3000`，需要先 `pnpm dev`

### 附录 C — 前端组件规范
- 文件命名：kebab-case，`<noun-noun>.tsx`
- props 接口：`interface Props {...}`，写在组件文件顶部
- 必有 4 态：在组件内用 `if (loading) return <SkeletonX/>` 等显式分支
- 避免 100% 复用 shadcn 组件而忽略 design 一致性，参考 `next-stage-hero.tsx` 风格

### 附录 D — 故障兜底（硬约束）
- LLM 调用失败：raise，让前端显示 error 态
- DB 写入失败：raise + rollback
- 缺前置 artifact（如 goal_pool 需要 field_brief）：返回 409 Conflict + msg 指明缺什么
- **绝对禁止** stub data 假装成功

### 附录 E — 验收文档模板（每个 iteration 一份）

文件：`docs/v3_design/acceptance/iter_NN.md`

```markdown
# Iter NN 验收报告

## 自检
- [ ] 后端 pytest 全绿（粘贴最后 5 行输出）
- [ ] 前端单元测试全绿
- [ ] Playwright E2E 全绿
- [ ] 手动 dev 环境点击通过

## 截图
（粘贴每态截图）

## 已知问题
（列遗留 bug 或 TODO）

## 演示视频
（可选：mp4 链接）
```

### 附录 F — 与 codex 的协议
若 iteration 中遇到设计模糊：
1. 在 `docs/v3_design/questions/iter_NN_q.md` 写下问题
2. 用 `codex:codex-rescue` agent 启动一次对抗审查
3. 把结论 append 回该问题文件再继续

---

## 14. 总体进度跟踪

进度文件：`docs/v3_design/PROGRESS.md`，每 iteration 完成后更新一行：
```
| Iter | 状态 | commit | acceptance | 备注 |
|------|------|--------|------------|------|
| 01   | ✅   | abc123 | iter_01.md | -    |
| 02   | 🚧   | -      | -          | -    |
```

---

> **执行入口**：从 § 2 (Iteration 01) 开始，按顺序执行。每个 iteration 完成验收清单全部勾选 + commit 后**停下**等待 review，不要自动开始下一个。
