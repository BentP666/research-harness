import type { DiscoverOpportunityBrief } from "./api";

export type DiscoveryCategory =
  | "Agent Evaluation"
  | "Agent Security"
  | "AI4Code"
  | "AI Infrastructure"
  | "Multimodal";

export type DiscoveryHorizon = "act-now" | "watch" | "frontier";

export interface DiscoverySignalSource {
  title: string;
  kind: "paper" | "product" | "benchmark" | "repo" | "workshop" | "blog";
  date: string;
  url: string;
  takeaway: string;
}

export interface DiscoveryOpportunity {
  slug: string;
  category: DiscoveryCategory;
  horizon: DiscoveryHorizon;
  title: string;
  oneLiner: string;
  brief: DiscoverOpportunityBrief;
  radar: {
    impact: number;
    saturation: number;
    momentum: number;
    feasibility: number;
  };
  audience: string[];
  productThesis: string;
  researchAngles: string[];
  thirtyDayPlan: Array<{ week: string; goal: string; output: string }>;
  signals: DiscoverySignalSource[];
  counterPosition: string;
}

export interface DiscoveryWatchlist {
  name: string;
  description: string;
  cadence: string;
  trackedSignals: string[];
}

export interface DiscoveryInspiration {
  name: string;
  url: string;
  whatToBorrow: string;
  boundary: string;
}

export interface DiscoveryDomainTrack {
  slug: string;
  name: string;
  thesisFit: string;
  whyNow: string;
  opportunityCount: number;
  difficulty: "friendly" | "medium" | "advanced";
  saturation: "low" | "medium" | "high";
  idealFor: string[];
  starterProblems: string[];
}

export interface DiscoveryPersonaProfile {
  id: string;
  name: string;
  description: string;
  need: string;
  bestFitDomainSlugs: string[];
  constraints: string[];
}

export interface DiscoveryTopicCandidate {
  slug: string;
  title: string;
  domainSlug: string;
  fitFor: string[];
  whyItFits: string;
  novelty: number;
  feasibility: number;
  resourceNeed: "low" | "medium" | "high";
  horizon: "8-weeks" | "semester" | "year";
  firstMoves: string[];
  starterPack: {
    papers: string[];
    skills: string[];
    outputs: string[];
  };
}

export interface DiscoveryDigestIssue {
  id: string;
  title: string;
  date: string;
  focus: string;
  topLine: string;
  highlights: string[];
  href: string;
}

export const DISCOVERY_CATEGORIES: Array<{
  name: DiscoveryCategory;
  description: string;
  color: string;
}> = [
  {
    name: "Agent Evaluation",
    description: "真实工作流、动态环境、鲁棒性和人类信任评测。",
    color: "from-cyan-400 to-blue-500",
  },
  {
    name: "Agent Security",
    description: "权限、工具调用、审计、goal drift 和高后果动作治理。",
    color: "from-rose-400 to-orange-500",
  },
  {
    name: "AI4Code",
    description: "从补代码走向算法发现、kernel 优化和研究工程自动化。",
    color: "from-violet-400 to-fuchsia-500",
  },
  {
    name: "AI Infrastructure",
    description: "推理成本、能耗、时延、可观测性与 agent workload systems。",
    color: "from-emerald-400 to-teal-500",
  },
  {
    name: "Multimodal",
    description: "长视频、音视频联合、具身 grounding 与真实环境评测。",
    color: "from-amber-300 to-pink-500",
  },
];

export const DISCOVERY_WATCHLISTS: DiscoveryWatchlist[] = [
  {
    name: "Agent Reliability Radar",
    description: "跟踪真实任务、动态环境、故障注入、agent trace 和评测协议。",
    cadence: "每周一刷新",
    trackedSignals: ["new benchmarks", "enterprise agent launches", "eval workshops"],
  },
  {
    name: "Agent Security Boundary",
    description: "跟踪工具权限、审计日志、沙箱、连接器安全和高后果动作 gate。",
    cadence: "每周三刷新",
    trackedSignals: ["security papers", "policy-as-code", "tool-use incidents"],
  },
  {
    name: "AI Systems Cost & Trace",
    description: "跟踪 agentic inference、P99 延迟、能耗、observability 和 replay 模拟器。",
    cadence: "每两周刷新",
    trackedSignals: ["systems papers", "serving infra", "energy reports"],
  },
];

export const DISCOVERY_INSPIRATIONS: DiscoveryInspiration[] = [
  {
    name: "STORM",
    url: "https://github.com/stanford-oval/storm",
    whatToBorrow: "借鉴 perspective-guided research 和报告式输出，把机会解释成可读叙事。",
    boundary: "不复制其论文写作/问答流程；Discovery 先做机会雷达和方向判断。",
  },
  {
    name: "PaperQA2",
    url: "https://github.com/Future-House/paper-qa",
    whatToBorrow: "借鉴带引用的科学问答体验，让每个机会都能追溯到 signal。",
    boundary: "不把产品做成纯 RAG；RAG 是详情页证据层，不是核心差异化。",
  },
  {
    name: "ASTA Paper Finder",
    url: "https://github.com/allenai/asta-paper-finder",
    whatToBorrow: "借鉴 query intent → planner → finder 的多步检索思路。",
    boundary: "Discovery 的输入不是单次 query，而是长期 watchlist 与个性化 scout。",
  },
  {
    name: "Argo Scholar",
    url: "https://github.com/argo-scholar/argo",
    whatToBorrow: "借鉴 graph exploration 的空间感，用 radar map 表达机会位置。",
    boundary: "避免复杂图谱优先；先让用户一眼判断 impact / saturation / feasibility。",
  },
];

export const DISCOVERY_DOMAIN_TRACKS: DiscoveryDomainTrack[] = [
  {
    slug: "agent-security",
    name: "Agent Security",
    thesisFit: "系统 / 安全 / 平台治理论文",
    whyNow: "真实 agent 正进入工具链和企业云，权限、审计、审批边界开始成为独立研究问题。",
    opportunityCount: 3,
    difficulty: "medium",
    saturation: "medium",
    idealFor: ["博一/研一", "安全背景", "想做 defensive systems 的同学"],
    starterProblems: [
      "harmless tool sandbox",
      "policy-as-code for tool calls",
      "audit log schema for multi-agent workflows",
    ],
  },
  {
    slug: "agent-evaluation",
    name: "Agent Evaluation",
    thesisFit: "benchmark / eval / HCI × systems 论文",
    whyNow: "benchmark 正从 toy task 转向真实工作流、动态环境和 failure analysis。",
    opportunityCount: 4,
    difficulty: "friendly",
    saturation: "medium",
    idealFor: ["刚入门科研", "需要较快做出可展示结果", "有标注/分析耐心的同学"],
    starterProblems: [
      "failure taxonomy for agent tasks",
      "dynamic-information benchmark slice",
      "framework vs model attribution",
    ],
  },
  {
    slug: "ai4code-systems",
    name: "AI4Code / Kernel / Research Engineering",
    thesisFit: "AI4Code / systems / performance 论文",
    whyNow: "coding agent 正从补代码走向算法发现、kernel 优化和长期研究工程自动化。",
    opportunityCount: 2,
    difficulty: "advanced",
    saturation: "high",
    idealFor: ["有较强工程背景", "会系统实验", "愿意做 correctness oracle 的同学"],
    starterProblems: [
      "small-task coding search benchmark",
      "oracle-backed kernel candidate verification",
      "agent search cost vs gain study",
    ],
  },
  {
    slug: "agent-infra-observability",
    name: "Agent Infra / Observability",
    thesisFit: "云系统 / observability / performance 论文",
    whyNow: "agentic workload 让 inference cost、latency attribution 和 replay correctness 成为研究问题。",
    opportunityCount: 2,
    difficulty: "advanced",
    saturation: "medium",
    idealFor: ["系统方向", "有 trace / infra 环境", "想做短期 systems project 的同学"],
    starterProblems: [
      "trace replay for agent workloads",
      "clock skew and observability failure analysis",
      "energy-per-task modeling",
    ],
  },
];

export const DISCOVERY_PERSONA_PROFILES: DiscoveryPersonaProfile[] = [
  {
    id: "new-grad-student",
    name: "博一 / 研一，还没有 topic",
    description: "知道大方向，但不知道从哪个具体问题切入，担心选题太大或太红海。",
    need: "需要从 domain 收缩到 2–3 个可执行的 topic 候选。",
    bestFitDomainSlugs: ["agent-evaluation", "agent-security"],
    constraints: ["希望 8–12 周能做出第一版结果", "更需要 starter pack 而不是纯榜单"],
  },
  {
    id: "thesis-sprinter",
    name: "想尽快起一个硕士题",
    description: "目标是 1 学期内有实验雏形，偏向 benchmark / audit / systems slice。",
    need: "需要高可行、低依赖、容易讲清楚贡献边界的题。",
    bestFitDomainSlugs: ["agent-evaluation", "agent-security", "agent-infra-observability"],
    constraints: ["数据和算力有限", "不希望选题过于依赖私有环境"],
  },
  {
    id: "topic-owner",
    name: "已经有方向，要持续追",
    description: "已有一个大致 topic，希望每天/每周知道什么值得继续看、什么可以转 RH。",
    need: "需要 watchlist、inbox、digest 和 dossier。",
    bestFitDomainSlugs: ["agent-security", "agent-evaluation", "ai4code-systems", "agent-infra-observability"],
    constraints: ["更在意 signal triage 而不是 topic generation"],
  },
];

export const DISCOVERY_TOPIC_CANDIDATES: DiscoveryTopicCandidate[] = [
  {
    slug: "policy-boundary-audit-sandbox",
    title: "面向 tool-using agents 的 policy boundary 与审计沙箱",
    domainSlug: "agent-security",
    fitFor: ["博一/研一，还没有 topic", "想尽快起一个硕士题"],
    whyItFits: "不需要训练大模型，也不依赖私有数据，可以通过 harmless tasks 做出严谨的系统安全评测。",
    novelty: 84,
    feasibility: 83,
    resourceNeed: "medium",
    horizon: "semester",
    firstMoves: [
      "定义 harmless tools 与高后果动作边界",
      "实现 allowlist / approval / policy-as-code 三种机制",
      "设计 benign failure scenarios 与 audit log schema",
    ],
    starterPack: {
      papers: [
        "Security Considerations for Artificial Intelligence Agents",
        "Auditable Agents",
        "Agent Audit",
      ],
      skills: ["paper-verify", "claim-extraction", "gap-analysis"],
      outputs: ["Threat model", "Policy harness", "Failure matrix"],
    },
  },
  {
    slug: "dynamic-task-benchmark-slice",
    title: "动态信息环境下的 agent benchmark slice",
    domainSlug: "agent-evaluation",
    fitFor: ["博一/研一，还没有 topic", "想尽快起一个硕士题"],
    whyItFits: "容易缩成小型但可发表的 benchmark audit / evaluation 论文，适合先做问题定义和 failure taxonomy。",
    novelty: 78,
    feasibility: 88,
    resourceNeed: "low",
    horizon: "8-weeks",
    firstMoves: [
      "选 10–15 个职业任务子集",
      "定义动态信息和冲突证据扰动",
      "记录 framework 与 model 的失败差异",
    ],
    starterPack: {
      papers: ["OccuBench", "ClawArena"],
      skills: ["literature-search", "claim-extraction", "section-drafting"],
      outputs: ["Task suite", "Failure taxonomy", "Short benchmark memo"],
    },
  },
  {
    slug: "agent-workload-trace-replay",
    title: "Agent workload trace replay 与 observability correctness",
    domainSlug: "agent-infra-observability",
    fitFor: ["想尽快起一个硕士题", "已经有方向，要持续追"],
    whyItFits: "相比做完整 infra paper，更适合先从 trace replay、clock skew 和 attribution correctness 做切口。",
    novelty: 76,
    feasibility: 72,
    resourceNeed: "medium",
    horizon: "semester",
    firstMoves: [
      "定义 token/tool/latency DAG schema",
      "做 replay simulator",
      "比较 skew、retry 和 batching 对 observability 的影响",
    ],
    starterPack: {
      papers: [
        "Blink: CPU-Free LLM Inference",
        "Time, Causality, and Observability Failures",
      ],
      skills: ["literature-search", "gap-analysis", "section-drafting"],
      outputs: ["Trace schema", "Replay harness", "Attribution dashboard"],
    },
  },
  {
    slug: "oracle-backed-coding-search",
    title: "有 correctness oracle 的 coding-agent search benchmark",
    domainSlug: "ai4code-systems",
    fitFor: ["已经有方向，要持续追"],
    whyItFits: "难度较高，但如果有工程背景，可以把大而空的 coding agent 叙事缩成可验证的小问题。",
    novelty: 81,
    feasibility: 66,
    resourceNeed: "high",
    horizon: "year",
    firstMoves: [
      "选择一个窄任务族：kernel / DP / 数值算法",
      "定义 correctness oracle",
      "比较 single-shot、search、evolution loop",
    ],
    starterPack: {
      papers: ["AlphaEvolve impact across fields", "KernelBench-X signals"],
      skills: ["paper-verify", "gap-analysis", "provenance-review"],
      outputs: ["Oracle spec", "Search harness", "Failure trace table"],
    },
  },
];

export const DISCOVERY_DIGEST_ISSUES: DiscoveryDigestIssue[] = [
  {
    id: "2026-05-12-weekly",
    title: "RH Discover Weekly #3",
    date: "2026-05-12",
    focus: "agents in production and scientific loops",
    topLine: "把 agent 产品部署、实时语音接口和 AlphaEvolve 式科研优化闭环转成可测研究题。",
    highlights: [
      "AlphaEvolve 类系统推动 verifier-driven scientific agents",
      "企业 agent ops 暴露部署、审计与 ROI 评测缺口",
      "实时语音 agent 需要联合评测延迟、翻译保真和任务完成",
    ],
    href: "/discover/issues/2026-05-12-weekly",
  },
  {
    id: "2026-05-10-weekly",
    title: "RH Discover Weekly #1",
    date: "2026-05-10",
    focus: "CS / AI trend triage",
    topLine: "把真实的论文、产品与系统信号转成可以立刻进入 RH 的研究机会。",
    highlights: [
      "工具权限安全进入黄海偏蓝区",
      "coding agent → 算法发现正在升温",
      "agentic inference observability 更适合 systems 切口",
    ],
    href: "/discover/issues/2026-05-10-weekly",
  },
  {
    id: "2026-04-26-weekly",
    title: "RH Discover Weekly #0",
    date: "2026-04-26",
    focus: "privacy, science agents, frontier safety",
    topLine: "把开放隐私模型、生命科学科研 agent 和 frontier safety 更新转成可验证研究题。",
    highlights: [
      "隐私过滤成为 tool-using agent 数据管线模块",
      "生命科学 agent 需要工作流可靠性评测",
      "frontier safety 从原则文件进入可操作 gate",
    ],
    href: "/discover/issues/2026-04-26-weekly",
  },
];

