# Track B: 综述论文 (Survey / Review)

系统梳理某个研究领域的进展、分类体系、开放问题和未来方向。目标 venue: ACM Computing Surveys, IEEE TPAMI, AI Open, 或 CCF-A 期刊的 survey track。

## 综述 vs 专项研究的本质差异

| 维度 | 专项研究 | 综述 |
|------|----------|------|
| 核心贡献 | 新方法/理论 | 分类框架 + gap 识别 + 路线图 |
| Related Work | 一个 section | **整篇论文就是** |
| 引用策略 | 精选 30-60 篇 | **全面覆盖 100-300 篇** |
| 最大风险 | 方法不 work | **漏引重要工作** |
| 写作核心能力 | 技术阐述 | **综合归纳与分类** |

## Section Blueprint

| Section | 核心任务 | 关键检查 |
|---------|----------|----------|
| Abstract | 领域 + 覆盖范围 + 分类框架 + 关键发现 + open challenges | 明确了 survey 的 scope boundary 吗？ |
| Introduction | 为什么需要这篇综述 + scope + 方法论 + 论文结构 | 说清楚了与已有 survey 的差异吗？ |
| Background | 基础概念 + 问题形式化 | 足以让读者理解后续分类吗？ |
| Taxonomy | 分类框架（**综述的核心贡献**） | 分类维度正交吗？覆盖完整吗？ |
| Category Analysis | 每个类别的深入分析 | 是综合比较还是逐篇介绍？ |
| Comparison | 跨类别比较 + benchmark 汇总 | 比较维度公平吗？ |
| Open Challenges | 3-5 个开放问题 | 问题够具体吗？有可操作性吗？ |
| Future Directions | 研究路线图 | 与 open challenges 对应吗？ |

## 导师原则在综述中的适配

### P1（引用分级）→ 全面覆盖优先，但排列有序

综述论文的引用策略与专项研究不同：

```
原则：覆盖完整 > tier 优先

操作方式：
1. 首先确保领域内所有重要工作被覆盖（无论 tier）
2. 在同一组引用中，★★★ 排前，★★/★☆ 排后
3. 对每个 category 的代表性工作深入讨论时，优先选 ★★★ 的
4. 漏引一篇有影响力的工作比多引一篇低 tier 工作更致命
```

### P2（综合归纳）→ 这是综述的核心技能

**综述论文中 P2 的重要性提升到最高级别。**

每个 category analysis 段落必须遵循：

```
[Category 名称] 方向的研究可追溯到 [seminal work, year]。
近年来，[N] 篇代表性工作 [top refs] 在 [具体方面] 取得了显著进展：
- 进展1: [具体技术进步，非笼统描述]
- 进展2: [另一个维度的进步]

然而，这些方法共同面临以下局限：
- 局限A: [结构性问题]
- 局限B: [另一个结构性问题]

其中最具代表性的是 [1-2篇最重要工作] 的方法，
通过 [具体描述] 实现了 [具体结果]，
但仍无法解决 [核心障碍]。
```

**绝对禁止的模式**：
- ❌ "Paper A proposed method X. Paper B proposed method Y. Paper C proposed method Z."
- ❌ 给每篇论文相同篇幅的独立段落
- ❌ 只罗列方法不比较优劣
- ❌ 只有缺点评价没有优点认可

### P9-P10 → 改为 Open Challenges + Research Roadmap

综述不使用 "3 问题→3 贡献" 的对称结构，改为：

```
Open Challenges (3-5 个):
  ❶ Challenge 1: [来自 category analysis 中反复出现的共性问题]
  ❷ Challenge 2: [跨 category 的系统性障碍]
  ❸ Challenge 3: [新兴趋势带来的新问题]
  ❹ Challenge 4 (可选): [应用场景特定的挑战]
  ❺ Challenge 5 (可选): [伦理/可扩展性/效率问题]

Future Directions:
  每个 challenge 对应 1-2 个研究方向建议
  方向建议要具体可操作，不是"需要更多研究"
```

### P3-P8（六维验证）→ "为什么现在需要这篇综述"

综述的 Introduction 需要回答：

