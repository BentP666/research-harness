---
name: paper-writing
description: "论文撰写全流程指导 skill，覆盖六种类型：专项研究、综述、系统/基准、短论文/Workshop、立场论文、科研汇报。融合导师核心原则 + 国际顶会写作方法论。Trigger: write paper, 写论文, 论文撰写, draft paper, paper writing, 写综述, survey writing, 科研汇报, research report, position paper, workshop paper, short paper, 写introduction, 写related work, 写实验, camera-ready, rebuttal, 投稿准备"
---

# Paper Writing — 论文撰写 Skill

六轨论文写作引擎：从问题定位到投稿就绪。

## 触发时机

- 起草/修改论文任意章节
- 准备投稿（格式、checklist、anonymization）
- 准备 rebuttal / camera-ready
- 给导师写科研进展汇报
- 讨论论文 framing 或 narrative

## 第 0 步：识别论文类型 → 选择 Track

在开始任何写作之前，**必须**确认论文类型并加载对应 track：

| Track | 类型 | 加载文件 | 典型 venue |
|-------|------|----------|------------|
| A | 专项研究 (Original Research) | `tracks/original-research.md` | CCF-A 会议/期刊 |
| B | 综述 (Survey / Review) | `tracks/survey-review.md` | ACM CSUR, IEEE TPAMI Survey |
| C | 系统/基准 (System / Benchmark) | `tracks/system-benchmark.md` | NeurIPS D&B, MLSys |
| D | 短论文/Workshop | `tracks/short-workshop.md` | Workshop, Findings |
| E | 立场论文 (Position Paper) | `tracks/position-paper.md` | TMLR, HotNets |
| F | 科研汇报 (Advisor Report) | `tracks/advisor-report.md` | 内部汇报 |

**如果用户没有明确类型**：通过以下问题判断——"这篇论文是提出新方法/理论，还是系统梳理某个领域？有实验结果吗？目标投哪里？"

---

## 核心原则（六轨共享）

以下原则按重要性排序，适用于所有论文类型。每条标注了来源（"导师"= 导师方法论，"国际"= 开源社区/顶级研究者共识）。

### 一、问题定位六维验证 [导师 P3-P8]

**写论文的第一步不是写，而是验证"这个问题值得写"。** 用以下六个维度检验，至少满足 4/6：

| 维度 | 检验问题 | 证据类型 |
|------|----------|----------|
| 🏭 **应用迫切性** | 是否有重大且紧迫的实际应用场景？ | 产业报告、新闻、市场数据 |
| 🧮 **理论空白** | 是否存在理论尚未解决的问题？ | 现有方法的failure case、bound gap |
| 🔥 **学术热度** | 是否是当前学术界的研究热点？ | 近2年顶会论文数量趋势 |
| 🏫 **顶校参与** | 全球顶级高校是否有团队在做？ | 发表记录（MIT/Stanford/THU/ETH等） |
| 🏢 **产业投入** | 国际大厂是否有相关论文/工具/研究？ | Google/Meta/MS/OpenAI的发表和开源 |
| 🤝 **产学共识** | 学术界和产业界是否都认为迫切？ | 同时出现在顶会和产业blog中 |

**应用方式**：在 Introduction 第一段就要传递出"这个问题重要且紧迫"的信号，用具体数据而非空洞形容词。

> 例：不要写"X is an important problem"，而是"X affects 2.3B daily queries (Google, 2025) and remains unsolved despite 47 papers at NeurIPS/ICML 2024-2025"。

### 二、三问题→三贡献对称结构 [导师 P9-P10]

Related Work / 综述部分归纳的**未解决问题不能太多，限制为 3 条**。然后自己的创新工作与这 3 条一一对应：

```
Related Work 归纳出:
  ❶ 问题1: [现有方法在X上的结构性局限]
  ❷ 问题2: [Y场景下的理论空白]
  ❸ 问题3: [Z维度上的效率/精度瓶颈]

Our Contributions:
  ❶ 贡献1: [针对问题1的方案] → 对应 Section 3.1 + Exp Table 2
  ❷ 贡献2: [针对问题2的方案] → 对应 Section 3.2 + Exp Table 3
  ❸ 贡献3: [针对问题3的方案] → 对应 Section 3.3 + Exp Table 4
```

**为什么是 3 条**：太少（1-2）显得贡献不足；太多（4+）导致散焦，审稿人记不住。3 条形成完整论证链且易于记忆。

**Track 适配**：
- Track A（专项研究）：严格 3 问题 → 3 贡献
- Track B（综述）：改为 3-5 个 open challenges → 对应 research roadmap
- Track D（短论文）：1-2 个问题 → 1-2 个贡献
- Track F（科研汇报）：不强制此结构