export const DISCOVERY_OPPORTUNITIES: DiscoveryOpportunity[] = [
  {
    slug: "real-world-agent-evaluation-under-dynamic-workflows",
    category: "Agent Evaluation",
    horizon: "act-now",
    title: "真实职业任务中的 AI Agent 评测",
    oneLiner:
      "Agent benchmark 正从静态 toy task 转向真实职业任务、动态信息和故障注入。",
    radar: { impact: 92, saturation: 46, momentum: 94, feasibility: 82 },
    audience: ["MS thesis", "Agent eval paper", "Systems + benchmark team"],
    productThesis:
      "当 managed agents 进入企业云环境，市场需要的不再是更会聊天的 agent，而是能解释、复现、审计失败的真实任务评测体系。",
    researchAngles: [
      "构建动态信息环境下的 agent benchmark slice",
      "比较模型能力与 agent framework 对任务完成的相对贡献",
      "把隐式数据损坏、冲突证据和工具错误做成故障注入协议",
    ],
    counterPosition:
      "风险是 benchmark 过快拥挤；差异化必须来自任务选择、故障模型和失败分析，而不是又做一套题。",
    signals: [
      {
        kind: "product",
        title: "OpenAI models, Codex, and Managed Agents come to AWS",
        date: "2026-04-28",
        url: "https://openai.com/index/openai-on-aws/",
        takeaway: "Managed agents 进入企业环境，真实工作流评测需求被放大。",
      },
      {
        kind: "benchmark",
        title: "OccuBench",
        date: "2026-04-13",
        url: "https://arxiv.org/abs/2604.10866",
        takeaway: "100 个真实职业任务，覆盖 10 个行业和故障注入。",
      },
      {
        kind: "benchmark",
        title: "ClawArena",
        date: "2026-04-05",
        url: "https://arxiv.org/abs/2604.04202",
        takeaway: "动态信息、冲突证据和 belief revision 成为核心评测对象。",
      },
    ],
    thirtyDayPlan: [
      {
        week: "Week 1",
        goal: "复现 OccuBench / ClawArena 的任务结构并整理失败维度。",
        output: "Benchmark taxonomy + 10 篇核心论文池。",
      },
      {
        week: "Week 2",
        goal: "设计 12 个小任务，覆盖静态、动态、隐式损坏和冲突证据。",
        output: "可运行 task suite v0。",
      },
      {
        week: "Week 3",
        goal: "跑 2 个模型 × 2 个 agent framework × 4 种故障设置。",
        output: "错误类型矩阵和 trace 样例。",
      },
      {
        week: "Week 4",
        goal: "写成 workshop/eval paper 的 problem framing。",
        output: "4 页 short paper draft + artifact checklist。",
      },
    ],
    brief: {
      title: "从 toy benchmark 转向真实职业任务的 AI Agent 评测",
      summary:
        "Agent 正在进入企业工作流，但 2026 年 4 月出现的 OccuBench、ClawArena 等工作说明：单轮答题或静态任务已经不足以判断 agent 是否可靠。新的评测重点正在转向跨行业任务、动态信息环境、隐式数据损坏、冲突信息和长期工作区 grounding。",
      why_now:
        "OpenAI 与 AWS 在 2026-04-28 宣布把 Codex 和 Managed Agents 推向企业云环境，说明 agent deployment 正在从 demo 进入 production；与此同时，OccuBench 和 ClawArena 把评测问题具体化为职业任务、环境鲁棒性、动态信念更新与框架差异。",
      signals: [],
      trend_context: {
        window: "7d",
        growth_summary:
          "Agent 产品部署与 agent benchmark 论文正在同步升温。",
        saturation: "medium",
      },
      seed_papers: [
        {
          title: "OccuBench: Evaluating AI Agents on Real-World Professional Tasks via Language Environment Simulation",
          doi: "10.48550/arXiv.2604.10866",
          arxiv_id: "2604.10866",
          url: "https://arxiv.org/abs/2604.10866",
          year: 2026,
        },
        {
          title: "ClawArena: Benchmarking AI Agents in Evolving Information Environments",
          doi: "10.48550/arXiv.2604.04202",
          arxiv_id: "2604.04202",
          url: "https://arxiv.org/abs/2604.04202",
          year: 2026,
        },
      ],
      fit_score: {
        trend: 0.92,
        novelty: 0.78,
        feasibility: 0.82,
        user_fit: 0.86,
        risk: 0.34,
      },
      goal_previews: [
        {
          id: "dynamic-workflow-benchmark-slice",
          title: "动态信息环境下的 agent benchmark slice",
          dataset: "12 个真实职业任务子集",
          baseline: "静态任务 benchmark",
          metric_name: "failure recall + task success",
          target_metric_delta: 0.08,
          time_window_days: 30,
          compute_need: "low",
          feasibility: 0.82,
          evidence_strength: 0.78,
          risk: 0.34,
          first_steps: ["定义动态信息扰动", "跑 2 个模型与 2 个 agent framework"],
          goalability: 1,
        },
      ],
      readiness: { evidence: 1, novelty: 0.78, feasibility: 0.82, goalability: 1, handoff_readiness: 1 },
      risks: ["容易变成 benchmark 拼盘，必须强调失败类型和故障模型。"],
      recommended_next_steps: [
        "入库 OccuBench、ClawArena 和 agent evaluation 核心论文。",
        "做一个动态信息环境下的小型 benchmark slice。",
      ],
      rh_handoff: {
        topic_name: "real-world-agent-evaluation-under-dynamic-workflows",
        initial_queries: [
          "AI agent benchmark real-world professional tasks fault injection",
          "dynamic information environment agent evaluation belief revision",
        ],
        suggested_primitives: [
          "paper_search",
          "paper_ingest",
          "baseline_identify",
          "gap_detect",
        ],
      },
    },
  },
  {
    slug: "security-policy-and-auditing-for-tool-using-ai-agents",
    category: "Agent Security",
    horizon: "act-now",
    title: "Agent 安全：从 Prompt Injection 到权限与审计",
    oneLiner:
      "Agent 安全正在变成系统安全：工具、连接器、权限、沙箱和多 agent 协调。",
    radar: { impact: 88, saturation: 32, momentum: 89, feasibility: 76 },
    audience: ["Security paper", "Systems thesis", "Agent platform team"],
    productThesis:
      "真实 agent 会执行动作、访问工具和跨系统传递权限；安全研究的主战场正在从 jailbreak 转向可审计的 policy boundary。",
    researchAngles: [
      "Least-privilege delegation for tool-using agents",
      "High-consequence action gates with deterministic policy checks",
      "Agent failure trace and audit log design",
    ],
    counterPosition:
      "这个方向 dual-use 敏感；产品和论文都应坚持防御评测、无害工具集和最小可复现实验。",
    signals: [
      {
        kind: "paper",
        title: "Security Considerations for Artificial Intelligence Agents",
        date: "2026-03-12",
        url: "https://arxiv.org/abs/2603.12230",
        takeaway: "Agent 改变 code-data separation、authority boundary 和执行可预测性。",
      },
      {
        kind: "workshop",
        title: "ICLR 2026 Agents in the Wild",
        date: "2026-03-13",
        url: "https://openreview.net/forum?id=etVUhp2igM",
        takeaway: "真实部署 agent 的安全、信任和治理成为专门议题。",
      },
      {
        kind: "workshop",
        title: "AIWILD submissions",
        date: "2026-04-24",
        url: "https://openreview.net/submissions?venue=ICLR.cc%2F2026%2FWorkshop%2FAIWILD",
        takeaway: "工具 agent、auditing、goal drift 和 monitoring 形成密集投稿带。",
      },
    ],
    thirtyDayPlan: [
      {
        week: "Week 1",
        goal: "整理 agent 安全攻击面和防御 taxonomy。",
        output: "Threat model + harmless tool sandbox spec。",
      },
      {
        week: "Week 2",
        goal: "实现 allowlist / policy-as-code / approval gate 三种防线。",
        output: "Policy harness v0。",
      },
      {
        week: "Week 3",
        goal: "设计 20 个 benign failure scenarios。",
        output: "Audit traces + confusion matrix。",
      },
      {
        week: "Week 4",
        goal: "把实验写成 defensive agent governance brief。",
        output: "Workshop draft + demo video script。",
      },
    ],
    brief: {
      title: "Agent 安全从 prompt injection 扩展到权限、工具和多 agent 协调",
      summary:
        "Agent 的安全问题正在从模型会不会被 prompt injection 升级为系统问题：工具调用、连接器权限、沙箱边界、长期工作流和高后果动作审批。",
      why_now:
        "当 agent 开始在 AWS、企业软件和真实工具链里执行动作，传统 LLM safety 评测不再够用。",
      signals: [],
      trend_context: {
        window: "7d",
        growth_summary: "Agent 安全正在形成独立系统安全议题。",
        saturation: "low",
      },
      seed_papers: [
        {
          title: "Security Considerations for Artificial Intelligence Agents",
          doi: "10.48550/arXiv.2603.12230",
          arxiv_id: "2603.12230",
          url: "https://arxiv.org/abs/2603.12230",
          year: 2026,
        },
      ],
      fit_score: {
        trend: 0.88,
        novelty: 0.82,
        feasibility: 0.76,
        user_fit: 0.8,
        risk: 0.42,
      },
      goal_previews: [
        {
          id: "harmless-tool-policy-audit",
          title: "无害工具集上的 policy boundary 审计",
          dataset: "harmless tool-use task suite",
          baseline: "allowlist-only sandbox",
          metric_name: "blocked unsafe action rate",
          target_metric_delta: 0.12,
          time_window_days: 30,
          compute_need: "low",
          feasibility: 0.76,
          evidence_strength: 0.74,
          risk: 0.42,
          first_steps: ["定义工具权限边界", "比较 allowlist、policy-as-code 和 human approval"],
          goalability: 1,
        },
      ],
      readiness: { evidence: 1, novelty: 0.82, feasibility: 0.76, goalability: 1, handoff_readiness: 1 },
      risks: ["需要避免 dual-use；应聚焦防御、审计和无害工具集。"],
      recommended_next_steps: [
        "构建 harmless sandbox。",
        "比较 allowlist、policy-as-code 和 human approval。",
      ],
      rh_handoff: {
        topic_name: "security-policy-and-auditing-for-tool-using-ai-agents",
        initial_queries: [
          "AI agent security permission delegation sandbox benchmark",
          "tool using LLM agents indirect prompt injection confused deputy",
        ],
        suggested_primitives: [
          "paper_search",
          "paper_ingest",
          "claim_extract",
          "gap_detect",
        ],
      },
    },
  },
  {
    slug: "verifiable-coding-agents-for-algorithm-and-kernel-discovery",
    category: "AI4Code",
    horizon: "act-now",
    title: "Coding Agent 进入算法发现与 Kernel 优化",
    oneLiner:
      "Coding agent 正从 issue fixing 升级为算法优化、GPU kernel 和研究工程自动化。",
    radar: { impact: 90, saturation: 55, momentum: 91, feasibility: 72 },
    audience: ["AI4Code paper", "ML systems", "GPU/kernel researchers"],
    productThesis:
      "下一个问题不是 agent 会不会写代码，而是 agent 生成的算法和 kernel 是否可验证、可迁移、可复现。",
    researchAngles: [
      "LLM-generated GPU kernel correctness and performance benchmark",
      "Evolutionary coding loop vs. single-shot coding assistant",
      "Research-engineering agents for training recipe discovery",
    ],
    counterPosition:
      "AlphaEvolve 级系统不适合照抄；要缩小到可验证、可复现的小任务。",
    signals: [
      {
        kind: "blog",
        title: "AlphaEvolve impact across fields",
        date: "2026-05-07",
        url: "https://deepmind.google/blog/alphaevolve-impact/",
        takeaway: "Coding agent 被用于科学算法和工程优化。",
      },
      {
        kind: "product",
        title: "Codex on AWS",
        date: "2026-04-28",
        url: "https://openai.com/index/openai-on-aws/",
        takeaway: "企业研发环境中的 coding agent 部署门槛降低。",
      },
      {
        kind: "paper",
        title: "KernelBench-X / Auto Research signals on Hugging Face Daily Papers",
        date: "2026-05-08",
        url: "https://huggingface.co/papers/date/2026-05-08",
        takeaway: "GPU kernel generation、specialist agents 和 skill evolution 同时出现。",
      },
    ],
    thirtyDayPlan: [
      {
        week: "Week 1",
        goal: "选择一个可验证任务族：kernel、DP 或数值算法。",
        output: "Task oracle + baseline list。",
      },
      {
        week: "Week 2",
        goal: "实现 single-shot、agentic search、evolution loop 三种方法。",
        output: "Runnable harness。",
      },
      {
        week: "Week 3",
        goal: "测 correctness、P95 performance、search cost。",
        output: "Result table + failure traces。",
      },
      {
        week: "Week 4",
        goal: "归纳可迁移设计原则。",
        output: "AI4Code paper outline。",
      },
    ],
    brief: {
      title: "Coding agent 正在从补代码升级为算法发现和研究工程自动化",
      summary:
        "DeepMind 展示 AlphaEvolve 跨科学领域效果，OpenAI/AWS 把 Codex 推向企业基础设施，Hugging Face 日榜也出现 kernel 和 auto research 信号。",
      why_now:
        "CS 研究问题从 agent 会不会写代码变成 agent 发现的算法/内核/训练 recipe 是否可复现、可验证、可迁移。",
      signals: [],
      trend_context: {
        window: "7d",
        growth_summary: "Coding agents 正扩展到算法发现和长期研究工程。",
        saturation: "medium",
      },
      seed_papers: [],
      fit_score: {
        trend: 0.9,
        novelty: 0.74,
        feasibility: 0.72,
        user_fit: 0.78,
        risk: 0.48,
      },
      goal_previews: [
        {
          id: "oracle-backed-coding-search",
          title: "有 correctness oracle 的 coding-agent search benchmark",
          dataset: "small algorithm/kernel task suite",
          baseline: "single-shot coding agent",
          metric_name: "verified improvement rate",
          target_metric_delta: 0.1,
          time_window_days: 45,
          compute_need: "medium",
          feasibility: 0.72,
          evidence_strength: 0.7,
          risk: 0.48,
          first_steps: ["选择窄任务族", "定义 correctness oracle", "记录搜索成本和失败类型"],
          goalability: 1,
        },
      ],
      readiness: { evidence: 1, novelty: 0.74, feasibility: 0.72, goalability: 1, handoff_readiness: 1 },
      risks: ["需要 correctness oracle 和性能基线，否则只是 demo。"],
      recommended_next_steps: ["从小型可验证任务切入。", "记录每个 agent 产物和失败类型。"],
      rh_handoff: {
        topic_name: "verifiable-coding-agents-for-algorithm-and-kernel-discovery",
        initial_queries: [
          "LLM coding agents algorithm discovery benchmark reproducibility",
          "LLM generated GPU kernels benchmark correctness performance",
        ],
        suggested_primitives: [
          "paper_search",
          "paper_ingest",
          "baseline_identify",
          "gap_detect",
        ],
      },
    },
  },
  {
    slug: "systems-observability-for-agentic-llm-inference",
    category: "AI Infrastructure",
    horizon: "watch",
    title: "Agentic LLM Inference 的系统与可观测性",
    oneLiner:
      "多轮 agent workload 让推理成本、P99 时延、能耗和因果可观测性成为系统论文机会。",
    radar: { impact: 84, saturation: 51, momentum: 83, feasibility: 68 },
    audience: ["Systems thesis", "Cloud infra", "Performance engineering"],
    productThesis:
      "Agentic workload 的瓶颈不只是模型，而是推理栈、时钟、trace、token 经济和系统边界。",
    researchAngles: [
      "Agent workload trace and latency attribution",
      "Clock skew effects in distributed AI inference observability",
      "Energy-per-token modeling for multi-step agents",
    ],
    counterPosition:
      "硬件依赖强；如果资源有限，应先做 trace replay、simulator 和 observability correctness。",
    signals: [
      {
        kind: "paper",
        title: "Blink: CPU-Free LLM Inference",
        date: "2026-04-08",
        url: "https://arxiv.org/abs/2604.07609",
        takeaway: "把 CPU 从 steady-state inference path 中移出，降低 P99 和能耗。",
      },
      {
        kind: "paper",
        title: "Time, Causality, and Observability Failures",
        date: "2026-04-23",
        url: "https://arxiv.org/abs/2604.21361",
        takeaway: "5ms 时钟偏斜即可造成因果错误的 observability。",
      },
      {
        kind: "paper",
        title: "Energy use of AI inference",
        date: "2026-04-22",
        url: "https://www.sciencedirect.com/science/article/pii/S2542435126001145",
        takeaway: "推理能耗、test-time scaling 和 serving/hardware efficiency 开始合流。",
      },
    ],
    thirtyDayPlan: [
      {
        week: "Week 1",
        goal: "采集 20 条真实 agent workflow trace。",
        output: "Token/tool/latency DAG schema。",
      },
      {
        week: "Week 2",
        goal: "实现 replay simulator 和 skew injection。",
        output: "Trace replay harness。",
      },
      {
        week: "Week 3",
        goal: "比较 batching、retry、clock skew 和 observability strategy。",
        output: "P99 attribution dashboard。",
      },
      {
        week: "Week 4",
        goal: "总结 agentic inference observability 设计原则。",
        output: "Systems short paper draft。",
      },
    ],
    brief: {
      title: "AI inference 正在变成 CS 系统问题：能耗、延迟、时钟和可观测性",
      summary:
        "Agentic AI 让一次任务包含多轮推理、工具调用、长上下文和多服务协作，推理成本与系统可靠性正在成为核心瓶颈。",
      why_now:
        "当 agent 从聊天变成生产工作流，模型能力之外的瓶颈会变成 systems paper 机会。",
      signals: [],
      trend_context: {
        window: "7d",
        growth_summary: "LLM inference 扩展为 datacenter、observability 和 energy 问题。",
        saturation: "medium",
      },
      seed_papers: [
        {
          title: "Blink: CPU-Free LLM Inference by Delegating the Serving Stack to GPU and SmartNIC",
          doi: "10.48550/arXiv.2604.07609",
          arxiv_id: "2604.07609",
          url: "https://arxiv.org/abs/2604.07609",
          year: 2026,
        },
      ],
      fit_score: {
        trend: 0.84,
        novelty: 0.7,
        feasibility: 0.68,
        user_fit: 0.74,
        risk: 0.46,
      },
      goal_previews: [
        {
          id: "agent-trace-replay-observability",
          title: "Agent workflow trace replay 与 attribution correctness",
          dataset: "token/tool/latency DAG traces",
          baseline: "aggregate latency dashboard",
          metric_name: "attribution error rate",
          target_metric_delta: 0.1,
          time_window_days: 45,
          compute_need: "medium",
          feasibility: 0.68,
          evidence_strength: 0.66,
          risk: 0.46,
          first_steps: ["定义 trace schema", "构建 replay simulator", "注入 skew、retry 和 batching"],
          goalability: 1,
        },
      ],
      readiness: { evidence: 1, novelty: 0.7, feasibility: 0.68, goalability: 1, handoff_readiness: 1 },
      risks: ["系统实验环境要求较高，应先做 trace replay。"],
      recommended_next_steps: [
        "记录 agent workflow trace。",
        "构建小型 replay/simulator。",
      ],
      rh_handoff: {
        topic_name: "systems-observability-for-agentic-llm-inference",
        initial_queries: [
          "agentic LLM inference observability latency energy systems",
          "distributed AI inference clock skew causality observability",
        ],
        suggested_primitives: [
          "paper_search",
          "paper_ingest",
          "baseline_identify",
          "gap_detect",
        ],
      },
    },
  },
  {
    slug: "long-horizon-multimodal-agent-grounding-evaluation",
    category: "Multimodal",
    horizon: "watch",
    title: "长视频多模态与具身 Agent Grounding 评测",
    oneLiner:
      "多模态正在从单图问答走向长视频、音视频联合、world action 和具身真实环境。",
    radar: { impact: 82, saturation: 58, momentum: 80, feasibility: 70 },
    audience: ["CV/NLP eval", "Embodied AI", "Dataset audit project"],
    productThesis:
      "模型发布很快，但长期时序、跨模态证据和真实环境 grounding 的评测仍落后。",
    researchAngles: [
      "Long-video evidence localization failure taxonomy",
      "Audio-visual conflict evaluation for MLLMs",
      "Embodied navigation benchmark audit with dynamic humans",
    ],
    counterPosition:
      "不要从零标大数据集；优先做 benchmark audit、错误分类和轻量 evaluator。",
    signals: [
      {
        kind: "paper",
        title: "Hugging Face Daily Papers May 8",
        date: "2026-05-08",
        url: "https://huggingface.co/papers/date/2026-05-08",
        takeaway: "多模态、world/action model 和 agentic reasoning 同时升温。",
      },
      {
        kind: "benchmark",
        title: "MMOU long complex video benchmark",
        date: "2026-03-14",
        url: "https://huggingface.co/papers/2603.14145",
        takeaway: "长复杂视频中的视觉、音频、文本联合推理仍有缺口。",
      },
      {
        kind: "paper",
        title: "VideoLLaMA 3",
        date: "2026-05-08",
        url: "https://huggingface.co/papers/date/2026-05-08",
        takeaway: "视频理解能力继续提升，但 grounding 评测更关键。",
      },
    ],
    thirtyDayPlan: [
      {
        week: "Week 1",
        goal: "选择 MMOU/VideoLLaMA 相关 benchmark 子集。",
        output: "Skill category map。",
      },
      {
        week: "Week 2",
        goal: "人工审计 50 个失败样例。",
        output: "Failure taxonomy v0。",
      },
      {
        week: "Week 3",
        goal: "实现证据定位/冲突检测轻量 evaluator。",
        output: "Evaluator + demo。",
      },
      {
        week: "Week 4",
        goal: "写 benchmark audit 报告。",
        output: "Research memo + RH topic handoff。",
      },
    ],
    brief: {
      title: "多模态长视频与具身 agent 评测正在成为新的 benchmark 战场",
      summary:
        "多模态研究正在从单图 VQA 走向长视频、音视频联合、世界动作模型、具身导航和真实环境 grounding。",
      why_now:
        "多模态模型能力提升很快，但 benchmark 正在暴露长期时序、跨模态证据整合和真实环境泛化缺口。",
      signals: [],
      trend_context: {
        window: "7d",
        growth_summary: "多模态从图文问答升级到长视频和具身任务。",
        saturation: "medium",
      },
      seed_papers: [
        {
          title: "MMOU: A Massive Multi-Task Omni Understanding and Reasoning Benchmark for Long and Complex Real-World Videos",
          doi: "10.48550/arXiv.2603.14145",
          arxiv_id: "2603.14145",
          url: "https://arxiv.org/abs/2603.14145",
          year: 2026,
        },
      ],
      fit_score: {
        trend: 0.82,
        novelty: 0.72,
        feasibility: 0.7,
        user_fit: 0.72,
        risk: 0.44,
      },
      goal_previews: [
        {
          id: "long-horizon-multimodal-grounding-audit",
          title: "长程多模态 grounding benchmark audit",
          dataset: "long-video QA and audio-visual grounding slices",
          baseline: "single-frame or short-clip VLM evaluation",
          metric_name: "grounding failure detection rate",
          target_metric_delta: 0.1,
          time_window_days: 45,
          compute_need: "medium",
          feasibility: 0.7,
          evidence_strength: 0.68,
          risk: 0.44,
          first_steps: ["选择一个窄问题", "做 benchmark audit", "标注 failure taxonomy"],
          goalability: 1,
        },
      ],
      readiness: { evidence: 1, novelty: 0.72, feasibility: 0.7, goalability: 1, handoff_readiness: 1 },
      risks: ["数据成本高；应从 benchmark audit 和失败诊断切入。"],
      recommended_next_steps: [
        "选择一个窄问题。",
        "做 benchmark audit 和 failure taxonomy。",
      ],
      rh_handoff: {
        topic_name: "long-horizon-multimodal-agent-grounding-evaluation",
        initial_queries: [
          "long video multimodal reasoning benchmark audio visual grounding 2026",
          "video language model long horizon evaluation failure taxonomy",
        ],
        suggested_primitives: [
          "paper_search",
          "paper_ingest",
          "claim_extract",
          "gap_detect",
        ],
      },
    },
  },
];

