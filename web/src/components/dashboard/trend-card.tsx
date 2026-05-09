"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  TrendingUp,
  TrendingDown,
  FlaskConical,
  AlertTriangle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { TrendEntry } from "@/lib/api";
import { useT } from "@/lib/i18n-provider";

/**
 * Expandable vertical trend card. Replaces the horizontal-scroll carousel.
 * Collapsed: name, one-line description, YoY velocity, publishability score.
 * Expanded: why, top venues, seed papers with links.
 */
export function TrendCard({ trend }: { trend: TrendEntry }) {
  const [expanded, setExpanded] = useState(false);
  const { t } = useT();
  const isHot = trend.velocity_yoy > 50;
  const isRedOcean = trend.velocity_yoy > 300;
  const isCool = trend.velocity_yoy <= 0;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border bg-card transition-all",
        expanded && "ring-1 ring-indigo-300/50 dark:ring-indigo-700/40"
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-3 p-4 text-left hover:bg-muted/30 transition-colors"
      >
        <div
          className={cn(
            "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg",
            isRedOcean
              ? "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300"
              : isHot
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                : isCool
                  ? "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                  : "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
          )}
        >
          {isRedOcean ? (
            <AlertTriangle className="size-4" />
          ) : isCool ? (
            <TrendingDown className="size-4" />
          ) : (
            <TrendingUp className="size-4" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="truncate text-sm font-semibold">{trend.name}</h3>
            {isRedOcean && (
              <Badge variant="outline" className="h-4 text-[10px] bg-red-50 border-red-300 text-red-700">
                {t("dashboard.redOcean")}
              </Badge>
            )}
            {isHot && !isRedOcean && (
              <Badge variant="outline" className="h-4 text-[10px] bg-emerald-50 border-emerald-300 text-emerald-700">
                {t("dashboard.hot")}
              </Badge>
            )}
          </div>
          <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
            {trend.description}
          </p>
          <div className="mt-2 flex items-center gap-3 text-[11px]">
            <span
              className={cn(
                "font-mono tabular-nums font-medium",
                trend.velocity_yoy > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-500"
              )}
            >
              {trend.velocity_yoy > 0 ? "+" : ""}
              {trend.velocity_yoy.toFixed(0)}% YoY
            </span>
            <span className="text-muted-foreground">
              {t("dashboard.score")}: {trend.publishability_score.toFixed(1)}
            </span>
            {trend.seed_papers.length > 0 && (
              <span className="text-muted-foreground">
                · {trend.seed_papers.length} {t("dashboard.seedPapers")}
              </span>
            )}
          </div>
        </div>

        <motion.div
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="mt-1 shrink-0 text-muted-foreground"
        >
          <ChevronDown className="size-4" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t bg-muted/30 p-4">
              {trend.why && (
                <div>
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t("common.whyThis")}
                  </p>
                  <p className="text-xs leading-relaxed">{trend.why}</p>
                </div>
              )}

              {trend.top_venues.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t("dashboard.topVenues")}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {trend.top_venues.slice(0, 6).map((v) => (
                      <Badge
                        key={v}
                        variant="secondary"
                        className="h-4 text-[10px] px-1.5"
                      >
                        {v}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {trend.seed_papers.length > 0 && (
                <div>
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t("dashboard.seedPapers")}
                  </p>
                  <ul className="space-y-1">
                    {trend.seed_papers.slice(0, 4).map((p) => (
                      <li key={p.id} className="text-xs">
                        <Link
                          href={`/papers/${p.id}`}
                          className="flex items-start gap-1.5 text-foreground hover:text-indigo-600 dark:hover:text-indigo-400"
                        >
                          <FlaskConical className="size-3 mt-0.5 shrink-0 text-muted-foreground" />
                          <span className="line-clamp-1">
                            {p.title}
                            {p.year ? (
                              <span className="ml-1 text-muted-foreground">
                                ({p.year})
                              </span>
                            ) : null}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
