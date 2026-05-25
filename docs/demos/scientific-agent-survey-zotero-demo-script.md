# Zotero × Research Harness Demo 脚本

## 从 Zotero 论文库到一份可信综述 PDF

**Demo 主题**：大模型驱动科研智能体综述：长程自动化、证据约束与可信工作流治理
**目标观众**：科研工具用户、研究生/博士生、对 Deep Research Agent / AI Scientist 方向感兴趣的研究者
**建议时长**：3–4 分钟完整演示；可剪成 90 秒小红书版本
**最终产物**：一份由 RH 从 Zotero/RH 证据池生成的《综述选题与证据地图 PDF》

---

## 1. 一句话记忆点

> **不是让 AI 在 Zotero 里陪我聊天，而是让 Zotero 变成一台会检索、会读证据、会守流程、最后能产出综述材料的科研驾驶舱。**

---

## 2. Demo 要展示的核心能力

| 核心能力 | Zotero 插件中的可见画面 | 观众应感受到的价值 |
|---|---|---|
| 上下文感知 | 目录状态是 topic/collection mode；选中论文后是 paper mode | 插件知道我是在整理方向，还是在读单篇论文 |
| 长程自动化 | 从主题初始化、补论文、抽证据、做 taxonomy 到生成 PDF | 不是单轮问答，而是在推进完整科研流程 |
| 证据约束 | 每个结论背后有论文、claim、citation、冲突/限制 | AI 不是顺嘴总结，而是被证据牵住 |
| 可信工作流治理 | 所有写 Zotero / 生成文件动作先 dry-run，再确认 apply | 不让模型直接乱改库，用户始终掌握控制权 |
| 双向同步 | RH 推荐/精读论文可以补回 Zotero，最终 PDF 可回挂到 Zotero | Zotero 不再是终点，而是研究工作流入口 |

---

## 3. Demo 环境设定

### Zotero Collection

```text
Research Harness / 科研智能体综述
```

### RH Topic

```text
LLM-driven Scientific Research Agents Survey
```

### 代表性论文

拍摄时可以准备这些论文作为可见条目：

1. Towards Scientific Intelligence: A Survey of LLM-based Scientific Agents
2. From AI for Science to Agentic Science: A Survey on Autonomous Scientific Discovery
3. Deep Research Bench: Evaluating AI Web Research Agents
4. Cited but Not Verified: Parsing and Evaluating Source Attribution in LLM Deep Research Agents
5. SciIntegrity-Bench: A Benchmark for Evaluating Academic Integrity in AI Scientist Systems
6. PARNESS: A Paper Harness for End-to-End Automated Scientific Research
7. Talk Freely, Execute Strictly: Schema-Gated Agentic AI for Flexible and Reproducible Scientific Workflows

> 拍摄建议：Zotero 左侧 collection 名称要非常清晰，右侧 RH 面板固定打开，输入框上方保留历史对话即可，不要出现多余的小窗口。

---

## 4. 完整演示脚本（3–4 分钟）

### Scene 0：开场钩子，5–10 秒

**画面**：Zotero 打开，左侧选中 `Research Harness / 科研智能体综述`，右侧 RH 面板为空闲状态。

**旁白**：

> “我最近在准备一篇综述：大模型驱动科研智能体。问题是，文献太多了，Deep Research、AI Scientist、证据约束、可信工作流全都混在一起。普通 Zotero 只能帮我存 PDF，但我想要的是：它能不能直接帮我把这个综述推进起来？”

**屏幕字幕**：

```text
从 Zotero 论文库 → 可信综述 PDF
```

---

### Scene 1：目录模式，插件理解“这是一个研究方向”，20–30 秒

**操作**：不选单篇论文，只停留在 collection。输入：

```text
这个目录是一篇综述的论文池。请判断这个综述可以怎么推进。
```

**预期 RH 面板输出**：

```text
当前上下文：Collection mode
主题：科研智能体综述
可执行动作：
1. 初始化/绑定 RH topic
2. 检查论文池覆盖度
3. 推荐缺失论文补库
4. 生成三轴 taxonomy 草案
5. 生成综述 proposal PDF（需先通过 gate）
```

**旁白**：

> “第一点很关键：没有选中论文时，它不会假装在读某一篇 paper，而是切到目录模式，把整个 collection 当作一个研究主题。”

**要展示的核心功能**：上下文感知、collection-level workflow。

---

### Scene 2：让 RH 推荐缺失论文，并补回 Zotero，35–45 秒

**操作**：输入：

```text
基于这个综述题目，推荐最应该补进 Zotero 的 5 篇关键论文。先 dry-run，不要直接写入。
```

**预期 RH 面板输出**：