export function getOpportunity(slug: string): DiscoveryOpportunity | undefined {
  return DISCOVERY_OPPORTUNITIES.find((opportunity) => opportunity.slug === slug);
}

export function getActNowOpportunities(): DiscoveryOpportunity[] {
  return DISCOVERY_OPPORTUNITIES.filter(
    (opportunity) => opportunity.horizon === "act-now",
  );
}

export function getDomainTrack(slug: string): DiscoveryDomainTrack | undefined {
  return DISCOVERY_DOMAIN_TRACKS.find((domain) => domain.slug === slug);
}

export function getTopicCandidatesForDomain(slug: string): DiscoveryTopicCandidate[] {
  return DISCOVERY_TOPIC_CANDIDATES.filter((candidate) => candidate.domainSlug === slug);
}

export function getRecommendedOpportunities(profile: string): DiscoveryOpportunity[] {
  const normalized = profile.toLowerCase();
  const scored = DISCOVERY_OPPORTUNITIES.map((opportunity) => {
    const haystack = [
      opportunity.category,
      opportunity.title,
      opportunity.oneLiner,
      opportunity.audience.join(" "),
      opportunity.researchAngles.join(" "),
    ]
      .join(" ")
      .toLowerCase();
    const keywordScore = [
      "agent",
      "security",
      "system",
      "infra",
      "code",
      "multimodal",
      "benchmark",
      "硕士",
      "thesis",
    ].reduce(
      (score, keyword) =>
        normalized.includes(keyword) && haystack.includes(keyword)
          ? score + 10
          : score,
      0,
    );
    return {
      opportunity,
      score:
        keywordScore + opportunity.radar.feasibility + opportunity.radar.momentum / 2,
    };
  });

  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map((item) => item.opportunity);
}

export type DiscoveryWindow = "today" | "week" | "month";

export type DiscoveryOcean = "blue" | "gray" | "yellow" | "red";

export type DiscoveryHotSourceKind =
  | "paper"
  | "repo"
  | "product"
  | "benchmark"
  | "workshop"
  | "community"
  | "blog";

export interface DiscoverySourceCounts {
  paper: number;
  repo: number;
  product: number;
  benchmark: number;
  workshop: number;
  community: number;
}

export interface DiscoveryHotTopicEvidence {
  kind: DiscoveryHotSourceKind;
  title: string;
  source: string;
  date: string;
  url: string;
  takeaway: string;
  stance: "support" | "risk" | "noise";
}

export interface DiscoveryHotTopic {
  id: string;
  title: string;
  shortTitle: string;
  category: DiscoveryCategory;
  windows: DiscoveryWindow[];
  summary: string;
  whyHot: string;
  researchQuestion: string;
  opportunitySlug?: string;
  ocean: DiscoveryOcean;
  oceanLabel: string;
  oceanRationale: string;
  heatScore: number;
  momentumDelta: number;
  freshness: number;
  saturation: number;
  opportunityScore: number;
  sourceCounts: DiscoverySourceCounts;
  trendline: number[];
  tags: string[];
  evidence: DiscoveryHotTopicEvidence[];
  contrarianSignals: string[];
  recommendedAction: string;
}

export interface DiscoverySnapshot {
  window: DiscoveryWindow;
  signalCount: number;
  topicCount: number;
  opportunityCandidateCount: number;
  oceanMix: Record<DiscoveryOcean, number>;
  topTopicId: string | null;
}

export interface DiscoverySourceStatus {
  name: string;
  label: string;
  cadence: string;
  status: "稳定" | "需复核" | "观察中";
  lastSync: string;
  signalCount: number;
}

export const DISCOVERY_LAST_UPDATED = "2026-05-11";

export const DISCOVERY_SOURCE_STATUS: DiscoverySourceStatus[] = [
  {
    name: "论文流",
    label: "arXiv / OpenReview / 期刊",
    cadence: "每日",
    status: "稳定",
    lastSync: "09:20",
    signalCount: 24,
  },
  {
    name: "开源流",
    label: "GitHub / Hugging Face / Papers with Code",
    cadence: "每日",
    status: "观察中",
    lastSync: "08:45",
    signalCount: 10,
  },
  {
    name: "产品流",
    label: "模型厂商 / 云厂商 / 开发者平台",
    cadence: "每日",
    status: "需复核",
    lastSync: "10:05",
    signalCount: 8,
  },
  {
    name: "评测流",
    label: "Benchmark / Leaderboard / Audit report",
    cadence: "每周",
    status: "稳定",
    lastSync: "昨天",
    signalCount: 12,
  },
];

export const DISCOVERY_OCEAN_META: Record<
  DiscoveryOcean,
  { label: string; description: string; color: string }
> = {
  blue: {
    label: "蓝海",
    description: "关注正在上升，但论文/产品密度还不高，适合抢先定义问题。",
    color: "text-cyan-200 bg-cyan-400/15 border-cyan-300/30",
  },
  gray: {
    label: "灰海",
    description: "信号明显，但问题边界尚未稳定，适合探索和做问题定义。",
    color: "text-slate-200 bg-slate-400/15 border-slate-300/25",
  },
  yellow: {
    label: "黄海",
    description: "方向有机会但已升温，需要明确差异化切口。",
    color: "text-amber-200 bg-amber-400/15 border-amber-300/30",
  },
  red: {
    label: "红海",
    description: "同质化论文和 benchmark 密集，普通切入风险高。",
    color: "text-rose-200 bg-rose-400/15 border-rose-300/30",
  },
};

