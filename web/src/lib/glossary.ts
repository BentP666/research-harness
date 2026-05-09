/**
 * Researcher-friendly glossary — single source of truth for user-facing terms.
 *
 * Design principle: surface language targets researchers (PhD student / PI),
 * not engineers. Backend keeps the canonical technical names; this file maps
 * them to human language in both English (polished) and Chinese (thoughtfully
 * translated, not word-for-word).
 *
 * Usage:
 *   import { term, hint } from "@/lib/glossary";
 *   <h2>{term("gate_check")}</h2>         // "Stage Checkpoint"
 *   <p className="...">{hint("gate_check")}</p>  // plain-language explanation
 */

export type Locale = "en" | "zh";

export type TermId =
  | "primitive"
  | "gate_check"
  | "rubric"
  | "provenance"
  | "stage"
  | "stage_pipeline"
  | "autonomy"
  | "autonomy_L0"
  | "autonomy_L1"
  | "autonomy_L2"
  | "autonomy_L3"
  | "adversarial_review"
  | "claim_verification"
  | "verified_registry"
  | "dag_gap_detection"
  | "rollback"
  | "stale_artifact"
  | "evidence_map"
  | "section_draft"
  | "workflow_memory"
  | "topic"
  | "domain"
  | "venue_tier"
  | "seed_papers";

export interface TermEntry {
  /** Short display label shown in headings, labels, chips. */
  label: Record<Locale, string>;
  /** One-sentence plain-language explanation for tooltips / help text. */
  hint: Record<Locale, string>;
  /** Emoji / icon key — kept in the glossary so we don't scatter emojis. */
  icon?: string;
}