```text
推荐补库：5 篇
Cluster A: Scientific agents survey
Cluster B: Deep research benchmarks
Cluster C: Evidence/citation verification
Cluster D: Workflow governance

动作预览：sync_rh_papers_to_collection
目标 Zotero collection: Research Harness / 科研智能体综述
计划新增：5 篇
风险：可能出现重复条目；不会修改已有笔记、topic、deepread 记录
[查看清单] [确认导入] [取消]
```

**拍摄动作**：

1. 点击 `查看清单`；
2. 镜头停留 1 秒，让观众看到论文标题；
3. 点击 `确认导入`；
4. Zotero collection 出现新增论文。

**旁白**：

> “注意，它不是直接改我的 Zotero。所有写入动作都先变成确认卡：来源、目标、数量、风险都写清楚。确认后才 apply。”

**要展示的核心功能**：RH→Zotero 同步、dry-run/confirm/apply、可信写入治理。

---

### Scene 3：切换到单篇论文模式，读证据而不是泛泛总结，35–45 秒

**操作**：选中论文：

```text
Cited but Not Verified: Parsing and Evaluating Source Attribution in LLM Deep Research Agents
```

输入：

```text
这篇论文对“证据约束”这条综述主线有什么价值？请给出 claim、证据、限制。
```

**预期 RH 面板输出**：

```text
当前上下文：Paper mode
论文：Cited but Not Verified

Claim 1：Deep Research Agent 的引用相关性不等于事实正确性。
证据：论文对 source attribution 进行解析和评估，发现 citation metrics 与 factual accuracy 之间存在落差。
综述位置：Section 5 Evidence-Constrained Research Agents
限制：主要关注引用归因与事实性，不覆盖完整科研 workflow governance。
```

**旁白**：

> “选中论文后，它立刻切回 paper mode。这里我不是要它给一段漂亮摘要，而是要它把 claim、证据和限制拆出来，直接服务我的综述结构。”

**要展示的核心功能**：paper-level evidence reading、claim extraction、综述结构映射。

---

### Scene 4：跨论文综合，形成综述 taxonomy，40–50 秒

**操作**：回到 collection mode，输入：

```text
把当前论文池组织成一个综述 taxonomy。主线是：长程自动化、证据约束、可信工作流治理。请指出已有综述没有覆盖好的空白。
```

**预期 RH 面板输出**：

```text
Taxonomy 草案：

Axis 1: Long-Horizon Automation
- Literature search and deep research
- Hypothesis generation and idea evolution
- Experiment/code execution
- Paper writing and review

Axis 2: Evidence Constraints
- Citation grounding
- Claim-evidence extraction
- Source attribution verification
- Conflict-aware synthesis

Axis 3: Trustworthy Workflow Governance
- Stage gates
- Schema-gated tool use
- Provenance and audit trails
- Human approval and rollback

主要空白：
已有综述多解释“科研 agent 能做什么”，但较少系统解释“科研 agent 何时可信、如何被证据与流程约束”。
```

**旁白**：

> “这一步是整个 demo 的核心：它不只是帮我读论文，而是在把一堆论文组织成综述的论证框架。”

**要展示的核心功能**：cross-paper synthesis、taxonomy、gap analysis。

---

### Scene 5：生成 PDF 前先做 gate 检查，30–40 秒

**操作**：输入：

```text
在生成综述 proposal PDF 之前，先做一次 gate 检查：这个题目现在是否足够支撑一份综述草案？
```

**预期 RH 面板输出**：

```text
Gate Check: Survey Proposal Readiness

通过项：
✓ 主题边界清晰：长程自动化 × 证据约束 × 工作流治理
✓ 已有种子论文覆盖三条主线
✓ 与已有综述存在差异化：从 capability survey 转向 trust/workflow survey

风险项：
! 需要补充产业证据：OpenAI/Anthropic/Google agent workflow 文档
! 需要补充高质量 benchmark 对比表
! 需要验证每条核心 claim 的引用来源

建议：允许生成 proposal PDF，但标记为 v0.1 draft。
[生成 PDF 预览] [继续补证据] [取消]
```

**旁白**：

> “生成前，它会先告诉我：哪些证据够了，哪些还不够。这个 gate 不是阻止我，而是防止我把一个还没证据支撑的选题包装成成熟综述。”

**要展示的核心功能**：evidence gating、risk surfacing、可信科研流程。

---

### Scene 6：最终生成综述 Proposal PDF，30–45 秒

**操作**：点击 `生成 PDF 预览`，或输入：

```text
生成一份 3 页的综述 proposal PDF，包含题目、摘要、taxonomy、核心论文池、风险与下一步计划。先 preview，再确认生成并附加到当前 Zotero collection。
```

**预期 RH 面板输出**：

```text
动作预览：render_research_artifact_pdf
产物：LLM-Driven Scientific Research Agents Survey Proposal v0.1.pdf
内容：
1. Title and framing
2. Three-axis taxonomy
3. Representative paper clusters
4. Evidence gaps and risks
5. Next-step reading plan

目标：当前 Zotero collection
写入方式：生成 PDF → 记录 RH artifact → 可选附加到 Zotero
[确认生成 PDF] [查看预览] [取消]
```