export const DISCOVERY_HOT_TOPICS: DiscoveryHotTopic[] = [
  {
    id: "agent-tool-security-audit",
    title: "Agent 工具权限与审计安全",
    shortTitle: "工具权限安全",
    category: "Agent Security",
    windows: ["today", "week", "month"],
    summary:
      "Agent 正从聊天界面进入真实工具链，权限委托、工具调用审计和高后果动作审批成为系统安全问题。",
    whyHot:
      "近期企业级 managed agents、工具型 agent workshop 和 agent security 论文同时出现，说明安全问题已从 prompt injection 扩展到执行边界。",
    researchQuestion:
      "如何为 tool-using agents 设计可验证、可审计、最小权限的执行边界？",
    opportunitySlug: "security-policy-and-auditing-for-tool-using-ai-agents",
    ocean: "yellow",
    oceanLabel: "黄海偏蓝",
    oceanRationale:
      "安全议题正在升温，但真正围绕权限、审计日志和高后果动作 gate 的系统化评测还不拥挤；只做 jailbreak 会红海，做 policy boundary 仍有空间。",
    heatScore: 94,
    momentumDelta: 42,
    freshness: 88,
    saturation: 36,
    opportunityScore: 91,
    sourceCounts: { paper: 6, repo: 2, product: 2, benchmark: 1, workshop: 3, community: 4 },
    trendline: [34, 38, 41, 55, 62, 79, 94],
    tags: ["Agent 安全", "工具调用", "审计", "系统安全"],
    evidence: [
      {
        kind: "paper",
        title: "Security Considerations for Artificial Intelligence Agents",
        source: "arXiv",
        date: "2026-03-12",
        url: "https://arxiv.org/abs/2603.12230",
        takeaway: "把 agent 安全明确为 authority boundary、tool execution 与可预测性问题。",
        stance: "support",
      },
      {
        kind: "workshop",
        title: "ICLR 2026 Agents in the Wild",
        source: "OpenReview",
        date: "2026-03-13",
        url: "https://openreview.net/forum?id=etVUhp2igM",
        takeaway: "真实部署 agent 的安全、信任、监控与治理成为独立 workshop 议题。",
        stance: "support",
      },
      {
        kind: "product",
        title: "Managed agents enter enterprise clouds",
        source: "AI product releases",
        date: "2026-04-28",
        url: "https://openai.com/index/openai-on-aws/",
        takeaway: "企业部署场景会放大权限、连接器和审计需求。",
        stance: "support",
      },
      {
        kind: "paper",
        title: "Auditable Agents",
        source: "arXiv",
        date: "2026-04-07",
        url: "https://arxiv.org/abs/2604.05485",
        takeaway: "把 accountability、auditability 和 tamper-evident evidence 明确为 agent 系统能力。",
        stance: "support",
      },
      {
        kind: "paper",
        title: "Agent Audit",
        source: "arXiv",
        date: "2026-03-24",
        url: "https://arxiv.org/abs/2603.22853",
        takeaway: "从代码、配置和 MCP 权限维度扫描 agent 应用，说明审计正在产品化。",
        stance: "support",
      },
    ],
    contrarianSignals: [
      "如果只围绕 prompt injection 做攻击样例，会非常拥挤。",
      "安全方向容易触碰 dual-use，必须限制在防御、审计和无害工具集。",
    ],
    recommendedAction: "加入观察并优先生成 RH topic，先做 harmless tool sandbox 与 policy-as-code 评测。",
  },
  {
    id: "real-work-agent-eval",
    title: "真实职业任务 Agent 评测",
    shortTitle: "真实任务评测",
    category: "Agent Evaluation",
    windows: ["today", "week", "month"],
    summary:
      "Agent benchmark 正从静态问答转向真实职业任务、动态信息环境、隐式数据损坏和故障注入。",
    whyHot:
      "OccuBench、ClawArena 等工作把 agent 评测推进到真实工作流和动态信念更新，企业 agent 部署又带来强产品牵引。",
    researchQuestion:
      "真实工作流中，模型能力、agent 框架和环境扰动分别贡献多少失败？",
    opportunitySlug: "real-world-agent-evaluation-under-dynamic-workflows",
    ocean: "yellow",
    oceanLabel: "黄海",
    oceanRationale:
      "agent eval 已经很热，但真实职业任务、动态环境和失败审计仍有差异化空间；泛泛做 benchmark 会快速红海。",
    heatScore: 91,
    momentumDelta: 35,
    freshness: 82,
    saturation: 48,
    opportunityScore: 86,
    sourceCounts: { paper: 5, repo: 1, product: 2, benchmark: 4, workshop: 2, community: 3 },
    trendline: [44, 50, 52, 59, 68, 82, 91],
    tags: ["Agent 评测", "真实任务", "Benchmark", "故障注入"],
    evidence: [
      {
        kind: "benchmark",
        title: "OccuBench",
        source: "arXiv",
        date: "2026-04-13",
        url: "https://arxiv.org/abs/2604.10866",
        takeaway: "以真实职业任务和语言环境模拟推动 agent benchmark。",
        stance: "support",
      },
      {
        kind: "benchmark",
        title: "ClawArena",
        source: "arXiv",
        date: "2026-04-05",
        url: "https://arxiv.org/abs/2604.04202",
        takeaway: "动态信息与冲突证据成为 agent 评测核心变量。",
        stance: "support",
      },
    ],
    contrarianSignals: [
      "Benchmark 方向同质化速度很快，必须有独特任务来源或失败模型。",
      "若缺少人工审计和 trace，结果容易变成排行榜而不是研究贡献。",
    ],
    recommendedAction: "先做 12 个动态信息小任务，验证失败 taxonomy 是否能稳定复现。",
  },
  {
    id: "coding-agent-kernel-discovery",
    title: "Coding Agent 的算法发现与 Kernel 优化",
    shortTitle: "代码智能体优化",
    category: "AI4Code",
    windows: ["today", "week"],
    summary:
      "Coding agent 正从补代码进入算法搜索、GPU kernel 生成和研究工程自动化。",
    whyHot:
      "算法发现、kernel benchmark、企业 coding agent 产品化三个信号同时出现，说明 AI4Code 正从工程效率扩展到科研与系统优化。",
    researchQuestion:
      "LLM 生成的算法/kernel 如何同时保证正确性、性能、成本和可迁移性？",
    opportunitySlug: "verifiable-coding-agents-for-algorithm-and-kernel-discovery",
    ocean: "yellow",
    oceanLabel: "黄海偏红",
    oceanRationale:
      "大厂系统已经很强，直接对标难度高；但缩小到可验证任务族和失败审计仍有论文空间。",
    heatScore: 88,
    momentumDelta: 31,
    freshness: 86,
    saturation: 56,
    opportunityScore: 79,
    sourceCounts: { paper: 4, repo: 4, product: 2, benchmark: 4, workshop: 1, community: 5 },
    trendline: [39, 42, 47, 58, 71, 77, 88],
    tags: ["AI4Code", "Kernel", "算法发现", "可验证"],
    evidence: [
      {
        kind: "blog",
        title: "AlphaEvolve impact across fields",
        source: "DeepMind",
        date: "2026-05-07",
        url: "https://deepmind.google/blog/alphaevolve-impact/",
        takeaway: "coding agent 被推向科学算法和工程优化。",
        stance: "support",
      },
      {
        kind: "repo",
        title: "Kernel generation benchmark signals",
        source: "GitHub / HF Papers",
        date: "2026-05-08",
        url: "https://huggingface.co/papers/date/2026-05-08",
        takeaway: "kernel 生成、specialist agents 与 skill evolution 同时出现。",
        stance: "support",
      },
      {
        kind: "benchmark",
        title: "CCBench real-world coding agent benchmark",
        source: "CodeCrafters",
        date: "2026-02-12",
        url: "https://ccbench.org/",
        takeaway: "以小型真实代码库任务评测 coding agents，强化了“真实工程可验证任务”的产品形态。",
        stance: "support",
      },
    ],
    contrarianSignals: [
      "没有 correctness oracle 和强 baseline，容易只剩 demo。",
      "GPU 资源不足时不应贸然做大规模 kernel 搜索。",
    ],
    recommendedAction: "选择小型可验证任务族，优先比较 single-shot、agentic search、evolution loop。",
  },
  {
    id: "agentic-inference-observability",
    title: "Agentic LLM Inference 系统可观测性",
    shortTitle: "推理系统观测",
    category: "AI Infrastructure",
    windows: ["week", "month"],
    summary:
      "多轮 agent workload 让推理成本、P99 延迟、能耗、时钟偏斜和 trace attribution 变成系统研究问题。",
    whyHot:
      "LLM 推理正在从单次请求转为多步骤工作流，系统瓶颈从模型扩展到 serving stack、trace、调度和能耗。",
    researchQuestion:
      "如何为多步骤 agent workload 构建可复现、可归因、可优化的推理观测体系？",
    opportunitySlug: "systems-observability-for-agentic-llm-inference",
    ocean: "gray",
    oceanLabel: "灰海偏蓝",
    oceanRationale:
      "需求明确但标准问题尚未稳定，硬件依赖较强；用 trace replay 和观测正确性切入比直接做 serving 系统更可行。",
    heatScore: 82,
    momentumDelta: 24,
    freshness: 76,
    saturation: 43,
    opportunityScore: 78,
    sourceCounts: { paper: 5, repo: 1, product: 1, benchmark: 1, workshop: 1, community: 2 },
    trendline: [31, 36, 40, 49, 58, 70, 82],
    tags: ["LLM 系统", "Observability", "P99", "Trace"],
    evidence: [
      {
        kind: "paper",
        title: "Blink: CPU-Free LLM Inference",
        source: "arXiv",
        date: "2026-04-08",
        url: "https://arxiv.org/abs/2604.07609",
        takeaway: "serving stack 优化进入 GPU/SmartNIC 等系统层。",
        stance: "support",
      },
      {
        kind: "paper",
        title: "Time, Causality, and Observability Failures",
        source: "arXiv",
        date: "2026-04-23",
        url: "https://arxiv.org/abs/2604.21361",
        takeaway: "时钟偏斜会造成因果错误的 observability。",
        stance: "support",
      },
    ],
    contrarianSignals: [
      "硬件与生产流量门槛较高，普通团队直接做系统优化不现实。",
      "如果没有真实 trace，论文贡献会偏弱。",
    ],
    recommendedAction: "先做 trace schema 与 replay simulator，把问题定义收紧到观测正确性。",
  },
  {
    id: "long-video-multimodal-grounding",
    title: "长视频多模态与具身 Grounding 评测",
    shortTitle: "长视频 Grounding",
    category: "Multimodal",
    windows: ["week", "month"],
    summary:
      "多模态从单图问答走向长视频、音视频冲突、world action 和真实环境 grounding。",
    whyHot:
      "长视频和多模态模型能力迅速提升，但证据定位、跨模态冲突和真实环境泛化仍是明显评测缺口。",
    researchQuestion:
      "长时序多模态任务中，模型失败来自感知、证据定位还是跨模态冲突？",
    opportunitySlug: "long-horizon-multimodal-agent-grounding-evaluation",
    ocean: "yellow",
    oceanLabel: "黄海偏红",
    oceanRationale:
      "多模态 benchmark 非常热，但做 benchmark audit、失败分类和轻量 evaluator 仍有空间；从零造大数据集不建议。",
    heatScore: 79,
    momentumDelta: 21,
    freshness: 74,
    saturation: 58,
    opportunityScore: 72,
    sourceCounts: { paper: 6, repo: 2, product: 1, benchmark: 3, workshop: 1, community: 3 },
    trendline: [37, 43, 48, 53, 61, 72, 79],
    tags: ["多模态", "长视频", "Grounding", "Benchmark audit"],
    evidence: [
      {
        kind: "benchmark",
        title: "MMOU long complex video benchmark",
        source: "Hugging Face Papers",
        date: "2026-03-14",
        url: "https://huggingface.co/papers/2603.14145",
        takeaway: "长复杂视频中的视觉、音频、文本联合推理仍有缺口。",
        stance: "support",
      },
      {
        kind: "paper",
        title: "VideoLLaMA 3 signals",
        source: "Hugging Face Daily Papers",
        date: "2026-05-08",
        url: "https://huggingface.co/papers/date/2026-05-08",
        takeaway: "视频理解能力快速推进，评测质量更关键。",
        stance: "support",
      },
    ],
    contrarianSignals: [
      "大规模数据标注成本高。",
      "热门模型迭代太快，单一排行榜贡献容易过期。",
    ],
    recommendedAction: "从 benchmark audit 和失败 taxonomy 切入，不从零造大数据集。",
  },
];

export function getHotTopics(window: DiscoveryWindow): DiscoveryHotTopic[] {
  return DISCOVERY_HOT_TOPICS.filter((topic) => topic.windows.includes(window)).sort(
    (a, b) => b.heatScore - a.heatScore,
  );
}

export function getHotTopic(id: string): DiscoveryHotTopic | undefined {
  return DISCOVERY_HOT_TOPICS.find((topic) => topic.id === id);
}

export function getTotalSignalCount(topic: DiscoveryHotTopic): number {
  return Object.values(topic.sourceCounts).reduce((sum, count) => sum + count, 0);
}

export function getDiscoverySnapshot(window: DiscoveryWindow): DiscoverySnapshot {
  const topics = getHotTopics(window);
  const oceanMix = topics.reduce<Record<DiscoveryOcean, number>>(
    (mix, topic) => ({
      ...mix,
      [topic.ocean]: mix[topic.ocean] + 1,
    }),
    { blue: 0, gray: 0, yellow: 0, red: 0 },
  );

  return {
    window,
    signalCount: topics.reduce((sum, topic) => sum + getTotalSignalCount(topic), 0),
    topicCount: topics.length,
    opportunityCandidateCount: topics.filter((topic) => topic.opportunityScore >= 78).length,
    oceanMix,
    topTopicId: topics[0]?.id ?? null,
  };
}

export type DiscoveryIntelligenceChannel = "ai_frontier" | "ai_for_research";

export type DiscoveryEvidenceKind =
  | "official"
  | "paper"
  | "benchmark"
  | "technical-report"
  | "community";

export interface DiscoveryIntelligenceSource {
  title: string;
  publisher: string;
  kind: DiscoveryEvidenceKind;
  date: string;
  url: string;
  note: string;
}

export interface DiscoveryFindingScore {
  authority: number;
  novelty: number;
  impact: number;
  evidence: number;
  userFit: number;
}

export interface DiscoveryFinding {
  id: string;
  channel: DiscoveryIntelligenceChannel;
  title: string;
  judgment: string;
  whyMatters: string;
  confidence: "high" | "medium" | "watch";
  attention: "act_now" | "track_weekly" | "background";
  tags: string[];
  score: DiscoveryFindingScore;
  implications: string[];
  openQuestions: string[];
  evidence: DiscoveryIntelligenceSource[];
}

export interface DiscoveryChannelProfile {
  id: DiscoveryIntelligenceChannel;
  name: string;
  purpose: string;
  scope: string;
  defaultCadence: string;
  sourceMix: string[];
}

export const DISCOVERY_INTELLIGENCE_RUN = {
  generatedAt: "2026-05-11",
  window: "2026-04-11 至 2026-05-11",
  sourceCount: 28,
  findingCount: 12,
  channels: ["ai_frontier", "ai_for_research"] as DiscoveryIntelligenceChannel[],
  collectionSummary: [
    "AI 全域重大事件方向可以稳定产出高质量发现，近一个月头部厂商信号密度足够，核心不是模型榜单，而是 agent runtime、治理、沙箱、企业部署、多模态感知和具身执行。",
    "自动科研方向信号密度也足够独立成频道，近一个月的论文和产品集中在 deep research、实验执行、训练闭环、科学发现与可复现评测。",
    "真正值得给科研人员看的不是所有新闻，而是能够改变研究问题定义的结构性变化：agent 从回答器变成有工具、有记忆、有执行环境、有审计边界的研究协作者。",
  ],
  conclusions: [
    "Discovery v0 应该优先做每周 2 到 3 个强判断，而不是信息流堆叠。",
    "AI 全域频道需要盯头部厂商和科研机构的产品化技术路线，尤其是 agent 基础设施化。",
    "自动科研频道需要盯闭环能力和验证能力，只有能规划、搜索、执行、复盘、产生可核验证据的系统才值得进入重点池。",
    "近期最大瓶颈不是模型会不会写报告，而是引用、实验、代码、数据、工具调用和安全边界能否被验证。",
  ],
} as const;

export const DISCOVERY_CHANNEL_PROFILES: DiscoveryChannelProfile[] = [
  {
    id: "ai_frontier",
    name: "AI 全域重大事件",
    purpose: "主动发现全球头部厂商、实验室、高校和技术领袖正在推动的结构性变化。",
    scope: "模型、agent 平台、开发者基础设施、多模态、具身智能、安全治理与企业部署。",
    defaultCadence: "每周筛出 2 到 3 个重大判断，日常保留候选池。",
    sourceMix: ["OpenAI / Google / Anthropic / NVIDIA 官方发布", "Google DeepMind / arXiv 技术报告", "顶会与高可信技术博客", "少量社区反馈作为需求侧噪声检测"],
  },
  {
    id: "ai_for_research",
    name: "自动科研",
    purpose: "跟踪 AI 如何参与科研发现、文献理解、实验执行、代码训练、证据验证和论文产出。",
    scope: "Deep Research agents、AI Scientist、自动实验、可复现 benchmark、科研软件工程、科学数据工作流。",
    defaultCadence: "每周筛出 1 到 2 个强发现，保留可进入 RH 的候选研究问题。",
    sourceMix: ["arXiv / OpenReview / Springer 开放论文", "Google DeepMind / OpenAI 等官方研究产品", "GitHub 代码与数据集", "Hugging Face Papers 趋势"],
  },
];

