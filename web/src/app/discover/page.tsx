"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Flame,
  HelpCircle,
  Compass,
  ArrowUpRight,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Target,
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  fetchDomainTrends,
  refreshDomainTrends,
  fetchTrendsYearly,
  fetchTopics,
  type TrendEntry,
} from "@/lib/api";
import { EmptyState } from "@/components/brand/empty-state";
import { WhyPopover } from "@/components/brand/why-popover";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n-provider";

/**
 * /discover — Three-tier research intelligence page.
 *
 * Tier 1: What's hot (trending clusters ranked by velocity)
 * Tier 2: Open problems (curated from gaps across topics)
 * Tier 3: Personalized direction recommendations with honest red-ocean warnings
 *
 * This replaces the bare carousel on the dashboard with real editorial
 * storytelling. Uses the existing trends pipeline on the backend.
 */
export default function DiscoverPage() {
  const qc = useQueryClient();
  const { t } = useT();

  const trendsQ = useQuery({
    queryKey: ["domain-trends-all"],
    queryFn: () => fetchDomainTrends({ limit: 24 }),
  });

  const yearlyQ = useQuery({
    queryKey: ["trends-yearly-global"],
    queryFn: () => fetchTrendsYearly({ years: 5 }),
  });

  const topicsQ = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });

  const refreshMut = useMutation({
    mutationFn: () => refreshDomainTrends({}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["domain-trends-all"] });
    },
  });

  const trends = trendsQ.data ?? [];
  const sorted = useMemo(
    () => [...trends].sort((a, b) => b.velocity_yoy - a.velocity_yoy),
    [trends]
  );

  const hot = sorted.slice(0, 6);
  const coldWisely = [...trends]
    .filter((t) => t.velocity_yoy < -10)
    .slice(0, 3);

  return (
    <div className="mx-auto max-w-6xl space-y-10 p-6 lg:p-10">
      <Hero onRefresh={() => refreshMut.mutate()} loading={refreshMut.isPending} />

      {trends.length === 0 ? (
        <EmptyState
          icon="🧭"
          title={t("discover.emptyTitle")}
          body={t("discover.emptyBody")}
          primary={{ label: t("discover.startTopic"), href: "/topics/new" }}
          secondary={{
            label: t("discover.refreshTrends"),
            onClick: () => refreshMut.mutate(),
            loading: refreshMut.isPending,
          }}
        />
      ) : (
        <>
          <TrendingSection trends={hot} yearly={yearlyQ.data?.rows ?? []} />
          <OpenProblemsSection trends={trends} />
          <RecommendationsSection
            trends={trends}
            coldWisely={coldWisely}
            hasTopics={(topicsQ.data ?? []).length > 0}
          />
        </>
      )}
    </div>
  );
}

function Hero({
  onRefresh,
  loading,
}: {
  onRefresh: () => void;
  loading: boolean;
}) {
  const { t } = useT();
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-indigo-50 via-white to-amber-50 p-8 dark:from-indigo-950/30 dark:via-slate-950 dark:to-amber-950/20"
    >
      <div className="pointer-events-none absolute -right-24 -top-24 size-56 rounded-full bg-indigo-200/40 blur-3xl dark:bg-indigo-700/10" />
      <div className="relative flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Compass className="size-3.5" />
            {t("discover.intelligence")}
          </div>
          <h1 className="font-serif text-4xl font-medium tracking-tight sm:text-5xl">
            {t("discover.heroTitle")}
          </h1>
          <p className="max-w-xl text-sm text-muted-foreground">
            {t("discover.heroBody")}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          {t("common.refresh")}
        </Button>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Section 1 — What's hot
// ---------------------------------------------------------------------------

function TrendingSection({
  trends,
  yearly,
}: {
  trends: TrendEntry[];
  yearly: Array<{ year: number; paper_count: number }>;
}) {
  const { t } = useT();
  return (
    <section className="space-y-4">
      <SectionHeader
        icon={Flame}
        tone="amber"
        title={t("discover.hot")}
        caption={t("discover.hotSubtitle")}
      />
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {trends.map((t, i) => (
          <motion.div
            key={t.name}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.04 }}
          >
            <TrendCard trend={t} rank={i + 1} />
          </motion.div>
        ))}
      </div>
      {yearly.length > 0 && <YearlySpark rows={yearly} />}
    </section>
  );
}

