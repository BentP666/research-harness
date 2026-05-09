"use client";

import { useEffect, useState, Fragment } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Loader2,
  Play,
  ChevronRight,
  Search,
  Scan,
  Target,
  FlaskConical,
  PenSquare,
  Settings,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  detectGaps,
  identifyBaselines,
  buildEvidenceMatrix,
  rankDirections,
  expandDesignBrief,
  generateAlgorithmCandidates,
  runCompetitiveLearning,
  generateCode,
  generateOutline,
  draftSection,
  reviewSection,
  checkConsistency,
  recordArtifact,
  type StageActionResponse,
} from "@/lib/api";
import type { ResearchStage } from "@/lib/types";
import { type StageGraphSummary } from "@/components/topic/stage-graph";

interface Props {
  topicId: number;
  paperCount: number;
  deepReadCount: number;
  currentStage?: ResearchStage | null;
  stageSummaries?: Partial<Record<ResearchStage, StageGraphSummary>>;
  onStageClick?: (stage: ResearchStage) => void;
}

type StepStatus = "idle" | "running" | "success" | "error";

interface Step {
  id: string;
  label: string;
  description: string;
  run: () => Promise<StageActionResponse>;
}

interface StageBlock {
  id: string;
  label: string;
  icon: typeof Search;
  steps: Step[];
}

const STAGE_ORDER: ResearchStage[] = [
  "init",
  "build",
  "analyze",
  "propose",
  "experiment",
  "write",
];

const STAGE_META: Record<
  string,
  { num: string; title: string; subtitle: string }
> = {
  init: { num: "1", title: "Init", subtitle: "环境感知" },
  build: { num: "2", title: "Build", subtitle: "文献检索" },
  analyze: { num: "3", title: "Analyze", subtitle: "文献分析" },
  propose: { num: "4", title: "Propose", subtitle: "提出方案" },
  experiment: { num: "5", title: "Experiment", subtitle: "实验验证" },
  write: { num: "6", title: "Write", subtitle: "论文撰写" },
};

type StageState = "done" | "running" | "error" | "partial" | "idle";

// Per-stage IDLE colors so each card has its own identity.
const STAGE_IDLE_THEME: Record<
  string,
  { card: string; iconBg: string; text: string; ring: string; bar: string; badge: string }