export const DISCOVERY_FINDINGS: DiscoveryFinding[] = [
  {
    id: "agent-platforms-become-enterprise-runtime",
    channel: "ai_frontier",
    title: "Agent 正在从 demo 变成企业级运行时",
    judgment: "这是近一个月 AI 全域最重要的主线：头部厂商不再只发布模型，而是在争夺 agent 的运行、治理、身份、工具、记忆和部署入口。",
    whyMatters: "科研上，这会把 agent 研究从 prompt 和 benchmark 推向系统问题：权限边界、长任务可靠性、trace、可观测性、成本归因和组织内治理。",
    confidence: "high",
    attention: "act_now",
    tags: ["agent runtime", "enterprise AI", "governance", "platform"],
    score: { authority: 95, novelty: 82, impact: 94, evidence: 92, userFit: 90 },
    implications: [
      "Agent 可靠性、审计和可观测性会成为 systems / security / HCI 交叉论文机会。",
      "企业平台把真实工作流和权限系统引入 agent 研究，单纯聊天式评测价值下降。",
      "Discovery 后续需要把厂商发布拆成 capability、runtime、governance 三层，而不是混成新闻。",
    ],
    openQuestions: [
      "不同平台的 agent identity、gateway、registry 和 sandbox 抽象能否形成通用评测基准？",
      "长期任务中的失败归因应归因于模型、工具、运行时还是数据权限？",
    ],
    evidence: [
      {
        title: "Gemini Enterprise Agent Platform optimizes your agents",
        publisher: "Google",
        kind: "official",
        date: "2026-04-22",
        url: "https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-enterprise-agent-platform/",
        note: "Google 将 Vertex AI 相关能力与 agent integration、security、DevOps 等功能合并为 Agent Platform。",
      },
      {
        title: "OpenAI models, Codex, and Managed Agents come to AWS",
        publisher: "OpenAI",
        kind: "official",
        date: "2026-04-28",
        url: "https://openai.com/index/openai-on-aws/",
        note: "OpenAI 与 AWS 将模型、Codex 和 Bedrock Managed Agents 推向企业云环境。",
      },
      {
        title: "Agents for financial services",
        publisher: "Anthropic",
        kind: "official",
        date: "2026-05-05",
        url: "https://www.anthropic.com/news/finance-agents",
        note: "Anthropic 发布金融服务 agent 模板，并把 Claude Cowork、Claude Code 和 Managed Agents 作为真实行业工作入口。",
      },
    ],
  },
  {
    id: "sandboxed-agent-infrastructure-is-now-core",
    channel: "ai_frontier",
    title: "沙箱、文件工具和长任务控制成为 agent 基础设施核心",
    judgment: "OpenAI、Anthropic 等厂商的近期动作表明，agent 的竞争焦点正在从模型能力转向可控执行环境。",
    whyMatters: "这直接影响科研系统设计：自动科研 agent 必须能读文件、跑代码、产生中间产物，但又不能破坏环境或泄露凭据。",
    confidence: "high",
    attention: "act_now",
    tags: ["sandbox", "agent safety", "long-horizon", "tool use"],
    score: { authority: 94, novelty: 80, impact: 91, evidence: 90, userFit: 93 },
    implications: [
      "安全边界会成为自动科研系统能否被信任的前提。",
      "评测应记录 agent 的工具调用轨迹、文件修改、测试证据和失败恢复，而不是只看最终答案。",
      "RH Discovery 可以把这类信号归入自动科研频道的基础设施层。",
    ],
    openQuestions: [
      "沙箱是否足以处理 prompt injection、供应链攻击和恶意文件输入？",
      "长任务 checkpoint 与人工审批应该在哪些节点介入？",
    ],
    evidence: [
      {
        title: "The next evolution of the Agents SDK",
        publisher: "OpenAI",
        kind: "official",
        date: "2026-04-15",
        url: "https://openai.com/index/the-next-evolution-of-the-agents-sdk",
        note: "OpenAI Agents SDK 增加 model-native harness 与 native sandbox execution，用于文件、命令和长任务。",
      },
      {
        title: "GPT-5.3-Codex System Card",
        publisher: "OpenAI",
        kind: "technical-report",
        date: "2026-05-04",
        url: "https://deploymentsafety.openai.com/gpt-5-3-codex/gpt-5-3-codex.pdf",
        note: "系统卡把数据破坏、代码执行和 coding agent 安全列为专门风险与评测对象。",
      },
      {
        title: "Trustworthy agents in practice",
        publisher: "Anthropic",
        kind: "official",
        date: "2026-04-09",
        url: "https://www.anthropic.com/research/trustworthy-agents",
        note: "Anthropic 将 agent 风险明确为治理问题，包括误解用户意图、越权行动和 prompt injection。",
      },
    ],
  },
  {
    id: "deep-research-becomes-product-api",
    channel: "ai_frontier",
    title: "Deep Research 从消费级功能变成可调用的研究基础设施",
    judgment: "Google Deep Research Max 把长程检索、MCP、自定义来源和可视化报告打包进 API，这对研究工作流的意义大于普通搜索增强。",
    whyMatters: "这说明 deep research 已经被头部厂商视为 agent pipeline 的第一步：先高质量获得上下文，再进入分析、实验或决策。",
    confidence: "high",
    attention: "act_now",
    tags: ["deep research", "MCP", "research workflow", "Google"],
    score: { authority: 96, novelty: 86, impact: 92, evidence: 92, userFit: 96 },
    implications: [
      "Discovery 自身也应该采用 gather → cluster → judge → explain 的链路，而不是搜索框式产品。",
      "自动科研方向需要把 deep research 与后续实验执行拆开评估。",
      "MCP 支持意味着企业和研究者会把私有资料纳入 agent research pipeline。",
    ],
    openQuestions: [
      "Deep Research 的引用质量和覆盖率如何在动态网页与私有数据源上验证？",
      "研究型 agent 什么时候应该停止搜索并进入实验或写作？",
    ],
    evidence: [
      {
        title: "Deep Research Max: a step change for autonomous research agents",
        publisher: "Google",
        kind: "official",
        date: "2026-04-21",
        url: "https://blog.google/innovation-and-ai/models-and-research/gemini-models/next-generation-gemini-deep-research/",
        note: "Google 称新 Deep Research agents 基于 Gemini 3.1 Pro，支持 MCP、自定义来源和原生可视化。",
      },
      {
        title: "AI Agents for Gemini Enterprise app",
        publisher: "Google Cloud",
        kind: "official",
        date: "2026-05-01",
        url: "https://cloud.google.com/gemini-enterprise/agents",
        note: "Google Cloud 把 Deep Research 列为企业可用 agent，覆盖 web 与企业访问控制数据。",
      },
    ],
  },
  {
    id: "open-multimodal-perception-subagents",
    channel: "ai_frontier",
    title: "开放多模态模型开始承担 agent 的感知子系统",
    judgment: "NVIDIA Nemotron 3 Nano Omni 的关键不只是开源多模态，而是把文本、图像、视频、音频和 GUI 感知变成可部署的 agent perception layer。",
    whyMatters: "研究者可以把多模态 agent 从昂贵闭源模型依赖中部分解耦，重点研究 GUI、文档、音视频和屏幕录制场景下的 evidence grounding。",
    confidence: "high",
    attention: "track_weekly",
    tags: ["multimodal", "open models", "agent perception", "NVIDIA"],
    score: { authority: 94, novelty: 84, impact: 88, evidence: 91, userFit: 84 },
    implications: [
      "多模态 research agent 的瓶颈会从能否看懂，转向看懂后的证据链、任务规划和错误恢复。",
      "开源模型提高了可复现实验的可能性，尤其适合文档智能、GUI agent 和视频理解研究。",
    ],
    openQuestions: [
      "9x 吞吐主张在真实混合模态 agent workload 下是否成立？",
      "开放权重是否足够支持安全评测和 failure taxonomy？",
    ],
    evidence: [
      {
        title: "NVIDIA Launches Nemotron 3 Nano Omni Model",
        publisher: "NVIDIA Blog",
        kind: "official",
        date: "2026-04-28",
        url: "https://blogs.nvidia.com/blog/nemotron-3-nano-omni-multimodal-ai-agents/",
        note: "NVIDIA 将其定位为 agentic systems 的 eyes and ears，覆盖文档、视频、音频和 GUI。",
      },
      {
        title: "Nemotron 3 Nano Omni: Efficient and Open Multimodal Intelligence",
        publisher: "arXiv",
        kind: "technical-report",
        date: "2026-04-27",
        url: "https://arxiv.org/abs/2604.24954",
        note: "技术报告描述原生音频、图像、视频、文本支持和低延迟高吞吐的多模态 token reduction。",
      },
    ],
  },
  {
    id: "embodied-reasoning-moves-to-industrial-inspection",
    channel: "ai_frontier",
    title: "具身推理从演示走向工业检查类任务",
    judgment: "Gemini Robotics-ER 1.6 显示，头部实验室在把 VLM 推向物理世界中的任务规划、成功检测和仪表读取。",
    whyMatters: "这把 AI agent 的边界从浏览器和文件系统扩展到机器人感知执行，研究问题会落在多视角理解、安全约束和现实环境鲁棒性。",
    confidence: "medium",
    attention: "track_weekly",
    tags: ["robotics", "embodied reasoning", "physical agents", "DeepMind"],
    score: { authority: 95, novelty: 83, impact: 87, evidence: 88, userFit: 72 },
    implications: [
      "物理 agent 需要与软件 agent 不同的安全评测，尤其是任务完成检测和环境不确定性。",
      "自动科研的实验室自动化方向可能借鉴 embodied reasoning 的 success detection。",
    ],
    openQuestions: [
      "工业现场的遮挡、污损、光照变化是否会显著降低仪表读取与成功检测？",
      "VLM 层与低层控制策略如何分工，才能保证安全可验证？",
    ],
    evidence: [
      {
        title: "Gemini Robotics-ER 1.6: Powering real-world robotics tasks through enhanced embodied reasoning",
        publisher: "Google DeepMind",
        kind: "official",
        date: "2026-04-14",
        url: "https://deepmind.google/blog/gemini-robotics-er-1-6/",
        note: "DeepMind 强调 spatial reasoning、multi-view understanding、task planning 和 success detection。",
      },
      {
        title: "Gemini Robotics-ER 1.6 Model Card",
        publisher: "Google DeepMind",
        kind: "official",
        date: "2026-04-20",
        url: "https://deepmind.google/models/model-cards/gemini-robotics-er-1-6/",
        note: "模型卡列出输入模态、128k context、用途限制和安全评测。",
      },
    ],
  },
  {
    id: "agent-safety-governance-is-research-domain",
    channel: "ai_frontier",
    title: "Agent 安全与治理正在独立成研究方向",
    judgment: "近期厂商文档、系统卡和产品发布共同说明，agent 风险不再只是 jailbreak，而是权限、越权行动、审计、审批疲劳和组织治理。",
    whyMatters: "这是适合 RH 后续重点跟踪的科研方向，能连接 security、systems、HCI 与企业 AI。",
    confidence: "high",
    attention: "act_now",
    tags: ["agent safety", "governance", "security", "audit"],
    score: { authority: 93, novelty: 78, impact: 90, evidence: 88, userFit: 91 },
    implications: [
      "防御向 agent security 论文可以从 harmless sandbox、policy-as-code、approval gate 和 audit log schema 切入。",
      "产品形态上，Discovery 应给出风险判断，而不是只给热度排序。",
    ],
    openQuestions: [
      "如何构造不具 dual-use 风险但能真实暴露越权行为的评测集？",
      "高后果动作 gate 是由模型判断、规则判断还是混合系统判断？",
    ],
    evidence: [
      {
        title: "Trustworthy agents in practice",
        publisher: "Anthropic",
        kind: "official",
        date: "2026-04-09",
        url: "https://www.anthropic.com/research/trustworthy-agents",
        note: "Anthropic 明确讨论 agent 自主性带来的误解意图、越权行动和 prompt injection 风险。",
      },
      {
        title: "The next evolution of the Agents SDK",
        publisher: "OpenAI",
        kind: "official",
        date: "2026-04-15",
        url: "https://openai.com/index/the-next-evolution-of-the-agents-sdk",
        note: "OpenAI 把受控 workspace 和 sandbox 作为构建 agent 的基础能力。",
      },
      {
        title: "Gemini Enterprise Agent Platform optimizes your agents",
        publisher: "Google",
        kind: "official",
        date: "2026-04-22",
        url: "https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-enterprise-agent-platform/",
        note: "Google Agent Platform 引入 agent integration、security、DevOps 和治理能力。",
      },
    ],
  },
  {
    id: "ai-research-agents-need-closed-loop-execution",
    channel: "ai_for_research",
    title: "自动科研正在从文献总结进入闭环执行",
    judgment: "近一个月的论文信号显示，自动科研系统不再满足于读论文和写综述，而是开始覆盖需求分析、文献检索、实验设计、训练执行和结果复盘。",
    whyMatters: "这和 RH 的长期方向高度相关：真正有价值的自动科研不是一次性报告，而是可追踪、可复现、可审计的研究流程。",
    confidence: "high",
    attention: "act_now",
    tags: ["AI for Research", "closed loop", "experiment automation", "LLM training"],
    score: { authority: 86, novelty: 88, impact: 91, evidence: 86, userFit: 98 },
    implications: [
      "自动科研频道应重点收集能产生可执行实验和可复核产物的系统。",
      "未来 RH 可以把 Discovery 的发现转成实验候选，但当前 v0 先不做接入。",
      "系统评测要看每一步是否有证据和失败记录，而不是只看最终 paper-like 文本。",
    ],
    openQuestions: [
      "闭环系统中的失败经验如何沉淀为可迁移策略？",
      "自动实验是否会过度优化 benchmark，而忽略真实科研问题的外部有效性？",
    ],
    evidence: [
      {
        title: "TREX: Automating LLM Fine-tuning via Agent-Driven Tree-based Exploration",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-04-15",
        url: "https://arxiv.org/abs/2604.14116",
        note: "TREX 用 Researcher 与 Executor 两个模块自动完成 LLM 微调生命周期，并用搜索树管理多轮实验。",
      },
      {
        title: "SciResearcher: Scaling Deep Research Agents for Frontier Scientific Reasoning",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-05-02",
        url: "https://arxiv.org/abs/2605.01489",
        note: "SciResearcher 关注前沿科学任务的数据构造、工具推理和长程能力训练。",
      },
      {
        title: "ResearchEVO: An End-to-End Framework for Automated Scientific Discovery and Documentation",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-04-07",
        url: "https://arxiv.org/abs/2604.05587",
        note: "窗口外延伸信号，覆盖算法演化、实验生成和带反幻觉验证的论文写作。",
      },
    ],
  },
  {
    id: "deep-research-agents-become-research-input-layer",
    channel: "ai_for_research",
    title: "Deep Research 成为科研 agent 的输入层",
    judgment: "Google Deep Research Max 的产品化说明，科研 agent 的第一层能力正在标准化：长程检索、来源筛选、证据整合、自定义数据源和可视化输出。",
    whyMatters: "这正是 Discovery 的底层工作流原型：不是等用户搜索，而是主动收集并说明为什么值得关注。",
    confidence: "high",
    attention: "act_now",
    tags: ["deep research", "literature discovery", "MCP", "evidence"],
    score: { authority: 96, novelty: 86, impact: 90, evidence: 91, userFit: 99 },
    implications: [
      "Discovery 应把原始网页、论文、技术文档统一成 signal，再聚合成 finding。",
      "自动科研系统必须把证据层展示出来，否则无法建立科研信任。",
    ],
    openQuestions: [
      "如何评估一个 deep research agent 的覆盖率与遗漏率？",
      "在自动科研里，自定义私有来源会不会导致不可复现？",
    ],
    evidence: [
      {
        title: "Deep Research Max: a step change for autonomous research agents",
        publisher: "Google",
        kind: "official",
        date: "2026-04-21",
        url: "https://blog.google/innovation-and-ai/models-and-research/gemini-models/next-generation-gemini-deep-research/",
        note: "Google 把 Deep Research 描述为复杂 agentic pipeline 的第一步。",
      },
      {
        title: "ResearchRubrics: A Benchmark of Prompts and Rubrics For Evaluating Deep Research Agents",
        publisher: "OpenReview",
        kind: "benchmark",
        date: "2026-04-20",
        url: "https://openreview.net/forum?id=ErnvfmSX0P",
        note: "ICLR 2026 论文给 deep research 输出质量提供专家 rubric 评测框架。",
      },
    ],
  },
  {
    id: "multimodal-search-agents-get-open-recipes",
    channel: "ai_for_research",
    title: "多模态深度搜索 agent 开始出现开放训练 recipe",
    judgment: "OpenSearch-VL、MTA-Agent 等工作说明，多模态研究检索不再只是闭源产品能力，正在变成可复现实验对象。",
    whyMatters: "科研人员经常需要跨图、表、PDF、视频和网页证据工作，多模态 deep search 会成为自动科研的重要底座。",
    confidence: "medium",
    attention: "track_weekly",
    tags: ["multimodal search", "open recipe", "agentic RL", "evidence verification"],
    score: { authority: 82, novelty: 89, impact: 86, evidence: 84, userFit: 91 },
    implications: [
      "未来的文献检索系统不能只处理文本摘要，还要处理图表、截图、PDF 版式和视频证据。",
      "开放数据和轨迹让研究者能比较工具环境、搜索策略和故障恢复。",
    ],
    openQuestions: [
      "多模态搜索 agent 的 judge 是否会过度依赖 GPT-4o 这类外部评审？",
      "视觉证据 grounding 的错误如何在 UI 中展示给科研人员？",
    ],
    evidence: [
      {
        title: "OpenSearch-VL: An Open Recipe for Frontier Multimodal Search Agents",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-05-06",
        url: "https://arxiv.org/abs/2605.05185",
        note: "提出开放训练 recipe，包含视觉 grounding 数据、统一工具环境和 fatal-aware GRPO。",
      },
      {
        title: "MTA-Agent: An Open Recipe for Multimodal Deep Search Agents",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-04-07",
        url: "https://arxiv.org/abs/2604.06376",
        note: "窗口外延伸信号，提出工具增强多跳视觉语言证据合成和可复现训练数据。",
      },
    ],
  },
  {
    id: "research-agent-evaluation-is-a-bottleneck",
    channel: "ai_for_research",
    title: "自动科研的评测正在从答案分数转向过程与证据",
    judgment: "Deep research 和自动科研 agent 的核心瓶颈不是能否生成长文，而是引用是否真实、推理是否完整、检索过程是否可靠、实验是否可复现。",
    whyMatters: "如果没有过程级评测，自动科研系统很容易产生看起来完整但无法复核的产物。",
    confidence: "high",
    attention: "act_now",
    tags: ["evaluation", "rubrics", "grounding", "reproducibility"],
    score: { authority: 87, novelty: 79, impact: 92, evidence: 86, userFit: 97 },
    implications: [
      "Discovery 详情页应该展示判断依据和反证，而不是只给摘要。",
      "自动科研系统要保留检索轨迹、来源列表、代码执行记录和实验配置。",
      "评测基准会从静态 QA 走向报告、过程、工具调用和多文件产出。",
    ],
    openQuestions: [
      "专家 rubric 成本高，能否形成半自动、可持续更新的评测流程？",
      "过程评测是否会鼓励 agent 做过多无效搜索以显得努力？",
    ],
    evidence: [
      {
        title: "DR3-Eval: Towards Realistic and Reproducible Deep Research Evaluation",
        publisher: "arXiv",
        kind: "benchmark",
        date: "2026-04-16",
        url: "https://arxiv.org/abs/2604.14683",
        note: "提出面向多模态、多文件报告生成的真实可复现 deep research 评测。",
      },
      {
        title: "ResearchRubrics",
        publisher: "OpenReview",
        kind: "benchmark",
        date: "2026-04-20",
        url: "https://openreview.net/forum?id=ErnvfmSX0P",
        note: "用专家撰写细粒度 rubric 评估 factual grounding、reasoning soundness 和 clarity。",
      },
      {
        title: "MiroEval: Benchmarking Multimodal Deep Research Agents in Process and Outcome",
        publisher: "arXiv",
        kind: "benchmark",
        date: "2026-03-30",
        url: "https://arxiv.org/abs/2603.28407",
        note: "窗口外延伸信号，强调 outcome 与过程双重评测。",
      },
    ],
  },
  {
    id: "ai-scientist-memory-and-self-evolution",
    channel: "ai_for_research",
    title: "AI Scientist 的关键部件变成记忆和自我演化",
    judgment: "自动科研系统的下一步不是更多 agent 名称，而是能否把失败实验、有效策略和研究偏好沉淀为长期记忆。",
    whyMatters: "这与 RH 的项目记忆和 provenance 高度一致，说明研究系统要从一次性任务工具变成持续学习的研究伙伴。",
    confidence: "medium",
    attention: "track_weekly",
    tags: ["AI scientist", "memory", "self-evolution", "provenance"],
    score: { authority: 79, novelty: 86, impact: 84, evidence: 78, userFit: 95 },
    implications: [
      "Discovery 未来可以从用户在 RH 中的历史行为学习关注主题，但 v0 先做显式频道。",
      "自动科研系统需要记录失败路径，否则会重复走无效实验。",
    ],
    openQuestions: [
      "长期记忆如何避免固化错误结论和早期偏见？",
      "不同 topic 的经验能否迁移，还是只能局部有效？",
    ],
    evidence: [
      {
        title: "TREX: Automating LLM Fine-tuning via Agent-Driven Tree-based Exploration",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-04-15",
        url: "https://arxiv.org/abs/2604.14116",
        note: "TREX 使用搜索树复用历史结果并从迭代实验中提炼高层洞见。",
      },
      {
        title: "EvoScientist: Towards Multi-Agent Evolving AI Scientists for End-to-End Scientific Discovery",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-03-09",
        url: "https://arxiv.org/abs/2603.08127",
        note: "窗口外背景信号，强调 persistent memory 与 self-evolution 对科研 agent 的作用。",
      },
    ],
  },
  {
    id: "research-software-quality-enters-ai-for-research",
    channel: "ai_for_research",
    title: "科研软件工程质量成为 AI for Research 的硬约束",
    judgment: "自动科研如果要进入真实科研流程，必须处理代码质量、FAIR 元数据、自动化测试、发布、可复现和 MLOps/AIOps 等问题。",
    whyMatters: "这提醒我们，自动科研不能只做 paper writing，必须把实验代码、数据处理、环境和验证作为一等产物。",
    confidence: "medium",
    attention: "background",
    tags: ["research software", "reproducibility", "FAIR", "MLOps"],
    score: { authority: 84, novelty: 72, impact: 82, evidence: 82, userFit: 88 },
    implications: [
      "RH 后续若接入 Discovery，应把发现转成可验证工程任务，而不是只转成阅读列表。",
      "自动科研 finding 的评分需要加入可复现性和工程可执行性。",
    ],
    openQuestions: [
      "科研软件质量指标如何与 agent 自动生成代码的质量评测结合？",
      "自动科研系统能否自动补齐数据卡、模型卡和实验环境说明？",
    ],
    evidence: [
      {
        title: "Advancing research software engineering with AI: a research framework",
        publisher: "Automated Software Engineering",
        kind: "paper",
        date: "2026-05-04",
        url: "https://link.springer.com/article/10.1007/s10515-026-00621-0",
        note: "论文从软件工程成熟度、FAIR4RS、AI 使用和 MLOps/AIOps 信号分析研究软件。",
      },
      {
        title: "TREX: Automating LLM Fine-tuning via Agent-Driven Tree-based Exploration",
        publisher: "arXiv",
        kind: "paper",
        date: "2026-04-15",
        url: "https://arxiv.org/abs/2604.14116",
        note: "自动训练生命周期把数据 recipe、训练执行和评测纳入同一个 agent loop。",
      },
    ],
  },
  {
    id: "automated-scientific-discovery-needs-sober-positioning",
    channel: "ai_for_research",
    title: "自动科学发现需要更冷静的能力边界",
    judgment: "近期综述和框架论文共同提醒：自动科研确实在前进，但重大科学发现仍依赖可验证实验、领域知识、实验室基础设施和人类判断。",
    whyMatters: "Discovery 应避免把自动科研包装成全自动科学家，而要筛出真实可用的科研流程增量。",
    confidence: "high",
    attention: "track_weekly",
    tags: ["automated discovery", "survey", "limitations", "scientific method"],
    score: { authority: 88, novelty: 75, impact: 87, evidence: 86, userFit: 94 },
    implications: [
      "自动科研频道应同时展示机会和限制，尤其是验证、grounding、reproducibility 和 domain execution。",
      "好 finding 必须说明它能启发什么研究问题，而不是只说系统很强。",
    ],
    openQuestions: [
      "哪些科学领域最先适合高自动化，哪些必须保持人类主导？",
      "自动发现系统的贡献如何在论文署名和审稿中界定？",
    ],
    evidence: [
      {
        title: "Automated Scientific Discovery: From Equation Discovery to Autonomous Discovery Systems",
        publisher: "Machine Learning",
        kind: "paper",
        date: "2026-04-29",
        url: "https://link.springer.com/article/10.1007/s10994-025-06955-2",
        note: "开放综述从 equation discovery、symbolic regression 到 autonomous discovery systems 系统梳理领域。",
      },
      {
        title: "Toward Autonomous Scientific Discovery: A Practical Framework for AI Agent Research Using Open Data",
        publisher: "clawrXiv",
        kind: "paper",
        date: "2026-05-11",
        url: "https://clawrxiv.org/papers/2026.00013",
        note: "提出自治层级和质量检查，强调可验证、统计有效性和可复现文档。",
      },
    ],
  },
];