### 三、引用质量分级 [导师 P1]

引用不只是支撑论点，更是向审稿人展示你的学术视野。**引用质量直接影响审稿人对论文成熟度的判断。**

| 优先级 | 来源 | 策略 |
|--------|------|------|
| ★★★ 必引 | CCF-A 会议/期刊、中科院一区 | 核心论点的主要支撑，放在引用序列前部 |
| ★★☆ 可引 | CCF-B 会议/期刊、中科院二区 | 补充性引用，用于扩展覆盖面 |
| ★☆☆ 慎引 | 其他 venue | 仅在以下情况使用：(a) 该领域可用文献确实稀缺，(b) 该论文是开创性工作（如早期 arXiv），(c) 唯一相关的实现/数据集 |

**操作规则**：
1. 每个核心论点至少有 1 篇 ★★★ 级引用支撑
2. 低 tier 引用如必须使用，在引用列表中放在 ★★★ 之后
3. 自引比例不超过 15%，除非该领域你的团队是主要贡献者
4. 引用年限：优先近 3 年，超过 5 年的仅保留 seminal works

**Track 适配**：
- Track B（综述）：★★★ 仍优先，但必须全面覆盖——漏引重要工作比引用低 tier 更危险
- Track D（短论文）：引用总数 15-25 篇，几乎全部 ★★★

### 四、综述式写作：综合归纳 > 逐篇介绍 [导师 P2]

**这是 Related Work 最常见的错误：变成文献列表而非知识综合。**

| ❌ 错误写法 | ✅ 正确写法 |
|-------------|-------------|
| "A et al. proposed X. B et al. proposed Y. C et al. proposed Z." | "Three lines of work address this problem: methods based on X [A,B], approaches using Y [C,D], and techniques leveraging Z [E,F]. While X-based methods achieve strong accuracy, they suffer from..." |
| 逐篇罗列每篇论文的方法和结果 | 按研究方向分组，综合比较优缺点，指出共同局限 |
| 给每篇论文相同篇幅 | 重要进展详写，边缘工作一笔带过 |

**写法公式**（每个研究方向一段）：
```
[方向名称] 的研究进展 [refs] 已经解决了 [具体问题]，
但仍面临 [具体局限]。
其中 [最重要的1-2篇] 通过 [具体方法] 取得了 [具体成果]，
然而 [结构性问题] 使得这些方法无法 [目标场景]。
```

### 五、技术包装：突出新颖性与深度 [导师 P11]

同一个技术，不同的包装，审稿人的感知完全不同。

| 弱包装 | 强包装 |
|--------|--------|
| "We combine A and B" | "We develop a unified framework that integrates A's efficiency with B's expressiveness through a novel coupling mechanism" |
| "We modify the loss function" | "We introduce a theoretically-grounded regularization term derived from [原理], which provably ensures [性质]" |
| "We use transformer for X" | "We identify that the key bottleneck in X is [具体问题], and propose [命名的方法] that exploits [具体结构特征] to achieve [具体改进]" |

**包装三要素**：
1. **命名**：给你的方法/框架取一个memorable的名字
2. **定位**：明确说出"first"/"novel"在哪个维度上成立
3. **深度**：展示为什么这个方案不是trivial的（理论保证、非显然的设计选择、失败的替代方案）

### 六、叙事原则 [国际：Nanda/Farquhar/Karpathy]

**一篇论文是一个有明确结论的技术故事，不是实验的堆砌。**

Introduction 结束时，读者必须清楚理解：

| 支柱 | 内容 | 测试 |
|------|------|------|
| **The What** | 1-3 个具体的、可证伪的 claims | 能用一句话说清楚吗？ |
| **The Why** | 支撑 claims 的证据 | 有强 baseline 对比吗？ |
| **The So What** | 读者为什么应该关心 | 与已知社区问题有联系吗？ |

**如果核心贡献无法用一句话说清楚，论文的 framing 还没有收敛。**

### 七、时间分配 [国际：Nanda]

在以下四部分投入**大致相等**的时间：

1. Abstract
2. Introduction
3. Figures（尤其 Figure 1）
4. 其余所有内容

**原因**：审稿人的阅读顺序是 Title → Abstract → Intro → Figure 1 → 可能看Methods。前两页不吸引人，后面的精彩内容可能永远不被看到。

### 八、句子级清晰度 [国际：Gopen & Swan 七原则]