> = {
  init: {
    card: "border-slate-300/80 bg-gradient-to-br from-slate-50 via-white to-slate-100/60 dark:border-slate-700 dark:from-slate-900 dark:via-slate-900/80 dark:to-slate-950",
    iconBg: "bg-gradient-to-br from-slate-400 via-slate-500 to-slate-700 shadow-md shadow-slate-500/30",
    text: "text-slate-600 dark:text-slate-400",
    ring: "ring-slate-400/40",
    bar: "bg-gradient-to-r from-slate-300 to-slate-500",
    badge: "border-slate-400 text-slate-700 dark:text-slate-300",
  },
  build: {
    card: "border-cyan-300/70 bg-gradient-to-br from-cyan-50/80 via-white to-teal-50/60 dark:border-cyan-800/60 dark:from-cyan-950/30 dark:via-slate-900/80 dark:to-teal-950/20",
    iconBg: "bg-gradient-to-br from-cyan-400 via-teal-500 to-teal-700 shadow-md shadow-teal-500/30",
    text: "text-teal-600 dark:text-teal-400",
    ring: "ring-teal-400/40",
    bar: "bg-gradient-to-r from-cyan-300 to-teal-500",
    badge: "border-teal-400 text-teal-700 dark:text-teal-300",
  },
  analyze: {
    card: "border-violet-300/70 bg-gradient-to-br from-violet-50/80 via-white to-purple-50/60 dark:border-violet-800/60 dark:from-violet-950/30 dark:via-slate-900/80 dark:to-purple-950/20",
    iconBg: "bg-gradient-to-br from-violet-400 via-purple-500 to-purple-700 shadow-md shadow-violet-500/30",
    text: "text-purple-600 dark:text-purple-400",
    ring: "ring-purple-400/40",
    bar: "bg-gradient-to-r from-violet-300 to-purple-500",
    badge: "border-purple-400 text-purple-700 dark:text-purple-300",
  },
  propose: {
    card: "border-amber-300/70 bg-gradient-to-br from-amber-50/80 via-white to-orange-50/60 dark:border-amber-800/60 dark:from-amber-950/30 dark:via-slate-900/80 dark:to-orange-950/20",
    iconBg: "bg-gradient-to-br from-amber-400 via-amber-500 to-orange-600 shadow-md shadow-amber-500/30",
    text: "text-amber-600 dark:text-amber-400",
    ring: "ring-amber-400/40",
    bar: "bg-gradient-to-r from-amber-300 to-orange-500",
    badge: "border-amber-400 text-amber-700 dark:text-amber-300",
  },
  experiment: {
    card: "border-rose-300/70 bg-gradient-to-br from-rose-50/80 via-white to-pink-50/60 dark:border-rose-800/60 dark:from-rose-950/30 dark:via-slate-900/80 dark:to-pink-950/20",
    iconBg: "bg-gradient-to-br from-rose-400 via-pink-500 to-fuchsia-600 shadow-md shadow-rose-500/30",
    text: "text-rose-600 dark:text-rose-400",
    ring: "ring-rose-400/40",
    bar: "bg-gradient-to-r from-rose-300 to-pink-500",
    badge: "border-rose-400 text-rose-700 dark:text-rose-300",
  },
  write: {
    card: "border-emerald-300/70 bg-gradient-to-br from-emerald-50/80 via-white to-green-50/60 dark:border-emerald-800/60 dark:from-emerald-950/30 dark:via-slate-900/80 dark:to-green-950/20",
    iconBg: "bg-gradient-to-br from-emerald-400 via-emerald-500 to-green-600 shadow-md shadow-emerald-500/30",
    text: "text-emerald-600 dark:text-emerald-400",
    ring: "ring-emerald-400/40",
    bar: "bg-gradient-to-r from-emerald-300 to-green-500",
    badge: "border-emerald-400 text-emerald-700 dark:text-emerald-300",
  },
};

// State-specific overrides (running / done / error / partial).
const STATE_THEME: Record<
  Exclude<StageState, "idle">,
  { card: string; iconBg: string; label: string; text: string; ring: string; bar: string; badge: string }
> = {
  done: {
    card: "border-emerald-400/80 bg-gradient-to-br from-emerald-50 via-emerald-50/80 to-emerald-100/70 dark:border-emerald-600/60 dark:from-emerald-950/50 dark:via-emerald-950/30 dark:to-emerald-900/30",
    iconBg: "bg-gradient-to-br from-emerald-400 via-emerald-500 to-emerald-700 shadow-lg shadow-emerald-500/40",
    label: "已完成",
    text: "text-emerald-700 dark:text-emerald-300",
    ring: "ring-emerald-400/70",
    bar: "bg-gradient-to-r from-emerald-400 to-emerald-600",
    badge: "border-emerald-500 text-emerald-700 dark:text-emerald-300",
  },
  running: {
    card: "border-blue-400/80 bg-gradient-to-br from-blue-50 via-blue-50/80 to-blue-100/70 dark:border-blue-600/60 dark:from-blue-950/50 dark:via-blue-950/30 dark:to-blue-900/30",
    iconBg: "bg-gradient-to-br from-blue-400 via-blue-500 to-blue-700 shadow-lg shadow-blue-500/40 animate-pulse",
    label: "进行中",
    text: "text-blue-700 dark:text-blue-300",
    ring: "ring-blue-400/70",
    bar: "bg-gradient-to-r from-blue-400 to-blue-600",
    badge: "border-blue-500 text-blue-700 dark:text-blue-300",
  },
  error: {
    card: "border-red-400/80 bg-gradient-to-br from-red-50 via-red-50/80 to-red-100/70 dark:border-red-600/60 dark:from-red-950/50 dark:via-red-950/30 dark:to-red-900/30",
    iconBg: "bg-gradient-to-br from-red-400 via-red-500 to-red-700 shadow-lg shadow-red-500/40",
    label: "失败",
    text: "text-red-700 dark:text-red-300",
    ring: "ring-red-400/70",
    bar: "bg-gradient-to-r from-red-400 to-red-600",
    badge: "border-red-500 text-red-700 dark:text-red-300",
  },
  partial: {
    card: "border-indigo-400/80 bg-gradient-to-br from-indigo-50 via-indigo-50/80 to-indigo-100/70 dark:border-indigo-600/60 dark:from-indigo-950/50 dark:via-indigo-950/30 dark:to-indigo-900/30",
    iconBg: "bg-gradient-to-br from-indigo-400 via-indigo-500 to-indigo-700 shadow-lg shadow-indigo-500/40",
    label: "有证据",
    text: "text-indigo-700 dark:text-indigo-300",
    ring: "ring-indigo-400/70",
    bar: "bg-gradient-to-r from-indigo-400 to-indigo-600",
    badge: "border-indigo-500 text-indigo-700 dark:text-indigo-300",
  },
};