export function getDiscoveryFindingsByChannel(channel: DiscoveryIntelligenceChannel) {
  return DISCOVERY_FINDINGS.filter((finding) => finding.channel === channel).sort(
    (a, b) => getFindingCompositeScore(b) - getFindingCompositeScore(a),
  );
}

export function getFindingCompositeScore(finding: DiscoveryFinding) {
  const { authority, evidence, impact, novelty, userFit } = finding.score;
  return Math.round(authority * 0.18 + novelty * 0.18 + impact * 0.25 + evidence * 0.19 + userFit * 0.2);
}

export function getTopDiscoveryFindings(limit = 5) {
  return [...DISCOVERY_FINDINGS]
    .sort((a, b) => getFindingCompositeScore(b) - getFindingCompositeScore(a))
    .slice(0, limit);
}

export type DiscoveryEvidenceSide = "industry" | "academia" | "bridge";
export type DiscoveryMaturity = "emerging" | "prototype" | "shipping" | "benchmarking";

export interface DiscoveryProblemEvidenceSignal {
  side: DiscoveryEvidenceSide;
  kind: DiscoveryEvidenceKind | "product" | "standard" | "system-card";
  title: string;
  organization: string;
  date: string;
  url: string;
  takeaway: string;
}

export interface DiscoverySolutionTrack {
  title: string;
  maturity: DiscoveryMaturity;
  summary: string;
  currentLimit: string;
  evidenceRefs: string[];
}

export interface DiscoveryStoryAngle {
  title: string;
  opener: string;
  researchQuestions: string[];
  suitableFor: string[];
}

export interface DiscoveryProblemCluster {
  id: string;
  title: string;
  problemStatement: string;
  whyNow: string;
  industryFocus: string;
  academicFocus: string;
  score: {
    urgency: number;
    industryConvergence: number;
    academicConvergence: number;
    solutionMaturity: number;
    gapDepth: number;
    narrativeValue: number;
  };
  solutionTracks: DiscoverySolutionTrack[];
  unresolvedGaps: string[];
  storyAngles: DiscoveryStoryAngle[];
  evidence: DiscoveryProblemEvidenceSignal[];
}

export interface DiscoveryProblemTheme {
  id: string;
  title: string;
  thesis: string;
  userValue: string;
  clusters: DiscoveryProblemCluster[];
}

export type DiscoveryCategorySaturation = "low" | "medium" | "high";

export interface DiscoveryProblemCategory {
  id: string;
  title: string;
  shortTitle: string;
  focus: string;
  decisionCue: string;
  primaryClusterIds: string[];
  trend12m: number[];
  saturation: DiscoveryCategorySaturation;
  researchSpace: string;
  evidenceTarget: number;
  priorityScore: number;
}

export interface DiscoveryEvidenceCoverageItem {
  evidenceCount: number;
  recentCount: number;
  routes: string[];
  providers: string[];
}