| 原则 | 规则 | 示例 |
|------|------|------|
| 主谓紧邻 | 主语和动词之间不插入长定语从句 | ❌ "The model, which was..." → ✅ "The model achieves..." |
| 重点后置 | 句末放最重要的信息 | ❌ "Accuracy improves by 15% when using X" → ✅ "When using X, accuracy improves by **15%**" |
| 语境先行 | 先给背景，再给新信息 | ✅ "Given these constraints, we propose..." |
| 旧信息→新信息 | 从已知过渡到未知 | 前后句之间要有逻辑链接 |
| 一段一事 | 每段只做一件事 | 多主题段落要拆分 |
| 动词承载动作 | 避免名词化 | ❌ "perform an analysis" → ✅ "analyze" |
| 先铺垫后展示 | 公式/结果前先解释为什么重要 | 不要突然出现一个等式 |

### 九、词语精确度 [国际：Lipton/Steinhardt]

- **消灭模糊词**：❌ "performance" → ✅ "accuracy" / "latency" / "throughput"
- **消灭对冲**：❌ "may improve" → ✅ "improves by 15%"（除非确实不确定）
- **消灭弱动词**：❌ "combine" / "modify" / "extend" → ✅ "develop" / "propose" / "introduce"
- **消灭修饰词**：❌ "very significant improvement" → ✅ "15% improvement"
- **术语一致**：全文同一概念只用一个术语

### 十、反 AI 痕迹检查 [国际：Imbad0202/SNL-UCSB]

LLM 辅助写作的论文容易出现以下模式，审稿人已经能识别：

| 模式 | 检测方法 | 修正 |
|------|----------|------|
| 过度使用 em-dash (—) | 全文搜索 `—` 计数 | 改用逗号、分号或拆句 |
| 每段开头千篇一律 | 检查段首词分布 | 变化句式结构 |
| "It is worth noting that" 等清嗓子 | 搜索固定短语 | 直接删除，lead with content |
| 段落长度高度一致 | 统计每段字数标准差 | 有意变化段落长度 |
| 过度使用 "Furthermore" / "Moreover" | 统计连接词频率 | 用逻辑关系替代（because/however/specifically） |
| "delve into" / "landscape" / "realm" | 搜索 AI 高频词 | 替换为具体表述 |

---

## 引用工作流（防幻觉）

**🚨 核心规则：绝不从记忆生成 BibTeX。必须程序化获取。🚨**

AI 生成的引用有约 40% 的错误率。幻觉引用（不存在的论文、错误作者、错误年份）是严重的学术不端。

### 引用验证流程（每条引用必须执行）

```
1. 搜索 → Semantic Scholar API / Exa MCP / Google Scholar
2. 验证 → 论文在 2+ 来源中存在（S2 + arXiv/CrossRef）
3. 获取 → 通过 DOI 程序化获取 BibTeX
4. 核实 → 你引用的 claim 确实在该论文中出现
5. 分级 → 按引用质量分级（★★★/★★☆/★☆☆）标注
6. 失败 → 标记 [CITATION NEEDED]，明确告知用户
```

**Research Harness 集成**（可选）：如果 MCP server 可用，使用 `paper_search` 和 `claim_extract` 工具验证引用和 claim 对应关系。

### 引用不可做的事

| ❌ 禁止 | ✅ 正确做法 |
|---------|-------------|
| 从记忆写 BibTeX | 通过 API 获取 |
| 记不清就猜一个类似的 | 标记 `[CITATION NEEDED]` |
| 引用未读过的论文 | 至少确认 abstract 和 conclusion |
| 用 arXiv 版本替代已发表版本 | 优先引用正式发表版 |

---

## 写作流程（五阶段 Pipeline）

改编自 SNL-UCSB 五阶段流水线，融合导师原则：

### Stage 1: 问题定位与 Brainstorming

- 运行**六维验证**（原则一），确认问题值得写
- 确定论文类型，加载对应 Track
- 明确一句话贡献（One-Sentence Contribution Test）
- 输出：`project_context.md`（论文身份声明、venue、贡献 claims）

### Stage 2: 架构设计 (Architecture)

- 设计章节大纲，分配 claim → section 映射
- 规划 figure/table plan（Figure 1 优先）
- 设定 page budget
- 运行 **3 问题 → 3 贡献对称检查**（原则二）
- 输出：结构化大纲表

| Section | Pages | Key Claim | Figures/Tables |
|---------|-------|-----------|----------------|
| ... | ... | ... | ... |

### Stage 3: 章节起草 (Section Drafts)

**推荐起草顺序**：
1. Draft 0 Introduction（定调，可丢弃）
2. Experiments / Evaluation
3. Method / Design
4. Related Work（运用原则四：综合归纳）
5. Final Introduction（基于实际证据重写）
6. Abstract（最后写）

**每个章节起草后**：运行对应 Track 的 section checklist。

