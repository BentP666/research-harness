"use client";

import Link from "next/link";
import { ArrowRight, FlaskConical } from "lucide-react";
import { motion } from "framer-motion";
import { STAGE_LABELS, STAGE_COLORS, type Topic } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";

/**
 * Compact strip of in-progress topics for the Today page.
 * Replaces the full topics grid — Today is for "what to do now", not a
 * project index. Shows at most 6 active topics as chips with stage badges.
 */
export function ActiveTopicsStrip({ topics }: { topics: Topic[] }) {
  const { t } = useT();
  const active = topics
    .filter((t) => (t as { status?: string }).status !== "archived")
    .slice(0, 6);

  if (active.length === 0) return null;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <FlaskConical className="size-4" />
          {t("dashboard.activeTopicsTitle")}
        </h2>
        <Link
          href="/research"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {t("common.viewAll")}
          <ArrowRight className="size-3" />
        </Link>
      </div>
      <div className="flex flex-wrap gap-2">
        {active.map((topic, i) => (
          <motion.div
            key={topic.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: i * 0.04 }}
          >
            <Link
              href={`/topics/${topic.id}`}
              className="group inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-sm transition-all hover:border-indigo-400 hover:shadow-sm"
            >
              <span className="max-w-[18ch] truncate font-medium">
                {topic.name}
              </span>
              {topic.current_stage ? (
                <Badge
                  variant="outline"
                  className={cn(
                    "h-4 shrink-0 text-[10px] px-1.5",
                    STAGE_COLORS[topic.current_stage]
                  )}
                >
                  {STAGE_LABELS[topic.current_stage]}
                </Badge>
              ) : (
                <Badge variant="outline" className="h-4 shrink-0 text-[10px] px-1.5">
                  {topic.paper_count} papers
                </Badge>
              )}
              <ArrowRight className="size-3 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
            </Link>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
