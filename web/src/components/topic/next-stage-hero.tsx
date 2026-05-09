"use client";

import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ChevronRight,
  ShieldCheck,
  Loader2,
  Compass,
  Library,
  Search,
  Lightbulb,
  FlaskConical,
  PenTool,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  RESEARCH_STAGES,
  STAGE_DESCRIPTIONS,
  STAGE_LABELS,
  type ResearchStage,
} from "@/lib/types";
import { advanceTopic, checkTopicGate } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";
import { startTask, updateTask, completeTask } from "@/lib/tasks-store";

const STAGE_ICON: Record<ResearchStage, typeof Compass> = {
  init: Compass,
  build: Library,
  analyze: Search,
  propose: Lightbulb,
  experiment: FlaskConical,
  write: PenTool,
};

const STAGE_GRADIENT: Record<ResearchStage, string> = {
  init: "from-slate-500 to-slate-700",
  build: "from-blue-500 to-indigo-600",
  analyze: "from-violet-500 to-purple-700",
  propose: "from-amber-500 to-orange-600",
  experiment: "from-emerald-500 to-teal-600",
  write: "from-rose-500 to-pink-600",
};

interface NextStageHeroProps {
  topicId: number;
  topicName?: string;
  currentStage: ResearchStage | null;
  stageStatus: string | null;
  onRefresh: () => void;
}

const STAGE_PHASES: Record<ResearchStage, string[]> = {
  init: ["选择研究领域", "录入意图", "基础元数据"],
  build: ["搜索相关文献", "去重并筛选", "下载 PDF", "录入文献池"],
  analyze: ["抽取核心主张", "识别证据链", "检测研究空白", "构建论据图谱"],
  propose: ["综合空白与主张", "构思 hypothesis", "评估可行性", "草拟提案"],
  experiment: ["设计实验方案", "选择基线", "估算资源", "记录预登记"],
  write: ["拼装章节大纲", "起草各小节", "插入证据", "格式与导出"],
};

/**
 * Hero-style Next Stage CTA. Primary action on the topic page —
 * big, colored, explains what's coming, with time/cost estimate.
 * Replaces the cramped "Next stage" button in the bottom toolbar.
 */
