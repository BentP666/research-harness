"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  Search,
  Scan,
  Shuffle,
  PenSquare,
  FileText,
  Target,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CostEstimate } from "@/components/tokens/cost-estimate";
import { cn } from "@/lib/utils";
import type { ResearchStage } from "@/lib/types";

/**
 * Stage-aware "what should I do now" recommendations. Shown near the top
 * of the topic detail page so users never ask "now what?"
 */
interface NextActionsProps {
  topicId: number;
  currentStage: ResearchStage | null | undefined;
  paperCount: number;
  hasDraft: boolean;
  hasReport: boolean;
}

interface Suggestion {
  title: string;
  why: string;
  href: string;
  icon: typeof Search;
  tone: "primary" | "secondary" | "tertiary";
  estimate?: { seconds: number; cost: number };
  tag?: string;
}

export function NextActionsCard({
  topicId,
  currentStage,
  paperCount,
  hasDraft,
  hasReport,
}: NextActionsProps) {
  const suggestions = buildSuggestions({
    topicId,
    currentStage: currentStage ?? "build",
    paperCount,
    hasDraft,
    hasReport,
  });

  if (suggestions.length === 0) return null;

  return (
    <Card className="overflow-hidden border-indigo-200/50 bg-gradient-to-br from-indigo-50/30 via-white to-white dark:from-indigo-950/20 dark:via-slate-950 dark:to-slate-950 dark:border-indigo-900/40">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-indigo-600 dark:text-indigo-400" />
          <CardTitle className="text-sm">
            What I&apos;d work on next
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {suggestions.map((s, i) => (
          <motion.div
            key={`${s.title}-${i}`}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.06 }}
          >
            <Link
              href={s.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg border bg-card p-3 transition-all hover:border-indigo-400 hover:shadow-sm",
                s.tone === "primary" && "ring-1 ring-indigo-300/50 dark:ring-indigo-700/40"
              )}
            >
              <div
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg",
                  s.tone === "primary"
                    ? "bg-indigo-600 text-white"
                    : s.tone === "secondary"
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300"
                      : "bg-muted text-muted-foreground"
                )}
              >
                <s.icon className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-sm font-medium">{s.title}</span>
                  {s.tag && (
                    <Badge variant="outline" className="h-4 text-[10px]">
                      {s.tag}
                    </Badge>
                  )}
                </div>
                <p className="line-clamp-1 text-xs text-muted-foreground">
                  {s.why}
                </p>
              </div>
              {s.estimate && (
                <CostEstimate
                  seconds={s.estimate.seconds}
                  cost={s.estimate.cost}
                  compact
                  className="shrink-0"
                />
              )}
              <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
            </Link>
          </motion.div>
        ))}
      </CardContent>
    </Card>
  );
}

function buildSuggestions(args: {
  topicId: number;
  currentStage: ResearchStage;
  paperCount: number;
  hasDraft: boolean;
  hasReport: boolean;
}): Suggestion[] {
  const { topicId, currentStage, paperCount, hasDraft, hasReport } = args;
  const out: Suggestion[] = [];

  if (currentStage === "build" || paperCount < 15) {
    out.push({
      title: "Find more papers",
      why: `You have ${paperCount} paper(s). I'd aim for 15+ before analyzing.`,
      href: `/topics/${topicId}`,
      icon: Search,
      tone: "primary",
      tag: "build stage",
    });
  }

  if (currentStage === "analyze" || (currentStage === "build" && paperCount >= 15)) {
    out.push({
      title: "Scan for research gaps",
      why: "Find open problems the field hasn't solved yet.",
      href: `/topics/${topicId}`,
      icon: Scan,
      tone: "primary",
      estimate: { seconds: 45, cost: 0.03 },
      tag: "analyze",
    });
    out.push({
      title: "Cross-check claims",
      why: "Spot contradictions between paper findings (95% vs 60% on the same benchmark).",
      href: `/topics/${topicId}`,
      icon: Shuffle,
      tone: "secondary",
      estimate: { seconds: 30, cost: 0.02 },
    });
  }

  if (currentStage === "propose") {
    out.push({
      title: "Rank research directions",
      why: "Prioritize directions by novelty × feasibility × red-ocean score.",
      href: `/topics/${topicId}`,
      icon: Target,
      tone: "primary",
      estimate: { seconds: 40, cost: 0.04 },
    });
  }

  if (currentStage === "write") {
    if (!hasDraft) {
      out.push({
        title: "Draft your first section",
        why: "I'll start with the Introduction, grounded in your evidence pool.",
        href: `/topics/${topicId}`,
        icon: PenSquare,
        tone: "primary",
        estimate: { seconds: 60, cost: 0.05 },
      });
    }
    if (!hasReport) {
      out.push({
        title: "Generate an advisor report",
        why: "Clean PDF with abstract + intro — perfect for a 5-minute advisor review.",
        href: `/topics/${topicId}/reports`,
        icon: FileText,
        tone: hasDraft ? "primary" : "secondary",
        estimate: { seconds: 180, cost: 0.1 },
      });
    }
  }

  if (out.length === 0) {
    out.push({
      title: "Review quality scorecard",
      why: "See how each stage scored and where the weak spots are.",
      href: `/topics/${topicId}`,
      icon: Target,
      tone: "tertiary",
    });
  }

  return out.slice(0, 3);
}