const GLOSSARY: Record<TermId, TermEntry> = {
  primitive: {
    label: { en: "Research Step", zh: "研究步骤" },
    hint: {
      en: "An atomic action your AI assistant performs — e.g. searching papers, extracting claims, drafting a section.",
      zh: "AI 研究助手执行的一个基础动作，例如搜索论文、抽取论断、撰写某个章节。",
    },
    icon: "⚙️",
  },
  gate_check: {
    label: { en: "Stage Checkpoint", zh: "阶段检查" },
    hint: {
      en: "A quality gate between stages. Verifies you have enough evidence to advance without shaky foundations.",
      zh: "两个阶段之间的质量关卡。确认当前积累的证据足以支撑进入下一阶段。",
    },
    icon: "🚦",
  },
  rubric: {
    label: { en: "Scoring Rubric", zh: "学术评分" },
    hint: {
      en: "A structured grading system that scores your artifacts on research-quality dimensions (novelty, rigor, evidence, etc.).",
      zh: "用多维度（新颖性、严谨性、证据强度等）对研究产出打分的框架。",
    },
    icon: "📊",
  },
  provenance: {
    label: { en: "Activity Log", zh: "执行记录" },
    hint: {
      en: "A tamper-evident log of every AI call — what ran, when, what it cost.",
      zh: "AI 每次调用的可追溯记录 — 跑了什么、何时跑、花费多少。",
    },
    icon: "📋",
  },
  stage: {
    label: { en: "Stage", zh: "阶段" },
    hint: {
      en: "One of the six phases of a research project: Build corpus, Analyze, Propose, Experiment, Write, Review.",
      zh: "研究项目的六个阶段之一：建库 → 分析 → 提案 → 实验 → 撰写 → 评审。",
    },
    icon: "🎯",
  },
  stage_pipeline: {
    label: { en: "Research Progress", zh: "研究进度" },
    hint: {
      en: "Your project's end-to-end journey, from first paper search to polished submission.",
      zh: "研究项目从搜集文献到最终投稿的完整进度线。",
    },
    icon: "🔀",
  },
  autonomy: {
    label: { en: "Autonomy Mode", zh: "自动化程度" },
    hint: {
      en: "How often your AI assistant pauses to ask for your input. Higher = more hands-off.",
      zh: "AI 助手多频繁地停下来征求你的意见。越高越放手让它跑。",
    },
    icon: "🎛️",
  },
  autonomy_L0: {
    label: { en: "Step-by-step", zh: "逐步确认" },
    hint: {
      en: "Pause after every AI call. You review each output. Slowest but most controlled.",
      zh: "每一步都暂停让你审阅。最慢但最可控。",
    },
  },
  autonomy_L1: {
    label: { en: "Stage-by-stage", zh: "分阶段确认" },
    hint: {
      en: "Pause at every stage checkpoint. You approve before advancing.",
      zh: "每个阶段结束时暂停，由你批准后进入下一阶段。",
    },
  },
  autonomy_L2: {
    label: { en: "Smart Checkpoints", zh: "关键节点确认" },
    hint: {
      en: "Pause only at critical gates (experiment, write). Recommended.",
      zh: "只在关键节点（实验、写作）暂停。推荐设置。",
    },
  },
  autonomy_L3: {
    label: { en: "Full Auto", zh: "全自动" },
    hint: {
      en: "Let it run end-to-end. Best for topics you've already scoped.",
      zh: "完全自动跑通全流程。适合已经明确方向的研究。",
    },
  },
  adversarial_review: {
    label: { en: "Skeptical Reviewer", zh: "挑刺审稿人" },
    hint: {
      en: "A critical-reviewer persona picks apart your draft for weaknesses — like a tough conference reviewer.",
      zh: "模拟一位严格的审稿人，从方法、证据、写作角度挑刺你的草稿。",
    },
    icon: "🛡️",
  },
  claim_verification: {
    label: { en: "Cross-Checking Claims", zh: "论断交叉验证" },
    hint: {
      en: "Hunts for contradictions between numerical claims in your paper pool (e.g. Paper A says 95%, Paper B says 60% on the same benchmark).",
      zh: "对比文献池中的论断，找出互相矛盾的地方（例如 A 文说 95%，B 文同一基准说 60%）。",
    },
    icon: "🔎",
  },
  verified_registry: {
    label: { en: "Verified Numbers", zh: "核验过的数字" },
    hint: {
      en: "Metrics from your own experiments that have been re-computed and signed — safe to cite in the paper.",
      zh: "你的实验中经过重新计算和签名的指标 — 可以放心写入论文。",
    },
    icon: "✅",
  },
  dag_gap_detection: {
    label: { en: "Deep Gap Scan (Beta)", zh: "分区深度挖掘（Beta）" },
    hint: {
      en: "Experimental multi-pass gap detection — clusters your papers and scans each cluster separately, then reconciles findings.",
      zh: "实验性多轮挖掘 — 把文献按主题聚类，分别扫描每一簇，再汇总结果。",
    },
    icon: "🧭",
  },
  rollback: {
    label: { en: "Redo from here", zh: "回到此处重做" },
    hint: {
      en: "Jump back to an earlier stage. Everything after will be marked as outdated so nothing stale slips into your paper.",
      zh: "跳回到较早的阶段。此后的所有产出会被标记为过期，避免旧结论混入论文。",
    },
    icon: "↺",
  },
  stale_artifact: {
    label: { en: "Outdated", zh: "已过期" },
    hint: {
      en: "This was generated before a rollback and may not reflect your current thinking. Regenerate before using.",
      zh: "这是回退之前生成的产物，可能已不反映你现在的想法。建议重新生成。",
    },
    icon: "⏳",
  },
  evidence_map: {
    label: { en: "Evidence Map", zh: "证据地图" },
    hint: {
      en: "Which source paper backs each sentence of your draft. Click any underlined sentence to see its sources.",
      zh: "草稿中每句话背后的来源论文。点击任一带下划线的句子即可看到来源。",
    },
    icon: "🗺️",
  },
  section_draft: {
    label: { en: "Section Draft", zh: "章节草稿" },
    hint: {
      en: "AI-generated draft for one part of your paper (introduction, methods, etc.). Fully editable.",
      zh: "论文某一部分的 AI 生成草稿（引言、方法等）。可任意编辑。",
    },
    icon: "✍️",
  },
  workflow_memory: {
    label: { en: "Research Memory", zh: "研究记忆" },
    hint: {
      en: "Surfaces decisions and outcomes from your past projects that might apply to this new topic.",
      zh: "从你过去的研究项目中，找出可能适用于当前 topic 的决策和经验。",
    },
    icon: "🧠",
  },
  topic: {
    label: { en: "Topic", zh: "课题" },
    hint: {
      en: "One research project with its own paper pool, draft, and timeline. You'll have many of these over a career.",
      zh: "一个独立的研究项目，有自己的文献池、草稿和进度线。",
    },
    icon: "📚",
  },
  domain: {
    label: { en: "Domain", zh: "领域" },
    hint: {
      en: "A broad field containing multiple topics — e.g. 'computational biology' or 'auto-bidding'.",
      zh: "一个大的学科方向，包含多个 topic — 例如「计算生物学」或「自动出价」。",
    },
    icon: "🌐",
  },
  venue_tier: {
    label: { en: "Target Venue", zh: "目标期刊/会议" },
    hint: {
      en: "The conference or journal you aim to submit to. Affects how strict the scoring rubric will be.",
      zh: "你计划投稿的会议或期刊。影响评分严格度。",
    },
    icon: "🎓",
  },
  seed_papers: {
    label: { en: "Seed Papers", zh: "种子论文" },
    hint: {
      en: "A handful of papers you already know are relevant. We'll use these as a starting point to discover more.",
      zh: "几篇你已经知道相关的论文。我们以它们为起点去扩展文献池。",
    },
    icon: "🌱",
  },
};

let CURRENT_LOCALE: Locale = "en";

export function setLocale(locale: Locale) {
  CURRENT_LOCALE = locale;
}

export function getLocale(): Locale {
  return CURRENT_LOCALE;
}

export function term(id: TermId, locale?: Locale): string {
  const entry = GLOSSARY[id];
  if (!entry) return id;
  return entry.label[locale ?? CURRENT_LOCALE];
}

export function hint(id: TermId, locale?: Locale): string {
  const entry = GLOSSARY[id];
  if (!entry) return "";
  return entry.hint[locale ?? CURRENT_LOCALE];
}

export function icon(id: TermId): string {
  return GLOSSARY[id]?.icon ?? "";
}

export function getEntry(id: TermId): TermEntry | undefined {
  return GLOSSARY[id];
}

export const ALL_TERMS: readonly TermId[] = Object.keys(GLOSSARY) as TermId[];
