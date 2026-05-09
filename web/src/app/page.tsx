"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Globe,
  BookOpen,
  TrendingUp,
  ArrowUpRight,
  RefreshCw,
  Plus,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import {
  fetchDashboardStats,
  fetchTopics,
  fetchDomainTrends,
  refreshDomainTrends,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { type DashboardStats } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/brand/empty-state";
import { useT } from "@/lib/i18n-provider";
import { TodayHero } from "@/components/dashboard/today-hero";
import { ActiveTopicsGrid } from "@/components/dashboard/active-topics-grid";
import { TrendCard } from "@/components/dashboard/trend-card";
import { startTask, updateTask, completeTask } from "@/lib/tasks-store";

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
  gradient: string;
}

function StatCard({ label, value, icon: Icon, accent, gradient }: StatCardProps) {
  return (
    <div className="group relative">
      {/* Soft outer glow on hover */}
      <div
        className={cn(
          "pointer-events-none absolute -inset-px rounded-2xl opacity-0 blur-md transition-opacity duration-500 group-hover:opacity-60",
          gradient,
        )}
      />
      <Card className="relative h-full overflow-hidden rounded-2xl border-white/60 bg-white/70 backdrop-blur transition-all duration-300 group-hover:-translate-y-0.5 group-hover:shadow-lg dark:border-white/5 dark:bg-slate-900/60">
        {/* Top gradient accent strip */}
        <div className={cn("absolute inset-x-0 top-0 h-px", gradient)} />
        <CardContent className="flex items-center gap-4 p-5">
          <div
            className={cn(
              "relative flex size-11 shrink-0 items-center justify-center rounded-xl shadow-md transition-transform group-hover:scale-105",
              accent,
            )}
          >
            <Icon className="size-5 text-white" />
            <div className="absolute inset-0 rounded-xl ring-1 ring-white/30" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {label}
            </p>
            <p className="truncate font-serif text-4xl font-medium tabular-nums tracking-tight sm:text-5xl">
              <CountUp value={value} />
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CountUp({ value }: { value: string | number }) {
  // Parse the visible number out of the formatted value (e.g. "3,882") so we
  // can animate it. If it's not numeric, render the value as-is. We keep the
  // animation snappy (650 ms) so the page feels alive without dragging.
  const text = String(value);
  const parsed = Number(text.replace(/,/g, ""));
  const isNumeric = Number.isFinite(parsed);
  const [display, setDisplay] = useState<string>(text);

  useEffect(() => {
    if (!isNumeric) return;
    const start = performance.now();
    const duration = 650;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const n = Math.round(parsed * eased);
      setDisplay(n.toLocaleString());
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isNumeric, parsed]);

  return <>{isNumeric ? display : text}</>;
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-4">
        <Skeleton className="size-10 rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-14" />
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Today page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { t } = useT();

  const statsQuery = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });

  const topicsQuery = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });

  const trendsQuery = useQuery({
    queryKey: ["domain-trends"],
    queryFn: () => fetchDomainTrends({ limit: 12 }),
  });

  const qc = useQueryClient();
  const refreshTrendsMut = useMutation({
    mutationFn: async () => {
      const taskId = `refresh-trends-${Date.now()}`;
      const phases = [
        "采样文献池",
        "提取关键词",
        "聚类相邻方向",
        "评估发表潜力",
        "排序与精炼",
      ] as const;
      startTask({
        id: taskId,
        title: "刷新研究趋势",
        subtitle: "聚类当前文献池，估计发表潜力",
        progress: 0,
        phase: phases[0],
        step: { current: 1, total: phases.length },
        href: "/research/trends",
      });
      // Drive a smooth phase animation while the API call is in flight.
      // We don't have streaming progress server-side, so this is a best-effort
      // narration based on observed timing (~6-12s end to end).
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
        if (phaseIdx < phases.length - 1) {
          setTimeout(tick, 1700);
        }
      };
      setTimeout(tick, 1500);
      try {
        const result = await refreshDomainTrends({});
        cancelled = true;
        completeTask(taskId, { status: "succeeded" });
        return result;
      } catch (err) {
        cancelled = true;
        completeTask(taskId, {
          status: "failed",
          error: (err as Error).message,
        });
        throw err;
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["domain-trends"] });
      qc.invalidateQueries({ queryKey: ["domain-trends-all"] });
    },
  });

  const stats: DashboardStats | undefined = statsQuery.data;
  const topics = topicsQuery.data ?? [];
  const trends = trendsQuery.data ?? [];

  const isEmpty = !topicsQuery.isPending && topics.length === 0;

  return (
    <div className="space-y-8 p-4 sm:p-6 lg:p-8">
      <TodayHero topicCount={topics.length} />

      {/* Stat strip */}
      <div className="grid gap-4 sm:grid-cols-3">
        {statsQuery.isPending ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : stats ? (
          <>
            <StatCard
              label={t("dashboard.statPapers")}
              value={stats.total_papers.toLocaleString()}
              icon={FileText}
              accent="bg-gradient-to-br from-sky-500 to-blue-600"
              gradient="bg-gradient-to-r from-sky-500/40 via-blue-500/40 to-indigo-500/40"
            />
            <StatCard
              label={t("dashboard.statDomains")}
              value={stats.total_domains}
              icon={Globe}
              accent="bg-gradient-to-br from-violet-500 to-fuchsia-600"
              gradient="bg-gradient-to-r from-violet-500/40 via-fuchsia-500/40 to-pink-500/40"
            />
            <StatCard
              label={t("dashboard.statTopics")}
              value={stats.total_topics}
              icon={BookOpen}
              accent="bg-gradient-to-br from-emerald-500 to-teal-600"
              gradient="bg-gradient-to-r from-emerald-500/40 via-teal-500/40 to-cyan-500/40"
            />
          </>
        ) : (
          <p className="col-span-full text-sm text-muted-foreground">
            {t("common.loading")}
          </p>
        )}
      </div>

      {/* Active topics — compact PM-style cards */}
      {!topicsQuery.isPending && topics.length > 0 && (
        <ActiveTopicsGrid topics={topics} />
      )}

      {/* Research Trends — vertical expandable cards */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
              <TrendingUp className="size-4" />
              {t("dashboard.trendsTitle")}
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {t("dashboard.trendsSubtitle")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => refreshTrendsMut.mutate()}
              disabled={refreshTrendsMut.isPending}
              className="h-7 text-xs"
            >
              <RefreshCw
                className={cn(
                  "size-3",
                  refreshTrendsMut.isPending && "animate-spin"
                )}
              />
              {refreshTrendsMut.isPending
                ? t("dashboard.refreshing")
                : t("dashboard.refresh")}
            </Button>
            <Link
              href="/research/trends"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {t("common.viewAll")}
              <ArrowUpRight className="size-3" />
            </Link>
          </div>
        </div>

        {trendsQuery.isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-xl border p-4">
                <Skeleton className="h-4 w-40 mb-2" />
                <Skeleton className="h-3 w-full mb-1" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            ))}
          </div>
        ) : trends.length > 0 ? (
          <div className="space-y-2">
            {trends.map((trend, i) => (
              <TrendCard key={`${trend.name}-${i}`} trend={trend} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed p-6">
            <p className="text-sm text-muted-foreground">
              {t("dashboard.noTrends")}
            </p>
            <Button
              size="sm"
              onClick={() => refreshTrendsMut.mutate()}
              disabled={refreshTrendsMut.isPending}
            >
              <RefreshCw
                className={cn(
                  "size-3.5",
                  refreshTrendsMut.isPending && "animate-spin"
                )}
              />
              {refreshTrendsMut.isPending
                ? t("dashboard.generating")
                : t("dashboard.generateTrends")}
            </Button>
            {refreshTrendsMut.isError && (
              <p className="text-xs text-red-500">
                {(refreshTrendsMut.error as Error).message}
              </p>
            )}
          </div>
        )}
      </section>

      {isEmpty && (
        <EmptyState
          icon="🌱"
          title={t("empty.topics.title")}
          body={t("empty.topics.body")}
          primary={{
            label: t("empty.topics.cta"),
            href: "/topics/new",
            icon: Plus,
          }}
          secondary={{
            label: t("dashboard.cta.tryDemo"),
            href: "/welcome",
            icon: Sparkles,
          }}
        />
      )}
    </div>
  );
}
