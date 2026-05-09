"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Clock,
  FileText,
  FlaskConical,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  RESEARCH_STAGES,
  STAGE_LABELS,
  STAGE_BG_COLORS,
  STAGE_TEXT_COLORS,
  type ResearchStage,
  type Topic,
} from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TOTAL_STAGES = RESEARCH_STAGES.length; // 6

function stageIndex(stage: ResearchStage): number {
  const idx = RESEARCH_STAGES.indexOf(stage);
  return idx === -1 ? 0 : idx + 1; // 1-based for display
}

function daysAgo(isoDate: string): number {
  const created = new Date(isoDate);
  const now = new Date();
  return Math.max(0, Math.floor((now.getTime() - created.getTime()) / 86_400_000));
}

// ---------------------------------------------------------------------------
// Progress dots — compact 6-dot indicator
// ---------------------------------------------------------------------------

function StageDots({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-0.5" role="img" aria-label={`Stage ${current} of ${TOTAL_STAGES}`}>
      {RESEARCH_STAGES.map((stage, i) => (
        <span
          key={stage}
          className={cn(
            "size-1.5 rounded-full transition-colors",
            i < current
              ? "bg-indigo-500 dark:bg-indigo-400"
              : "bg-muted-foreground/20",
          )}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single topic card
// ---------------------------------------------------------------------------

function TopicCard({ topic, index }: { topic: Topic; index: number }) {
  const { t } = useT();

  const stage = topic.current_stage ?? null;
  const currentIdx = stage ? stageIndex(stage) : 0;

  const age = useMemo(() => {
    const d = daysAgo(topic.created_at);
    if (d === 0) return t("dashboard.today");
    if (d === 1) return t("dashboard.yesterday");
    return t("dashboard.daysAgo", { days: d });
  }, [topic.created_at, t]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05 }}
    >
      <Link href={`/topics/${topic.id}`} className="block group">
        <Card className="h-full transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-400 hover:shadow-md">
          <CardContent className="flex flex-col gap-3 p-4">
            {/* Top: name + arrow */}
            <div className="flex items-start justify-between gap-2">
              <h3 className="min-w-0 truncate text-sm font-semibold leading-tight">
                {topic.name}
              </h3>
              <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </div>

            {/* Stage badge + progress */}
            <div className="flex items-center gap-2">
              {stage ? (
                <Badge
                  variant="secondary"
                  className={cn(
                    "h-5 text-[11px] font-medium",
                    STAGE_BG_COLORS[stage],
                    STAGE_TEXT_COLORS[stage],
                  )}
                >
                  {STAGE_LABELS[stage]}
                </Badge>
              ) : (
                <Badge variant="outline" className="h-5 text-[11px] font-medium">
                  {t("dashboard.stageNotStarted")}
                </Badge>
              )}
              <span className="text-[11px] text-muted-foreground">
                {t("dashboard.stageProgress", {
                  current: currentIdx,
                  total: TOTAL_STAGES,
                })}
              </span>
            </div>

            {/* Progress dots */}
            <StageDots current={currentIdx} />

            {/* Meta: papers + age */}
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <FileText className="size-3" />
                {t("dashboard.papersCount", { count: topic.paper_count })}
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="size-3" />
                {age}
              </span>
            </div>
          </CardContent>
        </Card>
      </Link>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Grid
// ---------------------------------------------------------------------------

export function ActiveTopicsGrid({ topics }: { topics: Topic[] }) {
  const { t } = useT();

  const active = useMemo(
    () => topics.filter((tp) => tp.status !== "archived").slice(0, 6),
    [topics],
  );

  if (active.length === 0) return null;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            <FlaskConical className="size-4" />
            {t("dashboard.activeTopicsTitle")}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("dashboard.activeTopicsSubtitle")}
          </p>
        </div>
        <Link
          href="/research"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {t("common.viewAll")}
          <ArrowRight className="size-3" />
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((topic, i) => (
          <TopicCard key={topic.id} topic={topic} index={i} />
        ))}
      </div>
    </section>
  );
}