**拍摄动作**：

1. 点击 `查看预览`，快速展示 PDF 首屏；
2. 点击 `确认生成 PDF`；
3. 画面显示 PDF 文件生成；
4. Zotero collection 或对应条目下出现 PDF 附件；
5. 打开 PDF，展示标题页和 taxonomy 图/表。

**旁白**：

> “最后，它把这次 Zotero 里的研究过程变成了一份 PDF：不是模型凭空写的，而是从论文池、证据、taxonomy、gate 检查一步步生成出来的。”

**要展示的核心功能**：research artifact generation、PDF export、artifact provenance、Zotero 回挂。

---

## 5. 90 秒小红书压缩版

### 0–8 秒：钩子

> “我把 Zotero 做成了一个能生成综述 PDF 的科研驾驶舱。”

### 8–22 秒：目录模式

输入：

```text
这个目录是一篇综述的论文池，可以怎么推进？
```

字幕：

```text
不选论文时，它理解的是整个研究方向。
```

### 22–38 秒：补论文 dry-run

输入：

```text
推荐 5 篇最应该补进 Zotero 的关键论文，先 dry-run。
```

字幕：

```text
写 Zotero 前必须确认：来源、目标、风险都给我看。
```

### 38–55 秒：单篇证据阅读

输入：

```text
这篇论文对“证据约束”有什么价值？给 claim、证据、限制。
```

字幕：

```text
不是摘要，而是 claim-evidence-limit。
```

### 55–73 秒：跨论文 taxonomy

输入：

```text
按长程自动化、证据约束、可信工作流治理生成 taxonomy。
```

字幕：

```text
一堆 PDF 被组织成综述框架。
```

### 73–90 秒：生成 PDF

输入：

```text
生成综述 proposal PDF，先 gate 检查，再确认。
```

字幕：

```text
最终产物：一份可继续修改的综述 proposal PDF。
```

---

## 6. 最终 PDF 内容建议

Demo 中生成的 PDF 不要太长，建议 3 页，便于视频展示。

### Page 1：选题定位

- 标题：LLM-Driven Scientific Research Agents
- 副标题：Long-Horizon Automation, Evidence Constraints, and Trustworthy Workflow Governance
- 一句话 thesis：科研 agent 的关键问题正在从“能否自动化”转向“自动化过程是否可验证、可治理、可复现”。

### Page 2：三轴 Taxonomy

| Axis | 关注问题 | 代表内容 |
|---|---|---|
| Long-Horizon Automation | agent 能自动推进哪些科研阶段 | deep research、hypothesis、experiment、writing |
| Evidence Constraints | 结论如何被证据约束 | citation grounding、claim-evidence、conflict synthesis |
| Workflow Governance | 长程过程如何可信执行 | stage gates、schema tools、provenance、approval |

### Page 3：证据缺口与下一步

- 需要补充产业证据；
- 需要构建 benchmark 对比表；
- 需要对关键论文做 claim extraction；
- 需要明确与已有综述的差异表；
- 下一步：生成 outline、导出 BibTeX、开始 Introduction 草稿。

---

## 7. 当前插件/后端建议实现点

为了让这个 demo 真实可跑，建议将“生成 PDF”也纳入通用 action-preview 协议，而不是做一次性按钮。

建议 action 类型：

```json
{
  "action_type": "render_research_artifact_pdf",
  "apply": {
    "type": "http_json",
    "path": "/api/topics/{topic_id}/artifacts/render-pdf",
    "payload": {
      "artifact_type": "survey_proposal",
      "zotero_collection_key": "...",
      "attach_to_zotero": true
    },
    "label": "确认生成 PDF"
  }
}
```

安全原则：

1. backend 决定 PDF 内容、路径、artifact ID；
2. frontend 只执行 backend 给出的 apply spec；
3. 生成前必须 preview/gate；
4. 生成后记录 RH artifact；
5. 附加到 Zotero 前再次确认目标 collection/item。

---

## 8. 拍摄检查清单

- [ ] Zotero 插件版本为 `0.2.4` 或更高；
- [ ] 右侧 RH 面板能识别 collection mode / paper mode；
- [ ] collection 名称清晰：`Research Harness / 科研智能体综述`；
- [ ] 至少准备 5 篇代表论文；
- [ ] 导入 Zotero 的动作会显示 dry-run 确认卡；
- [ ] 单篇论文能展示 claim-evidence-limit；
- [ ] taxonomy 输出不要太长，镜头里只展示三轴；
- [ ] PDF 生成前先展示 gate check；
- [ ] 结尾必须打开最终 PDF，让观众看到真实产物。

---

## 9. 结尾金句

> **这不是一个 Zotero 聊天框。它是一个把论文、证据、流程和产物串起来的科研工作台。**