function TrendCard({ trend, rank }: { trend: TrendEntry; rank: number }) {
  const velocityTone = trend.velocity_yoy > 0 ? "positive" : "negative";
  const velocityColor =
    trend.velocity_yoy > 100
      ? "text-emerald-700 dark:text-emerald-300"
      : trend.velocity_yoy > 20
        ? "text-emerald-600"
        : trend.velocity_yoy > 0
          ? "text-emerald-500"
          : "text-slate-500";

  return (
    <Card className="group relative h-full overflow-hidden transition-shadow hover:shadow-md">
      <div
        className={cn(
          "absolute inset-x-0 top-0 h-1",
          velocityTone === "positive"
            ? "bg-gradient-to-r from-emerald-400 to-amber-400"
            : "bg-gradient-to-r from-slate-300 to-slate-400"
        )}
      />
      <CardContent className="space-y-3 p-4 pt-5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs text-muted-foreground tabular-nums">
                #{rank}
              </span>
              <h3 className="text-sm font-semibold leading-tight">
                {trend.name}
              </h3>
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {trend.description}
            </p>
          </div>
          <WhyPopover
            title={trend.name}
            reasoning={
              trend.why ||
              "Identified as a trend cluster based on venue, citation, and velocity signals in the paper pool."
            }
            confidence={Math.min(1, trend.publishability_score / 10)}
          />
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className={cn("flex items-baseline gap-1 font-mono tabular-nums", velocityColor)}>
            <TrendingUp className="size-3.5" />
            <span className="text-sm font-semibold">
              {trend.velocity_yoy > 0 ? "+" : ""}
              {trend.velocity_yoy.toFixed(0)}%
            </span>
            <span className="text-[10px] text-muted-foreground">YoY</span>
          </div>
          <Badge variant="outline" className="font-mono text-[10px]">
            Score {trend.publishability_score.toFixed(1)}/10
          </Badge>
        </div>

        {trend.top_venues.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {trend.top_venues.slice(0, 4).map((v) => (
              <Badge
                key={v}
                variant="secondary"
                className="h-4 text-[10px] px-1.5"
              >
                {v}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function YearlySpark({
  rows,
}: {
  rows: Array<{ year: number; paper_count: number }>;
}) {
  const { t } = useT();
  const max = Math.max(...rows.map((r) => r.paper_count), 1);
  return (
    <Card>
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground">
            {t("discover.volumeTitle")}
          </p>
          <span className="text-[10px] text-muted-foreground">
            {t("discover.peak").replace("{count}", max.toLocaleString())}
          </span>
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={rows} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="yearlyFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(99 102 241)" stopOpacity={0.4} />
                <stop offset="95%" stopColor="rgb(99 102 241)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="year"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, borderRadius: 8 }}
              formatter={(value) => [value, t("discover.papers")]}
              labelFormatter={(label) => String(label)}
            />
            <Area
              type="monotone"
              dataKey="paper_count"
              stroke="rgb(99 102 241)"
              strokeWidth={2}
              fill="url(#yearlyFill)"
              animationDuration={800}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Section 2 — Open problems
// ---------------------------------------------------------------------------

function OpenProblemsSection({ trends }: { trends: TrendEntry[] }) {
  const { t } = useT();
  const [expanded, setExpanded] = useState(false);
  // Heuristic: trends whose description mentions "open", "gap", "unsolved", or
  // whose publishability score is high but velocity is moderate are
  // promising "underexplored" problems.
  const open = trends
    .filter((tr) => {
      const desc = (tr.description || "").toLowerCase();
      if (/\b(open|gap|unsolved|missing|no benchmark|unclear)\b/.test(desc)) {
        return true;
      }
      return tr.publishability_score >= 4 && tr.velocity_yoy < 80;
    });

  if (open.length === 0) return null;

  const visible = expanded ? open : open.slice(0, 5);

  return (
    <section className="space-y-4">
      <SectionHeader
        icon={HelpCircle}
        tone="indigo"
        title={t("discover.openProblems")}
        caption={t("discover.openProblemsSubtitle")}
      />
      <div className="grid gap-3 md:grid-cols-2">
        {visible.map((tr, i) => (
          <motion.div
            key={tr.name}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: i * 0.04 }}
          >
            <Card className="h-full">
              <CardContent className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-sm font-semibold leading-tight">
                    {tr.name}
                  </h4>
                  <Badge
                    variant="outline"
                    className="shrink-0 font-mono text-[10px]"
                  >
                    {tr.publishability_score.toFixed(1)}/10
                  </Badge>
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {tr.description}
                </p>

                {/* Structured evidence */}
                <div className="space-y-1.5 border-t pt-2">
                  <div className="flex flex-wrap gap-1">
                    {tr.top_venues.slice(0, 4).map((v) => (
                      <Badge
                        key={v}
                        variant="secondary"
                        className="h-4 text-[10px] px-1.5"
                      >
                        {v}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 text-[11px]">
                    <span
                      className={cn(
                        "font-mono tabular-nums",
                        tr.velocity_yoy > 0
                          ? "text-emerald-600"
                          : "text-slate-500"
                      )}
                    >
                      {tr.velocity_yoy > 0 ? "+" : ""}
                      {tr.velocity_yoy.toFixed(0)}% {t("discover.yoy")}
                    </span>
                    <span className="text-muted-foreground">
                      {t("discover.pubScore")}: {tr.publishability_score.toFixed(1)}/10
                    </span>
                  </div>
                  <p className="text-[11px] italic text-muted-foreground">
                    {tr.why || t("discover.whyMatters")}
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
      {open.length > 5 && (
        <div className="flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={() => setExpanded((prev) => !prev)}
          >
            {expanded ? (
              <>
                <ChevronUp className="size-3.5" />
                {t("discover.showLess")}
              </>
            ) : (
              <>
                <ChevronDown className="size-3.5" />
                {t("discover.showMore")}
              </>
            )}
          </Button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 3 — Recommendations (with honest warnings)
// ---------------------------------------------------------------------------

function RecommendationsSection({
  trends,
  coldWisely,
  hasTopics,
}: {
  trends: TrendEntry[];
  coldWisely: TrendEntry[];
  hasTopics: boolean;
}) {
  const { t } = useT();
  const top = [...trends]
    .sort((a, b) => b.publishability_score - a.publishability_score)
    .slice(0, 3);

  return (
    <section className="space-y-4">
      <SectionHeader
        icon={Target}
        tone="emerald"
        title={hasTopics ? t("discover.directionsPersonalized") : t("discover.directions")}
        caption={t("discover.directionsSubtitle")}
      />

      <div className="grid gap-3 md:grid-cols-3">
        {top.map((t, i) => (
          <motion.div
            key={t.name}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: i * 0.06 }}
          >
            <RecommendationCard trend={t} rank={i + 1} />
          </motion.div>
        ))}
      </div>

      {coldWisely.length > 0 && (
        <Card className="border-dashed bg-amber-50/40 dark:bg-amber-950/20">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-amber-600" />
              <CardTitle className="text-sm">{t("discover.coolingOff")}</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {coldWisely.map((ct) => (
              <div
                key={ct.name}
                className="flex items-center justify-between rounded-md border bg-background px-3 py-2 text-xs"
              >
                <div>
                  <div className="font-medium">{ct.name}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {t("discover.coolingDetail").replace("{pct}", Math.abs(ct.velocity_yoy).toFixed(0))}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </section>
  );
}

function RecommendationCard({ trend, rank }: { trend: TrendEntry; rank: number }) {
  const { t } = useT();
  const score = trend.publishability_score;
  const tone =
    score >= 7
      ? "strong"
      : score >= 5
        ? "promising"
        : "marginal";
  const toneStyle = {
    strong:
      "border-emerald-300/50 bg-gradient-to-br from-emerald-50/60 to-white dark:from-emerald-950/30 dark:to-slate-950 dark:border-emerald-800/40",
    promising:
      "border-amber-300/50 bg-gradient-to-br from-amber-50/60 to-white dark:from-amber-950/30 dark:to-slate-950 dark:border-amber-800/40",
    marginal: "border-slate-300/50 bg-card",
  }[tone];

  const venueList = trend.top_venues.slice(0, 3).join(", ");
  const summaryLine = trend.why
    || t("discover.recSummaryFallback")
      .replace("{score}", score.toFixed(1))
      .replace("{velocity}", `${trend.velocity_yoy > 0 ? "+" : ""}${trend.velocity_yoy.toFixed(0)}`);

  return (
    <Card className={cn("h-full overflow-hidden", toneStyle)}>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-xs text-muted-foreground tabular-nums">
              #{rank}
            </span>
            <h3 className="text-sm font-semibold leading-tight">
              {trend.name}
            </h3>
          </div>
          <Badge className="bg-indigo-600 text-[10px] text-white">
            {tone}
          </Badge>
        </div>

        <p className="text-xs leading-relaxed text-muted-foreground">
          {trend.description}
        </p>

        {/* Structured reasoning */}
        <div className="space-y-2 border-t pt-2">
          <div className="flex justify-between text-[11px]">
            <span className="text-muted-foreground">{t("discover.whyConsider")}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <Badge variant="outline" className="font-mono text-[10px]">
              {t("discover.recScore").replace("{score}", score.toFixed(1))}
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "font-mono text-[10px]",
                trend.velocity_yoy > 0 ? "border-emerald-300 text-emerald-700 dark:text-emerald-300" : ""
              )}
            >
              {trend.velocity_yoy > 0 ? "+" : ""}{trend.velocity_yoy.toFixed(0)}% {t("discover.yoy")}
            </Badge>
            {venueList && (
              <span className="text-muted-foreground">
                {t("discover.recVenues").replace("{venues}", venueList)}
              </span>
            )}
          </div>
          <p className="text-[11px] leading-relaxed text-foreground/80">
            {summaryLine}
          </p>
        </div>

        {trend.velocity_yoy > 300 && (
          <div className="flex items-start gap-2 rounded-md border-2 border-red-400 bg-red-50 p-2.5 text-[11px] text-red-700 dark:border-red-700 dark:bg-red-950/40 dark:text-red-300">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            <div>
              <strong>{t("discover.honestWarning").split(":")[0]}:</strong>{" "}
              {t("discover.honestWarning").split(":").slice(1).join(":").replace("{pct}", trend.velocity_yoy.toFixed(0))}
            </div>
          </div>
        )}

        <Link
          href="/topics/new"
          className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
        >
          {t("discover.turnIntoTopic")}
          <ArrowUpRight className="size-3" />
        </Link>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Section header atom
// ---------------------------------------------------------------------------

function SectionHeader({
  icon: Icon,
  tone,
  title,
  caption,
}: {
  icon: typeof Flame;
  tone: "amber" | "indigo" | "emerald";
  title: string;
  caption: string;
}) {
  const toneClass = {
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    indigo:
      "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300",
    emerald:
      "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  }[tone];

  return (
    <div className="flex items-start gap-3">
      <div className={cn("flex size-9 items-center justify-center rounded-lg", toneClass)}>
        <Icon className="size-4" />
      </div>
      <div>
        <h2 className="font-serif text-xl font-medium tracking-tight">
          {title}
        </h2>
        <p className="text-xs text-muted-foreground">{caption}</p>
      </div>
    </div>
  );
}