export function NextStageHero({
  topicId,
  topicName,
  currentStage,
  stageStatus,
  onRefresh,
}: NextStageHeroProps) {
  const { t } = useT();
  const [feedback, setFeedback] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);

  const showFeedback = (
    type: "success" | "error" | "info",
    message: string
  ) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 8000);
  };

  const advanceMut = useMutation({
    mutationFn: async () => {
      const taskId = `advance-topic-${topicId}-${Date.now()}`;
      const effective = (currentStage ?? "init") as ResearchStage;
      const idx = RESEARCH_STAGES.indexOf(effective);
      const target =
        idx >= 0 && idx < RESEARCH_STAGES.length - 1
          ? RESEARCH_STAGES[idx + 1]
          : effective;
      const phases = STAGE_PHASES[target] ?? ["执行中"];
      startTask({
        id: taskId,
        title: `推进到「${STAGE_LABELS[target]}」`,
        subtitle: topicName ?? `Topic #${topicId}`,
        progress: 0,
        phase: phases[0],
        step: { current: 1, total: phases.length },
        href: `/topics/${topicId}`,
      });
      let cancelled = false;
      let phaseIdx = 0;
      const tick = () => {
        if (cancelled) return;
        phaseIdx = Math.min(phases.length - 1, phaseIdx + 1);
        updateTask(taskId, {
          phase: phases[phaseIdx],
          step: { current: phaseIdx + 1, total: phases.length },
          progress: (phaseIdx + 0.5) / phases.length,
        });
        if (phaseIdx < phases.length - 1) setTimeout(tick, 2200);
      };
      setTimeout(tick, 2000);
      try {
        const data = await advanceTopic(topicId, { actor: "web_ui" });
        cancelled = true;
        if (data.status === "error") {
          completeTask(taskId, {
            status: "failed",
            error: data.summary || "执行失败",
          });
        } else {
          completeTask(taskId, { status: "succeeded" });
        }
        return data;
      } catch (err) {
        cancelled = true;
        completeTask(taskId, {
          status: "failed",
          error: (err as Error).message,
        });
        throw err;
      }
    },
    onSuccess: (data) => {
      showFeedback(
        data.status === "error" ? "error" : "success",
        data.summary || t("nextStage.advanced")
      );
      onRefresh();
    },
    onError: (err: Error) => showFeedback("error", err.message),
  });

  const gateMut = useMutation({
    mutationFn: () => checkTopicGate(topicId),
    onSuccess: (data) => {
      const gateStatus =
        typeof data.output === "object" && data.output !== null
          ? (data.output as Record<string, unknown>).gate_status
          : null;
      const type =
        gateStatus === "pass" || gateStatus === "passed"
          ? "success"
          : gateStatus === "fail" || gateStatus === "blocked"
            ? "error"
            : "info";
      showFeedback(
        type,
        data.summary || t("nextStage.readinessResult", { status: String(gateStatus ?? "checked") })
      );
      onRefresh();
    },
    onError: (err: Error) => showFeedback("error", err.message),
  });

  const isLoading = advanceMut.isPending || gateMut.isPending;
  const effectiveStage = (currentStage ?? "init") as ResearchStage;
  const currentIndex = RESEARCH_STAGES.indexOf(effectiveStage);
  const nextStage: ResearchStage | null =
    currentIndex >= 0 && currentIndex < RESEARCH_STAGES.length - 1
      ? RESEARCH_STAGES[currentIndex + 1]
      : null;

  const NextIcon = nextStage ? STAGE_ICON[nextStage] : Sparkles;
  const gradient = nextStage
    ? STAGE_GRADIENT[nextStage]
    : "from-emerald-500 to-green-600";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="relative overflow-hidden rounded-2xl border bg-card shadow-sm"
    >
      {/* Color band on the left */}
      <div
        className={cn(
          "absolute inset-y-0 left-0 w-1.5 bg-gradient-to-b",
          gradient
        )}
      />

      {/* Soft bg orb */}
      <div
        className={cn(
          "pointer-events-none absolute -right-20 -top-12 size-44 rounded-full bg-gradient-to-br blur-3xl opacity-20",
          gradient
        )}
      />

      <div className="relative flex flex-col gap-4 p-5 sm:p-6 sm:flex-row sm:items-center">
        {/* Icon block */}
        <div
          className={cn(
            "flex size-14 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md",
            gradient
          )}
        >
          <NextIcon className="size-6" />
        </div>

        {/* Copy */}
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <span>
              {t("nextStage.currentLabel")}:{" "}
              <span className="font-semibold text-foreground">
                {STAGE_LABELS[effectiveStage]}
              </span>
            </span>
            {stageStatus && (
              <Badge variant="outline" className="h-4 text-[10px] px-1.5">
                {stageStatus}
              </Badge>
            )}
          </div>
          <h3 className="font-serif text-xl font-medium tracking-tight sm:text-2xl">
            {nextStage
              ? t("nextStage.heroTitle", { stage: STAGE_LABELS[nextStage] })
              : t("nextStage.allDoneTitle")}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {nextStage
              ? STAGE_DESCRIPTIONS[nextStage]
              : t("nextStage.allDoneBody")}
          </p>
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="outline"
            size="lg"
            onClick={() => gateMut.mutate()}
            disabled={isLoading}
            className="h-12"
          >
            {gateMut.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ShieldCheck className="size-4" />
            )}
            {t("nextStage.checkReadiness")}
          </Button>
          <Button
            size="lg"
            onClick={() => advanceMut.mutate()}
            disabled={isLoading || !nextStage}
            className={cn(
              "h-12 bg-gradient-to-r text-white shadow-md hover:shadow-lg transition-shadow",
              gradient,
              "hover:brightness-110"
            )}
          >
            {advanceMut.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ChevronRight className="size-4" />
            )}
            {nextStage
              ? t("nextStage.advanceTo", { stage: STAGE_LABELS[nextStage] })
              : t("nextStage.complete")}
          </Button>
        </div>
      </div>

      {/* Inline feedback */}
      {feedback && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className={cn(
            "relative flex items-center gap-2 border-t px-5 py-3 text-sm sm:px-6",
            feedback.type === "success" &&
              "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300",
            feedback.type === "error" &&
              "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300",
            feedback.type === "info" &&
              "bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300"
          )}
        >
          {feedback.type === "success" && <CheckCircle2 className="size-4 shrink-0" />}
          {feedback.type === "error" && <XCircle className="size-4 shrink-0" />}
          {feedback.type === "info" && <AlertCircle className="size-4 shrink-0" />}
          <span>{feedback.message}</span>
        </motion.div>
      )}
    </motion.div>
  );
}
