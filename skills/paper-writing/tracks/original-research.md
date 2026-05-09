# Track A: 专项研究论文 (Original Research)

提出新方法、新理论、新发现的论文。目标 venue: CCF-A 会议/期刊（NeurIPS, ICML, ICLR, ACL, CVPR, AAAI 等）。

## Section Blueprint

| Section | 页数 (9页会议) | 核心任务 | 关键检查 |
|---------|----------------|----------|----------|
| Abstract | ~150 words | 五句话公式 | 有具体数字吗？能独立阅读吗？ |
| Introduction | 1-1.5 页 | 6 个 move（见下） | Method 在 page 2-3 开始了吗？ |
| Related Work | 0.5-1 页 | 3 个 gap 归纳 | 是综合比较还是逐篇介绍？ |
| Method | 2-2.5 页 | 技术方案 | 能复现吗？ |
| Experiments | 2-3 页 | 证据链 | 每个实验对应哪条 claim？ |
| Conclusion | 0.5 页 | 总结 + limitation | 诚实面对局限了吗？ |

## Introduction 六步法 (Rhetorical Moves)

```
Move 1: Stakes — 谁受影响？为什么现在重要？（六维验证的精华浓缩）
Move 2: Problem Gap — 现有方法的结构性局限（不是"不够好"，而是"原理上做不到"）
Move 3: Key Abstraction — 你的核心 insight，用一个命名的概念表达
Move 4: Approach Overview — 用 1-2 句话说清楚你的方法做了什么
Move 5: Contributions — 2-4 条 bullet，每条 claim-first，1-2 行
Move 6: Results Preview — 最有说服力的数字
```

**Move 1 写法要求**（来自导师六维验证）：

在 Move 1 中，必须在 2-3 句话内同时传递：
- 应用场景的紧迫性（P3）— 用数据，不用形容词
- 问题的学术热度（P5）— 可提及近年顶会论文数量
- 产学两界的重视（P6-P8）— 可提及顶校/大厂的工作

> 示例："Time series forecasting underpins critical applications from energy grid optimization (projected $47B impact by 2027, IEA) to financial risk management. The recent surge of 83 papers at NeurIPS/ICML 2024-2025 and dedicated industry efforts from Google (TimesFM), Amazon (Chronos), and Salesforce (Moirai) underscore both the urgency and the unsolved challenges in this domain."

## Related Work 三段式

导师原则 P9-P10 的具体操作化：

```
段1: Research Direction α
  - 重要进展: [具体描述，引 ★★★ refs]
  - 核心障碍 ❶: [结构性局限，不是"还不够好"]

段2: Research Direction β
  - 重要进展: [具体描述，引 ★★★ refs]
  - 核心障碍 ❷: [结构性局限]

段3: Research Direction γ
  - 重要进展: [具体描述，引 ★★★ refs]
  - 核心障碍 ❸: [结构性局限]

定位句: "Our work addresses ❶ through [贡献1], ❷ through [贡献2], and ❸ through [贡献3]."
```

**检查清单**：
- [ ] 每个方向先说进展，再说障碍（不能只有批评）
- [ ] 障碍是结构性的（"assumes stationarity"），不是量化的（"accuracy is low"）
- [ ] 3 个障碍分别对应 3 条贡献
- [ ] 没有逐篇介绍
- [ ] 最重要的 1-2 篇工作有具体分析，其余以 [refs] 归组

## Experiments Section 检查清单

每个实验子节必须包含：
- [ ] 明确声明测试什么 claim："This experiment evaluates whether [claim]..."
- [ ] Baseline 选择有理由且包含审稿人期望看到的方法
- [ ] Error bars + 方法说明（std dev vs std error, n runs）
- [ ] 每组实验结束后有 Takeaway 段落
- [ ] Ablation study 证明各组件的必要性
- [ ] 计算资源说明（GPU type, hours）

## Method Section 技术包装清单

对应导师原则 P11（突出新颖性和深度）：

- [ ] 方法有一个 memorable 的名字
- [ ] 清楚标明"first"在哪个维度上成立
- [ ] 至少一个 non-trivial design choice 有详细论证（为什么不是用更简单的方案）
- [ ] 有理论分析/复杂度分析/收敛保证（至少一项）
- [ ] 伪代码或 conceptual overview 使读者能理解而无需读完整 section

## Venue 快速参考

| Venue | Page Limit | Extra (CR) | 特殊要求 |
|-------|------------|------------|----------|
| NeurIPS | 9 | +0 | 必须 checklist, lay summary |
| ICML | 8 | +1 | Broader Impact |
| ICLR | 9 | +1 | LLM disclosure |
| ACL (long) | 8 | varies | Limitations 必须, Ethics |
| AAAI | 7 | +1 | 严格 style file |
| CVPR | 8 | +2 | Supplementary 鼓励 |

References 不计入 page limit（所有 ML/AI venue）。Appendix 无限但审稿人不必读。