### Stage 4: 整合与一致性 (Integration)

- 术语一致性：全文同一概念同一名称
- Claim-Evidence 映射：Introduction 每条 claim 对应实验
- 关键抽象传播：核心概念在各 section 都出现
- 过渡检查：N 段结尾 ↔ N+1 段开头逻辑连贯
- 运行**反 AI 痕迹检查**（原则十）

### Stage 5: 压缩与打磨 (Compression)

按顺序执行 7 个压缩操作：
1. 句子精简（删除从句、修饰词、清嗓子）
2. 段落合并（同一论点的多个例子 → 保留最佳）
3. 通用修饰词删除（"significant" → 具体数字）
4. Tutorial 删除（目标读者已知的知识）
5. Claim-first 改写（主句前置）
6. Takeaway 插入（实验组后加总结段）
7. 数据可视化提升（密集数字从文字移到图表）

**目标**：首稿减少 30-50%。报告压缩前后字符数。

---

## 质量门控 (Quality Gates)

每个阶段完成后，运行对应的质量检查：

### Gate 1: 问题定位检查（Stage 1 后）
- [ ] 六维验证至少 4/6 通过
- [ ] 一句话贡献清晰且可证伪
- [ ] 目标 venue 明确

### Gate 2: 结构检查（Stage 2 后）
- [ ] 3 问题 → 3 贡献对称（Track A）或 N challenges → roadmap（Track B）
- [ ] 每个 claim 有对应的 evidence section
- [ ] Figure 1 计划就绪
- [ ] Page budget 符合 venue 要求

### Gate 3: 章节检查（Stage 3 每章后）
- [ ] 引用质量分级达标（核心论点有 ★★★）
- [ ] 无逐篇介绍式 related work（原则四）
- [ ] 每个实验明确声明测试什么 claim
- [ ] Section checklist（来自 Track 文件）通过

### Gate 4: 一致性检查（Stage 4 后）
- [ ] 术语一致
- [ ] Claim 完整映射
- [ ] 反 AI 痕迹通过
- [ ] 交叉引用无断裂

### Gate 5: 投稿就绪检查（Stage 5 后）
- [ ] Page count 符合 venue 限制
- [ ] 所有引用已验证（无 `[CITATION NEEDED]`）
- [ ] Anonymization 完成（双盲 venue）
- [ ] LaTeX 编译无 warning
- [ ] 所有 figure 为矢量格式（PDF/EPS）
- [ ] Font 全部嵌入

---

## Abstract 五句话公式 [国际：Farquhar]

```
句1: 你做了什么（"We introduce..." / "We prove..." / "We demonstrate..."）
句2: 为什么这个问题难且重要
句3: 你怎么做的（含关键词，利于搜索发现）
句4: 你有什么证据
句5: 最值得记住的数字/结果
```

**删除标准**：如果第一句能套在任何 ML 论文上（"Large language models have achieved remarkable success..."），直接删除。

---

## Research Harness 集成（可选）

当 Research Harness MCP server 可用时，可使用以下工具增强写作流程：

| 阶段 | MCP 工具 | 用途 |
|------|----------|------|
| Stage 1 | `paper_search`, `gap_detect` | 验证问题定位、发现 gap |
| Stage 2 | `outline_generate`, `writing_architecture` | 生成大纲和写作架构 |
| Stage 3 | `section_draft`, `claim_extract` | 起草章节、提取 claim |
| Stage 4 | `consistency_check` | 全文一致性检查 |
| Stage 5 | `section_review`, `section_revise` | 章节审查和修订 |
| 引用 | `paper_search`, `paper_ingest` | 搜索和管理文献 |

**独立使用**：即使没有 Research Harness，本 skill 的所有原则和流程仍然完全可用——使用 web search 替代 `paper_search`，手动管理引用替代 MCP 工具。

---

## Track 快速参考

详细的 track-specific 写作指南见 `tracks/` 目录。以下是各 track 的核心差异速查：

| Track | 核心叙事 | 引用量 | 特殊要求 |
|-------|----------|--------|----------|
| A 专项研究 | 问题→方案→证据 | 30-60 | 严格 3→3 对称 |
| B 综述 | 领域→分类→空白→路线图 | 100-300 | 全面覆盖 > tier 优先 |
| C 系统/基准 | 需求→设计→评估→可复现 | 30-50 | 强调 reproducibility |
| D 短论文 | 一个 insight→初步证据 | 15-25 | 几乎全 ★★★ |
| E 立场论文 | 观点→论证→implications | 20-40 | 强调 provocativeness |
| F 科研汇报 | 进展→问题→下一步 | N/A | 面向导师，实用导向 |
