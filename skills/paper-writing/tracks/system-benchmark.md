# Track C: 系统/基准论文 (System / Benchmark / Dataset)

介绍新数据集、benchmark suite、开源工具或系统平台的论文。目标 venue: NeurIPS Datasets & Benchmarks, MLSys, VLDB, 或顶会主 track 的 benchmark 论文。

## 核心叙事

系统/基准论文的叙事不是"我们发明了新方法"，而是：

```
1. 社区面临 [评估/工具/数据] 缺口
2. 现有 [benchmark/tool/dataset] 在 [维度] 上不足
3. 我们构建了 [命名的系统]，提供 [具体能力]
4. 通过 [评估方式] 验证了 [具体价值]
5. 已开源/公开可用，附 [license] 和 [维护计划]
```

## Section Blueprint

| Section | 核心任务 | 特殊要求 |
|---------|----------|----------|
| Abstract | 系统名称 + 解决什么缺口 + 规模/特色 + 初步评估结果 | 必须说明公开可用性 |
| Introduction | 社区需求 + 现有工具不足 + 设计目标 + 贡献 | 重点在"为什么需要"而非"我们做了什么" |
| Related Work | 同类 benchmark/dataset/tool 对比 | 用对比表格而非文字 |
| Design / Architecture | 系统设计 + 数据构建流程 + 质量控制 | 必须详细到可复现 |
| Evaluation | 在自己系统上跑 existing methods + case study | 不是证明你的方法好，是证明系统有用 |
| Usage & Availability | 使用说明 + 开源链接 + license + 维护承诺 | venue 通常强制要求 |

## 导师原则适配

### P3-P8（六维验证）→ 社区需求验证

系统/基准论文需要证明的不是"问题重要"，而是"工具缺失"：

| 维度 | 适配 |
|------|------|
| 应用迫切性 | 多少研究者需要这个工具/数据？ |
| 理论空白 | → 评估空白：现有 benchmark 测不到什么？ |
| 学术热度 | 相关研究增速 → 对基础设施的需求增速 |
| 顶校参与 | 谁在用类似工具？谁会用你的？ |
| 产业投入 | 产业界有类似需求吗？ |
| 产学共识 | 学术和产业都需要标准化评估/工具吗？ |

### P9-P10（3→3 对称）→ 现有工具 N 个缺陷 → 我们的 N 个设计目标

```
现有 benchmark/tool 的局限：
  ❶ 缺陷1: [规模不足 / 场景覆盖不全 / ...]
  ❷ 缺陷2: [评估维度单一 / ...]
  ❸ 缺陷3: [不可复现 / 不维护 / ...]

Our Design Goals:
  ❶ 目标1: [对应缺陷1] → Section 3.1
  ❷ 目标2: [对应缺陷2] → Section 3.2
  ❸ 目标3: [对应缺陷3] → Section 3.3
```

### P11（技术包装）→ 强调设计决策的非平凡性

- 数据构建不是"爬下来清洗一下"，而是有质量控制 pipeline
- Benchmark 设计不是"跑几个模型"，而是有 evaluation protocol 和 metric 选择理由
- 系统架构不是"堆功能"，而是有设计 tradeoff 和可扩展性考虑

## Evaluation 特殊要求

系统/基准论文的 Evaluation 目的不同于方法论文：

| 方法论文 | 系统/基准论文 |
|----------|--------------|
| 证明"我的方法比别人好" | 证明"我的工具/数据对社区有用" |
| 对比 baselines | 在你的 benchmark 上对比 existing methods |
| Ablation: 各组件的贡献 | Analysis: 数据/benchmark 的特征分析 |
| 越高越好 | 展示有区分度（方法之间有差异） |

**必须包含**：
- [ ] Existing methods 在你的 benchmark 上的表现（体现 benchmark 的区分度和价值）
- [ ] 数据/benchmark 的统计分析（分布、难度分层、规模对比）
- [ ] Case study 展示具体使用场景
- [ ] 与已有同类 benchmark 的对比（不是方法对比，是 benchmark 本身的对比）

## Reproducibility 清单

系统/基准论文的可复现性要求远高于方法论文：

- [ ] 代码已开源，附 README 和 quickstart
- [ ] 数据集有下载链接（或构建脚本）
- [ ] License 明确（推荐 CC BY 4.0 for data, Apache 2.0 for code）
- [ ] 维护计划说明（谁维护、维护到什么时候、如何贡献）
- [ ] 环境依赖明确（requirements.txt / Dockerfile）
- [ ] 评估脚本可一键运行
- [ ] Leaderboard / 社区提交机制（如适用）
