"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Loader2,
  FileText,
  ShieldCheck,
  Sparkles,
  Lock,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  fetchReportTemplates,
  fetchTopicDetail,
  generateReportsBatch,
  type ReportTemplateId,
} from "@/lib/api";
import {
  RESEARCH_STAGES,
  STAGE_LABELS,
  type ResearchStage,
} from "@/lib/types";
import { useT } from "@/lib/i18n-provider";
import { CostEstimate } from "@/components/tokens/cost-estimate";
import { cn } from "@/lib/utils";

const TEMPLATE_ORDER: ReportTemplateId[] = [
  "abstract_only",
  "abstract_intro",
  "deep_pitch",
  "full_review",
];

const TEMPLATE_ACCENTS: Record<ReportTemplateId, string> = {
  abstract_only: "from-sky-400/10 to-sky-600/5 border-sky-300/40",
  abstract_intro: "from-emerald-400/10 to-emerald-600/5 border-emerald-300/40",
  deep_pitch: "from-amber-400/10 to-amber-600/5 border-amber-300/40",
  full_review: "from-indigo-400/10 to-indigo-600/5 border-indigo-300/40",
};

/**
 * Minimum research stage required before a template can be generated
 * meaningfully. Reports before this point would lack the backing artifacts.
 */
const TEMPLATE_MIN_STAGE: Record<ReportTemplateId, ResearchStage> = {
  abstract_only: "analyze",
  abstract_intro: "analyze",
  deep_pitch: "propose",
  full_review: "write",
};

function stageIndex(stage: ResearchStage | null | undefined): number {
  if (!stage) return -1;
  return RESEARCH_STAGES.indexOf(stage);
}