1. **时机紧迫性**：为什么是现在？（近 2-3 年论文爆发增长）
2. **已有综述不足**：最近的综述是什么时候？覆盖了什么？漏了什么？
3. **scope 独特性**：你的分类框架提供了什么新视角？
4. **读者群体**：谁需要读这篇综述？新入门者？跨领域研究者？
5. **产学需求**：学术界和产业界的双重需求

#### 前沿关注度证据（强制）

在写综述的 Introduction / Motivation 之前，必须先构建一个 `frontier_attention_evidence` 证据包，用**最新顶级成果和资料**证明该综述方向同时受到学术界和产业界高度关注。禁止只写“recently attracted significant attention”而没有可追溯证据。

证据包至少包含：

| 证据类型 | 要求 | 用途 |
|---------|------|------|
| 学术前沿 | 近 2-3 年顶会/顶刊、oral/spotlight/best paper、benchmark、survey、workshop/tutorial | 证明学术热度和研究空白 |
| 学术 anchor | 高引用/奠基性工作或被大量后续方法采用的基础论文 | 建立领域谱系和 taxonomy 根节点 |
| 产业前沿 | 大厂官方技术报告、产品发布、工程博客、开源框架、标准协议 | 证明产业投入和工程需求 |
| 社区生态 | leaderboard、开源项目、SDK、协议、工具链、开发者平台 | 证明方向不只是论文概念，而有实践扩散 |
| 趋势对比 | 近年论文/benchmark/工具增长与已有 survey 缺口 | 证明为什么需要“现在”写这篇综述 |

写作要求：

1. 学术证据优先来自顶会顶刊和正式论文；产业证据优先来自官方资料，不用二手新闻替代官方来源。
2. 每条“高度关注/快速发展/产业投入”的判断必须能追溯到具体论文或 URL。
3. 如果只能证明学术热、不能证明产业热，或反之，必须如实写成 scope limitation。
4. 该证据包应通过 RH artifact 记录；相关论文必须入库并关联 topic。

## Taxonomy 设计原则

分类框架是综述的核心贡献，设计要遵循：

| 原则 | 要求 | 检查 |
|------|------|------|
| 正交性 | 分类维度之间不重叠 | 一篇论文是否可能同时属于两个叶节点？ |
| 完备性 | 覆盖领域内所有主要方法 | 有遗漏的重要论文无法归类吗？ |
| 可区分性 | 不同类别之间有实质差异 | 两个类别合并是否会丢失信息？ |
| 深度适当 | 层次不超过 3 层 | 最深的分类还有意义吗？ |
| 可视化 | 必须有 taxonomy tree/table | 一张图能概括整个框架吗？ |

## Comparison Table 设计

综述必须包含至少一个 comprehensive comparison table：

```latex
\begin{table*}[t]
\caption{Comparison of representative methods across key dimensions.}
\centering
\begin{tabular}{l c c c c c c}
\toprule
Method & Category & Venue & Year & Metric1 ↑ & Metric2 ↓ & Key Limitation \\
\midrule
... \\
\bottomrule
\end{tabular}
\end{table*}
```

**Table 要求**：
- 覆盖每个 category 的代表性方法（至少 2-3 篇/category）
- 包含定量比较指标
- 标注方向符号（↑ higher better, ↓ lower better）
- 最后一列标注关键局限

## 写作顺序

```
1. Taxonomy 设计（先确定分类框架，这是核心贡献）
2. Category Analysis（按分类填充内容）
3. Comparison Table（跨类别定量比较）
4. Open Challenges（从 analysis 中提炼共性问题）
5. Future Directions（针对 challenges 提出路线图）
6. Introduction（回到开头，基于全文内容写 framing）
7. Abstract（最后写）
```

## 质量检查清单

- [ ] Taxonomy 可视化清晰，一图概括
- [ ] 每个 category 的分析是综合式而非逐篇式
- [ ] 没有遗漏领域内 ★★★ 级别的重要工作
- [ ] Open challenges 来自实际分析，不是泛泛而谈
- [ ] Comparison table 涵盖所有 category 的代表方法
- [ ] 明确了与已有综述的差异和新贡献
- [ ] 引用数量充足（100+），覆盖面广
- [ ] 每个 category 内的进展和局限都有涉及
- [ ] Introduction 中的“学术/产业高度关注”判断都有 `frontier_attention_evidence` 支撑