const IDLE_LABEL = "待执行";

export function WorkflowPipeline({
  topicId,
  paperCount,
  deepReadCount,
  currentStage,
  stageSummaries,
  onStageClick,
}: Props) {
  const defaultExpand = currentStage ?? "analyze";
  const [expandedStage, setExpandedStage] = useState<string | null>(defaultExpand);
  const [stepStatus, setStepStatus] = useState<Record<string, StepStatus>>({});
  const [stepOutput, setStepOutput] = useState<Record<string, Record<string, unknown> | null>>({});
  const [stepSummary, setStepSummary] = useState<Record<string, string>>({});

  useEffect(() => {
    if (currentStage) setExpandedStage(currentStage);
  }, [currentStage]);

  const stages: StageBlock[] = [
    {
      id: "init",
      label: "1. Init — 环境感知",
      icon: Settings,
      steps: [
        {
          id: "topic_brief",
          label: "研究简报",
          description: "确认研究问题、目标会议、排除条件",
          run: () =>
            recordArtifact(topicId, {
              artifact_type: "topic_brief",
              content: "Auto-generated topic brief for demo",
              stage: "init",
            }),
        },
      ],
    },
    {
      id: "build",
      label: "2. Build — 文献检索",
      icon: Search,
      steps: [
        {
          id: "expansion_hint",
          label: "检索与精读",
          description: "使用上方「检索与精读批次」面板搜索论文 + 并行精读",
          run: () =>
            Promise.resolve({
              status: "success",
              summary: "请使用上方 检索与精读批次 面板启动",
            } as StageActionResponse),
        },
      ],
    },
    {
      id: "analyze",
      label: "3. Analyze — 文献分析",
      icon: Scan,
      steps: [
        { id: "gap_detect", label: "发现研究空白", description: "分析文献中的开放问题", run: () => detectGaps(topicId) },
        { id: "baseline_identify", label: "识别基线方法", description: "梳理基线方法及其实验结果", run: () => identifyBaselines(topicId) },
        { id: "evidence_matrix", label: "证据矩阵", description: "方法 × 指标证据网格", run: () => buildEvidenceMatrix(topicId) },
      ],
    },
    {
      id: "propose",
      label: "4. Propose — 提出方案",
      icon: Target,
      steps: [
        { id: "direction_ranking", label: "方向排序", description: "按新颖性 × 可行性 × 影响力排序", run: () => rankDirections(topicId) },
        { id: "design_brief", label: "设计简报", description: "将研究方向展开为方法模块", run: () => expandDesignBrief(topicId, { direction: "Improve upon target paper methodology with combinatorial innovation" }) },
        { id: "algorithm_candidates", label: "算法候选", description: "组合创新生成候选方案", run: () => generateAlgorithmCandidates(topicId, { brief: { auto: true }, n_candidates: 3 }) },
        { id: "competitive_learning", label: "竞争分析", description: "目标会议方法趋势", run: () => runCompetitiveLearning(topicId, { venue: "EMNLP" }) },
      ],
    },
    {
      id: "experiment",
      label: "5. Experiment — 实验验证",
      icon: FlaskConical,
      steps: [
        { id: "code_generate", label: "生成实验代码", description: "基于设计简报生成实验脚本", run: () => generateCode(topicId, { focus: "time series forecasting experiment" }) },
        { id: "experiment_create", label: "创建实验轮次", description: "使用下方面板配置并运行", run: () => Promise.resolve({ status: "success", summary: "请使用下方 实验轮次 面板创建实验" } as StageActionResponse) },
      ],
    },
    {
      id: "write",
      label: "6. Write — 论文撰写",
      icon: PenSquare,
      steps: [
        { id: "outline", label: "生成大纲", description: "基于贡献和证据生成论文结构", run: () => generateOutline(topicId, { template: "neurips" }) },
        { id: "section_draft", label: "撰写 Introduction", description: "基于证据撰写引言", run: () => draftSection(topicId, { section: "introduction" }) },
        { id: "section_review", label: "审阅草稿", description: "评分与改进建议", run: () => { const d = stepOutput["section_draft"]; const c = (d?.draft as Record<string, unknown> | undefined)?.content as string | undefined; return reviewSection(topicId, { section: "introduction", content: c || "(no draft)" }); } },
        { id: "consistency_check", label: "一致性检查", description: "跨章节连贯性审计", run: () => checkConsistency(topicId) },
      ],
    },
  ];

  const runStep = useMutation({
    mutationFn: async ({ stepId, run }: { stepId: string; run: () => Promise<StageActionResponse> }) => {
      setStepStatus((prev) => ({ ...prev, [stepId]: "running" }));
      setStepSummary((prev) => ({ ...prev, [stepId]: "" }));
      setStepOutput((prev) => ({ ...prev, [stepId]: null }));
      const result = await run();
      return { stepId, result };
    },
    onSuccess: ({ stepId, result }) => {
      setStepStatus((prev) => ({ ...prev, [stepId]: result.status === "success" ? "success" : "error" }));
      setStepSummary((prev) => ({ ...prev, [stepId]: result.summary || result.status }));
      setStepOutput((prev) => ({ ...prev, [stepId]: (result.output as Record<string, unknown>) ?? null } as Record<string, Record<string, unknown> | null>));
    },
    onError: (err: Error, { stepId }) => {
      setStepStatus((prev) => ({ ...prev, [stepId]: "error" }));
      setStepSummary((prev) => ({ ...prev, [stepId]: err.message }));
    },
  });

  // Derive state from BOTH backend summaries and local step runs.
  function getStageState(stage: StageBlock): { state: StageState; ran: number; total: number; evidence: number; violations: number } {
    const stageId = stage.id as ResearchStage;
    const backend = stageSummaries?.[stageId];
    const localStatuses = stage.steps.map((s) => stepStatus[s.id] || "idle");
    const localRan = localStatuses.filter((s) => s === "success").length;

    if (localStatuses.includes("running")) return { state: "running", ran: localRan, total: localStatuses.length, evidence: 0, violations: 0 };
    if (localStatuses.includes("error")) return { state: "error", ran: localRan, total: localStatuses.length, evidence: 0, violations: 0 };
    if (localStatuses.every((s) => s === "success") && localStatuses.length > 0) return { state: "done", ran: localRan, total: localStatuses.length, evidence: 0, violations: 0 };

    // Backend truth takes precedence when no local run happened
    if (backend) {
      const ev = backend.evidenceCount ?? 0;
      const v = backend.invariantViolations;
      if (backend.ran > 0 && backend.ran >= backend.planned) return { state: "done", ran: backend.ran, total: backend.planned, evidence: ev, violations: v };
      if (backend.ran > 0) return { state: "partial", ran: backend.ran, total: backend.planned, evidence: ev, violations: v };
      if (ev > 0) return { state: "partial", ran: 0, total: backend.planned, evidence: ev, violations: v };
    }

    if (localRan > 0) return { state: "partial", ran: localRan, total: localStatuses.length, evidence: 0, violations: 0 };
    return { state: "idle", ran: 0, total: stage.steps.length, evidence: 0, violations: 0 };
  }

  function getTheme(stageId: string, state: StageState) {
    if (state === "idle") return { ...STAGE_IDLE_THEME[stageId], label: IDLE_LABEL };
    return STATE_THEME[state];
  }

  const selectedStage = stages.find((s) => s.id === expandedStage);
  const SelectedIcon = selectedStage?.icon;
  const selectedMeta = selectedStage ? STAGE_META[selectedStage.id] : null;
  const selectedState = selectedStage ? getStageState(selectedStage) : null;
  const selectedTheme = selectedStage && selectedState ? getTheme(selectedStage.id, selectedState.state) : null;

  return (
    <Card className="overflow-hidden border-2 border-slate-200/80 dark:border-slate-800 shadow-md">
      <CardHeader className="pb-3 border-b-2 border-slate-200/60 dark:border-slate-800/80 bg-gradient-to-br from-slate-50 via-white to-indigo-50/40 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/20">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm flex items-center gap-2.5">
            <div className="rounded-lg bg-gradient-to-br from-indigo-500 via-blue-600 to-blue-700 p-1.5 shadow-md shadow-blue-500/40 ring-1 ring-blue-400/30">
              <FlaskConical className="size-4 text-white drop-shadow" />
            </div>
            <div>
              <div className="font-semibold tracking-tight">研究工作流</div>
              <div className="text-[10px] font-normal text-muted-foreground mt-0.5">
                六阶段自动化研究流程 — 点击卡片查看子任务
              </div>
            </div>
          </CardTitle>
          <div className="flex gap-1.5">
            <Badge variant="outline" className="text-[10px] border-slate-300 bg-white/80 shadow-sm dark:bg-slate-900/60">
              {paperCount} 篇论文
            </Badge>
            <Badge variant="outline" className="text-[10px] border-slate-300 bg-white/80 shadow-sm dark:bg-slate-900/60">
              {deepReadCount} 已精读
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4 space-y-4">
        {/* Stage track */}
        <div className="flex items-stretch gap-0.5 overflow-x-auto pb-1 pt-2 -mx-1 px-1">
          {stages.map((stage, idx) => {
            const { state, ran, total, evidence, violations } = getStageState(stage);
            const theme = getTheme(stage.id, state);
            const isSelected = expandedStage === stage.id;
            const isCurrent = currentStage === stage.id;
            const meta = STAGE_META[stage.id];
            const Icon = stage.icon;
            const pct = total > 0 ? Math.max(ran / total, evidence > 0 ? 0.15 : 0) * 100 : 0;

            return (
              <Fragment key={stage.id}>
                <button
                  onClick={() => {
                    setExpandedStage(isSelected ? null : stage.id);
                    onStageClick?.(stage.id as ResearchStage);
                  }}
                  className={cn(
                    "group relative shrink-0 w-[124px] rounded-xl border-2 p-3 text-left",
                    "shadow-md hover:shadow-xl transition-all duration-200",
                    "hover:-translate-y-0.5 active:translate-y-0",
                    theme.card,
                    isSelected && cn("ring-2 ring-offset-2 ring-offset-background -translate-y-0.5 shadow-xl", theme.ring),
                  )}
                >
                  {/* Stage number */}
                  <div className="absolute -top-2 -left-2 size-6 rounded-full bg-white dark:bg-slate-900 border-2 border-slate-300 dark:border-slate-600 flex items-center justify-center text-[10px] font-bold shadow-md text-slate-700 dark:text-slate-300">
                    {meta.num}
                  </div>

                  {/* Current-stage indicator */}
                  {isCurrent && (
                    <div className="absolute -top-2 -right-2">
                      <div className="relative">
                        <div className="absolute inset-0 rounded-full bg-blue-400 blur-md animate-pulse" />
                        <div className="relative rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 px-1.5 py-0.5 text-[9px] font-semibold text-white shadow-lg shadow-blue-500/40 ring-1 ring-blue-300/50 flex items-center gap-0.5">
                          <Sparkles className="size-2.5" />
                          当前
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Invariant violations badge */}
                  {violations > 0 && (
                    <div className="absolute -bottom-1.5 -right-1.5">
                      <div className="flex items-center gap-0.5 rounded-full bg-red-500 px-1.5 py-0.5 text-[9px] font-bold text-white shadow-md">
                        <AlertCircle className="size-2.5" />
                        {violations}
                      </div>
                    </div>
                  )}

                  {/* Icon */}
                  <div className={cn("size-10 rounded-lg flex items-center justify-center mb-2 ring-1 ring-white/30", theme.iconBg)}>
                    <Icon className="size-5 text-white drop-shadow-md" />
                  </div>

                  {/* Title + subtitle */}
                  <div className="text-[13px] font-bold leading-tight tracking-tight text-slate-900 dark:text-slate-100">
                    {meta.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5">
                    {meta.subtitle}
                  </div>

                  {/* Progress + state */}
                  <div className="mt-2.5 space-y-1">
                    <div className="h-1.5 rounded-full bg-slate-200/80 dark:bg-slate-700/60 overflow-hidden shadow-inner">
                      <div
                        className={cn("h-full rounded-full transition-all duration-500 shadow-sm", theme.bar)}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between gap-1">
                      <span className={cn("text-[9px] font-semibold uppercase tracking-wide", theme.text)}>
                        {theme.label}
                      </span>
                      {evidence > 0 && state !== "done" && (
                        <span className="text-[9px] text-indigo-600 dark:text-indigo-400 tabular-nums font-medium">
                          {evidence} 证据
                        </span>
                      )}
                      {(state === "done" || ran > 0) && (
                        <span className="text-[9px] text-muted-foreground tabular-nums font-medium">
                          {ran}/{total}
                        </span>
                      )}
                    </div>
                  </div>
                </button>

                {idx < stages.length - 1 && (
                  <div className="flex items-center justify-center shrink-0 w-3">
                    <ChevronRight className="size-4 text-slate-300 dark:text-slate-600" />
                  </div>
                )}
              </Fragment>
            );
          })}
        </div>

        {/* Selected stage drawer */}
        {selectedStage && SelectedIcon && selectedMeta && selectedTheme ? (
          <div className={cn("rounded-xl border-2 shadow-inner p-3.5 transition-colors", selectedTheme.card)}>
            <div className="flex items-center justify-between mb-3 pb-2.5 border-b border-slate-200/60 dark:border-slate-700/60">
              <div className="flex items-center gap-2.5">
                <div className={cn("size-7 rounded-md flex items-center justify-center ring-1 ring-white/30", selectedTheme.iconBg)}>
                  <SelectedIcon className="size-3.5 text-white drop-shadow-sm" />
                </div>
                <div>
                  <div className="text-[13px] font-bold leading-tight">
                    {selectedMeta.title}
                    <span className="ml-1.5 text-muted-foreground font-normal">· {selectedMeta.subtitle}</span>
                  </div>
                  <div className={cn("text-[10px] font-semibold uppercase tracking-wide mt-0.5", selectedTheme.text)}>
                    {selectedTheme.label} · {selectedState!.ran}/{selectedState!.total} 子任务
                    {selectedState!.evidence > 0 && <span className="ml-1 text-indigo-600 dark:text-indigo-400">· {selectedState!.evidence} 证据</span>}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setExpandedStage(null)}
                className="text-[11px] text-muted-foreground hover:text-foreground transition px-2 py-0.5 rounded hover:bg-white/50 dark:hover:bg-slate-800/50"
              >
                收起
              </button>
            </div>
            <div className="space-y-1.5">
              {selectedStage.steps.map((step) => {
                const status = stepStatus[step.id] || "idle";
                const summary = stepSummary[step.id];
                const output = stepOutput[step.id];
                return (
                  <div
                    key={step.id}
                    className={cn(
                      "rounded-lg border bg-white/70 dark:bg-slate-900/50 px-3 py-2 text-xs transition-all shadow-sm",
                      status === "success" && "border-emerald-300 bg-emerald-50/70 dark:border-emerald-800/60 dark:bg-emerald-950/30",
                      status === "error" && "border-red-300 bg-red-50/70 dark:border-red-800/60 dark:bg-red-950/30",
                      status === "running" && "border-blue-300 bg-blue-50/70 dark:border-blue-800/60 dark:bg-blue-950/30",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-foreground">{step.label}</div>
                        <div className="text-muted-foreground truncate">{summary || step.description}</div>
                      </div>
                      <Button
                        size="sm"
                        variant={status === "success" ? "outline" : "default"}
                        className="h-7 text-xs shrink-0 shadow-sm"
                        disabled={status === "running" || runStep.isPending}
                        onClick={() => runStep.mutate({ stepId: step.id, run: step.run })}
                      >
                        {status === "running" ? <Loader2 className="size-3 animate-spin" /> : <Play className="size-3" />}
                        {status === "running" ? "运行中" : status === "success" ? "重新运行" : "运行"}
                      </Button>
                    </div>
                    {status === "success" && output && <ResultPreview stepId={step.id} output={output} />}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 px-4 py-3 text-center">
            <div className="text-[11px] text-muted-foreground">
              点击任一阶段卡片查看可执行的子任务 · 自动化流程已就绪
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ResultPreview({ stepId, output }: { stepId: string; output: unknown }) {
  const o = output as Record<string, unknown> | null;
  if (!o) return null;

  switch (stepId) {
    case "gap_detect": {
      const gaps = (o.gaps as Array<Record<string, string>>) ?? [];
      if (!gaps.length) return null;
      return (
        <div className="mt-2 space-y-1 border-t pt-2">
          <div className="text-[10px] font-medium text-muted-foreground">发现 {gaps.length} 个研究空白</div>
          {gaps.slice(0, 3).map((g, i) => (
            <div key={i} className="text-[11px] leading-relaxed line-clamp-2">
              <span className="font-medium text-amber-600 dark:text-amber-400">[{(g.severity ?? "medium").toUpperCase()}]</span> {g.description}
            </div>
          ))}
          {gaps.length > 3 && <div className="text-[10px] text-muted-foreground">+{gaps.length - 3} more</div>}
        </div>
      );
    }
    case "baseline_identify": {
      const baselines = (o.baselines as Array<Record<string, unknown>>) ?? [];
      if (!baselines.length) return null;
      return (
        <div className="mt-2 space-y-1 border-t pt-2">
          <div className="text-[10px] font-medium text-muted-foreground">{baselines.length} 个基线方法</div>
          {baselines.slice(0, 4).map((b, i) => <div key={i} className="text-[11px]"><span className="font-medium">{String(b.name ?? "?")}</span></div>)}
        </div>
      );
    }
    case "direction_ranking": {
      const dirs = (o.directions as Array<Record<string, unknown>>) ?? [];
      if (!dirs.length) return null;
      return (
        <div className="mt-2 space-y-1 border-t pt-2">
          <div className="text-[10px] font-medium text-muted-foreground">{dirs.length} 个研究方向</div>
          {dirs.slice(0, 3).map((d, i) => <div key={i} className="text-[11px] leading-relaxed line-clamp-2"><span className="font-semibold">#{i + 1}</span> {String(d.direction ?? d.description ?? "?")}</div>)}
        </div>
      );
    }
    case "outline": {
      const sections = (o.sections as Array<Record<string, unknown>>) ?? [];
      if (!sections.length) return null;
      return (
        <div className="mt-2 space-y-0.5 border-t pt-2">
          <div className="text-[10px] font-medium text-muted-foreground">{sections.length} 个章节</div>
          {sections.map((s, i) => <div key={i} className="text-[11px]">{i + 1}. {String(s.title ?? "?")}</div>)}
        </div>
      );
    }
    default:
      return null;
  }
}