export function ReportBuilder({ topicId }: { topicId: number }) {
  const qc = useQueryClient();
  const { t } = useT();
  const [selectedSet, setSelectedSet] = useState<Set<ReportTemplateId>>(
    () => new Set(["abstract_intro"])
  );
  const [extraInstructions, setExtraInstructions] = useState("");

  const templatesQ = useQuery({
    queryKey: ["report-templates"],
    queryFn: fetchReportTemplates,
    staleTime: 600_000,
  });

  const topicQ = useQuery({
    queryKey: ["topic-detail", topicId],
    queryFn: () => fetchTopicDetail(topicId),
    enabled: !isNaN(topicId),
  });

  const currentStage = topicQ.data?.current_stage ?? null;
  const currentIdx = stageIndex(currentStage);

  const selectedList = useMemo(() => Array.from(selectedSet), [selectedSet]);
  const blockedSelected = useMemo(
    () =>
      selectedList.filter((id) => currentIdx < stageIndex(TEMPLATE_MIN_STAGE[id])),
    [selectedList, currentIdx]
  );
  const runnableSelected = useMemo(
    () =>
      selectedList.filter((id) => currentIdx >= stageIndex(TEMPLATE_MIN_STAGE[id])),
    [selectedList, currentIdx]
  );

  function toggle(id: ReportTemplateId) {
    setSelectedSet((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const mut = useMutation({
    mutationFn: () =>
      generateReportsBatch(topicId, {
        templates: runnableSelected,
        extra_instructions: extraInstructions,
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["topic-reports", topicId] });
      const ok = data.results.filter((r) => r.ok);
      const failed = data.results.filter((r) => !r.ok);
      if (ok.length > 0) {
        toast.success(`✨ ${ok.length} report${ok.length === 1 ? "" : "s"} generated`, {
          description: ok
            .map((r) => `${r.template}: v0.${r.version_minor ?? "?"}`)
            .join(" · "),
        });
      }
      if (failed.length > 0) {
        toast.error(`${failed.length} template${failed.length === 1 ? "" : "s"} failed`, {
          description: failed.map((r) => `${r.template}: ${r.error}`).join(" · "),
        });
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const templates = templatesQ.data?.templates;

  const localizedName = useMemo(
    () => (id: ReportTemplateId) =>
      t(`reports.templates.${id}.name`) || templates?.[id]?.name || id,
    [t, templates]
  );

  const localizedDesc = useMemo(
    () => (id: ReportTemplateId) =>
      t(`reports.templates.${id}.description`) ||
      templates?.[id]?.description ||
      "",
    [t, templates]
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileText className="size-4" />
          <CardTitle className="text-sm">{t("reports.title")}</CardTitle>
        </div>
        <p className="text-xs text-muted-foreground">{t("reports.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {TEMPLATE_ORDER.map((id, i) => {
            const tmpl = templates?.[id];
            if (!tmpl) return null;
            const isSelected = selectedSet.has(id);
            const minStage = TEMPLATE_MIN_STAGE[id];
            const minIdx = stageIndex(minStage);
            const blocked = currentIdx < minIdx;

            return (
              <motion.button
                key={id}
                type="button"
                onClick={() => toggle(id)}
                aria-pressed={isSelected}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: i * 0.04 }}
                className={cn(
                  "group relative overflow-hidden rounded-xl border bg-gradient-to-br p-4 text-left transition-all",
                  TEMPLATE_ACCENTS[id],
                  isSelected
                    ? "ring-2 ring-indigo-500/60 shadow-md"
                    : "hover:border-foreground/30",
                  blocked && "opacity-75"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <h4 className="text-sm font-semibold">
                        {localizedName(id)}
                      </h4>
                      {isSelected && !blocked && (
                        <Badge className="h-4 bg-indigo-600 px-1.5 text-[10px] text-white">
                          {t("reports.selected")}
                        </Badge>
                      )}
                      {blocked && (
                        <Badge
                          variant="outline"
                          className="h-4 gap-0.5 px-1.5 text-[10px] bg-amber-50 border-amber-300 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900"
                        >
                          <Lock className="size-2.5" />
                          {t("reports.needsStage", {
                            stage: STAGE_LABELS[minStage],
                          })}
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {localizedDesc(id)}
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex flex-wrap gap-1">
                    {tmpl.sections.map((s) => (
                      <Badge
                        key={s}
                        variant="outline"
                        className="h-4 text-[10px] px-1.5 capitalize"
                      >
                        {s.replace("_", " ")}
                      </Badge>
                    ))}
                  </div>
                  <CostEstimate
                    seconds={tmpl.estimated_seconds}
                    cost={tmpl.estimated_cost_usd}
                    compact
                  />
                </div>
              </motion.button>
            );
          })}
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium">
            {t("reports.customRequirements") || "Custom requirements (optional)"}
          </label>
          <textarea
            className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:ring-2 focus:ring-indigo-500/40 focus:outline-none"
            rows={3}
            placeholder={
              t("reports.customPlaceholder") ||
              "e.g. Focus on contrast with GPT-4 baseline. Tone: concise, no hedging. Audience: my advisor."
            }
            value={extraInstructions}
            onChange={(e) => setExtraInstructions(e.target.value)}
          />
          <p className="text-[11px] text-muted-foreground">
            {t("reports.customHint") ||
              "Forwarded into every section draft as additional author guidance. Freshly regenerates sections instead of reusing old drafts."}
          </p>
        </div>

        {blockedSelected.length > 0 && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:bg-amber-950/20 dark:border-amber-900/40">
            <div className="flex items-center gap-2 text-xs text-amber-800 dark:text-amber-200">
              <Lock className="size-4 shrink-0" />
              <span>
                {(t("reports.someBlocked") ||
                  "Some selections need a later stage — they'll be skipped on generate") +
                  `: ${blockedSelected.join(", ")}`}
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              render={<Link href={`/topics/${topicId}`} />}
              className="shrink-0"
            >
              {t("reports.goToTopic")}
              <ArrowRight className="size-3.5" />
            </Button>
          </div>
        )}

        <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/40 p-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5" />
            {runnableSelected.length === 0
              ? t("reports.pickAtLeastOne") ||
                "Pick at least one template above."
              : `${runnableSelected.length} template${runnableSelected.length === 1 ? "" : "s"} ready`}
            {runnableSelected.length > 0 && (
              <span className="ml-1 font-mono tabular-nums">
                · ~${runnableSelected
                  .reduce((acc, id) => acc + (templates?.[id]?.estimated_cost_usd ?? 0), 0)
                  .toFixed(2)}
              </span>
            )}
          </div>
          <Button
            onClick={() => mut.mutate()}
            disabled={mut.isPending || runnableSelected.length === 0}
            className="gap-1.5"
          >
            {mut.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            {t("reports.actions.generate")}
            {runnableSelected.length > 1 ? ` × ${runnableSelected.length}` : ""}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