export const DISCOVERY_EVIDENCE_COVERAGE = {
  generatedAt: "2026-05-13T02:14:50.721248+00:00",
  freshnessYearFrom: 2025,
  minPerProblem: 100,
  routeErrorCount: 0,
  records: 2145,
  problems: {
    "agentic-systems": {
      evidenceCount: 213,
      recentCount: 213,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "ai-for-research": {
      evidenceCount: 227,
      recentCount: 227,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "evaluation-benchmarks": {
      evidenceCount: 218,
      recentCount: 218,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "safety-governance": {
      evidenceCount: 201,
      recentCount: 201,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "enterprise-ai-workflow": {
      evidenceCount: 209,
      recentCount: 209,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "multimodal-intelligence": {
      evidenceCount: 196,
      recentCount: 196,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "ai-infrastructure": {
      evidenceCount: 247,
      recentCount: 247,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "retrieval-knowledge-data": {
      evidenceCount: 221,
      recentCount: 221,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "domain-science-ai": {
      evidenceCount: 204,
      recentCount: 204,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
    "robotics-embodied-ai": {
      evidenceCount: 209,
      recentCount: 209,
      routes: ["provider_fanout", "rh_paper_search"],
      providers: ["crossref", "multi", "openalex"],
    },
  } satisfies Record<string, DiscoveryEvidenceCoverageItem>,
} as const;

export const DISCOVERY_PROBLEM_MAP_RUN = {
  generatedAt: "2026-05-11",
  window: "2026-04-11 至 2026-05-11",
  model: "category → problem tree → solution track → evidence → research story",
  scannedSignalCount: 2145,
  evidenceSignalCount: 2145,
  categoryCount: 10,
  themeCount: 3,
  problemClusterCount: 8,
  productPrinciple: "首页先给 10 个可筛选问题大类和趋势，再让用户展开证据与论文故事。",
  selectionRule:
    "只有同时具备业界关注、学术关注、可观察解决方案和仍未解决 gap 的问题，才进入主地图。",
} as const;

export const DISCOVERY_PROBLEM_CATEGORIES: DiscoveryProblemCategory[] = [
  {
    id: "agentic-systems",
    title: "Agentic Systems",
    shortTitle: "Agent 系统",
    focus: "从对话能力走向可执行工作流，核心是边界、长任务和失败复盘。",
    decisionCue: "适合做 agent safety、systems、workflow evaluation 的主入口。",
    primaryClusterIds: ["agent-execution-boundary-audit", "agentic-workload-observability-cost"],
    trend12m: [31, 34, 38, 42, 47, 53, 59, 66, 74, 82, 91, 96],
    saturation: "medium",
    researchSpace: "高关注但评测标准未定",
    evidenceTarget: 100,
    priorityScore: 96,
  },
  {
    id: "ai-for-research",
    title: "AI for Research",
    shortTitle: "自动科研",
    focus: "研究 agent 从总结论文走向实验执行、代码产物和过程 provenance。",
    decisionCue: "适合把 Discovery 钩子转成论文 abstract / intro / related work。",
    primaryClusterIds: ["closed-loop-experiment-automation", "research-process-reproducibility"],
    trend12m: [24, 26, 31, 35, 39, 44, 50, 57, 65, 73, 83, 92],
    saturation: "medium",
    researchSpace: "概念热，但可靠闭环还稀缺",
    evidenceTarget: 100,
    priorityScore: 94,
  },
  {
    id: "evaluation-benchmarks",
    title: "Evaluation & Benchmarks",
    shortTitle: "评测基准",
    focus: "真实任务、深度研究、多模态证据和动态环境正在重塑 benchmark。",
    decisionCue: "适合做低成本、可复现、容易讲清贡献的论文题。",
    primaryClusterIds: ["deep-research-evidence-reliability", "multimodal-research-search-grounding"],
    trend12m: [35, 36, 39, 41, 45, 48, 54, 61, 69, 78, 86, 93],
    saturation: "medium",
    researchSpace: "红海边缘，但细分任务仍有窗口",
    evidenceTarget: 100,
    priorityScore: 93,
  },
  {
    id: "safety-governance",
    title: "Safety & Governance",
    shortTitle: "安全治理",
    focus: "权限、审批、审计、模型卡和组织治理正在从原则变成工程问题。",
    decisionCue: "适合做防御向安全、policy gate、agent governance。",
    primaryClusterIds: ["agent-execution-boundary-audit", "enterprise-agent-governance"],
    trend12m: [29, 31, 35, 39, 45, 51, 58, 64, 72, 79, 86, 91],
    saturation: "low",
    researchSpace: "需求强，公开 benchmark 不足",
    evidenceTarget: 100,
    priorityScore: 92,
  },
  {
    id: "enterprise-ai-workflow",
    title: "Enterprise AI Workflow",
    shortTitle: "企业工作流",
    focus: "Agent 进入企业平台后，身份、权限、ROI 和任务级观测成为核心问题。",
    decisionCue: "适合做 agent ops、可观测性、human-in-the-loop 成本评估。",
    primaryClusterIds: ["enterprise-agent-governance", "agentic-workload-observability-cost"],
    trend12m: [27, 29, 32, 37, 42, 48, 55, 62, 71, 80, 88, 90],
    saturation: "low",
    researchSpace: "产品很热，学术定义未稳定",
    evidenceTarget: 100,
    priorityScore: 90,
  },
  {
    id: "multimodal-intelligence",
    title: "Multimodal Intelligence",
    shortTitle: "多模态智能",
    focus: "文本以外的图表、PDF、视频、GUI 和音频正在进入 agent 证据链。",
    decisionCue: "适合做 multimodal IR、document AI、grounding uncertainty。",
    primaryClusterIds: ["multimodal-research-search-grounding", "embodied-success-detection"],
    trend12m: [38, 40, 43, 47, 50, 54, 59, 64, 70, 76, 84, 89],
    saturation: "medium",
    researchSpace: "模型多，但任务级证据链少",
    evidenceTarget: 100,
    priorityScore: 89,
  },
  {
    id: "ai-infrastructure",
    title: "AI Infrastructure",
    shortTitle: "AI 基础设施",
    focus: "长任务推理、成本归因、sandbox、gateway 和 trace 成为 agent 落地底座。",
    decisionCue: "适合做 systems、observability、cost-aware inference。",
    primaryClusterIds: ["agentic-workload-observability-cost", "agent-execution-boundary-audit"],
    trend12m: [30, 32, 35, 38, 41, 47, 53, 60, 67, 74, 81, 87],
    saturation: "medium",
    researchSpace: "工程需求清晰，公开数据不足",
    evidenceTarget: 100,
    priorityScore: 87,
  },
  {
    id: "retrieval-knowledge-data",
    title: "Retrieval / Knowledge / Data",
    shortTitle: "检索与知识",
    focus: "深度研究和多源综合要求检索系统处理冲突证据、来源约束和引用粒度。",
    decisionCue: "适合做 retrieval evaluation、source grounding、多源证据 UI。",
    primaryClusterIds: ["deep-research-evidence-reliability", "multimodal-research-search-grounding"],
    trend12m: [33, 34, 36, 39, 43, 48, 52, 58, 64, 71, 79, 85],
    saturation: "high",
    researchSpace: "传统方向偏红海，新场景仍可切",
    evidenceTarget: 100,
    priorityScore: 85,
  },
  {
    id: "domain-science-ai",
    title: "Domain Science AI",
    shortTitle: "领域科学 AI",
    focus: "生命科学、材料、气候等领域正在把 AI agent 接到真实科学任务。",
    decisionCue: "适合做专用科研 agent、domain workflow reliability。",
    primaryClusterIds: ["closed-loop-experiment-automation", "research-process-reproducibility"],
    trend12m: [21, 23, 27, 30, 35, 40, 47, 54, 62, 70, 78, 84],
    saturation: "low",
    researchSpace: "需要领域约束，科研空间大",
    evidenceTarget: 100,
    priorityScore: 84,
  },
  {
    id: "robotics-embodied-ai",
    title: "Robotics / Embodied AI",
    shortTitle: "具身智能",
    focus: "机器人和物理/GUI agent 需要成功检测、安全执行和多视角证据。",
    decisionCue: "适合做 embodied success detection、physical safety evaluation。",
    primaryClusterIds: ["embodied-success-detection", "multimodal-research-search-grounding"],
    trend12m: [25, 27, 30, 34, 38, 42, 47, 53, 60, 68, 76, 82],
    saturation: "medium",
    researchSpace: "数据难，但问题清楚",
    evidenceTarget: 100,
    priorityScore: 82,
  },
];

export const DISCOVERY_PROBLEM_THEMES: DiscoveryProblemTheme[] = [
  {
    id: "agents-become-action-systems",
    title: "Agent 从对话系统走向行动系统",
    thesis:
      "大厂正在把 agent 放进真实工具、企业权限和长任务环境；学术界也开始把安全、审计、可观测性和动态环境作为核心问题。",
    userValue:
      "帮助研究者把“agent 很火”讲成更具体的科研故事：当 AI 开始行动，系统如何约束、观察和复盘它。",
    clusters: [
      {
        id: "agent-execution-boundary-audit",
        title: "执行边界与安全审计",
        problemStatement:
          "AI agent 已经能读文件、调用工具、运行代码和修改环境，但它的权限边界、审批机制和审计记录仍然不够标准化。",
        whyNow:
          "OpenAI、Google、Anthropic 都在近期把 sandbox、agent platform、trustworthy agents 和 managed agents 推到前台，说明问题已经从实验室进入产品化基础设施。",
        industryFocus:
          "受控 workspace、native sandbox、agent gateway、managed agents、企业数据访问控制和高后果动作审批。",
        academicFocus:
          "agent security、tool-use safety、confused deputy、prompt injection、防御性 audit log、policy boundary 与可复现安全评测。",
        score: {
          urgency: 96,
          industryConvergence: 95,
          academicConvergence: 88,
          solutionMaturity: 76,
          gapDepth: 91,
          narrativeValue: 98,
        },
        solutionTracks: [
          {
            title: "受控沙箱与长任务 workspace",
            maturity: "shipping",
            summary:
              "把 agent 的文件、命令、网络和中间产物放进受限环境，允许长任务执行但保留边界。",
            currentLimit:
              "沙箱解决执行隔离，但不能自动解决越权意图、工具误用和跨系统身份委托。",
            evidenceRefs: ["OpenAI Agents SDK", "GPT-5.3-Codex System Card"],
          },
          {
            title: "Policy gate 与可审计 trace",
            maturity: "prototype",
            summary:
              "在工具调用、高后果动作和跨系统访问前加入规则或模型辅助 gate，并记录可复盘轨迹。",
            currentLimit:
              "审批疲劳、规则覆盖不足和 trace schema 不统一，都会影响真实采用。",
            evidenceRefs: ["Trustworthy agents in practice", "Security Considerations for AI Agents"],
          },
        ],
        unresolvedGaps: [
          "跨平台 agent action trace 尚未形成统一 schema。",
          "审批机制如何避免既过度打断又漏放风险动作，仍缺少公开 benchmark。",
          "安全研究容易 dual-use，需要防御性、无害工具集和可复现实验协议。",
        ],
        storyAngles: [
          {
            title: "行动系统的边界问题",
            opener:
              "AI agents are moving from conversational interfaces into action-taking systems, but their execution boundaries remain underspecified and difficult to audit.",
            researchQuestions: [
              "如何定义 tool-using agents 的最小权限模型？",
              "能否构造 harmless sandbox benchmark 来评估审批与审计机制？",
            ],
            suitableFor: ["Agent Security", "Systems", "HCI / Trust"],
          },
        ],
        evidence: [
          {
            side: "industry",
            kind: "official",
            title: "The next evolution of the Agents SDK",
            organization: "OpenAI",
            date: "2026-04-15",
            url: "https://openai.com/index/the-next-evolution-of-the-agents-sdk",
            takeaway:
              "Agents SDK 引入 model-native harness 与 native sandbox execution，强调文件、命令和长任务执行环境。",
          },
          {
            side: "industry",
            kind: "official",
            title: "Trustworthy agents in practice",
            organization: "Anthropic",
            date: "2026-04-09",
            url: "https://www.anthropic.com/research/trustworthy-agents",
            takeaway:
              "Anthropic 把 agent 自主行动风险拆成误解意图、越权行动、prompt injection 和治理问题。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "Security Considerations for Artificial Intelligence Agents",
            organization: "arXiv",
            date: "2026-03-12",
            url: "https://arxiv.org/abs/2603.12230",
            takeaway:
              "系统化讨论 agent 架构对 authority boundary、code-data separation 和 execution predictability 的冲击。",
          },
          {
            side: "bridge",
            kind: "system-card",
            title: "GPT-5.3-Codex System Card",
            organization: "OpenAI",
            date: "2026-05-04",
            url: "https://deploymentsafety.openai.com/gpt-5-3-codex/gpt-5-3-codex.pdf",
            takeaway:
              "系统卡把代码执行、数据破坏和 coding agent 安全作为专门评测对象。",
          },
        ],
      },
      {
        id: "enterprise-agent-governance",
        title: "企业 Agent 的身份、权限与治理",
        problemStatement:
          "企业希望 agent 横跨邮件、文档、CRM、代码库和数据库工作，但 agent 身份、权限委托、数据边界和合规审计尚未稳定。",
        whyNow:
          "Google、OpenAI/AWS、Anthropic、ServiceNow/NVIDIA 都在把 agent 放进企业平台和垂直行业场景，治理能力开始成为产品卖点。",
        industryFocus:
          "agent platform、identity、gateway、registry、observability、enterprise data grounding、finance/legal/IT service workflows。",
        academicFocus:
          "agent governance、organizational trust、least-privilege delegation、human oversight、production agent measurement。",
        score: {
          urgency: 92,
          industryConvergence: 97,
          academicConvergence: 76,
          solutionMaturity: 82,
          gapDepth: 84,
          narrativeValue: 91,
        },
        solutionTracks: [
          {
            title: "Agent platform 与 gateway",
            maturity: "shipping",
            summary:
              "把 agent 创建、部署、集成、观测和治理收敛到统一平台或企业网关。",
            currentLimit:
              "各厂商抽象差异较大，跨平台可迁移性和标准化评测仍弱。",
            evidenceRefs: ["Google Gemini Enterprise Agent Platform", "OpenAI on AWS"],
          },
          {
            title: "行业模板与受监管场景",
            maturity: "prototype",
            summary:
              "先在金融、客服、IT 服务等可定义流程场景中提供 agent 模板和审批路径。",
            currentLimit:
              "模板容易掩盖真实组织差异，公开研究很难获得生产数据。",
            evidenceRefs: ["Anthropic finance agents", "ServiceNow AI Control Tower"],
          },
        ],
        unresolvedGaps: [
          "agent identity 是否应独立于人类账号，还是作为 delegated principal 存在？",
          "企业级 agent 观测指标尚未从产品 telemetry 上升为学术 benchmark。",
          "治理平台如何处理多 agent 协作中的责任归因和权限传递？",
        ],
        storyAngles: [
          {
            title: "从模型调用到组织治理",
            opener:
              "As enterprise agents start acting across organizational systems, the central question shifts from model capability to identity, delegation, and governance.",
            researchQuestions: [
              "如何度量生产环境 agent 的 delegation risk？",
              "能否设计跨平台的 agent governance capability model？",
            ],
            suitableFor: ["Enterprise AI", "Security", "Sociotechnical Systems"],
          },
        ],
        evidence: [
          {
            side: "industry",
            kind: "official",
            title: "Gemini Enterprise Agent Platform optimizes your agents",
            organization: "Google",
            date: "2026-04-22",
            url: "https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-enterprise-agent-platform/",
            takeaway:
              "Google 将 agent integration、security、DevOps 和治理能力纳入 Gemini Enterprise Agent Platform。",
          },
          {
            side: "industry",
            kind: "official",
            title: "OpenAI models, Codex, and Managed Agents come to AWS",
            organization: "OpenAI / AWS",
            date: "2026-04-28",
            url: "https://openai.com/index/openai-on-aws/",
            takeaway:
              "OpenAI 模型、Codex 和 Managed Agents 进入 AWS 企业云环境。",
          },
          {
            side: "industry",
            kind: "official",
            title: "Agents for financial services",
            organization: "Anthropic",
            date: "2026-05-05",
            url: "https://www.anthropic.com/news/finance-agents",
            takeaway:
              "Anthropic 将金融服务 agent 模板与 Claude Code、Claude Cowork、managed agents 等能力组合。",
          },
          {
            side: "academia",
            kind: "technical-report",
            title: "Measuring Agents in Production",
            organization: "IBM Research",
            date: "2026-04-20",
            url: "https://research.ibm.com/publications/measuring-agents-in-production",
            takeaway:
              "生产 agent 需要面向任务、成本、可靠性和用户影响的测量框架。",
          },
        ],
      },
      {
        id: "agentic-workload-observability-cost",
        title: "长任务 Agent 的可观测性与成本归因",
        problemStatement:
          "长任务 agent 会产生多轮模型调用、工具调用、重试、缓存和人机交互，传统单次请求指标难以解释成本、延迟和失败来源。",
        whyNow:
          "企业 agent 平台、deep research、coding agent 和自动科研都开始把多步骤执行作为默认模式。",
        industryFocus:
          "trace、replay、token/cost budget、tool latency、managed execution、workflow observability。",
        academicFocus:
          "agentic inference systems、distributed tracing、observability correctness、task-level utility 与能耗建模。",
        score: {
          urgency: 88,
          industryConvergence: 84,
          academicConvergence: 80,
          solutionMaturity: 64,
          gapDepth: 88,
          narrativeValue: 86,
        },
        solutionTracks: [
          {
            title: "Task-level trace 与 replay",
            maturity: "emerging",
            summary:
              "把 token、工具、延迟、重试、错误恢复和人工审批记录成可复盘 DAG。",
            currentLimit:
              "缺少公开数据集和跨平台 trace schema。",
            evidenceRefs: ["Measuring Agents in Production", "Agent platform observability"],
          },
          {
            title: "推理栈效率优化",
            maturity: "benchmarking",
            summary:
              "从系统层降低 P99 延迟、CPU 开销和能耗，使多步骤 agent 可规模化。",
            currentLimit:
              "单点系统优化不等于 task-level agent 效用提升。",
            evidenceRefs: ["Blink CPU-Free LLM Inference"],
          },
        ],
        unresolvedGaps: [
          "成本应该按 token、步骤、任务成功率还是用户价值归因，尚无共识。",
          "重试和工具错误会污染 trace，需要区分模型失败和环境失败。",
          "observability 本身可能引入隐私和安全暴露。",
        ],
        storyAngles: [
          {
            title: "从模型指标到任务指标",
            opener:
              "Agentic workloads make inference a multi-step systems problem where latency, cost, and failure must be attributed at the task level rather than the request level.",
            researchQuestions: [
              "如何设计 agent workload trace replay benchmark？",
              "P99 延迟优化是否转化为任务成功率提升？",
            ],
            suitableFor: ["ML Systems", "Observability", "Performance"],
          },
        ],
        evidence: [
          {
            side: "industry",
            kind: "official",
            title: "Gemini Enterprise Agent Platform optimizes your agents",
            organization: "Google",
            date: "2026-04-22",
            url: "https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/gemini-enterprise-agent-platform/",
            takeaway:
              "Agent Platform 将开发、部署、安全和运维放在统一视角，显示 agent observability 已进入产品层。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "Blink: CPU-Free LLM Inference",
            organization: "arXiv",
            date: "2026-04-08",
            url: "https://arxiv.org/abs/2604.07609",
            takeaway:
              "LLM inference 系统层优化直接影响延迟和能耗，为 agentic workload 成本问题提供背景。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "Time, Causality, and Observability Failures",
            organization: "arXiv",
            date: "2026-04-23",
            url: "https://arxiv.org/abs/2604.21361",
            takeaway:
              "分布式系统中的时间和因果错误会影响 observability 的正确性。",
          },
        ],
      },
    ],
  },
  {
    id: "research-agents-move-to-closed-loop-science",
    title: "Research Agent 从总结走向闭环科研",
    thesis:
      "Deep Research、自动实验、训练搜索和科研软件工程正在汇合，问题从“能否写报告”变成“能否产生可验证研究过程”。",
    userValue:
      "帮助科研人员判断自动科研的真实边界，并找到可以写成论文 introduction 的问题缺口。",
    clusters: [
      {
        id: "deep-research-evidence-reliability",
        title: "Deep Research 的证据可靠性",
        problemStatement:
          "Deep Research agent 能生成长报告，但来源覆盖、引用真实性、遗漏率和多文件证据一致性仍难以保证。",
        whyNow:
          "Google Deep Research Max 将 MCP、自定义来源和可视化报告产品化；同时 ResearchRubrics、DR3-Eval 等评测工作集中出现。",
        industryFocus:
          "长程检索、MCP 接入、企业私有知识源、图表报告、异步研究 workflow。",
        academicFocus:
          "deep research evaluation、expert rubrics、factual grounding、multi-source synthesis、reproducible reports。",
        score: {
          urgency: 94,
          industryConvergence: 90,
          academicConvergence: 92,
          solutionMaturity: 75,
          gapDepth: 90,
          narrativeValue: 97,
        },
        solutionTracks: [
          {
            title: "来源约束与自定义语料",
            maturity: "shipping",
            summary:
              "允许用户或企业指定可信来源，减少开放网页噪声，并把私有数据纳入研究流程。",
            currentLimit:
              "私有来源会降低可复现性，且不能自动解决引用误读。",
            evidenceRefs: ["Google Deep Research Max"],
          },
          {
            title: "Rubric-based evaluation",
            maturity: "benchmarking",
            summary:
              "用专家 rubric 或可复现任务评估报告的事实性、推理、覆盖和表达质量。",
            currentLimit:
              "专家 rubric 成本高，自动评审容易引入 judge bias。",
            evidenceRefs: ["ResearchRubrics", "DR3-Eval"],
          },
        ],
        unresolvedGaps: [
          "如何度量 deep research 的漏检率，而不仅是最终报告质量？",
          "多源冲突证据如何在 UI 中呈现，避免 agent 过早综合？",
          "私有知识库参与后，报告如何保持可复现和可审计？",
        ],
        storyAngles: [
          {
            title: "报告生成之后的证据问题",
            opener:
              "Deep research agents can now produce comprehensive reports, yet the reliability of their evidence gathering process remains under-specified.",
            researchQuestions: [
              "如何构造包含遗漏、冲突和多模态证据的 deep research benchmark？",
              "能否评估检索过程，而不仅评估最终报告？",
            ],
            suitableFor: ["Information Retrieval", "Agent Evaluation", "Research Tooling"],
          },
        ],
        evidence: [
          {
            side: "industry",
            kind: "official",
            title: "Deep Research Max: a step change for autonomous research agents",
            organization: "Google",
            date: "2026-04-21",
            url: "https://blog.google/innovation-and-ai/models-and-research/gemini-models/next-generation-gemini-deep-research/",
            takeaway:
              "Google 将 Deep Research 描述为复杂 agentic pipeline 的第一步，支持 MCP、自定义来源和可视化输出。",
          },
          {
            side: "academia",
            kind: "benchmark",
            title: "ResearchRubrics",
            organization: "OpenReview",
            date: "2026-04-20",
            url: "https://openreview.net/forum?id=ErnvfmSX0P",
            takeaway:
              "用专家 rubric 评估 deep research agents 的 factual grounding、reasoning soundness 和 clarity。",
          },
          {
            side: "academia",
            kind: "benchmark",
            title: "DR3-Eval: Towards Realistic and Reproducible Deep Research Evaluation",
            organization: "arXiv",
            date: "2026-04-16",
            url: "https://arxiv.org/abs/2604.14683",
            takeaway:
              "强调多模态、多文件、可复现报告生成，而不是单轮问答。",
          },
        ],
      },
      {
        id: "closed-loop-experiment-automation",
        title: "自动科研的闭环实验执行",
        problemStatement:
          "自动科研系统正在从文献阅读走向实验设计、代码执行、训练搜索和结果复盘，但闭环可靠性和科学有效性仍是硬问题。",
        whyNow:
          "TREX、SciResearcher、ResearchEVO 和自动科学发现综述在近期集中出现，显示学术界正在把 agent 放进真实科研流程。",
        industryFocus:
          "coding agents、managed sandboxes、自动化数据分析、云端训练和研究生产力工具。",
        academicFocus:
          "AI Scientist、agent-driven experiment search、autonomous discovery systems、scientific reasoning benchmark、reproducibility。",
        score: {
          urgency: 91,
          industryConvergence: 78,
          academicConvergence: 96,
          solutionMaturity: 68,
          gapDepth: 94,
          narrativeValue: 99,
        },
        solutionTracks: [
          {
            title: "Researcher / Executor 双 agent",
            maturity: "prototype",
            summary:
              "把文献理解、假设生成和实验执行拆成不同角色，并通过搜索树或记忆管理迭代。",
            currentLimit:
              "角色拆分不等于科学有效，仍需要 oracle、统计检验和失败复盘。",
            evidenceRefs: ["TREX", "ResearchEVO"],
          },
          {
            title: "实验轨迹与经验记忆",
            maturity: "emerging",
            summary:
              "记录实验尝试、失败原因、配置和高层洞见，避免 agent 重复无效路线。",
            currentLimit:
              "长期记忆可能固化错误假设，也可能难以跨领域迁移。",
            evidenceRefs: ["SciResearcher", "EvoScientist background"],
          },
        ],
        unresolvedGaps: [
          "自动生成实验是否真正回答科学问题，还是只是在 benchmark 上搜索？",
          "失败实验如何成为可迁移知识，而不是日志噪声？",
          "自动科研系统的贡献、署名和责任边界尚不清晰。",
        ],
        storyAngles: [
          {
            title: "从读论文到做实验",
            opener:
              "AI research agents are moving from literature synthesis to closed-loop experimentation, but their scientific validity remains difficult to verify.",
            researchQuestions: [
              "如何评估 agent-driven experiment loop 的科学有效性？",
              "能否设计可复现的小型自动科研 benchmark？",
            ],
            suitableFor: ["AI for Science", "AutoML", "Research Harness"],
          },
        ],
        evidence: [
          {
            side: "industry",
            kind: "official",
            title: "OpenAI models, Codex, and Managed Agents come to AWS",
            organization: "OpenAI / AWS",
            date: "2026-04-28",
            url: "https://openai.com/index/openai-on-aws/",
            takeaway:
              "Codex 与 Managed Agents 进入企业云，提供自动科研闭环所需的代码执行和托管运行环境背景。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "TREX: Automating LLM Fine-tuning via Agent-Driven Tree-based Exploration",
            organization: "arXiv",
            date: "2026-04-15",
            url: "https://arxiv.org/abs/2604.14116",
            takeaway:
              "TREX 使用 Researcher/Executor 与搜索树自动化 LLM fine-tuning 生命周期。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "SciResearcher: Scaling Deep Research Agents for Frontier Scientific Reasoning",
            organization: "arXiv",
            date: "2026-05-02",
            url: "https://arxiv.org/abs/2605.01489",
            takeaway:
              "关注前沿科学推理、数据构造、工具使用和长程任务训练。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "ResearchEVO",
            organization: "arXiv",
            date: "2026-04-07",
            url: "https://arxiv.org/abs/2604.05587",
            takeaway:
              "窗口外延伸信号，提出自动科学发现和文档生成的端到端框架。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "Automated Scientific Discovery survey",
            organization: "Machine Learning",
            date: "2026-04-29",
            url: "https://link.springer.com/article/10.1007/s10994-025-06955-2",
            takeaway:
              "从 equation discovery 到 autonomous discovery systems 梳理自动科学发现能力边界。",
          },
        ],
      },
      {
        id: "research-process-reproducibility",
        title: "科研过程可复现与软件工程质量",
        problemStatement:
          "自动科研如果只输出文本，无法进入真实科研；它必须同时产出代码、数据、环境、评测和 provenance。",
        whyNow:
          "Deep research evaluation、科研软件工程研究和 agent sandbox 发布共同指向同一件事：过程必须可复核。",
        industryFocus:
          "代码执行沙箱、文件系统、artifact 管理、数据连接器、long-running tasks。",
        academicFocus:
          "FAIR research software、reproducible reports、process/outcome evaluation、research provenance。",
        score: {
          urgency: 87,
          industryConvergence: 76,
          academicConvergence: 86,
          solutionMaturity: 62,
          gapDepth: 91,
          narrativeValue: 93,
        },
        solutionTracks: [
          {
            title: "Process-level artifact capture",
            maturity: "emerging",
            summary:
              "把检索、代码、实验配置、输出和失败原因作为科研产物保存。",
            currentLimit:
              "如果没有统一数据模型，artifact 很容易变成无法利用的文件堆。",
            evidenceRefs: ["DR3-Eval", "Research software engineering with AI"],
          },
          {
            title: "FAIR / MLOps / AIOps 融合",
            maturity: "benchmarking",
            summary:
              "借用软件工程和 MLOps 的成熟原则来约束 AI 生成科研代码和数据。",
            currentLimit:
              "传统软件质量指标不完全等价于科研结论质量。",
            evidenceRefs: ["Advancing research software engineering with AI"],
          },
        ],
        unresolvedGaps: [
          "如何把科研 provenance 做到轻量，避免使用负担过高？",
          "自动生成代码的 correctness oracle 在不同学科差异很大。",
          "科研故事、实验产物和软件质量之间缺少统一评价框架。",
        ],
        storyAngles: [
          {
            title: "自动科研的可信产物",
            opener:
              "For AI-assisted research to be trusted, the output cannot be only a narrative report; it must include reproducible artifacts and inspectable process traces.",
            researchQuestions: [
              "如何设计低负担的 research provenance schema？",
              "能否用过程轨迹预测科研报告可靠性？",
            ],
            suitableFor: ["Research Infrastructure", "Software Engineering", "Evaluation"],
          },
        ],
        evidence: [
          {
            side: "academia",
            kind: "paper",
            title: "Advancing research software engineering with AI",
            organization: "Automated Software Engineering",
            date: "2026-05-04",
            url: "https://link.springer.com/article/10.1007/s10515-026-00621-0",
            takeaway:
              "从 FAIR4RS、MLOps/AIOps、自动化测试和研究软件成熟度分析 AI 对科研软件工程的影响。",
          },
          {
            side: "academia",
            kind: "benchmark",
            title: "MiroEval",
            organization: "arXiv",
            date: "2026-03-30",
            url: "https://arxiv.org/abs/2603.28407",
            takeaway:
              "窗口外背景信号，强调 multimodal deep research agents 的过程与结果双重评测。",
          },
          {
            side: "industry",
            kind: "official",
            title: "The next evolution of the Agents SDK",
            organization: "OpenAI",
            date: "2026-04-15",
            url: "https://openai.com/index/the-next-evolution-of-the-agents-sdk",
            takeaway:
              "受控 workspace 与文件工具说明 agent 产物管理已经成为基础设施问题。",
          },
        ],
      },
    ],
  },
  {
    id: "multimodal-agents-ground-real-world-evidence",
    title: "多模态 Agent 从感知走向证据与执行",
    thesis:
      "图表、PDF、视频、GUI 和机器人场景正在进入 agent 工作流；问题从“看懂了吗”变成“证据如何 grounding，错误如何恢复”。",
    userValue:
      "帮助研究者看到自动科研和通用 agent 的共同底座：真实世界证据不是纯文本。",
    clusters: [
      {
        id: "multimodal-research-search-grounding",
        title: "多模态科研检索与证据 Grounding",
        problemStatement:
          "科研证据大量存在于图表、PDF 版式、实验截图、视频和网页交互中，纯文本检索无法覆盖真实研究过程。",
        whyNow:
          "OpenSearch-VL、MTA-Agent 与 Nemotron Omni 等开放或官方工作同时出现，让多模态 search agent 变得可训练、可复现、可部署。",
        industryFocus:
          "开放多模态模型、document/video/audio/GUI perception、低延迟部署、agent 感知子系统。",
        academicFocus:
          "multimodal deep search、visual grounding、tool-augmented multi-hop reasoning、RL training recipe。",
        score: {
          urgency: 86,
          industryConvergence: 84,
          academicConvergence: 90,
          solutionMaturity: 70,
          gapDepth: 88,
          narrativeValue: 92,
        },
        solutionTracks: [
          {
            title: "开放多模态 search recipe",
            maturity: "benchmarking",
            summary:
              "公开训练数据、工具环境和强化学习 recipe，让多模态 deep search 从闭源能力变成研究对象。",
            currentLimit:
              "训练 judge 和视觉 grounding 错误仍可能依赖闭源强模型。",
            evidenceRefs: ["OpenSearch-VL", "MTA-Agent"],
          },
          {
            title: "Agent perception layer",
            maturity: "shipping",
            summary:
              "用高吞吐开放多模态模型承担文档、音视频和 GUI 解析。",
            currentLimit:
              "感知正确不等于证据链正确，仍需任务级验证。",
            evidenceRefs: ["Nemotron 3 Nano Omni"],
          },
        ],
        unresolvedGaps: [
          "视觉 grounding 错误如何在科研 UI 中被发现和纠正？",
          "多模态证据的引用粒度应是页面、图表、区域还是时间片？",
          "开放 recipe 是否能覆盖真实科研文档的长尾版式和低质量扫描件？",
        ],
        storyAngles: [
          {
            title: "科研证据不只是文本",
            opener:
              "Scientific evidence is increasingly multimodal, yet most research agents still treat evidence gathering as a text-first retrieval problem.",
            researchQuestions: [
              "如何构造图表/PDF/视频混合的科研证据 benchmark？",
              "能否在 UI 中暴露视觉 grounding uncertainty？",
            ],
            suitableFor: ["Multimodal IR", "Document AI", "AI for Research"],
          },
        ],
        evidence: [
          {
            side: "academia",
            kind: "paper",
            title: "OpenSearch-VL",
            organization: "arXiv",
            date: "2026-05-06",
            url: "https://arxiv.org/abs/2605.05185",
            takeaway:
              "提出开放 recipe，覆盖视觉 grounding 数据、统一工具环境和 fatal-aware GRPO。",
          },
          {
            side: "academia",
            kind: "paper",
            title: "MTA-Agent",
            organization: "arXiv",
            date: "2026-04-07",
            url: "https://arxiv.org/abs/2604.06376",
            takeaway:
              "窗口外延伸信号，强调多跳视觉语言证据合成和工具增强搜索。",
          },
          {
            side: "industry",
            kind: "official",
            title: "NVIDIA Launches Nemotron 3 Nano Omni Model",
            organization: "NVIDIA",
            date: "2026-04-28",
            url: "https://blogs.nvidia.com/blog/nemotron-3-nano-omni-multimodal-ai-agents/",
            takeaway:
              "NVIDIA 将其定位为 agentic systems 的 eyes and ears，覆盖文档、视频、音频和 GUI。",
          },
          {
            side: "academia",
            kind: "technical-report",
            title: "Nemotron 3 Nano Omni",
            organization: "arXiv",
            date: "2026-04-27",
            url: "https://arxiv.org/abs/2604.24954",
            takeaway:
              "报告描述原生音频、图像、视频、文本支持和高吞吐多模态 token reduction。",
          },
        ],
      },
      {
        id: "embodied-success-detection",
        title: "具身任务的成功检测与安全执行",
        problemStatement:
          "机器人和 GUI/物理 agent 不只需要规划动作，还要判断动作是否成功、环境是否安全、视觉证据是否可靠。",
        whyNow:
          "Gemini Robotics-ER 1.6 把多视角理解、任务规划、成功检测和仪表读取作为核心能力，显示 embodied reasoning 正走向工业检查和真实执行。",
        industryFocus:
          "机器人任务规划、视觉检测、工业仪表读取、空间推理、安全约束。",
        academicFocus:
          "embodied reasoning、success detection、multi-view grounding、physical safety evaluation。",
        score: {
          urgency: 82,
          industryConvergence: 78,
          academicConvergence: 79,
          solutionMaturity: 72,
          gapDepth: 82,
          narrativeValue: 84,
        },
        solutionTracks: [
          {
            title: "VLM-based success detection",
            maturity: "prototype",
            summary:
              "用视觉语言模型判断任务是否完成，并读取仪表或环境状态。",
            currentLimit:
              "遮挡、反光、污损和异常环境会导致高后果误判。",
            evidenceRefs: ["Gemini Robotics-ER 1.6"],
          },
          {
            title: "Physical safety model cards",
            maturity: "benchmarking",
            summary:
              "用模型卡和安全评测明确机器人模型适用边界。",
            currentLimit:
              "模型卡难以覆盖真实部署中的长尾环境和机械控制风险。",
            evidenceRefs: ["Gemini Robotics-ER 1.6 Model Card"],
          },
        ],
        unresolvedGaps: [
          "真实工业场景中的长尾视觉异常很难从公开 benchmark 覆盖。",
          "成功检测错误可能比规划错误更隐蔽。",
          "自动科研实验室机器人如果采用此路线，需要额外 provenance 和安全层。",
        ],
        storyAngles: [
          {
            title: "执行之后的验证问题",
            opener:
              "Embodied agents require not only action planning but also reliable success detection under real-world uncertainty.",
            researchQuestions: [
              "如何评估 embodied agent 的 success detection robustness？",
              "多视角证据如何降低物理任务误判？",
            ],
            suitableFor: ["Robotics", "Vision-Language Models", "Safety Evaluation"],
          },
        ],
        evidence: [
          {
            side: "industry",
            kind: "official",
            title: "Gemini Robotics-ER 1.6",
            organization: "Google DeepMind",
            date: "2026-04-14",
            url: "https://deepmind.google/blog/gemini-robotics-er-1-6/",
            takeaway:
              "DeepMind 强调 spatial reasoning、multi-view understanding、task planning 和 success detection。",
          },
          {
            side: "bridge",
            kind: "official",
            title: "Gemini Robotics-ER 1.6 Model Card",
            organization: "Google DeepMind",
            date: "2026-04-20",
            url: "https://deepmind.google/models/model-cards/gemini-robotics-er-1-6/",
            takeaway:
              "模型卡列出输入模态、128k context、用途限制和安全评测。",
          },
        ],
      },
    ],
  },
];

export function getDiscoveryProblemClusters() {
  return DISCOVERY_PROBLEM_THEMES.flatMap((theme) => theme.clusters);
}

export function getProblemCategoryClusters(category: DiscoveryProblemCategory) {
  const clusterById = new Map(
    getDiscoveryProblemClusters().map((cluster) => [cluster.id, cluster]),
  );
  return category.primaryClusterIds
    .map((id) => clusterById.get(id))
    .filter((cluster): cluster is DiscoveryProblemCluster => Boolean(cluster));
}

export function getProblemCategoryEvidenceCount(category: DiscoveryProblemCategory) {
  const coverage =
    DISCOVERY_EVIDENCE_COVERAGE.problems[
      category.id as keyof typeof DISCOVERY_EVIDENCE_COVERAGE.problems
    ];
  if (coverage) {
    return coverage.evidenceCount;
  }
  return getProblemCategoryClusters(category).reduce(
    (total, cluster) => total + cluster.evidence.length,
    0,
  );
}

export function getProblemClusterEvidencePoolCount(cluster: DiscoveryProblemCluster) {
  const relatedCounts = DISCOVERY_PROBLEM_CATEGORIES.filter((category) =>
    category.primaryClusterIds.includes(cluster.id),
  ).map((category) => getProblemCategoryEvidenceCount(category));

  return Math.max(cluster.evidence.length, ...relatedCounts);
}

export function getProblemClusterRecentEvidencePoolCount(cluster: DiscoveryProblemCluster) {
  const relatedCounts = DISCOVERY_PROBLEM_CATEGORIES.filter((category) =>
    category.primaryClusterIds.includes(cluster.id),
  )
    .map(
      (category) =>
        DISCOVERY_EVIDENCE_COVERAGE.problems[
          category.id as keyof typeof DISCOVERY_EVIDENCE_COVERAGE.problems
        ]?.recentCount ?? 0,
    )
    .filter((count) => count > 0);

  return Math.max(cluster.evidence.length, ...relatedCounts);
}

export function getProblemCategoryMomentum(category: DiscoveryProblemCategory) {
  const first = category.trend12m[0] ?? 0;
  const last = category.trend12m.at(-1) ?? first;
  return last - first;
}

export function getTopProblemCategories(limit = 10) {
  return [...DISCOVERY_PROBLEM_CATEGORIES]
    .sort((a, b) => {
      const scoreDiff = b.priorityScore - a.priorityScore;
      return scoreDiff || getProblemCategoryMomentum(b) - getProblemCategoryMomentum(a);
    })
    .slice(0, limit);
}

export function getDiscoveryProblemEvidenceCount() {
  return getDiscoveryProblemClusters().reduce((total, cluster) => total + cluster.evidence.length, 0);
}

export function getProblemClusterScore(cluster: DiscoveryProblemCluster) {
  const {
    academicConvergence,
    gapDepth,
    industryConvergence,
    narrativeValue,
    solutionMaturity,
    urgency,
  } = cluster.score;

  return Math.round(
    urgency * 0.18 +
      industryConvergence * 0.16 +
      academicConvergence * 0.16 +
      solutionMaturity * 0.12 +
      gapDepth * 0.18 +
      narrativeValue * 0.2,
  );
}

export function getTopProblemClusters(limit = 4) {
  return getDiscoveryProblemClusters()
    .sort((a, b) => getProblemClusterScore(b) - getProblemClusterScore(a))
    .slice(0, limit);
}
